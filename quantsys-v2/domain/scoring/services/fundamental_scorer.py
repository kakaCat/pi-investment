"""
基本面评分器（领域层）

基于公司的基本面指标（PE、ROE、毛利率、负债率等）进行行业中性化评分。

改进：
- 使用行业内分位数排名（替代绝对值阈值）
- 科技股 PE=50 如果行业内排名靠前，得分高
"""

from typing import Dict, Any, List, Optional
import logging
import math

logger = logging.getLogger(__name__)


class FundamentalScorer:
    """
    基本面评分器（领域层）

    评分维度：
    - PE（市盈率）：行业内分位数（反向，权重 40%）
    - ROE（净资产收益率）：行业内分位数（正向，权重 30%）
    - 营收增长率：行业内分位数（正向，权重 30%）

    总分范围：0-100
    
    改进：
    - 行业中性化：使用行业内分位数，不再使用绝对值阈值
    - 科技股 PE=50 如果行业内排名靠前，得分高
    """

    def __init__(self, industry_data_port=None):
        """
        初始化基本面评分器
        
        Args:
            industry_data_port: 行业数据端口（可选，用于行业中性化）
        """
        self.industry_data_port = industry_data_port

    @staticmethod
    def _to_float(value):
        """🔧 安全转换为 float（数据库可能返回 Decimal 类型）"""
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def score(self, data: Dict[str, Any], sector: Optional[str] = None) -> Dict[str, float]:
        """
        计算基本面评分（行业中性化）

        Args:
            data: 基本面数据字典，包含以下字段：
                - pe: 市盈率
                - roe: 净资产收益率（%）
                - revenue_growth: 营收增长率（%）
            sector: 行业名称（可选，用于行业中性化）

        Returns:
            评分结果字典：
            {
                'total': 总分 (0-100),
                'breakdown': {
                    'pe': PE评分,
                    'roe': ROE评分,
                    'revenue_growth': 营收增长评分,
                },
                'sector_percentiles': {
                    'pe': PE分位数,
                    'roe': ROE分位数,
                    'revenue_growth': 营收增长分位数,
                }
            }
        """
        # 如果提供了行业数据端口和行业名称，使用行业中性化评分
        if self.industry_data_port and sector:
            return self._score_industry_neutral(data, sector)
        
        # 否则使用绝对值评分（向后兼容）
        return self._score_absolute(data)
    
    def _score_industry_neutral(self, data: Dict[str, Any], sector: str) -> Dict[str, float]:
        """
        行业中性化评分
        
        使用行业内分位数排名，而不是绝对值阈值。
        
        Args:
            data: 基本面数据字典
            sector: 行业名称
            
        Returns:
            评分结果字典
        """
        # 获取同行业所有值
        sector_pe_values = self.industry_data_port.get_sector_factor_values(sector, 'pe')
        sector_roe_values = self.industry_data_port.get_sector_factor_values(sector, 'roe')
        sector_growth_values = self.industry_data_port.get_sector_factor_values(sector, 'revenue_growth')
        
        # 计算各指标的行业内分位数
        pe = self._to_float(data.get('pe'))
        roe = self._to_float(data.get('roe'))
        revenue_growth = self._to_float(data.get('revenue_growth'))
        
        pe_percentile = self._calc_percentile(pe, sector_pe_values) if pe else 0.5
        roe_percentile = self._calc_percentile(roe, sector_roe_values) if roe else 0.5
        growth_percentile = self._calc_percentile(revenue_growth, sector_growth_values) if revenue_growth else 0.5
        
        # 计算得分（0-100）
        # PE 反向（越低越好），ROE/增长率 正向（越高越好）
        pe_score = (1 - pe_percentile) * 100
        roe_score = roe_percentile * 100
        growth_score = growth_percentile * 100
        
        # 加权合成
        total = pe_score * 0.40 + roe_score * 0.30 + growth_score * 0.30
        
        return {
            'total': total,
            'breakdown': {
                'pe': pe_score,
                'roe': roe_score,
                'revenue_growth': growth_score,
            },
            'sector_percentiles': {
                'pe': pe_percentile,
                'roe': roe_percentile,
                'revenue_growth': growth_percentile,
            }
        }
    
    def _score_absolute(self, data: Dict[str, Any]) -> Dict[str, float]:
        """
        绝对值评分（向后兼容）
        
        使用绝对值阈值，不使用行业中性化。
        
        Args:
            data: 基本面数据字典
            
        Returns:
            评分结果字典
        """
        # 基础分
        base_score = 50.0

        # 各维度评分
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
    
    @staticmethod
    def _calc_percentile(value: float, sector_values: List[float]) -> float:
        """
        计算分位数（0-1）
        
        Args:
            value: 当前值
            sector_values: 同行业所有值
            
        Returns:
            float: 分位数（0-1），0=最低，1=最高
        """
        if not sector_values:
            return 0.5
        
        # 过滤无效值
        valid_values = [v for v in sector_values if v is not None and not math.isnan(v)]
        if not valid_values:
            return 0.5
        
        sorted_values = sorted(valid_values)
        
        # 使用二分查找计算分位数
        import bisect
        rank = bisect.bisect_left(sorted_values, value)
        percentile = rank / len(sorted_values)
        
        return min(1.0, max(0.0, percentile))

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
