#!/usr/bin/env python3
"""检查strategy_configs表中的系统指标"""

import os
import psycopg2
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 数据库配置
db_config = {
    'dbname': os.getenv('PGDATABASE', 'quant_investment'),
    'user': os.getenv('PGUSER', 'mac'),
    'password': os.getenv('PGPASSWORD', ''),
    'host': os.getenv('PGHOST', '127.0.0.1'),
    'port': os.getenv('PGPORT', '5432')
}

def main():
    print("=" * 60)
    print("检查 strategy_configs 表中的系统指标")
    print("=" * 60)

    try:
        # 连接数据库
        print(f"\n连接数据库: {db_config['dbname']}@{db_config['host']}:{db_config['port']}")
        conn = psycopg2.connect(**db_config)
        cursor = conn.cursor()
        print("✓ 数据库连接成功")

        # 检查表是否存在
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'quant'
                AND table_name = 'strategy_configs'
            )
        """)
        table_exists = cursor.fetchone()[0]

        if not table_exists:
            print("\n✗ 表 quant.strategy_configs 不存在")
            return

        print("✓ 表 quant.strategy_configs 存在")

        # 统计所有指标
        cursor.execute("""
            SELECT COUNT(*) FROM quant.strategy_configs
            WHERE code_type='indicator'
        """)
        total_indicators = cursor.fetchone()[0]
        print(f"\n总指标数: {total_indicators}")

        # 统计系统指标（strategy_type != 'custom'）
        cursor.execute("""
            SELECT COUNT(*) FROM quant.strategy_configs
            WHERE code_type='indicator' AND strategy_type != 'custom'
        """)
        system_indicators = cursor.fetchone()[0]
        print(f"系统指标数: {system_indicators}")

        # 统计用户指标（strategy_type = 'custom'）
        cursor.execute("""
            SELECT COUNT(*) FROM quant.strategy_configs
            WHERE code_type='indicator' AND strategy_type = 'custom'
        """)
        user_indicators = cursor.fetchone()[0]
        print(f"用户指标数: {user_indicators}")

        # 列出所有指标
        if total_indicators > 0:
            print("\n" + "=" * 60)
            print("所有指标列表:")
            print("=" * 60)
            cursor.execute("""
                SELECT id, strategy_name, strategy_type, description, author
                FROM quant.strategy_configs
                WHERE code_type='indicator'
                ORDER BY strategy_type, strategy_name
            """)

            for row in cursor.fetchall():
                strategy_id, name, stype, desc, author = row
                type_label = "系统" if stype != 'custom' else "用户"
                print(f"\n[{type_label}] ID: {strategy_id}")
                print(f"  名称: {name}")
                print(f"  类型: {stype}")
                print(f"  作者: {author or '无'}")
                print(f"  描述: {desc or '无'}")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"\n✗ 错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
