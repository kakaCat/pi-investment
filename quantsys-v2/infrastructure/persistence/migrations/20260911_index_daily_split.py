"""指数价格与个股 K 线分表（2026-09-11，w-f4aa1f6a）

背景（实测）：
- quant.daily_klines 共 4,655,497 行，**全部是裸 6 位码**，没有任何市场命名空间；
  指数与深市股票同码冲突（000001 平安银行 / 000016 *ST康佳A / 000905 厦门港务 /
  000852 石化机械 / 000906 浙商中拓），指数价格实际"无家可归"。
- 指数与个股语义本不同：指数 volume 是成分股聚合（量纲不同）、无复权/停牌/涨跌停。
  混表已酿成过一次事故——w-23c70356 清掉的「深证成指被估成 949.86 万亿元」
  就是 amount = volume × close 套用在指数行上。
- 现状：quant.index_constituents（成分股）有表，但**指数价格无表**。

本迁移：
1. 建 quant.index_daily（symbol 带市场后缀，PK 同 daily_klines 形状）；
2. 把 daily_klines 中的真指数行（stocks.list_date 为空，即 000300/399300/399001/399006）
   搬进新表并补后缀；
3. 原行先整表备份到 quant.bak_index_rows_w_f4aa1f6a（回滚用），**暂不删除**——
   删除放到读路径切换之后（见 --drop-from-daily-klines 步骤），避免切换期读空。

用法：
  python infrastructure/persistence/migrations/20260911_index_daily_split.py            # dry-run
  python ... --apply                        # 建表 + 备份 + 搬迁
  python ... --apply --drop-from-daily-klines   # 读路径切换后再执行：删原行
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from sqlalchemy import create_engine, text  # noqa: E402

# 指数后缀：沪市 .SH / 深市 .SZ（399 族为深证指数）
SUFFIX = {'000300': 'SH', '000001': 'SH', '000016': 'SH', '000905': 'SH',
          '000852': 'SH', '000906': 'SH', '000903': 'SH',
          '399300': 'SZ', '399001': 'SZ', '399006': 'SZ', '399005': 'SZ'}
CANDIDATES = tuple(SUFFIX.keys())

DDL_INDEX_DAILY = """
CREATE TABLE IF NOT EXISTS quant.index_daily (
    symbol       text        NOT NULL,
    trade_date   date        NOT NULL,
    open         double precision,
    high         double precision,
    low          double precision,
    close        double precision,
    volume       double precision,
    amount       double precision,
    source       text,
    updated_at   timestamptz DEFAULT now(),
    PRIMARY KEY (symbol, trade_date)
)
"""

# 真指数判定：在 daily_klines 里出现、且 stocks 表无该代码的上市日（list_date 为空/无记录）
# —— 与 utils/symbol_classifier.is_index_symbol 同源语义（歧义码查 stocks 表定夺）
SELECT_TRUE_INDEX = f"""
SELECT k.symbol, s.list_date
FROM quant.daily_klines k
LEFT JOIN quant.stocks s ON s.symbol = k.symbol
WHERE k.symbol IN {CANDIDATES!r}
GROUP BY k.symbol, s.list_date
""".replace("'", "'")  # 占位（真实 SQL 见下）

SELECT_TRUE_INDEX = """
SELECT k.symbol, s.list_date
FROM quant.daily_klines k
LEFT JOIN quant.stocks s ON s.symbol = k.symbol
WHERE k.symbol = ANY(:cands)
GROUP BY k.symbol, s.list_date
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='真正执行（默认 dry-run）')
    ap.add_argument('--drop-from-daily-klines', action='store_true',
                    help='删除 daily_klines 中已搬迁的指数行（务必在读路径切换后再用）')
    ap.add_argument('--dsn', default=None,
                    help='默认走本机 libpq 默认连接（psycopg2）；也可显式指定')
    args = ap.parse_args()

    if args.dsn:
        engine = create_engine(args.dsn)
    else:
        # 优先复用项目 engine（若已初始化）；否则回落到本机 libpq 默认连接
        try:
            from infrastructure.persistence.orm.config import get_engine

            engine = get_engine()
        except Exception as e:  # noqa: BLE001
            print(f"[迁移] 项目 engine 不可用（{e}），回落到本机 libpq 默认连接")
            engine = None
        if engine is None:
            engine = create_engine('postgresql+psycopg2:///quant_investment')
    with engine.begin() as conn:
        rows = conn.execute(text(SELECT_TRUE_INDEX), {'cands': list(CANDIDATES)}).fetchall()
        true_index = [(r[0], SUFFIX[r[0]]) for r in rows if r[1] is None]
        stock_like = [(r[0], r[1]) for r in rows if r[1] is not None]

        print(f"[迁移] 候选代码 {len(rows)} 个：真指数 {len(true_index)} 个，个股（有上市日，保持不动） {len(stock_like)} 个")
        for sym, suf in true_index:
            n = conn.execute(text("SELECT count(*) FROM quant.daily_klines WHERE symbol=:s"), {'s': sym}).scalar()
            print(f"  待搬迁 {sym} → {sym}.{suf}（{n} 行）")
        for sym, ld in stock_like:
            print(f"  保持不动 {sym}（上市日 {ld}，属个股）")

        if not args.apply:
            print("[dry-run] 未做任何写入。加 --apply 执行。")
            return 0

        conn.execute(text(DDL_INDEX_DAILY))
        print("[迁移] quant.index_daily 就绪")

        # 备份（幂等：已存在则跳过，避免覆盖）
        exists = conn.execute(text(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_schema='quant' AND table_name='bak_index_rows_w_f4aa1f6a'")).scalar()
        if not exists:
            conn.execute(text(
                "CREATE TABLE quant.bak_index_rows_w_f4aa1f6a AS "
                "SELECT * FROM quant.daily_klines WHERE symbol = ANY(:cands)"),
                {'cands': [s for s, _ in true_index]})
            print("[迁移] 已备份原行到 quant.bak_index_rows_w_f4aa1f6a（回滚用）")
        else:
            print("[迁移] 备份表已存在，跳过（不覆盖）")

        total = 0
        for sym, suf in true_index:
            res = conn.execute(text("""
                INSERT INTO quant.index_daily
                    (symbol, trade_date, open, high, low, close, volume, amount, source, updated_at)
                SELECT :new_sym, trade_date, open, high, low, close, volume, amount,
                       COALESCE(source, 'legacy-daily_klines'), now()
                FROM quant.daily_klines WHERE symbol = :old_sym
                ON CONFLICT (symbol, trade_date) DO NOTHING
            """), {'new_sym': f'{sym}.{suf}', 'old_sym': sym})
            total += res.rowcount or 0
            print(f"[迁移] {sym} → {sym}.{suf}：写入 {res.rowcount} 行")

        if args.drop_from_daily_klines:
            res = conn.execute(text("DELETE FROM quant.daily_klines WHERE symbol = ANY(:cands)"),
                               {'cands': [s for s, _ in true_index]})
            print(f"[迁移] 已从 daily_klines 删除 {res.rowcount} 行指数行（备份仍在 bak_ 表）")

        print(f"[迁移] 完成：index_daily 新增 {total} 行")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
