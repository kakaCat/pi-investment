#!/usr/bin/env python3
"""
简化的系统指标检查脚本
"""
import os
import psycopg2

print("=" * 70)
print("系统指标快速检查")
print("=" * 70)

# 从环境变量获取数据库配置
db_name = os.environ.get('PGDATABASE', 'quant_investment')
db_host = os.environ.get('PGHOST', '127.0.0.1')
db_port = os.environ.get('PGPORT', '5432')
db_user = os.environ.get('PGUSER', 'postgres')
db_password = os.environ.get('PGPASSWORD', '')

print(f"\n数据库配置:")
print(f"  主机: {db_host}:{db_port}")
print(f"  数据库: {db_name}")
print(f"  用户: {db_user}")

try:
    # 连接数据库
    print("\n正在连接数据库...")
    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        database=db_name,
        user=db_user,
        password=db_password
    )
    cursor = conn.cursor()
    print("✓ 数据库连接成功")

    # 检查表是否存在
    print("\n检查 strategy_code 表...")
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_name = 'strategy_code'
        );
    """)
    table_exists = cursor.fetchone()[0]

    if not table_exists:
        print("✗ strategy_code 表不存在")
        print("\n需要运行数据库迁移:")
        print("  cd quantsys-v2")
        print("  python3 scripts/migrations/run_migration.py 001_add_strategy_code_fields.sql")
        conn.close()
        exit(1)

    print("✓ strategy_code 表存在")

    # 统计所有指标
    print("\n统计指标数量...")
    cursor.execute("SELECT COUNT(*) FROM strategy_code WHERE code_type='indicator'")
    total = cursor.fetchone()[0]
    print(f"  总指标数: {total}")

    # 统计系统指标
    cursor.execute("""
        SELECT COUNT(*) FROM strategy_code
        WHERE code_type='indicator' AND strategy_type != 'custom'
    """)
    system_count = cursor.fetchone()[0]
    print(f"  系统指标: {system_count}")

    # 统计用户指标
    cursor.execute("""
        SELECT COUNT(*) FROM strategy_code
        WHERE code_type='indicator' AND strategy_type = 'custom'
    """)
    user_count = cursor.fetchone()[0]
    print(f"  用户指标: {user_count}")

    # 显示系统指标列表
    if system_count > 0:
        print("\n系统指标列表:")
        cursor.execute("""
            SELECT id, strategy_name, category, strategy_type
            FROM strategy_code
            WHERE code_type='indicator' AND strategy_type != 'custom'
            ORDER BY id
        """)
        for row in cursor.fetchall():
            print(f"  [{row[0]}] {row[1]} ({row[2]}) - type: {row[3]}")
    else:
        print("\n❌ 没有系统指标！")
        print("\n解决方法:")
        print("  python3 scripts/diagnostics/create_builtin_indicators.py")

    # 显示 strategy_type 分布
    print("\nstrategy_type 字段分布:")
    cursor.execute("""
        SELECT strategy_type, COUNT(*)
        FROM strategy_code
        WHERE code_type='indicator'
        GROUP BY strategy_type
    """)
    for row in cursor.fetchall():
        type_name = row[0] if row[0] else '(NULL)'
        print(f"  {type_name}: {row[1]}")

    conn.close()

    print("\n" + "=" * 70)
    if system_count == 0:
        print("结论: 需要创建系统指标")
        print("运行: python3 scripts/diagnostics/create_builtin_indicators.py")
    else:
        print(f"结论: 系统指标正常 ({system_count} 个)")
    print("=" * 70)

except psycopg2.OperationalError as e:
    print(f"\n✗ 数据库连接失败: {e}")
    print("\n可能的原因:")
    print("  1. PostgreSQL 服务未启动")
    print("  2. 数据库不存在")
    print("  3. 用户名或密码错误")
    print("  4. 主机或端口配置错误")
    print("\n检查方法:")
    print("  pg_isready -h 127.0.0.1 -p 5432")
except Exception as e:
    print(f"\n✗ 错误: {e}")
    import traceback
    traceback.print_exc()
