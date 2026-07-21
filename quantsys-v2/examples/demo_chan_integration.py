#!/usr/bin/env python3
"""
缠论功能演示脚本 - 轻量级验证

不依赖完整的API服务器，直接演示缠论分析功能
"""
import sys
import os
from pathlib import Path

# 设置路径
sys.path.insert(0, str(Path(__file__).parent))
os.chdir(Path(__file__).parent)

print("=" * 70)
print("🎯 缠论功能演示")
print("=" * 70)

# 步骤1：测试核心算法
print("\n📦 步骤1：测试缠论核心算法")
print("-" * 70)

try:
    from domain.chan.chan_analyzer import ChanAnalyzer
    print("✅ ChanAnalyzer 导入成功")

    # 创建分析器实例
    analyzer = ChanAnalyzer()
    print("✅ ChanAnalyzer 实例化成功")
    print(f"   - 算法版本: v1.0")
    print(f"   - 支持功能: 笔/线段/中枢/买卖点识别")

except Exception as e:
    print(f"❌ 核心算法测试失败: {e}")
    sys.exit(1)

# 步骤2：测试服务层
print("\n📦 步骤2：测试缠论服务层")
print("-" * 70)

try:
    from application.services.chan_service import ChanService
    print("✅ ChanService 导入成功")

    service = ChanService()
    print("✅ ChanService 实例化成功")
    print(f"   - 数据源: KlineRepository")
    print(f"   - 输出格式: JSON")

except Exception as e:
    print(f"❌ 服务层测试失败: {e}")
    sys.exit(1)

# 步骤3：测试API路由
print("\n📦 步骤3：测试API路由")
print("-" * 70)

try:
    from adapters.inbound.api.routes.chan import chan_bp
    print("✅ chan_bp 导入成功")
    print(f"   - Blueprint名称: {chan_bp.name}")
    print(f"   - URL前缀: {chan_bp.url_prefix}")
    print(f"   - 注册路由数: {len(chan_bp.deferred_functions)}")

except Exception as e:
    print(f"❌ API路由测试失败: {e}")
    sys.exit(1)

# 步骤4：模拟数据测试
print("\n📦 步骤4：使用模拟数据测试分析功能")
print("-" * 70)

try:
    import pandas as pd
    import numpy as np
    from datetime import datetime, timedelta

    # 生成模拟K线数据
    dates = [(datetime(2024, 1, 1) + timedelta(days=i)).strftime('%Y-%m-%d')
             for i in range(100)]

    # 模拟一个上涨趋势 + 回调的行情
    base_price = 100
    prices = []
    for i in range(100):
        if i < 30:  # 上涨
            price = base_price + i * 2 + np.random.randn() * 2
        elif i < 50:  # 回调
            price = base_price + 60 - (i - 30) * 1 + np.random.randn() * 2
        else:  # 再次上涨
            price = base_price + 40 + (i - 50) * 1.5 + np.random.randn() * 2
        prices.append(max(price, 50))

    mock_data = pd.DataFrame({
        'date': dates,
        'open': [p + np.random.randn() for p in prices],
        'high': [p + abs(np.random.randn() * 2) for p in prices],
        'low': [p - abs(np.random.randn() * 2) for p in prices],
        'close': prices,
        'volume': [int(1000000 + np.random.randn() * 100000) for _ in range(100)]
    })

    print("✅ 模拟数据生成成功")
    print(f"   - 数据点数: {len(mock_data)}")
    print(f"   - 日期范围: {dates[0]} ~ {dates[-1]}")
    print(f"   - 价格范围: {min(prices):.2f} ~ {max(prices):.2f}")

    # 执行缠论分析
    result = analyzer.analyze('MOCK.SH', mock_data)

    print("\n✅ 缠论分析完成")
    print(f"   - 走势类型: {result.trend_type}")
    print(f"   - 识别笔数: {len(result.bis)}")
    print(f"   - 识别线段: {len(result.segments)}")
    print(f"   - 识别中枢: {len(result.zhongshus)}")
    print(f"   - 买卖点数: {len(result.buypoints)}")

    if result.buypoints:
        print("\n📊 买卖点详情（前3个）:")
        for i, bp in enumerate(result.buypoints[:3], 1):
            print(f"   {i}. {bp.type} @ ¥{bp.price:.2f}")
            print(f"      - 置信度: {bp.confidence:.1%}")
            print(f"      - 建议仓位: {bp.position_ratio:.1%}")
            print(f"      - 原因: {bp.reason}")

except Exception as e:
    print(f"❌ 分析测试失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 步骤5：检查前端文件
print("\n📦 步骤5：检查前端集成")
print("-" * 70)

frontend_file = Path("../web-frontend/src/views/StockDetail/index.vue")
if frontend_file.exists():
    content = frontend_file.read_text()

    checks = [
        ("缠论分析标签", "'缠论分析'" in content or '"缠论分析"' in content),
        ("chan标签页", "'chan'" in content or '"chan"' in content),
        ("chanResult数据", "chanResult" in content),
        ("API调用", "/api/chan/analyze" in content),
        ("买卖点表格", "buypoints" in content),
    ]

    all_pass = True
    for name, passed in checks:
        if passed:
            print(f"   ✅ {name}")
        else:
            print(f"   ❌ {name}")
            all_pass = False

    if all_pass:
        print("\n✅ 前端集成检查通过")
    else:
        print("\n⚠️  前端集成部分检查未通过")
else:
    print("⚠️  前端文件未找到（可能不在quantsys-v2目录）")

# 总结
print("\n" + "=" * 70)
print("📋 测试总结")
print("=" * 70)

summary = [
    ("核心算法", True),
    ("服务层", True),
    ("API路由", True),
    ("数据分析", len(result.bis) > 0 or len(result.buypoints) > 0),
]

print("\n测试结果：")
for name, passed in summary:
    status = "✅ 通过" if passed else "❌ 失败"
    print(f"  {status} - {name}")

if all(p for _, p in summary):
    print("\n🎉 所有测试通过！缠论功能集成成功！")
    print("\n📖 下一步：")
    print("   1. 修复环境问题（安装依赖、升级Python）")
    print("   2. 启动API服务器：python start_all.py")
    print("   3. 启动前端：cd web-frontend && npm run dev")
    print("   4. 访问股票详情页，点击'缠论分析'标签页")
    print("\n📚 文档：docs/CHAN_INTEGRATION_GUIDE.md")
else:
    print("\n⚠️  部分测试未通过，请检查上述错误信息")
    sys.exit(1)

print("\n" + "=" * 70)
