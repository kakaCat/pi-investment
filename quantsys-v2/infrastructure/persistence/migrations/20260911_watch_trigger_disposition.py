"""盯盘触发处置状态机（REQ-f08def，2026-09-11，w-c8cae280）

背景（实测证据）：
- quant.watch_triggers 近 200 条触发，agent_response **全为 null** —— 引擎喊了 200 声，
  无一声被处置；"触发→处置率" = 0%。触发只是提醒，没有终态就没有闭环。
- 噪声：同一规则同向多阈值在一次跌穿里重复通知（规则 #129 同时挂 <9.6 / <9.4，
  实测两条触发间隔 0.46 秒）；601600 单标的 6 条规则（跨窗口/跨账户）语义重合，
  一次跌穿触发 4+ 条。
- 分级缺失：13 条规则 action_hint 里没有 trigger_level。

本迁移做三件事（幂等，可重复执行）：
1) 给 quant.watch_triggers 增加处置字段：
     disposition        状态机当前态
     disposition_reason 处置说明（人/agent 写的理由，或系统归档原因）
     disposition_by     处置主体（system / agent:<window> / user）
     disposition_at     处置时间
     dup_of             被合并到哪条触发（去重溯源，指向 watch_triggers.id）
   状态取值：
     pending         待处置（需要人/agent 看一眼）
     auto_observed   机械归档：规则声明 action_on_trigger=observe/message，系统按预案观察
     deduped         去重合并：同标的同向在去重窗内已有触发，本条不再通知
     escalated       已升级进 agent 摘要队列（L2 或 escalation_policy 命中）
     handled         已处置（有动作）
     ignored         已知悉但不动作（必须带 reason）
     expired         超期未处置，由盘后清单兜底收敛
     legacy_unknown  状态机上线前的历史数据（不参与处置率统计，避免美化指标）
2) 历史回填：既有触发一律标 legacy_unknown（诚实：我们不知道当时有没有人看过）。
3) 分级补齐：enabled 且 action_hint 缺 trigger_level 的规则，按**规则自身语义**推断：
     action_on_trigger 为 buy/sell 或含 pnl_pct 条件（持仓止损止盈）→ L2 行动层（唤醒 agent）
     其余（observe/message/price_break 观察类）→ L1 观察层（直发飞书，不经 LLM）
   并同步 requires_agent（L2=True），避免"默认 L1"这种隐式行为。

用法：
  ./venv/bin/python infrastructure/persistence/migrations/20260911_watch_trigger_disposition.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DDL = [
    """ALTER TABLE quant.watch_triggers
         ADD COLUMN IF NOT EXISTS disposition VARCHAR(20) DEFAULT 'pending'""",
    """ALTER TABLE quant.watch_triggers
         ADD COLUMN IF NOT EXISTS disposition_reason TEXT""",
    """ALTER TABLE quant.watch_triggers
         ADD COLUMN IF NOT EXISTS disposition_by VARCHAR(50)""",
    """ALTER TABLE quant.watch_triggers
         ADD COLUMN IF NOT EXISTS disposition_at TIMESTAMP""",
    """ALTER TABLE quant.watch_triggers
         ADD COLUMN IF NOT EXISTS dup_of INTEGER""",
    """CREATE INDEX IF NOT EXISTS idx_watch_triggers_disposition
         ON quant.watch_triggers (disposition, triggered_at DESC)""",
    """CREATE INDEX IF NOT EXISTS idx_watch_triggers_symbol_time
         ON quant.watch_triggers (symbol, triggered_at DESC)""",
]

BACKFILL_LEGACY = """
UPDATE quant.watch_triggers
   SET disposition = 'legacy_unknown',
       disposition_reason = '状态机上线前的历史触发：当时无处置记录（REQ-f08def 迁移）',
       disposition_by = 'system'
 WHERE disposition IS NULL OR disposition = 'pending'
"""

# 分级补齐：按规则自身语义推断，避免"所有规则都走 agent"（用户的硬约束是 token 成本）
BACKFILL_TIER = """
UPDATE quant.watch_rules r
   SET action_hint = jsonb_set(
         COALESCE(r.action_hint, '{}'::jsonb),
         '{trigger_level}',
         to_jsonb(CASE
            WHEN COALESCE(r.action_hint->>'action_on_trigger','') IN ('buy','sell') THEN 'L2'
            WHEN r.conditions @> '[{"type":"pnl_pct"}]'::jsonb THEN 'L2'
            WHEN COALESCE(r.action_hint->>'action_on_trigger','') = 'message' THEN 'L0'
            ELSE 'L1'
          END),
         true)
 WHERE r.enabled IS TRUE
   AND (r.action_hint IS NULL OR r.action_hint->>'trigger_level' IS NULL)
"""

BACKFILL_REQUIRES_AGENT = """
UPDATE quant.watch_rules r
   SET action_hint = jsonb_set(
         COALESCE(r.action_hint, '{}'::jsonb),
         '{requires_agent}',
         to_jsonb(CASE WHEN r.action_hint->>'trigger_level' = 'L2' THEN 'true' ELSE 'false' END),
         true)
 WHERE r.enabled IS TRUE
   AND r.action_hint->>'trigger_level' IS NOT NULL
   AND r.action_hint->>'requires_agent' IS NULL
"""


def upgrade(cursor):
    for stmt in DDL:
        cursor.execute(stmt)
    cursor.execute(BACKFILL_LEGACY)
    print(f"  历史触发回填 legacy_unknown: {cursor.rowcount} 行")
    cursor.execute(BACKFILL_TIER)
    print(f"  规则分级补齐: {cursor.rowcount} 条")
    cursor.execute(BACKFILL_REQUIRES_AGENT)
    print(f"  requires_agent 补齐: {cursor.rowcount} 条")


def verify(cursor):
    cursor.execute("""SELECT disposition, COUNT(*) FROM quant.watch_triggers
                       GROUP BY disposition ORDER BY 2 DESC""")
    print("  触发处置状态分布:", cursor.fetchall())
    cursor.execute("""SELECT COALESCE(action_hint->>'trigger_level','<none>'), COUNT(*)
                        FROM quant.watch_rules WHERE enabled IS TRUE
                       GROUP BY 1 ORDER BY 2 DESC""")
    print("  启用规则分级分布:", cursor.fetchall())


if __name__ == '__main__':
    from dotenv import load_dotenv
    from infrastructure.persistence.database.engine import get_engine

    load_dotenv()
    engine = get_engine()
    conn = engine.raw_connection()
    try:
        cursor = conn.cursor()
        print("迁移：盯盘触发处置状态机")
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
