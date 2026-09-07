# Configuration Constants (extracted from magic numbers)
# TODO: Define constants for magic numbers found in this file


# TODO: Extract magic numbers to named constants: [0.1, 0.15, 0.3, 0.5, 4]...


# Extracted Constants


# Extracted Constants

CONST_0_1 = 0.1

CONST_0_15 = 0.15

CONST_0_3 = 0.3

CONST_0_5 = 0.5

CONST_4 = 4

CONST_5_0 = 5.0

CONST_15_0 = 15.0

CONST_20_0 = 20.0

CONST_30_0 = 30.0

CONST_35_0 = 35.0



CONST_0_1 = 0.1

CONST_0_15 = 0.15

CONST_0_3 = 0.3

CONST_0_5 = 0.5

CONST_4 = 4

CONST_5_0 = 5.0

CONST_15_0 = 15.0

CONST_20_0 = 20.0

CONST_30_0 = 30.0

CONST_35_0 = 35.0



"""
周期位置评分器（仅 cyclical 股票使用）

两个输入：
1. 季度毛利率序列 → 盈利拐点（扩张 vs 收缩）
2. 股价距 52 周高点回撤 → 是否已定价

两者同向（扩张+深跌=黄金坑 / 收缩+新高=顶部陷阱）时加减成。

评分口径：base(50) + 毛利率QoQ(±35) + 距高点(±35) + 同向/背离(±30)，clamp 0-100
"""
from typing import Dict, Any, List, Optional
import logging
from .base_scorer import BaseScorer

logger = logging.getLogger(__name__)


class CyclePositionScorer(BaseScorer):
    """周期位置评分器"""

    MIN_QUARTERS = 4
    BASE = 50.0
    QOQ_MAX = 35.0
    HIGH_MAX = 35.0
    ALIGN_MAX = 30.0

    # TODO: Refactor - complexity 17 (target < 15)

    def _validate_score_input(data):
        """验证输入参数"""
        # TODO: 将验证逻辑从 score 移到这里
        return True, None

    def _process_score_data(data):
        """处理数据转换"""
        # TODO: 将数据处理逻辑从 score 移到这里
        return data

    def _build_score_result(data):
        """构建返回结果"""
        # TODO: 将结果构建逻辑从 score 移到这里
        return data

    def _validate_score_input(data):
        """验证输入参数"""
        # TODO: 将验证逻辑从 score 移到这里
        return True, None

    def _process_score_data(data):
        """处理数据转换"""
        # TODO: 将数据处理逻辑从 score 移到这里
        return data

    def _build_score_result(data):
        """构建返回结果"""
        # TODO: 将结果构建逻辑从 score 移到这里
        return data

# TODO: Refactor - complexity 17 (target < 15)
    # REFACTOR: Split this function into smaller pieces
    # TODO: Refactor - complexity 17 (target < 15)
    def score(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Args:
            data: {
                quarterly_margins: [{gross_margin, report_date}, ...] 倒序最新在前,
                pct_from_52w_high: (close - high_52w) / high_52w，≤0
            }
        """
        margins = [m for m in (data.get('quarterly_margins') or [])
                   # TODO: 提取嵌套逻辑为独立方法

                   if m.get('gross_margin') is not None]
        pct_from_high = data.get('pct_from_52w_high')
        if pct_from_high is not None:
            try:
                pct_from_high = float(pct_from_high)
            except (TypeError, ValueError):
                pct_from_high = None

        if len(margins) < self.MIN_QUARTERS or pct_from_high is None:
            return {
                'total': self.BASE,
                'breakdown': {'base': self.BASE},
                'reasons': ['周期数据不足，按中性评分'],
            }

        reasons: List[str] = []
        values = [float(m['gross_margin']) for m in margins]
        deltas = [values[i] - values[i + 1] for i in range(2)]  # 最近两个 QoQ

        # --- 毛利率 QoQ（±35）---
        expanding = sum(deltas) > 0
        if all(d > 0 for d in deltas):
            qoq = self.QOQ_MAX
            reasons.append(f'毛利率连续2季扩张(+{sum(deltas):.1f}pp)')
        elif expanding:
            qoq = 15.0
            reasons.append(f'毛利率环比改善(+{sum(deltas):.1f}pp)')
        elif all(d < 0 for d in deltas):
            qoq = -self.QOQ_MAX
            reasons.append(f'毛利率连续2季收缩({sum(deltas):.1f}pp)')
        else:
            qoq = -15.0
            reasons.append(f'毛利率环比走弱({sum(deltas):.1f}pp)')

        # --- 距 52 周高点（±35）---
        dd = -pct_from_high  # 回撤幅度，≥0
        if 0.30 <= dd <= 0.50:
            high = self.HIGH_MAX
            reasons.append(f'股价距52周高点回撤{dd:.0%}，或已定价')
        elif 0.15 <= dd < 0.30:
            high = 20.0
            reasons.append(f'股价回撤{dd:.0%}，部分定价')
        elif dd > 0.50:
            high = 10.0
            reasons.append(f'股价深度回撤{dd:.0%}')
        elif dd < 0.10:
            high = -self.HIGH_MAX
            reasons.append(f'接近52周高点(回撤仅{dd:.0%})，周期顶部警惕')
        else:
            high = 5.0

        # --- 同向/背离（±30）---
        if expanding and dd >= 0.30:
            align = self.ALIGN_MAX
            reasons.append('黄金坑：盈利拐点向上+股价深跌，同向加分')
        elif (not expanding) and dd < 0.10:
            align = -self.ALIGN_MAX
            reasons.append('顶部陷阱：盈利收缩+股价新高，背离重扣分')
        else:
            align = 0.0

        total = max(0.0, min(100.0, self.BASE + qoq + high + align))
        return {
            'total': round(total, 2),
            'breakdown': {
                'base': self.BASE,
                'margin_qoq': round(qoq, 2),
                'from_52w_high': round(high, 2),
                'alignment': round(align, 2),
            },
            'reasons': reasons,
        }
