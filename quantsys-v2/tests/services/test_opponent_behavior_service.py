"""
测试对手行为分析服务
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv()

# 初始化数据库引擎
from infrastructure.persistence.database.engine import init_engine
init_engine()

from application.services.opponent_behavior_service import OpponentBehaviorService


def test_opponent_behavior_service():
    """测试对手行为分析服务"""
    print("=" * 60)
    print("测试对手行为分析服务")
    print("=" * 60)

    service = OpponentBehaviorService()
    result = service.analyze_current_behavior()

    print("\n📊 分析结果：")
    print("-" * 60)

    # 散户行为
    retail = result['retail']
    print(f"\n💰 散户行为:")
    print(f"   行为模式: {retail['behavior']}")
    print(f"   净流入: {retail['net_flow']/100000000:.2f} 亿元")
    print(f"   情绪指数: {retail['emotion_index']:.1f}/100")
    print(f"   描述: {retail['description']}")
    if retail['common_mistakes']:
        print(f"   常见错误: {', '.join(retail['common_mistakes'])}")

    # 机构行为
    institution = result['institution']
    print(f"\n🏛️  机构行为:")
    print(f"   行为模式: {institution['behavior']}")
    print(f"   净流入: {institution['net_flow']/100000000:.2f} 亿元")
    print(f"   仓位变化: {institution['position_change']}")
    print(f"   目标板块: {', '.join(institution['target_sectors'])}")
    print(f"   描述: {institution['description']}")

    # 游资行为
    hot_money = result['hot_money']
    print(f"\n🔥 游资行为:")
    print(f"   行为模式: {hot_money['behavior']}")
    print(f"   活跃度: {hot_money['activity_level']}")
    print(f"   描述: {hot_money['description']}")

    # 市场整体
    print(f"\n🌍 市场状态:")
    print(f"   市场阶段: {result['market_phase']}")
    print(f"   风险偏好: {result['risk_appetite']}")

    # 博弈机会
    opportunities = result['opportunity_map']
    if opportunities:
        print(f"\n🎯 博弈机会 ({len(opportunities)}个):")
        for key, opps in opportunities.items():
            print(f"\n   {key}:")
            for opp in opps:
                if 'strategy' in opp:
                    print(f"   - 策略: {opp['strategy']}")
                    print(f"     置信度: {opp.get('confidence', 'N/A')}")
                    print(f"     预期收益: {opp.get('expected_return', 'N/A')}")
                    print(f"     原因: {opp['reason']}")
                    print(f"     行动: {opp['action']}")
                else:
                    print(f"   - 风险: {opp.get('risk', 'N/A')}")
                    print(f"     原因: {opp['reason']}")
                    print(f"     行动: {opp['action']}")
    else:
        print(f"\n🎯 博弈机会: 暂无明显机会")

    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)

    return result


if __name__ == '__main__':
    try:
        result = test_opponent_behavior_service()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
