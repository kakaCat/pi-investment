#!/usr/bin/env python3
"""测试缠论集成"""
import sys

from application.services.chan_service import ChanService

def test_chan_service():
    """测试 ChanService 基本功能"""
    print("=" * 60)
    print("测试缠论服务集成")
    print("=" * 60)

    service = ChanService()

    # 测试分析接口
    print("\n1. 测试缠论分析（茅台 600519.SH）...")
    result = service.analyze(
        symbol='600519.SH',
        start_date='2024-01-01',
        end_date='2024-06-30'
    )

    print(f"   股票代码: {result['symbol']}")
    print(f"   走势类型: {result['trend_type']}")
    print(f"   笔数量: {len(result['bis'])}")
    print(f"   线段数量: {len(result['segments'])}")
    print(f"   中枢数量: {len(result['zhongshus'])}")
    print(f"   买卖点数量: {len(result['buypoints'])}")

    if result['buypoints']:
        print(f"\n2. 买卖点详情（前3个）:")
        for i, bp in enumerate(result['buypoints'][:3], 1):
            print(f"   {i}. {bp['type']} @ ¥{bp['price']:.2f}")
            print(f"      置信度: {bp['confidence']:.1%}, 仓位: {bp['position_ratio']:.1%}")
            print(f"      原因: {bp['reason']}")

    print("\n" + "=" * 60)
    print("✅ 测试完成")
    print("=" * 60)

    return result

if __name__ == '__main__':
    try:
        test_chan_service()
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
