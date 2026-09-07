"""
策略执行器

负责执行策略代码生成交易信号
"""

from domain.ports import IKlineRepository, ISignalRepository, IStrategyRepository
import structlog
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from domain.backtest.engine.indicator_strategy_executor import IndicatorStrategyExecutor
from domain.backtest.engine.script_strategy_executor import ScriptStrategyExecutor

logger = structlog.get_logger(__name__)


class StrategyExecutor:
    """策略执行服务

    P2-1: 支持依赖注入，保持向后兼容
    """

    def __init__(
        self,
        strategy_repo: Optional[IStrategyRepository] = None,
        kline_repo: Optional[IKlineRepository] = None,
        signal_repo: Optional[ISignalRepository] = None,
        indicator_executor: Optional[IndicatorStrategyExecutor] = None,
        script_executor: Optional[ScriptStrategyExecutor] = None,
    ):
        """初始化策略执行器

        Args:
            strategy_repo: 策略仓库（可选）
            kline_repo: K线仓库（可选）
            signal_repo: 信号仓库（可选）
            indicator_executor: 指标策略执行器（可选）
            script_executor: 脚本策略执行器（可选）

        P2-1: 推荐通过 ServiceFactory 获取实例
        """
        self.strategy_repo = strategy_repo
        self.kline_repo = kline_repo
        self.signal_repo = signal_repo
        self.indicator_executor = indicator_executor or IndicatorStrategyExecutor()
        self.script_executor = script_executor or ScriptStrategyExecutor()

    def generate_signal(
        self,
        strategy_id: int,
        symbol: str,
        date: Optional[str] = None
    ) -> Optional[Dict]:
        """
        生成交易信号

        Args:
            strategy_id: 策略ID
            symbol: 股票代码
            date: 信号日期（可选，默认今天）

        Returns:
            信号字典或 None（无信号）
            {
                'symbol': '600000',
                'strategy_id': 1,
                'strategy_name': '双均线策略',
                'signal_type': 'BUY' | 'SELL' | 'HOLD',
                'confidence': 0.85,
                'entry_price': 10.5,
                'stop_loss': 9.8,
                'target_price': 12.0,
                'reason': '均线金叉',
                'indicators': {...}
            }
        """
        logger.info(f"生成信号: 策略ID={strategy_id}, 股票={symbol}, 日期={date}")

        # 1. 获取策略
        strategy = self.strategy_repo.get_by_id(strategy_id)
        if not strategy:
            raise ValueError(f"策略不存在: {strategy_id}")

        # 2. 获取K线数据（最近400天）
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')

        start_date = (datetime.strptime(date, '%Y-%m-%d') - timedelta(days=400)).strftime('%Y-%m-%d')
        klines = self.kline_repo.get_range(symbol, start_date, date)

        # klines is a Polars DataFrame, check if empty using .is_empty()
        if klines.is_empty() or len(klines) < 20:
            logger.warning(f"K线数据不足: {symbol}, 数量={len(klines)}")
            return None

        # 3. 根据策略类型执行
        try:
            if strategy['code_type'] == 'indicator':
                signal = self._execute_indicator_strategy(strategy, klines, symbol, date)
            elif strategy['code_type'] == 'script':
                signal = self._execute_script_strategy(strategy, klines, symbol, date)
            else:
                raise ValueError(f"不支持的策略类型: {strategy['code_type']}")

            # 4. 附加策略信息
            if signal:
                signal['strategy_id'] = strategy_id
                signal['strategy_name'] = strategy.get('name', f"策略{strategy_id}")
                signal['symbol'] = symbol
                signal['date'] = date

            return signal

        except Exception as e:
            logger.error(f"策略执行失败: {e}", exc_info=True)
            return None

    def _execute_indicator_strategy(
        self,
        strategy: Dict,
        klines: List[Dict],
        symbol: str,
        date: str
    ) -> Optional[Dict]:
        """
        执行 Indicator 策略

        Returns:
            信号字典或 None
        """
        code = strategy['code_content']
        params = strategy.get('parsed_params')

        # 执行策略
        exec_result = self.indicator_executor.execute(
            code=code,
            klines=klines,
            params=params
        )

        signals_df = exec_result.signals
        # 检查信号是否为空（兼容 pandas 和 polars）
        from infrastructure.utils.dataframe_utils import is_dataframe_empty
        if is_dataframe_empty(signals_df):
            logger.debug("策略未生成信号")
            return None

        # 获取最后一行信号
        last_row = signals_df.iloc[-1]
        has_buy = bool(last_row.get('buy', False))
        has_sell = bool(last_row.get('sell', False))

        if not has_buy and not has_sell:
            return None

        # 构建信号
        signal_type = 'BUY' if has_buy else 'SELL'
        confidence = float(last_row.get('confidence', 0.7))
        close_price = float(last_row['close'])

        # 提取指标（排除价格和信号列）
        indicators = {}
        exclude_cols = {'buy', 'sell', 'open', 'high', 'low', 'close', 'volume', 'trade_date', 'date'}
        for col in signals_df.columns:
            if col not in exclude_cols:
                val = last_row.get(col)
                if val is not None and not (isinstance(val, float) and str(val) == 'nan'):
                    indicators[col] = float(val) if isinstance(val, (int, float)) else val

        return {
            'signal_type': signal_type,
            'confidence': confidence,
            'entry_price': close_price,
            'stop_loss': last_row.get('stop_loss'),
            'target_price': last_row.get('target_price'),
            'reason': f"Indicator signal: {signal_type}",
            'indicators': indicators
        }

    def _execute_script_strategy(
        self,
        strategy: Dict,
        klines: List[Dict],
        symbol: str,
        date: str
    ) -> Optional[Dict]:
        """
        执行 Script 策略

        Returns:
            信号字典或 None
        """
        code = strategy['code_content']
        params = strategy.get('parsed_params')

        # 执行策略
        exec_result = self.script_executor.execute(
            code=code,
            klines=klines,
            params=params
        )

        # Script executor 返回完整的交易结果
        if not exec_result or not exec_result.get('positions'):
            return None

        # 从最后一个持仓状态提取信号
        last_position = exec_result['positions'][-1]

        return {
            'signal_type': last_position.get('action', 'HOLD'),
            'confidence': last_position.get('confidence', 0.7),
            'entry_price': last_position.get('price'),
            'stop_loss': last_position.get('stop_loss'),
            'target_price': last_position.get('target_price'),
            'reason': last_position.get('reason', 'Script signal'),
            'indicators': last_position.get('indicators', {})
        }

    def run_strategy(
        self,
        strategy_id: int,
        symbol: str,
        date: Optional[str] = None,
        persist: bool = False
    ) -> Optional[Dict]:
        """
        运行策略并可选地持久化信号

        Args:
            strategy_id: 策略ID
            symbol: 股票代码
            date: 日期（可选）
            persist: 是否持久化信号到数据库

        Returns:
            信号字典或 None
        """
        signal = self.generate_signal(strategy_id, symbol, date)

        if signal and persist:
            # 持久化信号到数据库
            signal_id = self.signal_repo.create_signal({
                'signal_date': date or datetime.now().strftime('%Y-%m-%d'),
                'symbol': symbol,
                'name': signal['strategy_name'],
                'action': signal['signal_type'],
                'action_type': 1,
                'strategy_id': strategy_id,
                'price': signal.get('entry_price'),
                'reason': signal.get('reason', ''),
                'confidence': signal.get('confidence', 0.0),
                'indicators': signal.get('indicators')
            })
            signal['signal_id'] = signal_id
            logger.info(f"信号已持久化: signal_id={signal_id}")

        return signal

    def batch_generate_signals(
        self,
        strategy_id: int,
        symbols: List[str],
        date: Optional[str] = None,
        persist: bool = False
    ) -> List[Dict]:
        """
        批量生成信号

        Args:
            strategy_id: 策略ID
            symbols: 股票代码列表
            date: 日期（可选）
            persist: 是否持久化

        Returns:
            信号列表
        """
        signals = []
        for symbol in symbols:
            try:
                signal = self.run_strategy(strategy_id, symbol, date, persist)
                if signal:
                    signals.append(signal)
            except Exception as e:
                logger.error(f"生成信号失败: {symbol}, 错误: {e}")
                continue

        logger.info(f"批量生成信号完成: {len(signals)}/{len(symbols)}")
        return signals
