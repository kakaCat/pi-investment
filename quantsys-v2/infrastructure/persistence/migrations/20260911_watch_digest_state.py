"""盯盘摘要状态表（REQ-f08def P4，2026-09-11，w-c8cae280）

为什么需要：Phase 2 的摘要门把"上次唤醒时间/当日唤醒次数"存在**进程内存/文件**里，
导致重启即清零重计——实测重启后 escalated 重计、每日预算形同虚设。
摘要门要真的"与触发数解耦"，状态必须落库。

用法：./venv/bin/python infrastructure/persistence/migrations/20260911_watch_digest_state.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DDL = [
    """CREATE TABLE IF NOT EXISTS quant.watch_digest_state (
         id INTEGER PRIMARY KEY,
         last_wake_at TIMESTAMP,
         wake_date DATE,
         wake_count INTEGER DEFAULT 0,
         last_digest_at TIMESTAMP,
         note TEXT,
         updated_at TIMESTAMP DEFAULT NOW()
       )""",
    "INSERT INTO quant.watch_digest_state (id, wake_count) VALUES (1, 0) ON CONFLICT (id) DO NOTHING",
]


def upgrade(cursor):
    for stmt in DDL:
        cursor.execute(stmt)


def verify(cursor):
    cursor.execute("SELECT id, last_wake_at, wake_date, wake_count FROM quant.watch_digest_state")
    print("  摘要状态:", cursor.fetchall())


if __name__ == '__main__':
    from dotenv import load_dotenv
    from infrastructure.persistence.database.engine import get_engine
    load_dotenv()
    engine = get_engine()
    conn = engine.raw_connection()
    try:
        cursor = conn.cursor()
        print("迁移：盯盘摘要状态表")
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
