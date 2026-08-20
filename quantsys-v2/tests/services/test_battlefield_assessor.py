"""
测试战场评估服务
"""
import sys
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent

from dotenv import load_dotenv
load_dotenv()

# 初始化数据库引擎
from infrastructure.persistence.database.engine import init_engine
init_engine()

from application.services.battlefield_assessor import BattlefieldAssessor


def test_battlefield_assessment():
    """测试战场评估服务"""
    print("=" * 60)
    print("测试战场评估服务")
    print("=" * 60)

    assessor = BattlefieldAssessor()

    # 假设池子ID为1（需要先确保数据库中有这个池子）
    pool_id = 1

    try:
        result = assessor.assess_pool(pool_id)

        print("\n📊 战场评估结果：")
        print("-" * 60)

        print(f"\n🎯 综合评分: {result['battlefield_score']:.1f}/100")

        print(f"\n🎭 对手强度:")
        strength = result['opponent_strength']
        print(f"   散户压力: {strength['retail_pressure']}")
        print(f"   机构兴趣: {strength['institution_interest']}")
        print(f"   游资风险: {strength['hot_money_risk']}")

        print(f"\n📍 博弈阶段: {result['game_phase']}")

        if result['advantages']:
            print(f"\n✅ 竞争优势:")
            for adv in result['advantages']:
                print(f"   - {adv}")

        if result['disadvantages']:
            print(f"\n⚠️  竞争劣势:")
            for dis in result['disadvantages']:
                print(f"   - {dis}")

        print(f"\n💡 操作建议: {result['recommendation']}")
        print(f"   紧急度: {result['urgency']}")
        print(f"   置信度: {result['confidence']:.2f}")

        print("\n" + "=" * 60)
        print("✅ 测试完成")
        print("=" * 60)

        return result

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == '__main__':
    test_battlefield_assessment()
