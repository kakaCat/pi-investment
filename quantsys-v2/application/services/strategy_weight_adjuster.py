"""
策略权重调整服务

根据市场风格和策略历史表现动态调整策略权重
"""
from domain.ports import IStrategyPerformanceRepository, IStrategyWeightRepository
from typing import Dict, Optional
import structlog


logger = structlog.get_logger(__name__)


class StrategyWeightAdjuster:
    """策略权重调整器

    P2-1: 支持依赖注入，保持向后兼容
    """

    # 模式切换阈值
    DYNAMIC_MODE_THRESHOLD = 30  # 样本 >= 30 切换到动态模式

    # 平滑过渡权重
    DYNAMIC_WEIGHT_RATIO = 0.7  # 动态权重占比 70%
    STATIC_WEIGHT_RATIO = 0.3   # 静态权重占比 30%

    def __init__(
        self,
        weight_repo: Optional[IStrategyWeightRepository] = None,
        performance_repo: Optional[IStrategyPerformanceRepository] = None,
    ):
        """初始化服务

        Args:
            weight_repo: 策略权重仓库（可选）
            performance_repo: 策略表现仓库（可选）

        P2-1: 推荐通过 ServiceFactory 获取实例
        """
        self.weight_repo = weight_repo
        self.performance_repo = performance_repo

    def get_weight(
        self,
        strategy_name: str,
        strategy_type: str,
        market_style: str
    ) -> Dict:
        """
        获取策略权重调整

        Args:
            strategy_name: 策略名称
            strategy_type: 策略类型
            market_style: 市场风格

        Returns:
            {
                'strategy_name': str,
                'strategy_type': str,
                'market_style': str,
                'weight_adjustment': float,
                'mode': 'static' | 'dynamic',
                'sample_size': int,
                'historical_performance': dict (可选)
            }
        """
        # 1. 查询样本数量
        sample_size = self._count_samples(strategy_name)

        # 2. 判断模式
        if sample_size < self.DYNAMIC_MODE_THRESHOLD:
            # 静态模式
            weight = self._get_static_weight(strategy_type, market_style)
            mode = 'static'
            historical_performance = None
        else:
            # 动态模式
            weight = self._calculate_dynamic_weight(
                strategy_name,
                strategy_type,
                market_style
            )
            mode = 'dynamic'
            historical_performance = self._get_historical_performance(strategy_name)

        result = {
            'strategy_name': strategy_name,
            'strategy_type': strategy_type,
            'market_style': market_style,
            'weight_adjustment': weight,
            'mode': mode,
            'sample_size': sample_size
        }

        if historical_performance:
            result['historical_performance'] = historical_performance

        logger.info(
            f"策略权重查询: {strategy_name} ({strategy_type}) "
            f"在 {market_style} 市场, 权重: {weight:.2f}, 模式: {mode}"
        )

        return result

    def _count_samples(self, strategy_name: str) -> int:
        """统计策略样本数量"""
        try:
            stats = self.performance_repo.get_statistics(strategy_name)
            if stats is None:
                return 0
            return stats.get('total_trades', 0)
        except Exception as e:
            logger.warning(f"统计样本数量失败: {e}")
            return 0

    def _get_static_weight(self, strategy_type: str, market_style: str) -> float:
        """
        获取静态权重

        Args:
            strategy_type: 策略类型
            market_style: 市场风格

        Returns:
            权重调整值（基准 1.0）
        """
        if market_style in ['unknown', 'mixed_market']:
            return 1.0

        try:
            static_weight = self.weight_repo.get_static_weight(strategy_type, market_style)
            return 1.0 + static_weight
        except Exception as e:
            logger.error(f"获取静态权重失败: {e}")
            return 1.0

    def _calculate_dynamic_weight(
        self,
        strategy_name: str,
        strategy_type: str,
        market_style: str
    ) -> float:
        """
        计算动态权重

        Args:
            strategy_name: 策略名称
            strategy_type: 策略类型
            market_style: 市场风格

        Returns:
            权重调整值
        """
        try:
            # 1. 查询各风格下的表现
            perf_by_style = self._get_performance_by_style(strategy_name)

            if not perf_by_style or market_style not in perf_by_style:
                # 回退到静态权重
                logger.warning(f"策略 {strategy_name} 在 {market_style} 风格下无历史数据，回退到静态模式")
                return self._get_static_weight(strategy_type, market_style)

            # 2. 计算各风格的夏普比率
            sharpe_values = {}
            for style, perf in perf_by_style.items():
                sharpe = perf.get('sharpe', 0.0)
                sharpe_values[style] = max(0, sharpe)  # 负夏普视为 0

            # 3. 归一化权重
            total_sharpe = sum(sharpe_values.values())
            if total_sharpe == 0:
                # 所有风格表现都不好，回退到静态权重
                return self._get_static_weight(strategy_type, market_style)

            dynamic_weight = sharpe_values[market_style] / total_sharpe * 2.0

            # 4. 平滑过渡：70% 动态 + 30% 静态
            static_weight = self._get_static_weight(strategy_type, market_style)
            final_weight = (
                dynamic_weight * self.DYNAMIC_WEIGHT_RATIO +
                static_weight * self.STATIC_WEIGHT_RATIO
            )

            # 5. 限制范围 [0.6, 2.0]
            final_weight = max(0.6, min(2.0, final_weight))

            return final_weight

        except Exception as e:
            logger.error(f"动态权重计算失败: {e}", exc_info=True)
            return self._get_static_weight(strategy_type, market_style)

    def _get_performance_by_style(self, strategy_name: str) -> Dict:
        """
        查询策略在各市场风格下的表现

        Args:
            strategy_name: 策略名称

        Returns:
            {
                'momentum': {'sharpe': 1.8, 'win_rate': 0.65},
                'oscillation': {'sharpe': 0.6, 'win_rate': 0.42},
                ...
            }
        """
        try:
            # 查询按 market_style 分组的统计
            query = """
                SELECT
                    scenario_tags->>0 as market_style,
                    COUNT(*) as total_trades,
                    AVG(pnl_pct) as avg_return,
                    STDDEV(pnl_pct) as std_return,
                    SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END)::FLOAT / COUNT(*) as win_rate
                FROM quant.strategy_performance
                WHERE strategy_name = %s
                  AND scenario_tags IS NOT NULL
                  AND exit_price IS NOT NULL
                GROUP BY scenario_tags->>0
            """

            cursor = self.performance_repo._get_cursor()
            cursor.execute(query, (strategy_name,))
            results = cursor.fetchall()
            cursor.close()

            perf_by_style = {}
            for row in results:
                if isinstance(row, dict):
                    style = row['market_style']
                    if not style:
                        continue
                    avg_return = float(row['avg_return']) if row['avg_return'] else 0.0
                    std_return = float(row['std_return']) if row['std_return'] else 1.0
                    win_rate = float(row['win_rate']) if row['win_rate'] else 0.0
                else:
                    # Tuple format: (market_style, avg_return, std_return, win_rate, count)
                    style = row[0]
                    if not style:
                        continue
                    avg_return = float(row[1]) if row[1] else 0.0
                    std_return = float(row[2]) if row[2] else 1.0
                    win_rate = float(row[3]) if row[3] else 0.0

                # 计算夏普比率（简化版：年化假设 252 个交易日）
                sharpe = (avg_return / std_return) * (252 ** 0.5) if std_return > 0 else 0.0

                perf_by_style[style] = {
                    'sharpe': sharpe,
                    'win_rate': win_rate,
                    'avg_return': avg_return
                }

            return perf_by_style

        except Exception as e:
            logger.error(f"查询风格表现失败: {e}", exc_info=True)
            return {}

    def _get_historical_performance(self, strategy_name: str) -> Dict:
        """获取策略历史表现摘要"""
        try:
            perf_by_style = self._get_performance_by_style(strategy_name)
            return perf_by_style
        except Exception as e:
            logger.warning(f"获取历史表现失败: {e}")
            return {}
