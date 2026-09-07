#!/usr/bin/env python3
"""
quant_test 与 quant_investment 的 schema 漂移检查

2026-08-05 背景：多次测试失败的根因是 quant_test 表结构落后生产
（strategy_configs 缺 4 列、account_balance 整表缺失、positions.id 无默认值等）。
本脚本对比两库 quant schema 的表/列/可空/默认值，输出漂移清单。

用法：
    python scripts/check_test_schema_drift.py          # 仅报告
    python scripts/check_test_schema_drift.py --apply  # 生成并执行补列 SQL（只增不改）
退出码：0 = 无漂移；1 = 有漂移（可用于 CI/cron 告警）
"""
import os
import sys

from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

import psycopg2

PG = dict(
    host=os.getenv('PGHOST', '127.0.0.1'),
    port=os.getenv('PGPORT', '5432'),
    user=os.getenv('PGUSER'),
    password=os.getenv('PGPASSWORD'),
)

PROD_DB = 'quant_investment'
TEST_DB = 'quant_test'


def get_schema(db: str) -> dict:
    """{table: {column: (data_type, is_nullable, column_default)}}"""
    conn = psycopg2.connect(dbname=db, **PG)
    cur = conn.cursor()
    cur.execute("""
        SELECT c.table_name, c.column_name, c.data_type, c.is_nullable, c.column_default
        FROM information_schema.columns c
        JOIN information_schema.tables t
          ON t.table_schema = c.table_schema AND t.table_name = c.table_name
        WHERE c.table_schema = 'quant'
          AND t.table_type = 'BASE TABLE'          -- 排除视图
          AND c.table_name NOT LIKE '%\\_backup\\_%'  -- 排除备份表
        ORDER BY c.table_name, c.ordinal_position
    """)
    schema: dict = {}
    for table, col, dtype, nullable, default in cur.fetchall():
        schema.setdefault(table, {})[col] = (dtype, nullable, default)
    conn.close()
    return schema


def column_type_sql(dtype: str, nullable: str, default) -> str:
    """把 information_schema 类型翻回 DDL 片段（覆盖本项目用到的类型）"""
    type_map = {
        'character varying': 'varchar',
        'timestamp without time zone': 'timestamp',
        'timestamp with time zone': 'timestamptz',
        'double precision': 'double precision',
        'boolean': 'boolean',
        'integer': 'integer',
        'bigint': 'bigint',
        'text': 'text',
        'jsonb': 'jsonb',
        'json': 'json',
        'date': 'date',
        'uuid': 'uuid',
        'numeric': 'numeric',
        'ARRAY': 'text[]',
    }
    sql_type = type_map.get(dtype, dtype)
    parts = [sql_type]
    if default is not None:
        parts.append(f"DEFAULT {default}")
    if nullable == 'NO':
        parts.append('NOT NULL')
    return ' '.join(parts)


def main() -> int:
    apply = '--apply' in sys.argv
    prod = get_schema(PROD_DB)
    test = get_schema(TEST_DB)

    missing_tables = sorted(set(prod) - set(test))
    drift_columns = {}   # 生产有、测试缺的列
    type_mismatch = {}   # 类型/可空性不一致（只报告，不自动改）

    for table in sorted(set(prod) & set(test)):
        prod_cols = prod[table]
        test_cols = test[table]
        missing = {c: prod_cols[c] for c in prod_cols if c not in test_cols}
        if missing:
            drift_columns[table] = missing
        for col in set(prod_cols) & set(test_cols):
            pt, pn, _ = prod_cols[col]
            tt, tn, _ = test_cols[col]
            if pt != tt or pn != tn:
                type_mismatch.setdefault(table, []).append(
                    (col, f"prod=({pt},{pn}) test=({tt},{tn})"))

    if not missing_tables and not drift_columns and not type_mismatch:
        print("✅ quant_test 与生产 schema 无漂移")
        return 0

    print(f"⚠️  缺表（{len(missing_tables)}）: {missing_tables}")
    for table, cols in drift_columns.items():
        print(f"⚠️  {table} 缺列: {list(cols)}")
    for table, cols in type_mismatch.items():
        for col, detail in cols:
            print(f"⚠️  {table}.{col} 定义不一致: {detail}")

    if apply:
        conn = psycopg2.connect(dbname=TEST_DB, **PG)
        conn.autocommit = True
        cur = conn.cursor()
        for table, cols in drift_columns.items():
            for col, (dtype, nullable, default) in cols.items():
                # 只加可空/有默认值的列——NOT NULL 无默认的列加不上也报错，跳过并提示
                if nullable == 'NO' and default is None:
                    print(f"⏭️  跳过 {table}.{col}（NOT NULL 无默认值，需人工处理）")
                    continue
                ddl = (f"ALTER TABLE quant.{table} ADD COLUMN IF NOT EXISTS "
                       f"{col} {column_type_sql(dtype, nullable, default)}")
                cur.execute(ddl)
                print(f"✅ 已补 {table}.{col}")
        conn.close()
        print("（缺表不自动建——请从生产 pg_dump -s 对应表结构后人工执行）")

    return 1


if __name__ == '__main__':
    sys.exit(main())
