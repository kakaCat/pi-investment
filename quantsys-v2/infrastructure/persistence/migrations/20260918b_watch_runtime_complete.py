"""盯盘运行态补完：影子起始时间 + 去重窗 + 事件窗口 + 价格历史（REQ-c9f899 返工 B+C，2026-09-18）

为什么需要（对应 implementation.md §6 待接线项 9/10 与 §5.2 的 t12 欠账）：
  1) t3 只持久化了「闩锁 + 冷却基准」，去重窗 recent_notified、触发事件窗口
     trigger_events、velocity 用的 price_history 仍全在进程内存 —— 重启后：
       · 去重窗清零 → 同标的同向在窗内被重复推送；
       · 事件窗口清零 → 频率/共振统计从 0 起算，自愈阈值误判；
       · 价格历史清零 → velocity 条件有 ~30 分钟冷启动盲区（不判定）。
  2) 影子模式起始时间只由 shadow_mode_clock 写进程 env，重启即丢 —— 进程不满 48h
     时会把「影子已挂很久」读成「刚挂上」，超期告警被无限推迟（实测已挂 7 天无人知）。

本迁移是 **additive**：只新增表与列，不改既有列语义、不删任何东西（R-020）。
幂等：表用 CREATE TABLE IF NOT EXISTS、列用 ADD COLUMN IF NOT EXISTS、索引用
CREATE INDEX IF NOT EXISTS，且每项都先查 information_schema —— 重复执行的变更数应为 0。

用法（**由父 agent 在真库执行，子任务不跑**）：
  ./venv/bin/python infrastructure/persistence/migrations/20260918b_watch_runtime_complete.py
  （第二次执行应打印：变更数 0）
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCHEMA = 'quant'

# ── 新表（三张轻量表：去重窗 / 触发事件窗口 / 价格历史）────────────────────
TABLES = [
    (
        'watch_runtime_dedup',
        """CREATE TABLE IF NOT EXISTS quant.watch_runtime_dedup (
             symbol VARCHAR(32) NOT NULL,
             direction VARCHAR(32) NOT NULL,
             notified_at TIMESTAMPTZ NOT NULL,
             trigger_id INTEGER,
             rule_id INTEGER,
             updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
             PRIMARY KEY (symbol, direction)
           )""",
    ),
    (
        'watch_trigger_events',
        """CREATE TABLE IF NOT EXISTS quant.watch_trigger_events (
             triggered_at TIMESTAMPTZ NOT NULL,
             rule_id INTEGER NOT NULL,
             symbol VARCHAR(32) NOT NULL,
             PRIMARY KEY (triggered_at, rule_id, symbol)
           )""",
    ),
    (
        'watch_price_history',
        """CREATE TABLE IF NOT EXISTS quant.watch_price_history (
             symbol VARCHAR(32) NOT NULL,
             ts TIMESTAMPTZ NOT NULL,
             price DOUBLE PRECISION NOT NULL,
             PRIMARY KEY (symbol, ts)
           )""",
    ),
]

# ── 既有表加列（additive）──────────────────────────────────────────────
# digest_shadow_since：影子模式**首次**进入的时间（跨重启保持，不再由 env 独占）。
COLUMNS = [
    ('watch_runtime_meta', 'digest_shadow_since', 'TIMESTAMPTZ'),
]

# ── 索引（裁剪/查询用）─────────────────────────────────────────────────
INDEXES = [
    ('idx_watch_runtime_dedup_notified', 'quant.watch_runtime_dedup (notified_at)'),
    ('idx_watch_trigger_events_ts', 'quant.watch_trigger_events (triggered_at)'),
    ('idx_watch_price_history_ts', 'quant.watch_price_history (ts)'),
]


def _table_exists(cursor, table: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema = %s AND table_name = %s", (SCHEMA, table))
    return cursor.fetchone() is not None


def _column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s AND column_name = %s",
        (SCHEMA, table, column))
    return cursor.fetchone() is not None


def _index_exists(cursor, index: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM pg_indexes WHERE schemaname = %s AND indexname = %s",
        (SCHEMA, index))
    return cursor.fetchone() is not None


def upgrade(cursor) -> int:
    """执行变更，返回本次实际变更数（幂等：重复执行为 0）。"""
    changes = 0

    # 前置检查：watch_runtime_meta 由 20260918_watch_todo_loop.py 创建，本迁移只给它加列。
    # 表不存在 = 前置迁移没跑——响亮失败，绝不静默跳过（跳过会让"影子时间已落库"成为假象）。
    if not _table_exists(cursor, 'watch_runtime_meta'):
        raise RuntimeError(
            'quant.watch_runtime_meta 不存在：请先执行 20260918_watch_todo_loop.py')

    for name, ddl in TABLES:
        if not _table_exists(cursor, name):
            cursor.execute(ddl)
            changes += 1
            print('  + 建表 quant.%s' % name)

    for table, column, coltype in COLUMNS:
        if not _column_exists(cursor, table, column):
            cursor.execute(
                'ALTER TABLE quant.%s ADD COLUMN IF NOT EXISTS %s %s'
                % (table, column, coltype))
            changes += 1
            print('  + 加列 quant.%s.%s' % (table, column))

    for index, target in INDEXES:
        if not _index_exists(cursor, index):
            cursor.execute('CREATE INDEX IF NOT EXISTS %s ON %s' % (index, target))
            changes += 1
            print('  + 建索引 %s' % index)

    # 运行态 meta 单行存在性（列加在该行上；与 20260918 迁移同款幂等）
    cursor.execute(
        'INSERT INTO quant.watch_runtime_meta (id) VALUES (1) ON CONFLICT (id) DO NOTHING')

    return changes


def verify(cursor):
    for name, _ in TABLES:
        ok = _table_exists(cursor, name)
        print('  表 quant.%-24s %s' % (name, '存在' if ok else '缺失'))
    for table, column, _ in COLUMNS:
        ok = _column_exists(cursor, table, column)
        print('  列 %-24s.%-20s %s' % (table, column, '存在' if ok else '缺失'))
    for index, _ in INDEXES:
        ok = _index_exists(cursor, index)
        print('  索引 %-30s %s' % (index, '存在' if ok else '缺失'))


if __name__ == '__main__':
    from dotenv import load_dotenv
    from infrastructure.persistence.database.engine import get_engine
    load_dotenv()
    engine = get_engine()
    conn = engine.raw_connection()
    try:
        cursor = conn.cursor()
        print('迁移：盯盘运行态补完（REQ-c9f899 返工 B+C）')
        n = upgrade(cursor)
        conn.commit()
        verify(cursor)
        print('变更数 %d' % n)
        print('✓ 完成' if n else '✓ 完成（无变更，已是目标结构）')
    except Exception as e:
        conn.rollback()
        print('✗ 失败:', e)
        raise
    finally:
        cursor.close()
        conn.close()
