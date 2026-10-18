"""盯盘触发处置人列加宽（2026-10-19，fix/watch-disposition-by-width）

背景（实测证据）：
- quant.watch_triggers.disposition_by 定义为 VARCHAR(50)
  （20260911_watch_trigger_disposition 建立）。
- 生产实测 15 条顶格值全为 agent 会话 ID `investor-session-f0101ceb-bf3e487e8ed2a36089ac4788`
  —— 恰 50 字符 = 列上限，真实会话 ID 尾部被裁。裁剪点不在本服务：
  PG 对超宽 varchar 是报错而非静默截断，路由层 `by=str(payload.get('by') or 'agent')`
  无切片直传（watch_async.py PATCH /api/watch/triggers/{id}），故值是调用方
  （agent 链路）为适配 50 宽度先自裁再发——v2 侧加宽消除这一约束张力。
- 处置人是审计归因字段（谁处置的）。截断破坏溯源性（会话 ID 尾码丢失后
  无法与 agent 会话记录对账）。
- 口径澄清：原登记"watch_triggers.condition varchar(50)"系张冠李戴——
  condition 列是 JSONB 无宽度问题；真正的 varchar(50) 是 disposition_by。

本迁移做一件事（幂等，可重复执行）：
1) disposition_by 加宽 VARCHAR(50) → VARCHAR(120)。
   仅加宽（保未来写入完整）；历史顶格截断值的尾部已丢失，不可恢复。

用法：
  PYTHONPATH=. ./venv/bin/python infrastructure/persistence/migrations/20261019_watch_triggers_disposition_by_widen.py
"""
import sys

DDL = [
    """ALTER TABLE quant.watch_triggers
         ALTER COLUMN disposition_by TYPE VARCHAR(120)""",
]


def upgrade(cursor):
    for stmt in DDL:
        cursor.execute(stmt)
    print(f"  disposition_by 加宽 50→120: 执行 {len(DDL)} 条 DDL")


def verify(cursor):
    cursor.execute("""SELECT data_type, character_maximum_length
                       FROM information_schema.columns
                      WHERE table_schema='quant' AND table_name='watch_triggers'
                        AND column_name='disposition_by'""")
    print("  列定义:", cursor.fetchall())
    cursor.execute("""SELECT COALESCE(max(char_length(disposition_by)),0) AS maxlen,
                             count(*) FILTER (WHERE char_length(disposition_by)>=50) AS at_cap
                        FROM quant.watch_triggers WHERE disposition_by IS NOT NULL""")
    print("  长度分布(maxlen, 顶格行数):", cursor.fetchall())


if __name__ == '__main__':
    from dotenv import load_dotenv
    from infrastructure.persistence.database.engine import get_engine

    load_dotenv()
    engine = get_engine()
    conn = engine.raw_connection()
    try:
        cursor = conn.cursor()
        print("迁移：盯盘触发处置人列加宽")
        upgrade(cursor)
        conn.commit()
        verify(cursor)
        print("✓ 迁移完成")
    except Exception as e:
        conn.rollback()
        print(f"✗ 迁移失败: {e}")
        raise
    finally:
        cursor.close()
        conn.close()
