"""
测试市场环境识别器和策略表现统计系统

验证：
1. 市场环境识别功能
2. 策略适用性评估
3. 执行建议生成
4. 完整的工具输出格式
"""
import sys
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from application.services.market_regime_detector import MarketRegimeDetector
from application.services.strategy_performance_stats import StrategyPerformanceStats


def test_market_regime_detector():
    """测试市场环境识别器"""
    print("=" * 60)
    print("测试 1: 市场环境识别器")
    print("=" * 60)

    detector = MarketRegimeDetector()

    # 测试默认环境识别（无数据）
    regime_info = detector.detect_current_regime()

    print(f"\n市场环境: {regime_info['regime']} ({regime_info['characteristics']['name']})")
    print(f"置信度: {regime_info['confidence']:.2f}")
    print(f"描述: {regime_info['characteristics']['description']}")
    print(f"\n推荐策略: {', '.join(regime_info['characteristics']['recommended_strategies'])}")
    print(f"避免策略: {', '.join(regime_info['characteristics']['avoid_strategies'])}")
    print(f"风险等级: {regime_info['characteristics']['risk_level']}")
    print(f"建议仓位: {regime_info['characteristics']['position_sizing']}")

    # 测试策略适用性
    print("\n" + "-" * 60)
    print("测试策略适用性评估:")

    test_strategies = ['ma_cross', 'rsi_reversal', 'turtle']
    for strategy in test_strategies:
        suitability = detector.get_strategy_suitability(strategy, regime_info['regime'])
        print(f"\n  {strategy}:")
        print(f"    适用性: {suitability['suitability']}")
        print(f"    原因: {suitability['reason']}")
        print(f"    建议: {suitability['recommendation']}")


def test_strategy_performance_stats():
    """测试策略表现统计"""
    print("\n\n" + "=" * 60)
    print("测试 2: 策略表现统计系统")
    print("=" * 60)

    stats_service = StrategyPerformanceStats()

    # 测试不同市场环境下的策略统计
    test_cases = [
        ('ma_cross', 'bull'),
        ('ma_cross', 'sideways'),
        ('rsi_reversal', 'sideways'),
        ('turtle', 'bull'),
    ]

    for strategy, regime in test_cases:
        print(f"\n{'-' * 60}")
        print(f"策略: {strategy} | 市场环境: {regime}")
        print(f"{'-' * 60}")

        # 获取统计数据
        stats = stats_service.get_strategy_stats(strategy, regime)
        print(f"\n历史表现:")
        print(f"  胜率: {stats.get('win_rate', 0):.1%}")
        print(f"  平均收益: {stats.get('avg_return', stats.get('avg_profit', 0)):.1%}")
        print(f"  夏普比率: {stats.get('sharpe_ratio', 0):.2f}")
        print(f"  最大回撤: {stats.get('max_drawdown', 0):.1%}")
        if stats.get('note'):
            print(f"  备注: {stats['note']}")

        # 评估适用性
        suitability = stats_service.evaluate_strategy_suitability(strategy, regime)
        print(f"\n适用性评估:")
        print(f"  等级: {suitability['suitability']} (评分: {suitability['score']:.2f})")
        print(f"  建议: {suitability['recommendation']}")
        print(f"  原因: {', '.join(suitability['reasons'])}")
        if suitability['risk_warnings']:
            print(f"  风险警告: {', '.join(suitability['risk_warnings'])}")

        # 获取执行建议
        exec_rec = stats_service.get_execution_recommendations(
            strategy, regime, suitability['suitability']
        )
        print(f"\n执行建议:")
        print(f"  建议仓位: {exec_rec['position_size']}")
        print(f"  止损位: {exec_rec['stop_loss']:.1%}")
        print(f"  止盈位: {exec_rec['take_profit']:.1%}")
        print(f"  风险回报比: 1:{exec_rec['risk_reward_ratio']:.2f}")
        print(f"  持有周期: {exec_rec['holding_period']}")
        print(f"  执行条件: {exec_rec['conditions'][0]}, {exec_rec['conditions'][1]}")


