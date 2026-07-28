"""
基本面评分器

基于公司的基本面指标（PE、ROE、毛利率、负债率等）进行灰度化评分
"""
from typing import Dict, Any
from .base_scorer import BaseScorer


class FundamentalScorer(BaseScorer):
    """
    基本面评分器

    评分维度：
    - PE（市盈率）：估值水平评估（±20分）
    - ROE（净资产收益率）：盈利能力评估（±20分）
    - 毛利率：经营质量评估（0-15分）
    - 负债率：财务健康度评估（0-15分）
    - 营收增长率：成长性评估（0-15分）
    - 财务共振：多指标协同加成（0-15分）

    总分范围：0-100（自动截断）
    """

    def __init__(self):
        """初始化基本面评分器"""
        super().__init__()

    @staticmethod
    def _to_float(value):
        """🔧 安全转换为 float（数据库可能返回 Decimal 类型）"""
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def score(self, data: Dict[str, Any]) -> Dict[str, float]:
        """
        计算基本面评分

        Args:
            data: 基本面数据字典，包含以下字段：
                - pe: 市盈率
                - roe: 净资产收益率（%）
                - gross_margin: 毛利率（%）
                - debt_ratio: 负债率（%）
                - revenue_growth: 营收增长率（%）
                - net_profit_margin: 净利率（%）

        Returns:
            评分结果字典：
            {
                'total': 总分 (0-100),
                'breakdown': {
                    'base': 基础分,
                    'pe': PE评分,
                    'roe': ROE评分,
                    'gross_margin': 毛利率评分,
                    'debt_ratio': 负债率评分,
                    'revenue_growth': 营收增长评分,
                    'resonance': 财务共振加成
                }
            }
        """
        # 基础分
        base_score = 50.0

        # 各维度评分（🔧 数据库可能返回 Decimal，统一转 float）
        pe_score = self._score_pe(self._to_float(data.get('pe')))
        roe_score = self._score_roe(self._to_float(data.get('roe')))
        gross_margin_score = self._score_gross_margin(self._to_float(data.get('gross_margin')))
        debt_ratio_score = self._score_debt_ratio(self._to_float(data.get('debt_ratio')))
        revenue_growth_score = self._score_revenue_growth(self._to_float(data.get('revenue_growth')))

        # 财务共振加成
        resonance_score = self._calculate_resonance(data)

        # 汇总评分
        total = (
            base_score +
            pe_score +
            roe_score +
            gross_margin_score +
            debt_ratio_score +
            revenue_growth_score +
            resonance_score
        )

        # 截断到 0-100
        total = max(0.0, min(100.0, total))

        return {
            'total': total,
            'breakdown': {
                'base': base_score,
                'pe': pe_score,
                'roe': roe_score,
                'gross_margin': gross_margin_score,
                'debt_ratio': debt_ratio_score,
                'revenue_growth': revenue_growth_score,
                'resonance': resonance_score
            }
        }

    def _score_pe(self, pe: float) -> float:
        """
        PE（市盈率）评分（±20分）

        评分逻辑：
        - PE < 0：亏损，-20分
        - PE 0-10：极度低估，+20分
        - PE 10-15：低估，线性递减到 +15分
        - PE 15-25：合理估值，+10分
        - PE 25-40：略高估，线性递减到 0分
        - PE 40-60：高估，线性递减到 -10分
        - PE > 60：极度高估，-20分

        Args:
            pe: 市盈率

        Returns:
            PE评分（-20 到 +20）
        """
        if pe is None:
            return 0.0

        if pe < 0:
            # 亏损
            return -20.0
        elif pe <= 10:
            # 极度低估
            return 20.0
        elif pe <= 15:
            # 低估，线性递减：20 -> 15
            return 20.0 - (pe - 10) * (5.0 / 5.0)
        elif pe <= 25:
            # 合理估值
            return 10.0
        elif pe <= 40:
            # 略高估，线性递减：10 -> 0
            return 10.0 - (pe - 25) * (10.0 / 15.0)
        elif pe <= 60:
            # 高估，线性递减：0 -> -10
            return 0.0 - (pe - 40) * (10.0 / 20.0)
        else:
            # 极度高估
            return -20.0

    def _score_roe(self, roe: float) -> float:
        """
        ROE（净资产收益率）评分（±20分）

        评分逻辑：
        - ROE < 0：亏损，-20分
        - ROE 0-5：较差，-10分
        - ROE 5-10：一般，线性增长到 +5分
        - ROE 10-15：良好，线性增长到 +12分
        - ROE 15-20：优秀，线性增长到 +18分
        - ROE > 20：卓越，+20分

        Args:
            roe: 净资产收益率（%）

        Returns:
            ROE评分（-20 到 +20）
        """
        if roe is None:
            return 0.0

        if roe < 0:
            # 亏损
            return -20.0
        elif roe < 5:
            # 较差
            return -10.0
        elif roe <= 10:
            # 一般，线性增长：-10 -> +5
            return -10.0 + (roe - 5) * (15.0 / 5.0)
        elif roe <= 15:
            # 良好，线性增长：+5 -> +12
            return 5.0 + (roe - 10) * (7.0 / 5.0)
        elif roe <= 20:
            # 优秀，线性增长：+12 -> +18
            return 12.0 + (roe - 15) * (6.0 / 5.0)
        else:
            # 卓越
            return 20.0

    def _score_gross_margin(self, gross_margin: float) -> float:
        """
        毛利率评分（0-15分）

        评分逻辑：
        - 毛利率 < 10%：0分
        - 毛利率 10-20%：线性增长到 5分
        - 毛利率 20-30%：线性增长到 10分
        - 毛利率 > 30%：15分

        Args:
            gross_margin: 毛利率（%）

        Returns:
            毛利率评分（0-15）
        """
        if gross_margin is None:
            return 0.0

        if gross_margin < 10:
            return 0.0
        elif gross_margin <= 20:
            # 线性增长：0 -> 5
            return (gross_margin - 10) * (5.0 / 10.0)
        elif gross_margin <= 30:
            # 线性增长：5 -> 10
            return 5.0 + (gross_margin - 20) * (5.0 / 10.0)
        else:
            # 优秀
            return 15.0

    def _score_debt_ratio(self, debt_ratio: float) -> float:
        """
        负债率评分（0-15分）

        评分逻辑：
        - 负债率 < 30%：15分（低负债，财务稳健）
        - 负债率 30-50%：线性递减到 10分
        - 负债率 50-70%：线性递减到 5分
        - 负债率 > 70%：0分（高负债，风险大）

        Args:
            debt_ratio: 负债率（%）

        Returns:
            负债率评分（0-15）
        """
        if debt_ratio is None:
            return 0.0

        if debt_ratio < 30:
            # 低负债
            return 15.0
        elif debt_ratio <= 50:
            # 线性递减：15 -> 10
            return 15.0 - (debt_ratio - 30) * (5.0 / 20.0)
        elif debt_ratio <= 70:
            # 线性递减：10 -> 5
            return 10.0 - (debt_ratio - 50) * (5.0 / 20.0)
        else:
            # 高负债
            return 0.0

    def _score_revenue_growth(self, revenue_growth: float) -> float:
        """
        营收增长率评分（0-15分）

        评分逻辑：
        - 增长 < -10%：0分（严重萎缩）
        - 增长 -10% 到 0%：线性增长到 3分
        - 增长 0-10%：线性增长到 8分
        - 增长 10-30%：线性增长到 13分
        - 增长 > 30%：15分（高成长）

        Args:
            revenue_growth: 营收增长率（%）

        Returns:
            营收增长评分（0-15）
        """
        if revenue_growth is None:
            return 0.0

        if revenue_growth < -10:
            # 严重萎缩
            return 0.0
        elif revenue_growth <= 0:
            # 线性增长：0 -> 3
            return (revenue_growth + 10) * (3.0 / 10.0)
        elif revenue_growth <= 10:
            # 线性增长：3 -> 8
            return 3.0 + revenue_growth * (5.0 / 10.0)
        elif revenue_growth <= 30:
            # 线性增长：8 -> 13
            return 8.0 + (revenue_growth - 10) * (5.0 / 20.0)
        else:
            # 高成长
            return 15.0

    def _calculate_resonance(self, data: Dict[str, Any]) -> float:
        """
        计算财务共振加成（0-15分）

        共振规则：
        1. 价值 + 高盈利：低 PE (<20) + 高 ROE (>15%) → +10分
        2. 优质成长：高毛利 (>30%) + 高增长 (>20%) → +5分
        3. 稳健优质：低负债 (<40%) + 高 ROE (>15%) → +5分

        Args:
            data: 基本面数据字典

        Returns:
            共振加成分（0-15）
        """
        resonance = 0.0

        # 字段可能为 None（stocks 表基本面列未填充），必须先经 _to_float
        pe = self._to_float(data.get('pe'))
        roe = self._to_float(data.get('roe'))
        gross_margin = self._to_float(data.get('gross_margin'))
        revenue_growth = self._to_float(data.get('revenue_growth'))
        debt_ratio = self._to_float(data.get('debt_ratio'))

        pe = pe if pe is not None else float('inf')
        roe = roe if roe is not None else 0
        gross_margin = gross_margin if gross_margin is not None else 0
        revenue_growth = revenue_growth if revenue_growth is not None else 0
        debt_ratio = debt_ratio if debt_ratio is not None else 100

        # 规则1：价值 + 高盈利
        if pe < 20 and pe > 0 and roe > 15:
            resonance += 10.0

        # 规则2：优质成长
        if gross_margin > 30 and revenue_growth > 20:
            resonance += 5.0

        # 规则3：稳健优质
        if debt_ratio < 40 and roe > 15:
            resonance += 5.0

        return min(resonance, 15.0)
