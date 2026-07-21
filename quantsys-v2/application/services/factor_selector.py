"""
因子动态入选服务

根据因子评级自动过滤和调整权重
"""
from typing import List, Dict
import structlog

logger = structlog.get_logger(__name__)


class FactorSelector:
    """因子动态入选器"""

    # 评级阈值
    RATING_EXCLUDE = 'D'       # 排除评级
    RATING_MIN_WEIGHT = 'C'    # 最低权重评级
    
    # 评级权重系数
    RATING_COEFFICIENTS = {
        'A': 1.0,    # 正常权重
        'B': 0.8,    # 略微降低
        'C': 0.5,    # 最低权重
        'D': 0.0     # 排除
    }

    def __init__(self):
        pass

    def select_factors(
        self,
        factor_analysis: Dict,
        min_rating: str = 'C'
    ) -> Dict:
        """
        根据因子评级动态筛选因子

        Args:
            factor_analysis: 因子分析结果
            min_rating: 最低评级要求（C/B/A）

        Returns:
            {
                'selected_factors': List[Dict],   # 入选因子列表
                'excluded_factors': List[Dict],   # 排除因子列表
                'selection_summary': Dict         # 筛选摘要
            }
        """
        try:
            factors = factor_analysis.get('factors', [])
            
            selected = []
            excluded = []
            
            # 评级优先级
            rating_priority = {'A': 4, 'B': 3, 'C': 2, 'D': 1}
            min_priority = rating_priority.get(min_rating, 2)
            
            for factor in factors:
                rating = factor.get('rating', 'D')
                priority = rating_priority.get(rating, 1)
                
                if priority >= min_priority:
                    # 添加权重系数
                    factor_copy = factor.copy()
                    factor_copy['weight_coefficient'] = self.RATING_COEFFICIENTS.get(rating, 0.5)
                    selected.append(factor_copy)
                else:
                    excluded.append(factor)
            
            # 生成摘要
            summary = {
                'total_factors': len(factors),
                'selected_count': len(selected),
                'excluded_count': len(excluded),
                'min_rating': min_rating,
                'rating_distribution': self._get_rating_distribution(selected)
            }
            
            logger.info(
                f"因子筛选完成: {len(selected)}/{len(factors)} 入选 "
                f"(最低评级: {min_rating})"
            )
            
            return {
                'selected_factors': selected,
                'excluded_factors': excluded,
                'selection_summary': summary
            }
            
        except Exception as e:
            logger.error(f"因子筛选失败: {e}", exc_info=True)
            return {
                'selected_factors': factors,
                'excluded_factors': [],
                'selection_summary': {}
            }

    def adjust_weights_by_rating(
        self,
        weights: Dict[str, float],
        selected_factors: List[Dict]
    ) -> Dict[str, float]:
        """
        根据评级调整权重

        Args:
            weights: 原始权重
            selected_factors: 入选因子列表（包含weight_coefficient）

        Returns:
            调整后的权重
        """
        try:
            adjusted_weights = {}
            
            # 按维度分组因子
            dimension_factors = {
                'technical': [],
                'fundamental': [],
                'capital': []
            }
            
            for factor in selected_factors:
                factor_name = factor.get('factor_name', '').lower()
                coef = factor.get('weight_coefficient', 1.0)
                
                # 分类因子
                if factor_name in ['rsi', 'macd', 'bollinger', 'volume', 'momentum']:
                    dimension_factors['technical'].append(coef)
                elif factor_name in ['roe', 'pe', 'pb', 'debt_ratio', 'gross_margin']:
                    dimension_factors['fundamental'].append(coef)
                else:
                    dimension_factors['capital'].append(coef)
            
            # 计算各维度的平均系数
            for dim, coefs in dimension_factors.items():
                if coefs:
                    avg_coef = sum(coefs) / len(coefs)
                    adjusted_weights[dim] = weights.get(dim, 0.33) * avg_coef
                else:
                    adjusted_weights[dim] = weights.get(dim, 0.33) * 0.5  # 无因子时降低权重
            
            # 归一化
            total = sum(adjusted_weights.values())
            if total > 0:
                adjusted_weights = {k: v / total for k, v in adjusted_weights.items()}
            
            logger.info(f"权重调整完成: {adjusted_weights}")
            
            return adjusted_weights
            
        except Exception as e:
            logger.error(f"权重调整失败: {e}", exc_info=True)
            return weights

    def _get_rating_distribution(self, factors: List[Dict]) -> Dict[str, int]:
        """获取评级分布"""
        distribution = {'A': 0, 'B': 0, 'C': 0, 'D': 0}
        for factor in factors:
            rating = factor.get('rating', 'D')
            if rating in distribution:
                distribution[rating] += 1
        return distribution
