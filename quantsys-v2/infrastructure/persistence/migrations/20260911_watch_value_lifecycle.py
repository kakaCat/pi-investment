"""盯盘价值生命周期字段（REQ-f08def P1，RFC 014 v3 §7.1，2026-09-11，w-c8cae280）

为什么：RFC 014 v2/v3 都依赖这些字段，而现有 watch_rules 只有
symbol/conditions/context/cost_price/active_window/expires_at/account/notify_mode/
action_hint/escalation_policy——agent 无法知道「这条规则盯的是趋势还是买点、处于哪个
生命周期阶段、上次什么时候被复核、它贡献过多少价值」。缺这些，介入判据（§3）与
退出判据（§4）都落不了地。

幂等：ADD COLUMN IF NOT EXISTS；回填只更新空值。

用法：./venv/bin/python infrastructure/persistence/migrations/20260911_watch_value_lifecycle.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DDL = [
    "ALTER TABLE quant.watch_rules ADD COLUMN IF NOT EXISTS intent VARCHAR(30)",
    "ALTER TABLE quant.watch_rules ADD COLUMN IF NOT EXISTS lifecycle_stage VARCHAR(30) DEFAULT 'tracking'",
    "ALTER TABLE quant.watch_rules ADD COLUMN IF NOT EXISTS scope VARCHAR(20) DEFAULT 'symbol'",
    "ALTER TABLE quant.watch_rules ADD COLUMN IF NOT EXISTS target VARCHAR(60)",
    "ALTER TABLE quant.watch_rules ADD COLUMN IF NOT EXISTS linked_account VARCHAR(60)",
    "ALTER TABLE quant.watch_rules ADD COLUMN IF NOT EXISTS created_from VARCHAR(80)",
    "ALTER TABLE quant.watch_rules ADD COLUMN IF NOT EXISTS next_action_hint VARCHAR(160)",
    "ALTER TABLE quant.watch_rules ADD COLUMN IF NOT EXISTS last_reviewed_at TIMESTAMP",
    "ALTER TABLE quant.watch_rules ADD COLUMN IF NOT EXISTS review_interval_days INTEGER",
    "ALTER TABLE quant.watch_rules ADD COLUMN IF NOT EXISTS review_due_at TIMESTAMP",
    "ALTER TABLE quant.watch_rules ADD COLUMN IF NOT EXISTS burst_count_window INTEGER DEFAULT 0",
    "ALTER TABLE quant.watch_rules ADD COLUMN IF NOT EXISTS valuable_actions INTEGER DEFAULT 0",
    "ALTER TABLE quant.watch_rules ADD COLUMN IF NOT EXISTS valuable_reviews INTEGER DEFAULT 0",
    "ALTER TABLE quant.watch_rules ADD COLUMN IF NOT EXISTS interventions INTEGER DEFAULT 0",
    "ALTER TABLE quant.watch_rules ADD COLUMN IF NOT EXISTS noise_triggers INTEGER DEFAULT 0",
    "ALTER TABLE quant.watch_rules ADD COLUMN IF NOT EXISTS tokens_cost DOUBLE PRECISION DEFAULT 0",
    "ALTER TABLE quant.watch_rules ADD COLUMN IF NOT EXISTS last_value_at TIMESTAMP",
]

# 按现有规则语义回填 intent：
#   action_on_trigger=sell 且含 pnl_pct 下穿越 → exit_stop（止损）
#   action_on_trigger=sell 且含 pnl_pct 上穿越 → exit_take_profit（止盈）
#   action_on_trigger=sell 其余 → exit_reduce（减仓/清仓）
#   action_on_trigger=buy  → entry（等买）
#   其余（observe/message/未声明）→ trend_observe（趋势观察）
BACKFILL_INTENT = """
UPDATE quant.watch_rules r SET intent = CASE
  WHEN COALESCE(r.action_hint->>'action_on_trigger','') = 'sell'
       AND r.conditions @> '[{"type":"pnl_pct","params":{"direction":"below"}}]'::jsonb
    THEN 'exit_stop'
  WHEN COALESCE(r.action_hint->>'action_on_trigger','') = 'sell'
       AND r.conditions @> '[{"type":"pnl_pct","params":{"direction":"above"}}]'::jsonb
    THEN 'exit_take_profit'
  WHEN COALESCE(r.action_hint->>'action_on_trigger','') = 'sell' THEN 'exit_reduce'
  WHEN COALESCE(r.action_hint->>'action_on_trigger','') = 'buy'  THEN 'entry'
  ELSE 'trend_observe'
END
WHERE r.intent IS NULL
"""

# scope：有归属账户的视作持仓级，否则标的级
BACKFILL_SCOPE = """
UPDATE quant.watch_rules r SET scope = CASE
  WHEN r.account IS NOT NULL THEN 'position'
  ELSE 'symbol'
END
WHERE r.scope IS NULL
"""


def upgrade(cursor):
    for stmt in DDL:
        cursor.execute(stmt)
    cursor.execute(BACKFILL_INTENT)
    print('  intent 回填:', cursor.rowcount, '条')
    cursor.execute(BACKFILL_SCOPE)
    print('  scope 回填:', cursor.rowcount, '条')


def verify(cursor):
    cursor.execute("SELECT COALESCE(intent,'<null>'), COUNT(*) FROM quant.watch_rules WHERE enabled IS TRUE GROUP BY 1 ORDER BY 2 DESC")
    print('  启用规则 intent 分布:', cursor.fetchall())
    cursor.execute("SELECT COALESCE(scope,'<null>'), COUNT(*) FROM quant.watch_rules WHERE enabled IS TRUE GROUP BY 1")
    print('  启用规则 scope 分布:', cursor.fetchall())


if __name__ == '__main__':
    from dotenv import load_dotenv
    from infrastructure.persistence.database.engine import get_engine
    load_dotenv()
    engine = get_engine()
    conn = engine.raw_connection()
    try:
        cursor = conn.cursor()
        print('迁移：盯盘价值生命周期字段（REQ-f08def P1）')
        upgrade(cursor)
        conn.commit()
        verify(cursor)
        print('✓ 迁移完成')
    except Exception as e:
        conn.rollback()
        print('✗ 迁移失败:', e)
        raise
    finally:
        cursor.close()
        conn.close()
