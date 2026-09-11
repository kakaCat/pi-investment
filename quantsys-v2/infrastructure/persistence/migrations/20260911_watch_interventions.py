"""介入记账表 + 元触发复核（REQ-f08def P4/P7，2026-09-11，w-c8cae280）

为什么需要（P4 成本记账）：
  介入判据的"每日预算"原用进程内存计数 —— 实测重启即清零（今天 escalated 计数冲到 18，
  远超预算 8），预算形同虚设。介入次数必须落库，才能：
    1) 跨重启准确执行每日预算；
    2) 算"单位唤醒产出 = 有价值动作 / 介入次数"（RFC 014 v3 §6 二级约束）；
    3) 对每次介入留痕（哪个触发、什么类型、什么结果）。

为什么需要（P7 元触发）：RFC 014 v3 §13 要求"规则不能无限期盯下去"——
  频次超限（一直响）/ 静默超时（一直不响）/ 阶段滞留 / 快到期，都要回到 agent 复核。
  复核结果以 watch_triggers 的 meta_review 态进入未处置清单（复用现有流转），无需新队列。

用法：./venv/bin/python infrastructure/persistence/migrations/20260911_watch_interventions.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DDL = [
    """CREATE TABLE IF NOT EXISTS quant.watch_interventions (
         id SERIAL PRIMARY KEY,
         rule_id INTEGER,
         symbol VARCHAR(20),
         intent VARCHAR(30),
         trigger_kind VARCHAR(20),
         outcome VARCHAR(30),
         trigger_ids TEXT,
         tokens INTEGER,
         cost_yuan DOUBLE PRECISION DEFAULT 0,
         decision_audit_id VARCHAR(60),
         created_at TIMESTAMP DEFAULT NOW()
       )""",
    "CREATE INDEX IF NOT EXISTS idx_watch_interventions_day ON quant.watch_interventions (created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_watch_interventions_rule ON quant.watch_interventions (rule_id)",
    # 让元触发可判"上次复核"：规则表已有 last_reviewed_at/review_due_at/review_interval_days（P1 迁移）
    "ALTER TABLE quant.watch_rules ADD COLUMN IF NOT EXISTS last_burst_alert_at TIMESTAMP",
]


def upgrade(cursor):
    for stmt in DDL:
        cursor.execute(stmt)


def verify(cursor):
    cursor.execute("SELECT count(*) FROM quant.watch_interventions")
    print("  介入记账行数:", cursor.fetchone()[0])
    cursor.execute("""SELECT column_name FROM information_schema.columns
                      WHERE table_schema=%s AND table_name=%s AND column_name=%s""",
                   ("quant", "watch_rules", "last_burst_alert_at"))
    print("  last_burst_alert_at 存在:", bool(cursor.fetchone()))


if __name__ == '__main__':
    from dotenv import load_dotenv
    from infrastructure.persistence.database.engine import get_engine
    load_dotenv()
    engine = get_engine()
    conn = engine.raw_connection()
    try:
        cursor = conn.cursor()
        print("迁移：介入记账表 + 元触发字段（P4/P7）")
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
