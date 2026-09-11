"""资金流表数据质量标记列（2026-09-11，w-f436d4ea）

为什么需要：quant.stock_fund_flow 存在**系统性历史污染**——与权威 K 线
quant.daily_klines 做同 symbol+trade_date 比对，60,211 条可比对行中 **14,314 条
（23.8%）收盘价偏差 >0.5%**。根因是 fund_flow_update_job 的 trade_date 取自**墙钟**
而非数据本身的交易日，两次全市场事故（2026-09-10 5,233 行、2026-09-01 4,471 行）
都是「盘中跑回补、把盘中价记成历史交易日收盘」。

根因已在 adaec83c 修掉（非交易日不落库 + 抽样比对 K 线一致性两道闸门），
**新增污染不会再发生**；本迁移处理**存量**：
  · 不删除任何数据（备份见 quant.stock_fund_flow_backup_20260911，81,335 行）；
  · 加 quality_flag 列，NULL = 干净，'close_mismatch_vs_kline' = 已知坏行；
  · 明细证据在 quant.stock_fund_flow_suspect（symbol/trade_date/flow_close/
    kline_close/deviation_pct/reason/flagged_at），可逐行追溯。

消费者规避：WHERE quality_flag IS NULL。
幂等：重复执行安全（IF NOT EXISTS + 按 suspect 表回填）。

用法：QUANT_DATABASE_URL=... ./venv/bin/python infrastructure/persistence/migrations/20260911_fund_flow_quality_flag.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DDL = [
    "ALTER TABLE quant.stock_fund_flow ADD COLUMN IF NOT EXISTS quality_flag VARCHAR(32)",
    # 回填：只标记证据表里那批已知坏行，不扩大范围、不删除
    """UPDATE quant.stock_fund_flow f
          SET quality_flag = 'close_mismatch_vs_kline'
         FROM quant.stock_fund_flow_suspect s
        WHERE s.symbol = f.symbol AND s.trade_date = f.trade_date
          AND f.quality_flag IS NULL""",
    "CREATE INDEX IF NOT EXISTS idx_stock_fund_flow_quality ON quant.stock_fund_flow (quality_flag)",
]


def upgrade(cursor):
    for stmt in DDL:
        cursor.execute(stmt)


def verify(cursor):
    cursor.execute("""SELECT COALESCE(quality_flag, '(clean)') AS flag, COUNT(*)
                        FROM quant.stock_fund_flow GROUP BY 1 ORDER BY 2 DESC""")
    print("  标记分布:", cursor.fetchall())


if __name__ == '__main__':
    from dotenv import load_dotenv

    from infrastructure.persistence.database.engine import get_engine
    load_dotenv()
    engine = get_engine()
    conn = engine.raw_connection()
    cursor = conn.cursor()
    try:
        print("迁移：资金流表数据质量标记列")
        upgrade(cursor)
        conn.commit()
        verify(cursor)
        print("✓ 完成")
    except Exception as e:
        conn.rollback()
        print("✗ 失败:", e)
        raise
    finally:
        cursor.close()
        conn.close()
