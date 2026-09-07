"""
策略组合器

支持多种方式组合多个策略的信号:
- AND: 所有策略必须一致才输出信号
- OR: 任一策略有信号即输出
- majority: 多数投票决定
- weighted: 按权重聚合置信度
"""
from typing import Dict, List, Any, Optional

from domain.backtest.engine.strategy_base import StrategyBase


class StrategyCombiner:
    """
    策略组合器

    将多个策略的信号按指定模式合并为单一信号。
    """

    MODE_AND = 'and'
    MODE_OR = 'or'
    MODE_MAJORITY = 'majority'
    MODE_WEIGHTED = 'weighted'

    VALID_MODES = {MODE_AND, MODE_OR, MODE_MAJORITY, MODE_WEIGHTED}

    def __init__(self, mode: str = 'majority'):
        """
        初始化策略组合器

        Args:
            mode: 组合模式 ('and' | 'or' | 'majority' | 'weighted')
        """
        if mode not in self.VALID_MODES:
            raise ValueError(
                f"无效的组合模式: {mode}，支持: {', '.join(sorted(self.VALID_MODES))}"
            )
        self.mode = mode

    def combine(
        self,
        signals: List[Dict[str, Any]],
        weights: List[float] = None
    ) -> Dict[str, Any]:
        """
        合并多个信号

        Args:
            signals: 信号列表，每个元素为 generate_signal 的返回值
            weights: 各策略权重（用于 weighted 模式），与 signals 一一对应

        Returns:
            合并后的信号字典
        """
        if not signals:
            return {
                'action': 'hold',
                'confidence': 0.0,
                'reason': '无策略信号输入'
            }

        actions = [s['action'] for s in signals]
        confidences = [s['confidence'] for s in signals]
        reasons = [s.get('reason', '') for s in signals]

        if self.mode == self.MODE_AND:
            return self._combine_and(actions, confidences, reasons)

        elif self.mode == self.MODE_OR:
            return self._combine_or(actions, confidences, reasons)

        elif self.mode == self.MODE_MAJORITY:
            return self._combine_majority(actions, confidences, reasons)

        elif self.mode == self.MODE_WEIGHTED:
            if weights is None:
                weights = [1.0] * len(signals)
            return self._combine_weighted(actions, confidences, reasons, weights)

    def _combine_and(
        self,
        actions: List[str],
        confidences: List[float],
        reasons: List[str]
    ) -> Dict[str, Any]:
        """AND 模式：所有策略必须一致"""
        unique_actions = set(actions)
        if len(unique_actions) == 1:
            action = actions[0]
            avg_confidence = sum(confidences) / len(confidences)
            return {
                'action': action,
                'confidence': round(avg_confidence, 4),
                'reason': f'AND({len(actions)}策略一致): {"; ".join(reasons)}'
            }
        else:
            return {
                'action': 'hold',
                'confidence': 0.2,
                'reason': f'AND(策略分歧: {unique_actions}): {" | ".join(reasons)}'
            }

    def _combine_or(
        self,
        actions: List[str],
        confidences: List[float],
        reasons: List[str]
    ) -> Dict[str, Any]:
        """OR 模式：任一非 hold 信号即输出"""
        non_hold = [
            (a, c, r) for a, c, r in zip(actions, confidences, reasons)
            if a != 'hold'
        ]

        if non_hold:
            # 取非 hold 中置信度最高的
            best = max(non_hold, key=lambda x: x[1])
            return {
                'action': best[0],
                'confidence': round(best[1], 4),
                'reason': f'OR(触发策略): {best[2]}'
            }
        else:
            return {
                'action': 'hold',
                'confidence': 0.3,
                'reason': f'OR(无触发策略): {" | ".join(reasons)}'
            }

    def _combine_majority(
        self,
        actions: List[str],
        confidences: List[float],
        reasons: List[str]
    ) -> Dict[str, Any]:
        """多数投票模式"""
        from collections import Counter
        action_counts = Counter(actions)
        most_common = action_counts.most_common()

        # 找到得票最多的 action
        top_action, top_count = most_common[0]

        # 如果有平票，优先取非 hold
        if len(most_common) > 1 and most_common[1][1] == top_count:
            non_hold_top = [
                (a, c) for a, c in most_common if a != 'hold' and c == top_count
            ]
            if non_hold_top:
                top_action = non_hold_top[0][0]

        # 计算该 action 的平均置信度
        matching_confidences = [
            c for a, c in zip(actions, confidences) if a == top_action
        ]
        avg_confidence = sum(matching_confidences) / len(matching_confidences)

        matching_reasons = [
            r for a, r in zip(actions, reasons) if a == top_action
        ]

        total = len(actions)
        return {
            'action': top_action,
            'confidence': round(avg_confidence, 4),
            'reason': (
                f'多数投票({top_count}/{total}): '
                f'{"; ".join(matching_reasons)}'
            )
        }

    def _combine_weighted(
        self,
        actions: List[str],
        confidences: List[float],
        reasons: List[str],
        weights: List[float]
    ) -> Dict[str, Any]:
        """加权聚合模式"""
        total_weight = sum(weights)

        if total_weight == 0:
            return {
                'action': 'hold',
                'confidence': 0.0,
                'reason': '权重总和为0，无法计算结果'
            }

        # 按 action 分组加权得分
        action_scores: Dict[str, Dict[str, float]] = {
            'buy': {'score': 0.0, 'weight': 0.0},
            'sell': {'score': 0.0, 'weight': 0.0},
            'hold': {'score': 0.0, 'weight': 0.0},
        }

        for action, conf, weight in zip(actions, confidences, weights):
            action_scores[action]['score'] += conf * weight
            action_scores[action]['weight'] += weight

        best_action = 'hold'
        best_normalized = 0.0

        for action in ['buy', 'sell', 'hold']:
            if action_scores[action]['weight'] > 0:
                normalized = (
                    action_scores[action]['score'] / action_scores[action]['weight']
                )
                if normalized > best_normalized:
                    best_normalized = normalized
                    best_action = action

        return {
            'action': best_action,
            'confidence': round(best_normalized, 4),
            'reason': (
                f'加权聚合(权重={weights}): '
                f'buy={action_scores["buy"]["score"]:.2f}, '
                f'sell={action_scores["sell"]["score"]:.2f}, '
                f'hold={action_scores["hold"]["score"]:.2f}'
            )
        }
