"""
策略优化器
使用真实回测进行参数搜索
"""
from typing import Dict, List, Optional
import structlog
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = structlog.get_logger(__name__)


class StrategyOptimizer:
    """策略优化器 - 并行回测执行引擎"""

    def __init__(self, strategy_service, max_workers: int = 10):
        """
        初始化优化器

        Args:
            strategy_service: StrategyCodeService 实例
            max_workers: 最大并行工作线程数
        """
        self.strategy_service = strategy_service
        self.max_workers = max_workers

    def optimize(
        self,
        strategy_id: int,
        symbol: str,
        start_date: str,
        end_date: str,
        param_grid: List[Dict],
        initial_cash: float = 1000000,
        sort_by: str = 'sharpe_ratio',
        period: Optional[str] = None
    ) -> List[Dict]:
        """
        优化策略参数

        Args:
            strategy_id: 策略ID
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            param_grid: 参数网格
            initial_cash: 初始资金
            sort_by: 排序指标（默认 sharpe_ratio）
            period: K线周期（可选），None=日线, '5min'/'15min'/'30min'=分钟线

        Returns:
            按指标排序的回测结果列表，每个结果包含 params 和所有回测指标
        """
        if not param_grid:
            return []

        logger.info(f"开始参数优化: 策略ID={strategy_id}, 参数组合数={len(param_grid)}")

        results = []

        # 并行执行回测
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 提交所有任务
            future_to_params = {
                executor.submit(
                    self._run_single_backtest,
                    strategy_id,
                    symbol,
                    start_date,
                    end_date,
                    params,
                    initial_cash,
                    period
                ): params
                for params in param_grid
            }

            # 收集结果
            for future in as_completed(future_to_params):
                params = future_to_params[future]
                try:
                    backtest_result = future.result()
                    if backtest_result:
                        # 将参数和回测结果合并
                        result = {
                            'params': params,
                            **backtest_result
                        }
                        results.append(result)
                except Exception as e:
                    logger.warning(f"参数 {params} 回测失败: {e}")
                    continue

        # 按指定指标降序排序
        results.sort(key=lambda x: x.get(sort_by, float('-inf')), reverse=True)

        logger.info(f"参数优化完成: 成功 {len(results)}/{len(param_grid)} 组")

        return results

    def _run_single_backtest(
        self,
        strategy_id: int,
        symbol: str,
        start_date: str,
        end_date: str,
        params: Dict,
        initial_cash: float,
        period: Optional[str] = None
    ) -> Optional[Dict]:
        """
        运行单次回测

        Args:
            strategy_id: 策略ID
            symbol: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            params: 参数字典
            initial_cash: 初始资金
            period: K线周期（可选）

        Returns:
            回测结果字典，失败返回 None
        """
        try:
            result = self.strategy_service.backtest_strategy(
                strategy_id=strategy_id,
                symbol=symbol,
                start_date=start_date,
                end_date=end_date,
                initial_cash=initial_cash,
                params_override=params,
                period=period
            )
            return result
        except Exception as e:
            logger.debug(f"回测失败 (params={params}): {e}")
            raise