def test_integrated_tool_output():
    """测试完整的工具输出格式"""
    print("\n\n" + "=" * 60)
    print("测试 3: 完整工具输出示例")
    print("=" * 60)

    # 模拟 strategy_execute 工具的优化后输出
    detector = MarketRegimeDetector()
    stats_service = StrategyPerformanceStats()

    # 1. 识别市场环境
    market_info = detector.detect_current_regime()

    # 2. 获取策略统计
    strategy_name = 'ma_cross'
    regime = market_info['regime']
    strategy_stats = stats_service.get_strategy_stats(strategy_name, regime)

    # 3. 评估适用性
    suitability = stats_service.evaluate_strategy_suitability(strategy_name, regime)

    # 4. 执行建议
    exec_rec = stats_service.get_execution_recommendations(
        strategy_name, regime, suitability['suitability']
    )

    # 构建完整输出
    enhanced_output = {
        'signal': 'buy',  # 原始信号
        'entry_price': 1850.0,
        'stop_loss': 1850 * (1 + exec_rec['stop_loss']),
        'target_price': 1850 * (1 + exec_rec['take_profit']),

        # 新增：策略统计信息
        'strategy_stats': {
            'name': strategy_name,
            'historical_win_rate': strategy_stats.get('win_rate', 0),
            'avg_return': strategy_stats.get('avg_return', strategy_stats.get('avg_profit', 0)),
            'sharpe_ratio': strategy_stats.get('sharpe_ratio', 0),
            'max_drawdown': strategy_stats.get('max_drawdown', 0),
            'data_period': strategy_stats.get('data_period', '2020-2024'),
        },

        # 新增：市场环境
        'market_context': {
            'regime': market_info['regime'],
            'regime_name': market_info['characteristics']['name'],
            'confidence': market_info['confidence'],
            'suitability': suitability['suitability'],
        },

        # 新增：风险提示
        'warnings': suitability['risk_warnings'],

        # 新增：执行建议
        'execution_tips': {
            'position_size': exec_rec['position_size'],
            'holding_period': exec_rec['holding_period'],
            'risk_reward': f"1:{exec_rec['risk_reward_ratio']:.1f}",
            'conditions': exec_rec['conditions'][:3],
        },

        # 新增：推荐等级
        'recommendation': suitability['recommendation'],  # 'use', 'caution', 'avoid'
    }

    print("\n优化后的 strategy_execute 输出:\n")
    import json
    print(json.dumps(enhanced_output, indent=2, ensure_ascii=False))

    # 生成用户友好的文本总结
    print("\n" + "=" * 60)
    print("用户友好总结:")
    print("=" * 60)

    print(f"\n📊 信号: {enhanced_output['signal'].upper()}")
    print(f"💰 入场价: ¥{enhanced_output['entry_price']:.2f}")
    print(f"🛑 止损位: ¥{enhanced_output['stop_loss']:.2f} ({exec_rec['stop_loss']:.1%})")
    print(f"🎯 目标价: ¥{enhanced_output['target_price']:.2f} (+{exec_rec['take_profit']:.1%})")

    print(f"\n📈 策略表现 ({strategy_stats.get('data_period', '2020-2024')})")
    print(f"   胜率: {strategy_stats.get('win_rate', 0):.1%}")
    print(f"   平均收益: {strategy_stats.get('avg_return', 0):.1%}")
    print(f"   夏普比率: {strategy_stats.get('sharpe_ratio', 0):.2f}")

    print(f"\n🌍 市场环境: {market_info['characteristics']['name']} (置信度: {market_info['confidence']:.0%})")
    print(f"   适用性: {suitability['suitability'].upper()}")
    print(f"   建议: {suitability['recommendation'].upper()}")

    if suitability['risk_warnings']:
        print(f"\n⚠️  风险警告:")
        for warning in suitability['risk_warnings']:
            print(f"   • {warning}")

    print(f"\n💡 执行建议:")
    print(f"   • 建议仓位: {exec_rec['position_size']}")
    print(f"   • 持有周期: {exec_rec['holding_period']}")
    print(f"   • 风险回报比: 1:{exec_rec['risk_reward_ratio']:.1f}")
    print(f"   • 执行条件:")
    for condition in exec_rec['conditions'][:3]:
        print(f"     - {condition}")


if __name__ == '__main__':
    try:
        test_market_regime_detector()
        test_strategy_performance_stats()
        test_integrated_tool_output()

        print("\n\n" + "=" * 60)
        print("✅ 所有测试完成！优化系统运行正常")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
