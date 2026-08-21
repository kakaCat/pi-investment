"""
股票池每日扫描服务

功能：
1. 定时扫描股票池中的所有股票
2. 检测策略信号（策略272、273等）
3. 生成扫描报告
4. 通知发现的买入机会
"""
from domain.ports import IKlineRepository, IStockPoolRepository, IStrategyRepository
import structlog
from typing import List, Dict, Optional
from datetime import datetime, time
import json

logger = structlog.get_logger(__name__)


class PoolScannerService:
    """股票池扫描服务"""

    def __init__(self):
        self.scanner_config = {
            'enabled': True,
            'scan_time': '16:05',  # 每天16:05执行（盘后5分钟）
            'strategies': [272, 273],  # 默认使用的策略
            'min_score': 70,  # 最低评分
        }

    def scan_pool(
        self,
        pool_id: int,
        strategy_ids: Optional[List[int]] = None,
        min_score: int = 70
    ) -> Dict:
        """
        扫描股票池，检测买入信号

        Args:
            pool_id: 股票池ID
            strategy_ids: 策略ID列表，默认[272, 273]
            min_score: 最低评分

        Returns:
            扫描结果字典
        """
                from application.services.strategy_code_service import StrategyCodeService

        pool_repo = IStockPoolRepository()
        strategy_service = StrategyCodeService()

        # 1. 获取股票池
        pool = pool_repo.get_pool(pool_id)
        if not pool:
            return {
                'success': False,
                'error': f'股票池 {pool_id} 不存在'
            }

        symbols = pool.get('symbols', [])
        if not symbols:
            return {
                'success': False,
                'error': f'股票池 {pool_id} 为空'
            }

        # 2. 获取策略列表
        if not strategy_ids:
            strategy_ids = self.scanner_config['strategies']

        # 3. 扫描每只股票
        signals = []
        scan_time = datetime.now()

        for symbol in symbols:
            for strategy_id in strategy_ids:
                try:
                    # 使用 PoolSignalScanner 实时检测信号
                    from application.services.pool_signal_scanner import PoolSignalScanner
                                        
                    # 使用 BaseRepository 的方式创建实例（不需要显式传session）
                    kline_repo = IKlineRepository()
                    strategy_repo = IStrategyRepository()
                    scanner = PoolSignalScanner(kline_repo, strategy_repo)

                    # 扫描单只股票
                    signal_result = scanner.scan_pool_signals(
                        symbols=[symbol],
                        strategy_id=strategy_id,
                        lookback_days=60
                    )

                    # 如果有买入信号，添加到结果
                    if signal_result['buy_signals']:
                        buy_signal = signal_result['buy_signals'][0]
                        signals.append({
                            'symbol': symbol,
                            'strategy_id': strategy_id,
                            'signal': 'buy',
                            'current_price': buy_signal['current_price'],
                            'reasons': buy_signal['reasons'],
                            'indicators': buy_signal['indicators'],
                            'trade_params': buy_signal['trade_params'],
                            'scan_time': scan_time.isoformat()
                        })

                except Exception as e:
                    logger.error(f'扫描 {symbol} (策略{strategy_id}) 失败: {e}')
                    continue

        # 4. 生成扫描报告
        result = {
            'success': True,
            'pool_id': pool_id,
            'pool_name': pool.get('name'),
            'scan_time': scan_time.isoformat(),
            'symbols_scanned': len(symbols),
            'strategies_used': strategy_ids,
            'signals_found': len(signals),
            'signals': signals
        }

        # 5. 保存扫描记录
        self._save_scan_result(result)

        return result

    def _check_signal(self, symbol: str, strategy_id: int) -> Optional[Dict]:
        """
        检查单只股票的策略信号（重构版：策略模式）

        Args:
            symbol: 股票代码
            strategy_id: 策略ID

        Returns:
            信号详情，如果无信号返回None
        """
        try:
                        from domain.strategies.strategy_factory import StrategyFactory
            from datetime import datetime, timedelta

            # 1. 获取K线数据
            kline_repo = IKlineRepository()
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=30)

            klines = kline_repo.get_klines(
                symbol=symbol,
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )

            if not klines or len(klines) < 20:
                return None

            # 2. 获取策略对象
            strategy = StrategyFactory.get_strategy(strategy_id)
            if not strategy:
                logger.error(f'策略 {strategy_id} 不存在')
                return None

            # 3. 调用策略检查信号
            signal = strategy.check_signal(symbol, klines)

            return signal

        except Exception as e:
            logger.error(f'检查信号失败 {symbol}: {e}')
            return None
        """
        检查单只股票的策略信号

        Args:
            symbol: 股票代码
            strategy_id: 策略ID

        Returns:
            信号详情，如果无信号返回None
        """
        try:
                        import pandas as pd
            import numpy as np
            from datetime import datetime, timedelta

            kline_repo = IKlineRepository()

            # 1. 获取最近30天的K线数据
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=30)

            klines = kline_repo.get_klines(
                symbol=symbol,
                start_date=start_date.strftime('%Y-%m-%d'),
                end_date=end_date.strftime('%Y-%m-%d')
            )

            if not klines or len(klines) < 20:
                return None

            # 2. 转换为DataFrame并计算技术指标
            df = pd.DataFrame(klines)
            close = df['close'].values
            volume = df['volume'].values

            # 计算RSI
            def calculate_rsi(prices, period=14):
                deltas = np.diff(prices)
                seed = deltas[:period+1]
                up = seed[seed >= 0].sum() / period
                down = -seed[seed < 0].sum() / period
                if down == 0:
                    return 100
                rs = up / down
                rsi = 100 - (100 / (1 + rs))

                # 继续计算
                for i in range(period, len(deltas)):
                    delta = deltas[i]
                    if delta > 0:
                        upval = delta
                        downval = 0
                    else:
                        upval = 0
                        downval = -delta
                    up = (up * (period - 1) + upval) / period
                    down = (down * (period - 1) + downval) / period
                    if down == 0:
                        return 100
                    rs = up / down
                    rsi = 100 - (100 / (1 + rs))
                return rsi

            rsi = calculate_rsi(close)

            # 计算MACD
            def calculate_macd(prices):
                ema12 = pd.Series(prices).ewm(span=12).mean().iloc[-1]
                ema26 = pd.Series(prices).ewm(span=26).mean().iloc[-1]
                macd = ema12 - ema26
                return macd

            macd = calculate_macd(close)

            # 计算MA5
            ma5 = np.mean(close[-5:])

            # 计算成交量比
            vol_ma10 = np.mean(volume[-10:])
            vol_ratio = volume[-1] / vol_ma10 if vol_ma10 > 0 else 1

            current_price = close[-1]

            # 3. 检查策略条件
            if strategy_id == 272:
                # 策略272：新能源动量策略 v1.0
                # 买入条件：
                # 1. RSI < 50 (不过热)
                # 2. 价格突破MA5
                # 3. MACD > 0
                # 4. 放量 > 1.3倍

                buy_signal = (
                    rsi < 50 and
                    current_price > ma5 * 1.01 and
                    macd > 0 and
                    vol_ratio > 1.3
                )

                if buy_signal:
                    # 计算评分
                    score = 70
                    if rsi < 45: score += 5
                    if rsi < 40: score += 5
                    if vol_ratio > 1.5: score += 5
                    if vol_ratio > 2.0: score += 5
                    if macd > 0.5: score += 5

                    return {
                        'symbol': symbol,
                        'strategy_id': 272,
                        'strategy_name': '策略272',
                        'score': min(score, 100),
                        'indicators': {
                            'rsi': round(rsi, 2),
                            'macd': round(macd, 2),
                            'ma5': round(ma5, 2),
                            'price': round(current_price, 2),
                            'vol_ratio': round(vol_ratio, 2)
                        },
                        'scan_time': datetime.now().isoformat()
                    }

            elif strategy_id == 273:
                # 策略273：宽松动量策略 v1.0
                # 买入条件更宽松
                buy_signal = (
                    rsi < 60 and
                    current_price > ma5 * 1.005 and
                    macd > -0.5 and
                    vol_ratio > 1.2
                )

                if buy_signal:
                    score = 70
                    if rsi < 50: score += 5
                    if vol_ratio > 1.5: score += 5

                    return {
                        'symbol': symbol,
                        'strategy_id': 273,
                        'strategy_name': '策略273',
                        'score': min(score, 100),
                        'indicators': {
                            'rsi': round(rsi, 2),
                            'macd': round(macd, 2),
                            'ma5': round(ma5, 2),
                            'price': round(current_price, 2),
                            'vol_ratio': round(vol_ratio, 2)
                        },
                        'scan_time': datetime.now().isoformat()
                    }

            return None

        except Exception as e:
            logger.error(f'检查信号失败 {symbol}: {e}')
            return None

    def _save_scan_result(self, result: Dict):
        """
        保存扫描结果到数据库

        Args:
            result: 扫描结果
        """
        # TODO: 保存到 pool_scan_results 表
        logger.info(f"扫描完成：{result['pool_name']}, 发现 {result['signals_found']} 个信号")

    def scan_all_pools(
        self,
        strategy_ids: Optional[List[int]] = None,
        min_score: int = 70
    ) -> Dict:
        """
        扫描所有启用扫描的股票池

        Args:
            strategy_ids: 策略ID列表
            min_score: 最低评分

        Returns:
            汇总扫描结果
        """
        
        pool_repo = IStockPoolRepository()
        pools = pool_repo.get_all_pools()

        all_signals = []
        scan_results = []
        skipped_pools = []

        for pool in pools:
            pool_id = pool['id']
            pool_name = pool.get('name')

            # 检查是否启用扫描
            scan_enabled = pool.get('scan_enabled', True)  # 默认启用

            if not scan_enabled:
                logger.info(f"跳过股票池 {pool_name}（扫描已禁用）")
                skipped_pools.append({
                    'pool_id': pool_id,
                    'pool_name': pool_name,
                    'reason': 'scan_disabled'
                })
                continue

            result = self.scan_pool(pool_id, strategy_ids, min_score)

            if result['success']:
                scan_results.append(result)
                all_signals.extend(result['signals'])

        return {
            'success': True,
            'scan_time': datetime.now().isoformat(),
            'pools_scanned': len(scan_results),
            'pools_skipped': len(skipped_pools),
            'total_signals': len(all_signals),
            'results': scan_results,
            'skipped': skipped_pools
        }


# 全局实例
pool_scanner_service = PoolScannerService()
