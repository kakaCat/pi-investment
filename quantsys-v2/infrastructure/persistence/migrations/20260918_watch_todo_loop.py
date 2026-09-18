"""盯盘闭环底座：待办 / 运行态 / 规则变更审计 / 回执（REQ-c9f899 t1，2026-09-18）

为什么需要：
  1) 现有触发只有"状态位"（disposition）没有"待办"——172 条 escalated/pending/meta_review
     无人消费，正是因为缺少"谁在什么时候必须处置完"的载体（需求 I1/I3/I4）。
  2) 闩锁/冷却/价格历史全在进程内存，重启即丢——实测单日触发 23 次 > 1800s 冷却理论上限
     16 次，冷却形同虚设（需求 R10）。
  3) 规则变更（自愈与人工修复）必须可审计、可反向应用（需求 R6）。

本迁移是 **additive**：只新增表与列，不改既有列语义、不删任何东西（R-020）。
幂等：表用 CREATE TABLE IF NOT EXISTS、列用 ADD COLUMN IF NOT EXISTS；重复执行的变更数应为 0。

用法：
  ./venv/bin/python infrastructure/persistence/migrations/20260918_watch_todo_loop.py
  （第二次执行应打印：变更数 0）
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SCHEMA = 'quant'

# ── 新表（四张核心表 + 一张运行态单行 meta）─────────────────────────────
TABLES = [
    (
        'watch_todos',
        """CREATE TABLE IF NOT EXISTS quant.watch_todos (
             id SERIAL PRIMARY KEY,
             trigger_id INTEGER REFERENCES quant.watch_triggers(id) ON DELETE SET NULL,
             rule_id INTEGER,
             symbol VARCHAR(20) NOT NULL,
             account VARCHAR(64),
             level VARCHAR(2) NOT NULL CHECK (level IN ('P0','P1','P2','P3')),
             flow_state VARCHAR(2) NOT NULL CHECK (flow_state IN ('L1','L2','L3')),
             owner_kind VARCHAR(8) CHECK (owner_kind IN ('agent','user')),
             owner_ref VARCHAR(64),
             autonomy VARCHAR(16) CHECK (autonomy IN ('autonomous','remind_only')),
             sla_seconds INTEGER NOT NULL,
             due_at TIMESTAMPTZ NOT NULL,
             claimed_at TIMESTAMPTZ,
             closed_at TIMESTAMPTZ,
             terminal VARCHAR(16) CHECK (terminal IN ('handled','ignored','expired')),
             close_reason TEXT,
             next_condition TEXT,
             action_kind VARCHAR(24),
             decision_audit_id VARCHAR(64),
             escalate_count INTEGER NOT NULL DEFAULT 0,
             created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
             updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
             CONSTRAINT watch_todos_closed_pair CHECK ((terminal IS NULL) = (closed_at IS NULL)),
             CONSTRAINT watch_todos_ignored_needs_next CHECK (terminal IS NULL OR terminal <> 'ignored' OR next_condition IS NOT NULL),
             CONSTRAINT watch_todos_action_needs_audit CHECK (
                 terminal IS NULL OR action_kind IS NULL OR action_kind NOT IN ('trade','rule_change')
                 OR decision_audit_id IS NOT NULL)
           )""",
    ),
    (
        'watch_runtime_state',
        """CREATE TABLE IF NOT EXISTS quant.watch_runtime_state (
             rule_id INTEGER NOT NULL,
             cond_idx INTEGER NOT NULL,
             latched BOOLEAN NOT NULL DEFAULT FALSE,
             last_triggered_at TIMESTAMPTZ,
             cooldown_effective_sec INTEGER,
             updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
             PRIMARY KEY (rule_id, cond_idx)
           )""",
    ),
    (
        'watch_runtime_meta',
        """CREATE TABLE IF NOT EXISTS quant.watch_runtime_meta (
             id INTEGER PRIMARY KEY,
             heartbeat_at TIMESTAMPTZ,
             state_date DATE,
             event_watermark TIMESTAMPTZ,
             updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
           )""",
    ),
    (
        'watch_rule_changes',
        """CREATE TABLE IF NOT EXISTS quant.watch_rule_changes (
             id SERIAL PRIMARY KEY,
             rule_id INTEGER NOT NULL,
             changed_by VARCHAR(16) NOT NULL CHECK (changed_by IN ('agent','user','system')),
             change_kind VARCHAR(24) NOT NULL,
             before JSONB,
             after JSONB,
             reason TEXT NOT NULL,
             trigger_id INTEGER,
             todo_id INTEGER,
             decision_audit_id VARCHAR(64),
             created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
           )""",
    ),
    (
        'watch_receipts',
        """CREATE TABLE IF NOT EXISTS quant.watch_receipts (
             id SERIAL PRIMARY KEY,
             todo_id INTEGER NOT NULL,
             kind VARCHAR(16) NOT NULL CHECK (kind IN ('escalate','result','timeout','suppressed')),
             channel VARCHAR(32),
             delivery_status VARCHAR(16),
             message_id VARCHAR(64),
             payload_digest VARCHAR(64) NOT NULL,
             created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
           )""",
    ),
]

# ── 既有表加列（additive）──────────────────────────────────────────────
COLUMNS = [
    ('watch_triggers', 'metric', 'VARCHAR(24)'),
    ('watch_triggers', 'metric_unit', 'VARCHAR(12)'),
    ('watch_triggers', 'level', 'VARCHAR(2)'),
    ('watch_triggers', 'todo_id', 'INTEGER'),
    ('watch_triggers', 'suppressed', 'BOOLEAN DEFAULT FALSE'),
    ('watch_rules', 'noise_state', 'VARCHAR(16)'),
    ('watch_rules', 'suppress_until', 'TIMESTAMP'),
    ('watch_rules', 'self_heal_count', 'INTEGER DEFAULT 0'),
    ('watch_rules', 'last_repair_at', 'TIMESTAMP'),
]

# ── 索引 ───────────────────────────────────────────────────────────────
INDEXES = [
    ('idx_watch_todos_overdue', 'quant.watch_todos (terminal, due_at)'),
    ('idx_watch_todos_account', 'quant.watch_todos (account, level, terminal)'),
    ('idx_watch_todos_rule', 'quant.watch_todos (rule_id, created_at)'),
    ('idx_watch_receipts_todo', 'quant.watch_receipts (todo_id, created_at)'),
    ('idx_watch_rule_changes_rule', 'quant.watch_rule_changes (rule_id, created_at)'),
    ('idx_watch_runtime_state_updated', 'quant.watch_runtime_state (updated_at)'),
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

    # 运行态 meta 单行（幂等：ON CONFLICT DO NOTHING）
    cursor.execute(
        'INSERT INTO quant.watch_runtime_meta (id) VALUES (1) ON CONFLICT (id) DO NOTHING')

    return changes


def verify(cursor):
    for name, _ in TABLES:
        ok = _table_exists(cursor, name)
        print('  表 quant.%-22s %s' % (name, '存在' if ok else '缺失'))
    for table, column, _ in COLUMNS:
        ok = _column_exists(cursor, table, column)
        print('  列 %-22s.%-18s %s' % (table, column, '存在' if ok else '缺失'))


if __name__ == '__main__':
    from dotenv import load_dotenv
    from infrastructure.persistence.database.engine import get_engine
    load_dotenv()
    engine = get_engine()
    conn = engine.raw_connection()
    try:
        cursor = conn.cursor()
        print('迁移：盯盘闭环底座（REQ-c9f899 t1）')
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
