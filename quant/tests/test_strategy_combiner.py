"""
策略组合器单元测试
"""

import unittest
from datetime import datetime
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from quantsys.strategies.combiner import (
    StrategyCombiner,
    CombinerConfig,
    Signal,
    MultiStrategyCombiner
)


class TestStrategyCombiner(unittest.TestCase):
    """策略组合器测试"""

    def setUp(self):
        """测试前准备"""
        self.timestamp = datetime.now()
        self.symbol = '600036.SH'
        self.price = 50.0

    def test_or_mode(self):
        """测试OR模式"""
        config = CombinerConfig(mode='or')
        combiner = StrategyCombiner(config)

        signals = [
            Signal(self.timestamp, self.symbol, 'buy', self.price, 1000, 's1', confidence=0.8),
            Signal(self.timestamp, self.symbol, 'sell', self.price, 500, 's2', confidence=0.6)
        ]

        combined, metadata = combiner.combine_signals(signals)

        # OR模式应该保留所有信号
        self.assertEqual(len(combined), 2)
        self.assertEqual(metadata['mode'], 'or')
        self.assertEqual(metadata['kept_signals'], 2)

    def test_and_mode_agree(self):
        """测试AND模式 - 所有策略一致"""
        config = CombinerConfig(mode='and', min_agree_count=2)
        combiner = StrategyCombiner(config)

        signals = [
            Signal(self.timestamp, self.symbol, 'buy', self.price, 1000, 's1', confidence=0.8),
            Signal(self.timestamp, self.symbol, 'buy', self.price, 1000, 's2', confidence=0.7)
        ]

        combined, metadata = combiner.combine_signals(signals)

        # 所有策略一致，应该保留
        self.assertEqual(len(combined), 2)
        self.assertEqual(metadata['agreed_action'], 'buy')

    def test_and_mode_conflict(self):
        """测试AND模式 - 策略冲突"""
        config = CombinerConfig(mode='and')
        combiner = StrategyCombiner(config)

        signals = [
            Signal(self.timestamp, self.symbol, 'buy', self.price, 1000, 's1', confidence=0.8),
            Signal(self.timestamp, self.symbol, 'sell', self.price, 500, 's2', confidence=0.6)
        ]

        combined, metadata = combiner.combine_signals(signals)

        # 策略冲突，应该返回空
        self.assertEqual(len(combined), 0)
        self.assertEqual(metadata['reason'], 'direction_conflict')

    def test_vote_mode_buy_wins(self):
        """测试VOTE模式 - 买入胜出"""
        config = CombinerConfig(
            mode='vote',
            weights={'s1': 1.5, 's2': 1.0, 's3': 0.8}
        )
        combiner = StrategyCombiner(config)

        signals = [
            Signal(self.timestamp, self.symbol, 'buy', self.price, 1000, 's1', confidence=0.8),
            Signal(self.timestamp, self.symbol, 'buy', self.price, 1000, 's2', confidence=0.7),
            Signal(self.timestamp, self.symbol, 'sell', self.price, 500, 's3', confidence=0.5)
        ]

        combined, metadata = combiner.combine_signals(signals)

        # 买入得分更高，应该保留买入信号
        self.assertEqual(len(combined), 2)
        self.assertEqual(metadata['winner'], 'buy')
        self.assertGreater(metadata['buy_score'], metadata['sell_score'])

    def test_vote_mode_tie(self):
        """测试VOTE模式 - 平局"""
        config = CombinerConfig(
            mode='vote',
            tie_policy='skip'
        )
        combiner = StrategyCombiner(config)

        signals = [
            Signal(self.timestamp, self.symbol, 'buy', self.price, 1000, 's1', confidence=0.6),
            Signal(self.timestamp, self.symbol, 'sell', self.price, 1000, 's2', confidence=0.6)
        ]

        combined, metadata = combiner.combine_signals(signals)

        # 平局且策略为skip，应该返回空
        self.assertEqual(len(combined), 0)
        self.assertEqual(metadata['reason'], 'tie_skip')

    def test_confidence_threshold(self):
        """测试置信度阈值"""
        config = CombinerConfig(
            mode='vote',
            confidence_threshold=0.6
        )
        combiner = StrategyCombiner(config)

        signals = [
            Signal(self.timestamp, self.symbol, 'buy', self.price, 1000, 's1', confidence=0.8),
            Signal(self.timestamp, self.symbol, 'buy', self.price, 1000, 's2', confidence=0.5),  # 低于阈值
            Signal(self.timestamp, self.symbol, 'sell', self.price, 500, 's3', confidence=0.4)   # 低于阈值
        ]

        combined, metadata = combiner.combine_signals(signals)

        # 只有s1的信号应该被保留
        self.assertEqual(len(combined), 1)
        self.assertEqual(combined[0].strategy_id, 's1')

    def test_create_combined_signal(self):
        """测试创建组合信号"""
        config = CombinerConfig(mode='vote')
        combiner = StrategyCombiner(config)

        signals = [
            Signal(self.timestamp, self.symbol, 'buy', self.price, 1000, 's1', 'reason1', 0.8),
            Signal(self.timestamp, self.symbol, 'buy', self.price, 800, 's2', 'reason2', 0.7)
        ]

        combined_signal = combiner.create_combined_signal(signals, {'mode': 'vote'})

        self.assertIsNotNone(combined_signal)
        self.assertEqual(combined_signal.strategy_id, 'combined')
        self.assertEqual(combined_signal.action, 'buy')
        self.assertEqual(combined_signal.quantity, 1800)  # 总和
        self.assertEqual(combined_signal.confidence, 0.75)  # 平均

    def test_statistics(self):
        """测试统计功能"""
        config = CombinerConfig(mode='vote')
        combiner = StrategyCombiner(config)

        # 执行多次组合
        for _ in range(5):
            signals = [
                Signal(self.timestamp, self.symbol, 'buy', self.price, 1000, 's1', confidence=0.8)
            ]
            combiner.combine_signals(signals)

        stats = combiner.get_statistics()

        self.assertEqual(stats['total_combinations'], 5)
        self.assertIn('vote', stats['combinations_by_mode'])

    def test_empty_signals(self):
        """测试空信号列表"""
        config = CombinerConfig(mode='vote')
        combiner = StrategyCombiner(config)

        combined, metadata = combiner.combine_signals([])

        self.assertEqual(len(combined), 0)
        self.assertEqual(metadata['reason'], 'no_signals')


