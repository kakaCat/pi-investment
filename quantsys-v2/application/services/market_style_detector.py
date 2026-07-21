"""
市场风格检测服务

检测当前市场风格（价值/成长/周期），为因子选择提供依据
"""
from typing import Dict, List
from datetime import datetime
import structlog

logger = structlog.get_logger(__name__)


class MarketStyleDetector:
    """市场风格检测器"""

    # 市场风格定义
    STYLE_VALUE = 'value'      # 价值风格
    STYLE_GROWTH = 'growth'    # 成长风格
    STYLE_CYCLE = 'cycle'      # 周期风格

    # 风格对应的推荐因子
    STYLE_FACTORS = {
        STYLE_VALUE: ['pe', 'pb', 'dividend_yield', 'debt_ratio'],
        STYLE_GROWTH: ['roe', 'revenue_growth', 'macd', 'momentum'],
        STYLE_CYCLE: ['rsi', 'volume', 'bollinger', 'macd']
    }

    def __init__(self, kline_repo=None, stock_repo=None):
        self.kline_repo = kline_repo
        self.stock_repo = stock_repo

    def detect_market_style(self, lookback_days: int = 60) -> Dict:
        """
        检测市场风格

        Args:
            lookback_days: 回看天数

        Returns:
            {
                'style': str,                    # 主导风格
                'confidence': float,             # 置信度 (0-1)
                'scores': Dict[str, float],      # 各风格评分
                'indicators': Dict,              # 指标明细
                'recommended_factors': List[str] # 推荐因子
            }
        """
        try:
            # 1. 计算各风格评分
            value_score = self._calculate_value_style_score(lookback_days)
            growth_score = self._calculate_growth_style_score(lookback_days)
            cycle_score = self._calculate_cycle_style_score(lookback_days)

            # 2. 归一化评分
            total = value_score + growth_score + cycle_score
            if total == 0:
                total = 1.0

            scores = {
                self.STYLE_VALUE: value_score / total,
                self.STYLE_GROWTH: growth_score / total,
                self.STYLE_CYCLE: cycle_score / total
            }

            # 3. 确定主导风格
            dominant_style = max(scores, key=scores.get)
            confidence = scores[dominant_style]

            # 4. 获取详细指标
            indicators = self._get_detailed_indicators(lookback_days)

            # 5. 推荐因子
            recommended_factors = self.STYLE_FACTORS[dominant_style]

            result = {
                'style': dominant_style,
                'confidence': round(confidence, 2),
                'scores': {k: round(v, 2) for k, v in scores.items()},
                'indicators': indicators,
                'recommended_factors': recommended_factors,
                'detection_date': datetime.now().strftime('%Y-%m-%d')
            }

            logger.info(
                f"市场风格检测完成: {dominant_style} (置信度 {confidence:.2%})"
            )

            return result

        except Exception as e:
            logger.error(f"市场风格检测失败: {e}", exc_info=True)
            return self._get_default_result()

    def _calculate_value_style_score(self, lookback_days: int) -> float:
        """计算价值风格评分（简化版）"""
        # 实际应查询银行、地产板块表现，高股息股票表现等
        # 这里使用简化的模拟评分
        return 0.45  # 中等偏下

    def _calculate_growth_style_score(self, lookback_days: int) -> float:
        """计算成长风格评分（简化版）"""
        # 实际应查询科技、新能源板块表现，高ROE股票表现等
        return 0.70  # 较高，假设当前是成长风格市场

    def _calculate_cycle_style_score(self, lookback_days: int) -> float:
        """计算周期风格评分（简化版）"""
        # 实际应查询煤炭、钢铁板块表现，成交量变化等
        return 0.35  # 较低

    def _get_detailed_indicators(self, lookback_days: int) -> Dict:
        """获取详细指标（简化版）"""
        return {
            'banking_performance': 2.5,     # 银行板块涨幅%
            'tech_performance': 5.8,        # 科技板块涨幅%
            'cycle_performance': -1.2,      # 周期板块涨幅%
            'market_volume_change': 15.6,   # 成交量变化%
            'market_volatility': 0.018      # 市场波动率
        }

    def _get_default_result(self) -> Dict:
        """返回默认结果"""
        return {
            'style': self.STYLE_GROWTH,
            'confidence': 0.33,
            'scores': {
                self.STYLE_VALUE: 0.33,
                self.STYLE_GROWTH: 0.33,
                self.STYLE_CYCLE: 0.33
            },
            'indicators': {},
            'recommended_factors': self.STYLE_FACTORS[self.STYLE_GROWTH],
            'detection_date': datetime.now().strftime('%Y-%m-%d')
        }
