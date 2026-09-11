"""迁移：事件表扩展列（政策/个股事件源，RFC 015 §3.5，REQ-cf627b，P3，2026-09-11）

为什么需要：
  RFC 015 缺口②（无政策/个股事件源）——2026-09-11 农业崩盘归因 100% 依赖 web_search 新闻；
  quant.event_calendar 原有 67 行**全是宏观**（cpi_ppi/pmi/lpr/fomc/nbs/futures_delivery），
  既无政策文件也无个股财报/解禁/定增。既有表结构只够装"宏观日历"：
  单值 symbol 列装不下多标的、没有 scope 区分影响范围、没有 evidence_hash 做幂等去重。

**扩展而非重建**（RFC §3.5 明确要求）：
  既有 67 行宏观事件与其消费方（每日 16:45 event_calendar_check → 飞书提醒、
  /api/events/upcoming）必须原样可用，故新增列一律**可空或带默认值**，
  不改既有列、不动既有数据（scope 默认 'macro' 正好与既有语义一致）。

新增 4 列：
  scope         VARCHAR(16) NOT NULL DEFAULT 'macro'   macro/industry/individual
  symbols       JSONB DEFAULT '[]'                    多标的（个股事件；宏观为 []）
  source_url    TEXT                                  原文链接（可追溯，R-013 数据来源标注）
  evidence_hash VARCHAR(64)                           幂等去重锚（领域层 sha1(scope|type|symbols|日期|归一标题)）

索引：
  uq_event_calendar_evidence_hash  局部唯一索引（WHERE evidence_hash IS NOT NULL），
     保证"重复 ingest 不产生重复行"（RFC §5 幂等验收）——用**局部**是因为既有 67 行
     evidence_hash 为 NULL，全量唯一索引在 PG 下虽允许多个 NULL，但局部索引语义更明确。
  idx_event_calendar_scope         按 scope+日期查询（feed 端点主查询路径）
  idx_event_calendar_symbols       GIN(symbols)，支撑 symbols @> '["600150"]' 的个股查询

用法：./venv/bin/python infrastructure/persistence/migrations/20260912_events_event_source.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DDL = [
    "ALTER TABLE quant.event_calendar ADD COLUMN IF NOT EXISTS scope VARCHAR(16) DEFAULT 'macro'",
    "UPDATE quant.event_calendar SET scope = 'macro' WHERE scope IS NULL",
    "ALTER TABLE quant.event_calendar ALTER COLUMN scope SET DEFAULT 'macro'",
    "ALTER TABLE quant.event_calendar ALTER COLUMN scope SET NOT NULL",
    "ALTER TABLE quant.event_calendar ADD COLUMN IF NOT EXISTS symbols JSONB DEFAULT '[]'::jsonb",
    "UPDATE quant.event_calendar SET symbols = '[]'::jsonb WHERE symbols IS NULL",
    "ALTER TABLE quant.event_calendar ADD COLUMN IF NOT EXISTS source_url TEXT",
    "ALTER TABLE quant.event_calendar ADD COLUMN IF NOT EXISTS evidence_hash VARCHAR(64)",
    """CREATE UNIQUE INDEX IF NOT EXISTS uq_event_calendar_evidence_hash
         ON quant.event_calendar (evidence_hash) WHERE evidence_hash IS NOT NULL""",
    "CREATE INDEX IF NOT EXISTS idx_event_calendar_scope ON quant.event_calendar (scope, event_date)",
    """CREATE INDEX IF NOT EXISTS idx_event_calendar_symbols
         ON quant.event_calendar USING GIN (symbols)""",
]

# 既有 67 行不受影响的口径快照（迁移前后比对）
# 迁移前：新列还不存在，只能统计全表；迁移后：用 evidence_hash IS NULL 圈出"既有行"再统计，
# 两者必须完全一致——这是"扩展而非重建、既有数据不被破坏"的硬证据。
_BASELINE_PRE = """
    SELECT event_type, status, count(*) FROM quant.event_calendar GROUP BY 1, 2 ORDER BY 1, 2
"""
_BASELINE_POST = """
    SELECT event_type, status, count(*) FROM quant.event_calendar
     WHERE evidence_hash IS NULL GROUP BY 1, 2 ORDER BY 1, 2
"""


def _has_column(cursor, column: str) -> bool:
    cursor.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_schema='quant' AND table_name='event_calendar' AND column_name=%s
    """, (column,))
    return cursor.fetchone() is not None


def upgrade(cursor):
    for stmt in DDL:
        cursor.execute(stmt)


def verify(cursor):
    cursor.execute("SELECT count(*) FROM quant.event_calendar")
    print('  quant.event_calendar 总行数:', cursor.fetchone()[0])
    cursor.execute("""
        SELECT column_name, data_type, is_nullable, column_default
          FROM information_schema.columns
         WHERE table_schema='quant' AND table_name='event_calendar'
           AND column_name IN ('scope','symbols','source_url','evidence_hash')
         ORDER BY column_name
    """)
    print('  新增列:')
    for row in cursor.fetchall():
        print('   ', row)
    cursor.execute("""
        SELECT indexname FROM pg_indexes
         WHERE schemaname='quant' AND tablename='event_calendar' ORDER BY indexname
    """)
    print('  索引:', [r[0] for r in cursor.fetchall()])
    cursor.execute(_BASELINE_POST)
    print('  既有（evidence_hash IS NULL）行分布:')
    for row in cursor.fetchall():
        print('   ', row)
    cursor.execute("SELECT scope, count(*) FROM quant.event_calendar GROUP BY 1 ORDER BY 1")
    print('  按 scope 分布:', cursor.fetchall())


if __name__ == '__main__':
    from dotenv import load_dotenv
    from infrastructure.persistence.database.engine import get_engine
    load_dotenv()
    engine = get_engine()
    conn = engine.raw_connection()
    cursor = conn.cursor()
    try:
        print('迁移：事件表扩展列（RFC 015 §3.5，P3）')
        # 幂等口径：首次执行时 evidence_hash 还不存在，只能统计全表；
        # 重复执行（或表已被 P3 写入过数据）时用 evidence_hash IS NULL 圈出"既有行"再统计——
        # 否则第二次跑迁移会把新采集的事件也算进 baseline，自比对本就不同（实测踩坑）。
        already_applied = _has_column(cursor, 'evidence_hash')
        cursor.execute(_BASELINE_POST if already_applied else _BASELINE_PRE)
        baseline = cursor.fetchall()
        print(f'  迁移前既有行分布（{("增量校验口径" if already_applied else "首跑口径")}）:', baseline)
        upgrade(cursor)
        conn.commit()
        cursor.execute(_BASELINE_POST)
        after = cursor.fetchall()
        print('  迁移后既有行分布:', after)
        assert baseline == after, '既有数据被破坏：迁移前后分布不一致'
        print('  ✓ 既有行未被破坏（分布一致）')
        verify(cursor)
        print('✓ 完成')
    except Exception as e:
        conn.rollback()
        print('✗ 失败:', e)
        raise
    finally:
        cursor.close()
        conn.close()
