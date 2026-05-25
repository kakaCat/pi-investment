"""
策略组合器 - Strategy Combiner

实现多策略信号融合，支持多种组合模式。

组合模式:
1. OR模式 - 任一策略发出信号即执行
2. AND模式 - 所有策略必须一致才执行
3. VOTE模式 - 加权投票，得分高的方向执行

使用示例:
    combiner = StrategyCombiner(mode='vote', weights={'ma_cross': 1.5, 'rsi': 1.0})

    # 组合多个策略的信号
    combined_signals = combiner.combine_signals([
        Signal(action='buy', strategy_id='ma_cross', confidence=0.8),
        Signal(action='buy', strategy_id='rsi', confidence=0.6),
        Signal(action='sell', strategy_id='bollinger', confidence=0.5)
    ])
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    """交易信号"""
    timestamp: datetime
    symbol: str
    action: str  # 'buy', 'sell', 'hold'
    price: float
    quantity: int = 0
    strategy_id: str = ''
    reason: str = ''
    confidence: float = 0.0  # 0.0-1.0
    metadata: Dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class CombinerConfig:
    """组合器配置"""
    mode: str = 'vote'  # 'or', 'and', 'vote'
    weights: Dict[str, float] = None  # 策略权重
    min_agree_count: int = 1  # 最小同意数量
    tie_policy: str = 'skip'  # 平局处理: 'skip', 'buy', 'sell'
    confidence_threshold: float = 0.0  # 最小置信度阈值
    require_all_strategies: bool = False  # AND模式是否要求所有策略
    use_confidence_weighting: bool = True  # 是否使用置信度加权

    def __post_init__(self):
        if self.weights is None:
            self.weights = {}

        # 验证模式
        if self.mode not in ['or', 'and', 'vote']:
            raise ValueError(f"Invalid mode: {self.mode}. Must be 'or', 'and', or 'vote'")

        # 验证平局策略
        if self.tie_policy not in ['skip', 'buy', 'sell']:
            raise ValueError(f"Invalid tie_policy: {self.tie_policy}")


class StrategyCombiner:
    """
    策略组合器

    将多个策略的信号组合成最终决策。
    """

    def __init__(self, config: Optional[CombinerConfig] = None):
        """
        初始化策略组合器

        Args:
            config: 组合器配置，如果为None则使用默认配置
        """
        self.config = config or CombinerConfig()

        # 统计数据
        self.total_combinations = 0
        self.combinations_by_mode = defaultdict(int)
        self.tie_count = 0
        self.conflict_count = 0

    def combine_signals(
        self,
        signals: List[Signal],
        strategy_ids: Optional[List[str]] = None
    ) -> Tuple[List[Signal], Dict]:
        """
        组合多个策略的信号

        Args:
            signals: 信号列表
            strategy_ids: 期望的策略ID列表（用于AND模式）

        Returns:
            (combined_signals, metadata)
            - combined_signals: 组合后的信号列表
            - metadata: 组合元数据（包含决策过程信息）
        """
        if not signals:
            return [], {'reason': 'no_signals', 'mode': self.config.mode}

        self.total_combinations += 1
        self.combinations_by_mode[self.config.mode] += 1

        # 过滤低置信度信号
        if self.config.confidence_threshold > 0:
            signals = [s for s in signals if s.confidence >= self.config.confidence_threshold]
            if not signals:
                return [], {'reason': 'below_confidence_threshold', 'mode': self.config.mode}

        # 根据模式组合
        if self.config.mode == 'or':
            return self._or_combine(signals)
        elif self.config.mode == 'and':
            return self._and_combine(signals, strategy_ids)
        elif self.config.mode == 'vote':
            return self._vote_combine(signals)
        else:
            raise ValueError(f"Unknown mode: {self.config.mode}")

    def _or_combine(self, signals: List[Signal]) -> Tuple[List[Signal], Dict]:
        """
        OR模式：任一策略发出信号即执行

        返回所有信号，不做过滤。
        """
        metadata = {
            'mode': 'or',
            'total_signals': len(signals),
            'kept_signals': len(signals),
            'reason': 'or_mode_keep_all'
        }

        return signals, metadata

    def _and_combine(
        self,
        signals: List[Signal],
        strategy_ids: Optional[List[str]] = None
    ) -> Tuple[List[Signal], Dict]:
        """
        AND模式：所有策略必须一致才执行

        检查所有策略是否发出相同方向的信号。
        """
        if not signals:
            return [], {'mode': 'and', 'reason': 'no_signals'}

        # 按策略ID分组
        signals_by_strategy = {}
        for signal in signals:
            if signal.strategy_id:
                signals_by_strategy[signal.strategy_id] = signal

        # 如果指定了期望的策略列表，检查是否都有信号
        if strategy_ids:
            if self.config.require_all_strategies:
                missing = set(strategy_ids) - set(signals_by_strategy.keys())
                if missing:
                    return [], {
                        'mode': 'and',
                        'reason': 'missing_strategies',
                        'missing': list(missing)
                    }

        # 检查所有信号的方向是否一致
        actions = {s.action for s in signals}
        if len(actions) > 1:
            self.conflict_count += 1
            return [], {
                'mode': 'and',
                'reason': 'direction_conflict',
                'actions': list(actions)
            }

        # 检查是否满足最小同意数量
        if len(signals) < self.config.min_agree_count:
            return [], {
                'mode': 'and',
                'reason': 'below_min_agree',
                'count': len(signals),
                'required': self.config.min_agree_count
            }

        # 所有信号一致，返回
        agreed_action = list(actions)[0]
        metadata = {
            'mode': 'and',
            'agreed_action': agreed_action,
            'strategy_count': len(signals),
            'reason': 'all_agreed'
        }

        return signals, metadata

    def _vote_combine(self, signals: List[Signal]) -> Tuple[List[Signal], Dict]:
        """
        VOTE模式：加权投票

        根据策略权重和置信度计算得分，选择得分高的方向。
        """
        if not signals:
            return [], {'mode': 'vote', 'reason': 'no_signals'}

        # 计算买入和卖出的得分
        buy_score = 0.0
        sell_score = 0.0
        hold_score = 0.0

        buy_signals = []
        sell_signals = []
        hold_signals = []

        for signal in signals:
            # 获取策略权重
            weight = self.config.weights.get(signal.strategy_id, 1.0)

            # 是否使用置信度加权
            if self.config.use_confidence_weighting:
                score = weight * signal.confidence
            else:
                score = weight

            # 累加得分
            if signal.action == 'buy':
                buy_score += score
                buy_signals.append(signal)
            elif signal.action == 'sell':
                sell_score += score
                sell_signals.append(signal)
            elif signal.action == 'hold':
                hold_score += score
                hold_signals.append(signal)

        # 确定胜出方向
        winner = None
        winner_signals = []

        if buy_score > sell_score and buy_score > hold_score:
            winner = 'buy'
            winner_signals = buy_signals
        elif sell_score > buy_score and sell_score > hold_score:
            winner = 'sell'
            winner_signals = sell_signals
        elif hold_score > buy_score and hold_score > sell_score:
            winner = 'hold'
            winner_signals = hold_signals
        else:
            # 平局处理
            self.tie_count += 1

            if self.config.tie_policy == 'buy':
                winner = 'buy'
                winner_signals = buy_signals
            elif self.config.tie_policy == 'sell':
                winner = 'sell'
                winner_signals = sell_signals
            else:  # skip
                return [], {
                    'mode': 'vote',
                    'reason': 'tie_skip',
                    'buy_score': round(buy_score, 4),
                    'sell_score': round(sell_score, 4),
                    'hold_score': round(hold_score, 4)
                }

        metadata = {
            'mode': 'vote',
            'winner': winner,
            'buy_score': round(buy_score, 4),
            'sell_score': round(sell_score, 4),
            'hold_score': round(hold_score, 4),
            'kept_signals': len(winner_signals),
            'reason': 'vote_winner'
        }

        return winner_signals, metadata

    def create_combined_signal(
        self,
        signals: List[Signal],
        metadata: Dict
    ) -> Optional[Signal]:
        """
        创建组合后的单一信号

        将多个信号合并为一个代表性信号。
        """
        if not signals:
            return None

        # 使用第一个信号作为基础
        base_signal = signals[0]

        # 计算平均置信度
        avg_confidence = sum(s.confidence for s in signals) / len(signals)

        # 计算总数量（如果需要）
        total_quantity = sum(s.quantity for s in signals)

        # 合并原因
        reasons = [s.reason for s in signals if s.reason]
        combined_reason = '; '.join(reasons) if reasons else 'combined'

        # 创建新信号
        combined_signal = Signal(
            timestamp=base_signal.timestamp,
            symbol=base_signal.symbol,
            action=base_signal.action,
            price=base_signal.price,
            quantity=total_quantity,
            strategy_id='combined',
            reason=combined_reason,
            confidence=avg_confidence,
            metadata={
                'original_signals': len(signals),
                'combiner_mode': self.config.mode,
                'combiner_metadata': metadata
            }
        )

        return combined_signal

    def get_statistics(self) -> Dict:
        """获取组合统计"""
        return {
            'total_combinations': self.total_combinations,
            'combinations_by_mode': dict(self.combinations_by_mode),
            'tie_count': self.tie_count,
            'conflict_count': self.conflict_count,
            'tie_rate': self.tie_count / self.total_combinations if self.total_combinations > 0 else 0,
            'conflict_rate': self.conflict_count / self.total_combinations if self.total_combinations > 0 else 0
        }

    def reset_statistics(self):
        """重置统计"""
        self.total_combinations = 0
        self.combinations_by_mode.clear()
        self.tie_count = 0
        self.conflict_count = 0


class MultiStrategyCombiner:
    """
    多策略组合器（高级版）

    支持策略分组、动态权重调整等高级功能。
    """

    def __init__(self):
        self.strategy_groups: Dict[str, List[str]] = {}  # 策略分组
        self.dynamic_weights: Dict[str, float] = {}  # 动态权重
        self.performance_tracker: Dict[str, Dict] = defaultdict(lambda: {
            'total_signals': 0,
            'correct_signals': 0,
            'accuracy': 0.0
        })

    def add_strategy_group(self, group_name: str, strategy_ids: List[str]):
        """添加策略分组"""
        self.strategy_groups[group_name] = strategy_ids

    def update_strategy_performance(self, strategy_id: str, is_correct: bool):
        """更新策略表现（用于动态权重调整）"""
        tracker = self.performance_tracker[strategy_id]
        tracker['total_signals'] += 1

        if is_correct:
            tracker['correct_signals'] += 1

        tracker['accuracy'] = tracker['correct_signals'] / tracker['total_signals']

    def get_dynamic_weight(self, strategy_id: str, base_weight: float = 1.0) -> float:
        """
        获取动态权重

        根据策略历史表现调整权重。
        """
        if strategy_id not in self.performance_tracker:
            return base_weight

        accuracy = self.performance_tracker[strategy_id]['accuracy']

        # 简单的动态权重：准确率越高，权重越大
        # 准确率50%以下降权，50%以上加权
        if accuracy < 0.5:
            return base_weight * (accuracy / 0.5)  # 0-1倍
        else:
            return base_weight * (1 + (accuracy - 0.5))  # 1-1.5倍

    def combine_by_group(
        self,
        signals: List[Signal],
        group_name: str,
        combiner: StrategyCombiner
    ) -> Tuple[List[Signal], Dict]:
        """
        按分组组合信号

        只组合指定分组内的策略信号。
        """
        if group_name not in self.strategy_groups:
            return [], {'reason': 'group_not_found', 'group': group_name}

        group_strategy_ids = set(self.strategy_groups[group_name])

        # 过滤出分组内的信号
        group_signals = [s for s in signals if s.strategy_id in group_strategy_ids]

        if not group_signals:
            return [], {'reason': 'no_signals_in_group', 'group': group_name}

        # 使用组合器组合
        return combiner.combine_signals(group_signals, list(group_strategy_ids))
