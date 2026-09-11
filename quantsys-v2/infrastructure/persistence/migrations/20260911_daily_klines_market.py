#!/usr/bin/env python
"""daily_klines 命名空间显式化：加 market 列 + 触发器 + 复合唯一索引（步4，2026-09-11，w-f4aa1f6a）

## 背景
`quant.daily_klines` 存裸 6 位代码，历史上"指数与股票同名"（000001 上证指数/平安银行、
000016 上证50/*ST康佳A、000905 中证500/厦门港务）造成过误判（"上证50 掉队"）。
指数数据已于 2026-09-11 拆分到 `quant.index_daily`（migration 20260911_index_daily_split.py），
本迁移把**交易所归属**显式落到列上，消除"同一代码属于哪个市场"的隐含假设。

## 为什么不是直接换主键
勘查发现 `daily_klines.symbol` **已有外键**指向 `quant.stocks.symbol`（ondelete=CASCADE），
符号空间本就受约束、不可能出现跨市场同名；而换主键会打断 7 处
`ON CONFLICT (symbol, trade_date)` 的原始 SQL（2 个 tools + 5 个测试）。
故本迁移采取**零破坏**方案：加列 + 触发器自动推导 + 复合唯一索引
（uq_daily_klines_symbol_market_date），保留原主键 (symbol, trade_date)。
若日后要换主键，先把那些 upsert 改成 (symbol, market, trade_date) 再执行
`ALTER TABLE ... DROP CONSTRAINT daily_klines_pkey; ALTER TABLE ... ADD PRIMARY KEY USING INDEX uq_...`。

## 幂等
全部语句 IF NOT EXISTS / CREATE OR REPLACE，可重复执行；回填按 symbol 前缀分段 UPDATE。

用法：
    ./venv/bin/python infrastructure/persistence/migrations/20260911_daily_klines_market.py            # dry-run（默认）
    ./venv/bin/python infrastructure/persistence/migrations/20260911_daily_klines_market.py --apply

## 测试库也要跑（实测坑）
ORM 模型加了 market 字段后，**测试库 quant_test 的 daily_klines 仍是旧 schema**，
tests/test_kline_repository.py 立刻报 "column daily_klines.market does not exist"（1 failed / 22 passed）。
测试库需同样执行本迁移：
    ./venv/bin/python infrastructure/persistence/migrations/20260911_daily_klines_market.py \
        --apply --dsn postgresql+psycopg2:///quant_test
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from sqlalchemy import create_engine, text  # noqa: E402

DDL = [
    "ALTER TABLE quant.daily_klines ADD COLUMN IF NOT EXISTS market varchar(8)",
    # 早期版本为 varchar(6)，UNKNOWN 有 7 字符 → 统一放宽（扩宽是元数据操作，不重写）
    "ALTER TABLE quant.daily_klines ALTER COLUMN market TYPE varchar(8)",
    """COMMENT ON COLUMN quant.daily_klines.market IS
       '交易所归属 SH/SZ/BJ/UNKNOWN（2026-09-11 w-f4aa1f6a 步4；指数数据在 quant.index_daily）'""",
    """CREATE OR REPLACE FUNCTION quant.derive_kline_market(sym text) RETURNS varchar AS $$
         SELECT CASE
           WHEN sym ~ '^6' THEN 'SH'
           WHEN sym ~ '^[03]' THEN 'SZ'
           WHEN sym ~ '^(4|8|92)' THEN 'BJ'
           ELSE 'UNKNOWN'
         END;
       $$ LANGUAGE sql IMMUTABLE""",
    """CREATE OR REPLACE FUNCTION quant.daily_klines_set_market() RETURNS trigger AS $$
       BEGIN
         IF NEW.market IS NULL OR NEW.market = '' THEN
           NEW.market := quant.derive_kline_market(NEW.symbol);
         END IF;
         IF NEW.market IS NULL THEN
           -- 本文件的 DDL 一律经原生 DBAPI 游标（params=None）下发。
           RAISE EXCEPTION '无法从 symbol=% 推导 market（2026-09-11 w-f4aa1f6a 步4）', NEW.symbol;
         END IF;
         RETURN NEW;
       END;
       $$ LANGUAGE plpgsql""",
    "DROP TRIGGER IF EXISTS trg_daily_klines_set_market ON quant.daily_klines",
    """CREATE TRIGGER trg_daily_klines_set_market
       BEFORE INSERT OR UPDATE OF symbol ON quant.daily_klines
       FOR EACH ROW EXECUTE FUNCTION quant.daily_klines_set_market()""",
]

# 回填顺序有讲究：92xxxx 属北交所，必须排在 ^[03]（SZ）规则之后单独处理，
# 否则 '92' 不以 0/3 开头不受影响，但 ^(4|8) 也不匹配 → 会漏（首轮实测漏 156,892 行）。
BACKFILL = [
    ("SH", "symbol ~ '^6'"),
    ("SZ", "symbol ~ '^[03]'"),
    ("BJ", "symbol ~ '^(4|8|92)'"),
]

UNIQUE_INDEX = (
    'CREATE UNIQUE INDEX CONCURRENTLY IF NOT EXISTS '
    'uq_daily_klines_symbol_market_date ON quant.daily_klines (symbol, market, trade_date)'
)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='真正执行（默认仅 dry-run）')
    ap.add_argument('--dsn', default=None)
    args = ap.parse_args()

    engine = create_engine(args.dsn) if args.dsn else create_engine('postgresql+psycopg2:///quant_investment')

    if not args.apply:
        with engine.connect() as conn:
            n = conn.execute(text('SELECT count(*) FROM quant.daily_klines WHERE market IS NULL')).scalar()
            total = conn.execute(text('SELECT count(*) FROM quant.daily_klines')).scalar()
        print(f'[dry-run] daily_klines 共 {total} 行，market 为空 {n} 行')
        print('[dry-run] 将执行：加列 → 建函数/触发器 → 分段回填 → 并发建复合唯一索引')
        print('[dry-run] 加参数 --apply 真正执行（幂等，可重复跑）')
        return 0

    # 用原生 DBAPI 游标下发 DDL：psycopg2 在 params=None 时不做占位符插值，
    # 避免 SQLAlchemy exec_driver_sql 把 plpgsql 里的 % 当参数占位符
    # （实测报 TypeError: immutabledict is not a sequence）
    raw = engine.raw_connection()
    try:
        with raw.cursor() as cur:
            for ddl in DDL:
                cur.execute(ddl)
        raw.commit()
        print('[migrate] 列/函数/触发器就绪')
    finally:
        raw.close()

    with engine.begin() as conn:
        for market, cond in BACKFILL:
            res = conn.execute(text(
                f"UPDATE quant.daily_klines SET market = :m WHERE market IS NULL AND {cond}"
            ), {'m': market})
            print(f'[migrate] 回填 {market}: {res.rowcount} 行')
        left = conn.execute(text('SELECT count(*) FROM quant.daily_klines WHERE market IS NULL')).scalar()
        print(f'[migrate] 回填后仍为空: {left} 行')

    # 并发建索引必须真正脱离事务块：SQLAlchemy 池连接的隐式事务会报
    # "CREATE INDEX CONCURRENTLY cannot run inside a transaction block"，
    # 故另开一条独立 psycopg2 连接并从一开始就 autocommit。
    import psycopg2

    conn2 = psycopg2.connect(**engine.url.translate_connect_args())
    conn2.autocommit = True
    try:
        with conn2.cursor() as cur:
            cur.execute(UNIQUE_INDEX)
        print('[migrate] 复合唯一索引就绪')
    finally:
        conn2.close()

    with engine.connect() as conn:
        rows = conn.execute(text('SELECT market, count(*) FROM quant.daily_klines GROUP BY 1 ORDER BY 2 DESC')).fetchall()
    for m, c in rows:
        print(f'[verify] market={m}: {c} 行')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