class TestMultiStrategyCombiner(unittest.TestCase):
    """高级多策略组合器测试"""

    def setUp(self):
        """测试前准备"""
        self.multi_combiner = MultiStrategyCombiner()
        self.timestamp = datetime.now()
        self.symbol = '600036.SH'
        self.price = 50.0

    def test_add_strategy_group(self):
        """测试添加策略分组"""
        self.multi_combiner.add_strategy_group('trend', ['ma', 'macd'])

        self.assertIn('trend', self.multi_combiner.strategy_groups)
        self.assertEqual(self.multi_combiner.strategy_groups['trend'], ['ma', 'macd'])

    def test_combine_by_group(self):
        """测试按分组组合"""
        self.multi_combiner.add_strategy_group('trend', ['s1', 's2'])

        signals = [
            Signal(self.timestamp, self.symbol, 'buy', self.price, 1000, 's1', confidence=0.8),
            Signal(self.timestamp, self.symbol, 'buy', self.price, 1000, 's2', confidence=0.7),
            Signal(self.timestamp, self.symbol, 'sell', self.price, 500, 's3', confidence=0.6)
        ]

        config = CombinerConfig(mode='vote')
        combiner = StrategyCombiner(config)

        combined, metadata = self.multi_combiner.combine_by_group(signals, 'trend', combiner)

        # 只应该包含s1和s2的信号
        self.assertEqual(len(combined), 2)
        self.assertTrue(all(s.strategy_id in ['s1', 's2'] for s in combined))

    def test_update_strategy_performance(self):
        """测试更新策略表现"""
        # 记录正确的信号
        self.multi_combiner.update_strategy_performance('s1', True)
        self.multi_combiner.update_strategy_performance('s1', True)
        self.multi_combiner.update_strategy_performance('s1', False)

        tracker = self.multi_combiner.performance_tracker['s1']

        self.assertEqual(tracker['total_signals'], 3)
        self.assertEqual(tracker['correct_signals'], 2)
        self.assertAlmostEqual(tracker['accuracy'], 2/3)

    def test_get_dynamic_weight(self):
        """测试动态权重"""
        # 高准确率策略
        self.multi_combiner.update_strategy_performance('s1', True)
        self.multi_combiner.update_strategy_performance('s1', True)

        # 低准确率策略
        self.multi_combiner.update_strategy_performance('s2', False)
        self.multi_combiner.update_strategy_performance('s2', False)

        weight_s1 = self.multi_combiner.get_dynamic_weight('s1', base_weight=1.0)
        weight_s2 = self.multi_combiner.get_dynamic_weight('s2', base_weight=1.0)

        # 高准确率策略权重应该更高
        self.assertGreater(weight_s1, weight_s2)


class TestCombinerConfig(unittest.TestCase):
    """组合器配置测试"""

    def test_default_config(self):
        """测试默认配置"""
        config = CombinerConfig()

        self.assertEqual(config.mode, 'vote')
        self.assertEqual(config.tie_policy, 'skip')
        self.assertEqual(config.min_agree_count, 1)

    def test_invalid_mode(self):
        """测试无效模式"""
        with self.assertRaises(ValueError):
            CombinerConfig(mode='invalid')

    def test_invalid_tie_policy(self):
        """测试无效平局策略"""
        with self.assertRaises(ValueError):
            CombinerConfig(tie_policy='invalid')


if __name__ == '__main__':
    unittest.main()
