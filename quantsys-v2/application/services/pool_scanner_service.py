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

    def __init__(self, pool_repo=None, kline_repo=None, strategy_repo=None):
        self._pool_repo = pool_repo
        self._kline_repo = kline_repo
        self._strategy_repo = strategy_repo
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

        if self._pool_repo is None:
            from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
            pool_repo = EnhancedServiceFactory.resolve(IStockPoolRepository)
        else:
            pool_repo = self._pool_repo
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

                    # 获取 Repository 实例
                    if self._kline_repo is None or self._strategy_repo is None:
                        from infrastructure.services.enhanced_service_factory import EnhancedServiceFactory
                        kline_repo = self._kline_repo or EnhancedServiceFactory.resolve(IKlineRepository)
                        strategy_repo = self._strategy_repo or EnhancedServiceFactory.resolve(IStrategyRepository)
                    else:
                        kline_repo = self._kline_repo
                        strategy_repo = self._strategy_repo
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
