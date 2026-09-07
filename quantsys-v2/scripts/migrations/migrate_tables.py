#!/usr/bin/env python3
"""
创建缺失的8张数据库表
"""
import os
import sys
import psycopg2
from psycopg2.extras import RealDictCursor

# 添加项目根目录到路径

def get_db_connection():
    """获取数据库连接"""
    # 尝试多个环境变量
    dsn = (
        os.environ.get("QUANT_DATABASE_URL") or
        os.environ.get("DATABASE_URL") or
        os.environ.get("POSTGRES_DSN")
    )

    if not dsn:
        pgdatabase = os.environ.get("PGDATABASE")
        if pgdatabase:
            pghost = os.environ.get("PGHOST", "127.0.0.1")
            pgport = os.environ.get("PGPORT", "5432")
            pguser = os.environ.get("PGUSER", "")
            pgpassword = os.environ.get("PGPASSWORD", "")
            auth = f"{pguser}:{pgpassword}@" if pguser else ""
            dsn = f"postgresql://{auth}{pghost}:{pgport}/{pgdatabase}"

    if not dsn:
        print("❌ 错误: 未找到数据库连接配置")
        print("请设置以下环境变量之一:")
        print("  - QUANT_DATABASE_URL")
        print("  - DATABASE_URL")
        print("  - POSTGRES_DSN")
        print("  - PGDATABASE (and optionally PGHOST/PGPORT/PGUSER/PGPASSWORD)")
        sys.exit(1)

    try:
        conn = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
        print(f"✅ 成功连接到数据库")
        return conn
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        sys.exit(1)

def execute_sql_file(conn, sql_file):
    """执行SQL文件"""
    with open(sql_file, 'r', encoding='utf-8') as f:
        sql = f.read()

    cursor = conn.cursor()
    try:
        cursor.execute(sql)
        conn.commit()

        # 获取最后的SELECT结果
        if cursor.description:
            result = cursor.fetchone()
            if result:
                print(f"✅ {result['status']}")

        return True
    except Exception as e:
        conn.rollback()
        print(f"❌ SQL执行失败: {e}")
        return False
    finally:
        cursor.close()

def verify_tables(conn):
    """验证表是否创建成功"""
    cursor = conn.cursor()

    tables = [
        'portfolio_holdings',
        'trades',
        'orders',
        'backtest_results',
        'strategy_configs',
        'account_balance',
        'risk_metrics',
        'minute_klines'
    ]

    print("\n📊 验证表创建情况:")

    for table in tables:
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'quant'
                AND table_name = %s
            );
        """, (table,))

        exists = cursor.fetchone()['exists']
        status = "✅" if exists else "❌"
        print(f"  {status} quant.{table}")

    cursor.close()

def main():
    print("=" * 60)
    print("创建缺失的8张数据库表")
    print("=" * 60)

    # 获取数据库连接
    conn = get_db_connection()

    # 执行SQL文件
    sql_file = os.path.join(
        os.path.dirname(__file__),
        'create_missing_tables.sql'
    )

    print(f"\n📝 执行SQL脚本: {sql_file}")

    if execute_sql_file(conn, sql_file):
        # 验证表创建
        verify_tables(conn)
        print("\n✅ 所有表创建完成！")
    else:
        print("\n❌ 表创建失败")
        sys.exit(1)

    conn.close()

if __name__ == '__main__':
    main()
