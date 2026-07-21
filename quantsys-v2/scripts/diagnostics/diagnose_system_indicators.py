#!/usr/bin/env python3
"""
诊断系统指标显示问题
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

print("=" * 70)
print("系统指标诊断工具")
print("=" * 70)

# 1. 检查数据库连接
print("\n[1] 检查数据库连接...")
try:
    # 尝试多种导入方式
    db = None
    try:
        from adapters.outbound.repositories import StrategyORMRepository
        repo = StrategyORMRepository()
        db = repo.db
    except:
        try:
            from quantsys.data.db import get_db
            db = get_db()
        except:
            pass

    if db:
        print("✓ 数据库连接成功")
    else:
        print("✗ 数据库连接失败 (返回 None)")
        print("\n建议：")
        print("  1. 检查数据库配置")
        print("  2. 确保数据库文件存在")
        print("  3. 检查数据库权限")
        sys.exit(1)
except Exception as e:
    print(f"✗ 数据库连接失败: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 2. 检查 strategy_code 表
print("\n[2] 检查 strategy_code 表...")
try:
    cursor = db.cursor()
    cursor.execute("SELECT COUNT(*) FROM strategy_code WHERE code_type='indicator'")
    total_indicators = cursor.fetchone()[0]
    print(f"✓ 表中共有 {total_indicators} 个指标")
except Exception as e:
    print(f"✗ 查询失败: {e}")
    sys.exit(1)

# 3. 检查系统指标
print("\n[3] 检查系统指标...")
try:
    cursor.execute("""
        SELECT id, strategy_name, strategy_type, is_public, category
        FROM strategy_code
        WHERE code_type='indicator' AND strategy_type != 'custom'
    """)
    system_indicators = cursor.fetchall()

    if system_indicators:
        print(f"✓ 找到 {len(system_indicators)} 个系统指标:")
        for ind in system_indicators:
            print(f"  - ID: {ind[0]}, 名称: {ind[1]}, 类型: {ind[2]}, 公开: {ind[3]}, 分类: {ind[4]}")
    else:
        print("✗ 没有找到系统指标")
        print("\n原因分析：")
        print("  数据库中没有 strategy_type != 'custom' 的指标")
        print("\n解决方法：")
        print("  运行以下命令创建系统指标：")
        print("  python3 scripts/diagnostics/create_builtin_indicators.py")
except Exception as e:
    print(f"✗ 查询失败: {e}")

# 4. 检查用户指标
print("\n[4] 检查用户指标...")
try:
    cursor.execute("""
        SELECT id, strategy_name, strategy_type
        FROM strategy_code
        WHERE code_type='indicator' AND strategy_type = 'custom'
    """)
    user_indicators = cursor.fetchall()

    if user_indicators:
        print(f"✓ 找到 {len(user_indicators)} 个用户指标:")
        for ind in user_indicators[:5]:  # 只显示前5个
            print(f"  - ID: {ind[0]}, 名称: {ind[1]}, 类型: {ind[2]}")
        if len(user_indicators) > 5:
            print(f"  ... 还有 {len(user_indicators) - 5} 个")
    else:
        print("✓ 没有用户指标（正常）")
except Exception as e:
    print(f"✗ 查询失败: {e}")

# 5. 检查 strategy_type 字段值分布
print("\n[5] 检查 strategy_type 字段值分布...")
try:
    cursor.execute("""
        SELECT strategy_type, COUNT(*)
        FROM strategy_code
        WHERE code_type='indicator'
        GROUP BY strategy_type
    """)
    type_distribution = cursor.fetchall()

    if type_distribution:
        print("✓ strategy_type 分布:")
        for type_name, count in type_distribution:
            type_label = type_name if type_name else '(NULL)'
            print(f"  - {type_label}: {count} 个")
    else:
        print("✗ 没有数据")
except Exception as e:
    print(f"✗ 查询失败: {e}")

# 6. 测试 API 过滤逻辑
print("\n[6] 测试 API 过滤逻辑...")
try:
    from application.services.strategy_code_service import StrategyCodeService
    service = StrategyCodeService()

    # 获取所有指标
    all_indicators = service.list_strategies(code_type='indicator')
    print(f"✓ 所有指标: {len(all_indicators)} 个")

    # 模拟系统指标过滤
    system_indicators_filtered = [i for i in all_indicators if i.get('strategy_type') != 'custom']
    print(f"✓ 系统指标（过滤后）: {len(system_indicators_filtered)} 个")

    if system_indicators_filtered:
        print("\n系统指标列表:")
        for ind in system_indicators_filtered:
            name = ind.get('strategy_name', ind.get('name', '未命名'))
            print(f"  - {name} (ID: {ind.get('id')})")

    # 模拟用户指标过滤
    user_indicators_filtered = [i for i in all_indicators if i.get('strategy_type') == 'custom']
    print(f"\n✓ 用户指标（过滤后）: {len(user_indicators_filtered)} 个")

except Exception as e:
    print(f"✗ 测试失败: {e}")
    import traceback
    traceback.print_exc()

# 7. 检查字段映射
print("\n[7] 检查字段映射...")
try:
    from adapters.inbound.api.utils.response import normalize_indicator_fields

    # 测试数据
    test_indicators = [
        {'id': 1, 'strategy_name': 'Test 1'},
        {'id': 2, 'strategy_name': 'Test 2', 'name': 'Override'},
    ]

    result = normalize_indicator_fields(test_indicators)

    if result[0].get('name') == 'Test 1' and result[1].get('name') == 'Override':
        print("✓ 字段映射工作正常")
    else:
        print("✗ 字段映射异常")
        print(f"  结果: {result}")
except Exception as e:
    print(f"✗ 测试失败: {e}")

# 总结
print("\n" + "=" * 70)
print("诊断总结")
print("=" * 70)

if not system_indicators:
    print("\n❌ 问题：数据库中没有系统指标")
    print("\n解决方案：")
    print("  1. 运行创建脚本：")
    print("     cd quantsys-v2")
    print("     python3 scripts/diagnostics/create_builtin_indicators.py")
    print("\n  2. 或手动插入系统指标到数据库")
    print("\n  3. 重启后端服务")
    print("\n  4. 刷新前端页面")
else:
    print("\n✅ 系统指标数据正常")
    print("\n如果前端仍然不显示，请检查：")
    print("  1. 后端服务是否正常运行")
    print("  2. 前端API请求是否成功（查看浏览器控制台）")
    print("  3. 前端是否正确调用 getSystemIndicators()")
    print("  4. 检查浏览器控制台的错误信息")

print("=" * 70)
