"""
策略组合器示例

演示如何使用策略组合器进行多策略信号融合。
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from quantsys.strategies.combiner import (
    StrategyCombiner,
    CombinerConfig,
    Signal,
    MultiStrategyCombiner
)
from datetime import datetime


def example_or_mode():
    """示例1: OR模式 - 任一策略发出信号即执行"""
    print("=" * 60)
    print("示例 1: OR模式")
    print("=" * 60)

    config = CombinerConfig(mode='or')
    combiner = StrategyCombiner(config)

    # 创建多个策略的信号
    signals = [
        Signal(
            timestamp=datetime.now(),
            symbol='600036.SH',
            action='buy',
            price=50.0,
            quantity=1000,
            strategy_id='ma_cross',
            confidence=0.8
        ),
        Signal(
            timestamp=datetime.now(),
            symbol='600036.SH',
            action='sell',
            price=50.0,
            quantity=500,
            strategy_id='rsi_reversal',
            confidence=0.6
        )
    ]

    # 组合信号
    combined, metadata = combiner.combine_signals(signals)

    print(f"\n输入信号: {len(signals)}个")
    for s in signals:
        print(f"  - {s.strategy_id}: {s.action} (置信度: {s.confidence})")

    print(f"\n组合结果: {len(combined)}个信号")
    print(f"元数据: {metadata}")
    print(f"\nOR模式说明: 保留所有信号，不做过滤")


def example_and_mode():
    """示例2: AND模式 - 所有策略必须一致"""
    print("\n" + "=" * 60)
    print("示例 2: AND模式")
    print("=" * 60)

    config = CombinerConfig(
        mode='and',
        min_agree_count=2
    )
    combiner = StrategyCombiner(config)

    # 场景1: 所有策略一致
    print("\n场景1: 所有策略一致 (买入)")
    signals_agree = [
        Signal(datetime.now(), '600036.SH', 'buy', 50.0, 1000, 'ma_cross', confidence=0.8),
        Signal(datetime.now(), '600036.SH', 'buy', 50.0, 1000, 'rsi_reversal', confidence=0.7),
        Signal(datetime.now(), '600036.SH', 'buy', 50.0, 1000, 'bollinger', confidence=0.6)
    ]

    combined, metadata = combiner.combine_signals(signals_agree)
    print(f"  输入: 3个买入信号")
    print(f"  结果: {len(combined)}个信号 - {metadata['reason']}")

    # 场景2: 策略冲突
    print("\n场景2: 策略冲突")
    signals_conflict = [
        Signal(datetime.now(), '600036.SH', 'buy', 50.0, 1000, 'ma_cross', confidence=0.8),
        Signal(datetime.now(), '600036.SH', 'sell', 50.0, 1000, 'rsi_reversal', confidence=0.7)
    ]

    combined, metadata = combiner.combine_signals(signals_conflict)
    print(f"  输入: 1个买入 + 1个卖出")
    print(f"  结果: {len(combined)}个信号 - {metadata['reason']}")
    print(f"\nAND模式说明: 只有所有策略方向一致时才执行")


def example_vote_mode():
    """示例3: VOTE模式 - 加权投票"""
    print("\n" + "=" * 60)
    print("示例 3: VOTE模式 (加权投票)")
    print("=" * 60)

    # 设置策略权重
    config = CombinerConfig(
        mode='vote',
        weights={
            'ma_cross': 1.5,      # 均线策略权重1.5
            'rsi_reversal': 1.0,  # RSI策略权重1.0
            'bollinger': 0.8      # 布林带策略权重0.8
        },
        use_confidence_weighting=True  # 使用置信度加权
    )
    combiner = StrategyCombiner(config)

    # 场景1: 买入信号占优
    print("\n场景1: 买入信号占优")
    signals = [
        Signal(datetime.now(), '600036.SH', 'buy', 50.0, 1000, 'ma_cross', confidence=0.8),
        Signal(datetime.now(), '600036.SH', 'buy', 50.0, 1000, 'rsi_reversal', confidence=0.7),
        Signal(datetime.now(), '600036.SH', 'sell', 50.0, 500, 'bollinger', confidence=0.5)
    ]

    combined, metadata = combiner.combine_signals(signals)

    print(f"  输入信号:")
    for s in signals:
        weight = config.weights.get(s.strategy_id, 1.0)
        score = weight * s.confidence
        print(f"    - {s.strategy_id}: {s.action} (权重:{weight}, 置信度:{s.confidence}, 得分:{score:.2f})")

    print(f"\n  投票结果:")
    print(f"    买入得分: {metadata['buy_score']}")
    print(f"    卖出得分: {metadata['sell_score']}")
    print(f"    胜出方向: {metadata['winner']}")
    print(f"    保留信号: {len(combined)}个")

    # 场景2: 平局处理
    print("\n场景2: 平局处理")
    signals_tie = [
        Signal(datetime.now(), '600036.SH', 'buy', 50.0, 1000, 'ma_cross', confidence=0.6),
        Signal(datetime.now(), '600036.SH', 'sell', 50.0, 1000, 'rsi_reversal', confidence=0.6)
    ]

    combined, metadata = combiner.combine_signals(signals_tie)
    print(f"  买入得分: {metadata.get('buy_score', 0)}")
    print(f"  卖出得分: {metadata.get('sell_score', 0)}")
    print(f"  结果: {metadata['reason']}")
    print(f"\nVOTE模式说明: 根据权重和置信度计算得分，选择得分高的方向")


def example_confidence_threshold():
    """示例4: 置信度阈值过滤"""
    print("\n" + "=" * 60)
    print("示例 4: 置信度阈值过滤")
    print("=" * 60)

    config = CombinerConfig(
        mode='vote',
        confidence_threshold=0.6  # 只保留置信度>=0.6的信号
    )
    combiner = StrategyCombiner(config)

    signals = [
        Signal(datetime.now(), '600036.SH', 'buy', 50.0, 1000, 'ma_cross', confidence=0.8),
        Signal(datetime.now(), '600036.SH', 'buy', 50.0, 1000, 'rsi_reversal', confidence=0.5),  # 低置信度
        Signal(datetime.now(), '600036.SH', 'sell', 50.0, 500, 'bollinger', confidence=0.4)  # 低置信度
    ]

    print(f"\n输入信号:")
    for s in signals:
        status = "✅" if s.confidence >= 0.6 else "❌"
        print(f"  {status} {s.strategy_id}: {s.action} (置信度: {s.confidence})")

    combined, metadata = combiner.combine_signals(signals)

    print(f"\n过滤后: {len(combined)}个信号")
    if combined:
        print(f"保留的信号:")
        for s in combined:
            print(f"  - {s.strategy_id}: {s.action} (置信度: {s.confidence})")


def example_create_combined_signal():
    """示例5: 创建组合信号"""
    print("\n" + "=" * 60)
    print("示例 5: 创建组合信号")
    print("=" * 60)

    config = CombinerConfig(mode='vote', weights={'ma_cross': 1.5, 'rsi': 1.0})
    combiner = StrategyCombiner(config)

    signals = [
        Signal(datetime.now(), '600036.SH', 'buy', 50.0, 1000, 'ma_cross', 'MA金叉', 0.8),
        Signal(datetime.now(), '600036.SH', 'buy', 50.0, 800, 'rsi', 'RSI超卖', 0.7)
    ]

    combined_signals, metadata = combiner.combine_signals(signals)

    # 创建单一组合信号
    combined_signal = combiner.create_combined_signal(combined_signals, metadata)

    print(f"\n原始信号: {len(signals)}个")
    for s in signals:
        print(f"  - {s.strategy_id}: {s.action} {s.quantity}股 (置信度:{s.confidence})")

    print(f"\n组合信号:")
    print(f"  策略ID: {combined_signal.strategy_id}")
    print(f"  动作: {combined_signal.action}")
    print(f"  数量: {combined_signal.quantity}股")
    print(f"  平均置信度: {combined_signal.confidence:.2f}")
    print(f"  原因: {combined_signal.reason}")
    print(f"  元数据: {combined_signal.metadata}")


def example_multi_strategy_combiner():
    """示例6: 高级多策略组合器"""
    print("\n" + "=" * 60)
    print("示例 6: 高级多策略组合器 (策略分组)")
    print("=" * 60)

    multi_combiner = MultiStrategyCombiner()

    # 定义策略分组
    multi_combiner.add_strategy_group('trend_following', ['ma_cross', 'macd'])
    multi_combiner.add_strategy_group('mean_reversion', ['rsi_reversal', 'bollinger'])

    # 创建信号
    signals = [
        Signal(datetime.now(), '600036.SH', 'buy', 50.0, 1000, 'ma_cross', confidence=0.8),
        Signal(datetime.now(), '600036.SH', 'buy', 50.0, 1000, 'macd', confidence=0.7),
        Signal(datetime.now(), '600036.SH', 'sell', 50.0, 500, 'rsi_reversal', confidence=0.6),
        Signal(datetime.now(), '600036.SH', 'sell', 50.0, 500, 'bollinger', confidence=0.5)
    ]

    print(f"\n策略分组:")
    print(f"  趋势跟踪组: {multi_combiner.strategy_groups['trend_following']}")
    print(f"  均值回归组: {multi_combiner.strategy_groups['mean_reversion']}")

    # 按组组合
    config = CombinerConfig(mode='vote')
    combiner = StrategyCombiner(config)

    print(f"\n趋势跟踪组信号:")
    trend_signals, trend_meta = multi_combiner.combine_by_group(
        signals, 'trend_following', combiner
    )
    print(f"  结果: {len(trend_signals)}个信号")
    print(f"  元数据: {trend_meta}")

    print(f"\n均值回归组信号:")
    reversion_signals, reversion_meta = multi_combiner.combine_by_group(
        signals, 'mean_reversion', combiner
    )
    print(f"  结果: {len(reversion_signals)}个信号")
    print(f"  元数据: {reversion_meta}")


def example_statistics():
    """示例7: 统计信息"""
    print("\n" + "=" * 60)
    print("示例 7: 组合统计")
    print("=" * 60)

    config = CombinerConfig(mode='vote', weights={'s1': 1.5, 's2': 1.0})
    combiner = StrategyCombiner(config)

    # 模拟多次组合
    for i in range(10):
        signals = [
            Signal(datetime.now(), '600036.SH', 'buy', 50.0, 1000, 's1', confidence=0.6),
            Signal(datetime.now(), '600036.SH', 'sell', 50.0, 1000, 's2', confidence=0.6)
        ]
        combiner.combine_signals(signals)

    # 获取统计
    stats = combiner.get_statistics()

    print(f"\n组合统计:")
    print(f"  总组合次数: {stats['total_combinations']}")
    print(f"  按模式统计: {stats['combinations_by_mode']}")
    print(f"  平局次数: {stats['tie_count']}")
    print(f"  冲突次数: {stats['conflict_count']}")
    print(f"  平局率: {stats['tie_rate']:.2%}")
    print(f"  冲突率: {stats['conflict_rate']:.2%}")


if __name__ == '__main__':
    # 运行所有示例
    example_or_mode()
    example_and_mode()
    example_vote_mode()
    example_confidence_threshold()
    example_create_combined_signal()
    example_multi_strategy_combiner()
    example_statistics()

    print("\n" + "=" * 60)
    print("所有示例运行完成！")
    print("=" * 60)
