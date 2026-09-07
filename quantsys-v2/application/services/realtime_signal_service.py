"""
实时信号服务 - 解决信号滞后问题

三种模式：
1. T+1 模式：收盘后生成信号，次日开盘执行
2. 盘中监控模式：分钟级实时监控（需要实时数据源）
3. 开盘预判模式：集合竞价 + 昨日信号综合判断
"""

from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd
from loguru import logger


class RealtimeSignalService:
    """实时信号服务"""

    def __init__(self):
        self.signal_cache = {}  # 缓存今日信号

    def filter_executable_signals(
        self,
        signals: List[Dict],
        max_gap_pct: float = 3.0,  # 最大可接受价差（%）
        check_realtime: bool = True
    ) -> List[Dict]:
        """
        过滤可执行信号

        Args:
            signals: 策略生成的原始信号列表
            max_gap_pct: 最大可接受价差百分比（信号价 vs 当前价）
            check_realtime: 是否检查实时价格

        Returns:
            可执行的信号列表（附加执行建议）
        """
        from application.services.market_data_service import MarketDataService

        executable = []
        market_service = MarketDataService()

        for signal in signals:
            symbol = signal.get('symbol')
            entry_price = signal.get('entry_price')
            signal_date = signal.get('timestamp', '').split('T')[0]

            # 检查信号日期
            today = datetime.now().strftime('%Y-%m-%d')
            if signal_date != today:
                # 隔日信号，检查价格偏离
                if check_realtime:
                    try:
                        quote = market_service.get_realtime_quote(symbol)
                        current_price = quote.get('price')

                        gap_pct = (current_price / entry_price - 1) * 100

                        if abs(gap_pct) > max_gap_pct:
                            logger.warning(
                                f"{symbol} 价格偏离过大: 信号价 {entry_price}, "
                                f"当前价 {current_price}, 偏离 {gap_pct:.2f}%"
                            )
                            signal['executable'] = False
                            signal['reject_reason'] = f'价格偏离 {gap_pct:.2f}% 超过阈值 {max_gap_pct}%'
                            continue

                        signal['current_price'] = current_price
                        signal['price_gap_pct'] = gap_pct

                    except Exception as e:
                        logger.error(f"获取 {symbol} 实时价格失败: {e}")
                        signal['executable'] = False
                        signal['reject_reason'] = '无法获取实时价格'
                        continue

            # 标记为可执行
            signal['executable'] = True
            signal['execution_mode'] = self._suggest_execution_mode(signal)
            executable.append(signal)

        return executable

    def _suggest_execution_mode(self, signal: Dict) -> str:
        """
        建议执行模式

        Returns:
            'immediate' - 立即执行（当前价格可接受）
            'limit_order' - 限价单（等待回调）
            'next_day' - 次日开盘执行
        """
        signal_date = signal.get('timestamp', '').split('T')[0]
        today = datetime.now().strftime('%Y-%m-%d')

        if signal_date == today:
            # 当日信号
            if 'current_price' in signal:
                gap = signal.get('price_gap_pct', 0)
                if gap < 1:
                    return 'immediate'  # 价差小于1%，立即执行
                elif gap < 3:
                    return 'limit_order'  # 价差1-3%，限价单等待
            return 'next_day'  # 无法确定，建议次日
        else:
            # 隔日信号
            gap = signal.get('price_gap_pct', 0)
            if gap < 0:
                return 'immediate'  # 当前价格更低，立即执行
            elif gap < 2:
                return 'limit_order'  # 略高，限价单
            else:
                return 'skip'  # 价格已大幅偏离，放弃

    def generate_t1_signals(
        self,
        strategy_id: str,
        symbols: List[str],
        execution_date: Optional[str] = None
    ) -> List[Dict]:
        """
        生成 T+1 信号（今日收盘后生成，明日开盘执行）

        Args:
            strategy_id: 策略ID
            symbols: 股票列表
            execution_date: 执行日期（默认次日）

        Returns:
            T+1 信号列表
        """
        from application.services.strategy_execution_service import StrategyExecutionService

        if execution_date is None:
            # 默认次日
            tomorrow = datetime.now() + timedelta(days=1)
            execution_date = tomorrow.strftime('%Y-%m-%d')

        execution_service = StrategyExecutionService()
        signals = []

        for symbol in symbols:
            try:
                # 执行策略（基于今日收盘数据）
                result = execution_service.execute_strategy(
                    action='single',
                    symbol=symbol,
                    strategy_name=strategy_id
                )

                if result.get('success') and result['data'].get('signal_type') == 'BUY':
                    signal = result['data']
                    signal['execution_date'] = execution_date
                    signal['mode'] = 'T+1'
                    signal['generated_at'] = datetime.now().isoformat()
                    signals.append(signal)

            except Exception as e:
                logger.error(f"生成 {symbol} T+1 信号失败: {e}")

        return signals

    def schedule_morning_scan(
        self,
        strategy_ids: List[str],
        stock_pool: List[str],
        notification_callback: Optional[callable] = None
    ):
        """
        定时早盘扫描（每日 9:00 执行）

        Args:
            strategy_ids: 策略列表
            stock_pool: 股票池
            notification_callback: 通知回调函数（推送飞书/企业微信）
        """
        logger.info(f"开始早盘扫描，策略数: {len(strategy_ids)}, 股票数: {len(stock_pool)}")

        all_signals = []

        for strategy_id in strategy_ids:
            signals = self.generate_t1_signals(strategy_id, stock_pool)

            # 过滤可执行信号
            executable_signals = self.filter_executable_signals(signals)
            all_signals.extend(executable_signals)

        if all_signals and notification_callback:
            notification_callback(all_signals)

        return all_signals


class IntraDayMonitor:
    """盘中实时监控（需要分钟级数据源）"""

    def __init__(self):
        self.active_monitors = {}

    def start_monitor(
        self,
        symbol: str,
        strategy_id: str,
        callback: callable,
        interval_seconds: int = 60  # 每分钟检查一次
    ):
        """
        启动盘中监控

        Args:
            symbol: 股票代码
            strategy_id: 策略ID
            callback: 触发回调（信号生成时调用）
            interval_seconds: 检查间隔（秒）
        """
        logger.info(f"启动 {symbol} 盘中监控，策略 {strategy_id}")

        # TODO: 实现分钟级K线获取 + 滚动指标计算
        # 1. 获取最近N根分钟K线
        # 2. 计算指标（RSI/MACD/MA等）
        # 3. 检查策略条件
        # 4. 触发时调用 callback

        pass

    def stop_monitor(self, symbol: str):
        """停止监控"""
        if symbol in self.active_monitors:
            del self.active_monitors[symbol]
            logger.info(f"停止 {symbol} 监控")
