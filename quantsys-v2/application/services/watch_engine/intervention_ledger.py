"""介入记账（REQ-f08def P4，2026-09-11，w-c8cae280）

职责：把"agent 被唤醒介入多少次、为什么介入、结果如何、花了多少"落库。

为什么必须落库（实测缺陷）：介入判据的每日预算原用进程内存计数——今天重启一次就清零重计，
escalated 计数冲到 18，远超预算 8，预算形同虚设。落库后才谈得上"成本与利润一致"。
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)


class InterventionLedger:

    def count_today(self) -> int:
        """当日介入次数（预算门用）。失败返回 0（宁可放行一次，也不因记账故障堵死风控）。"""
        from infrastructure.persistence.database.engine import get_engine
        from sqlalchemy import text
        try:
            with get_engine().connect() as conn:
                return int(conn.execute(text(
                    "SELECT count(*) FROM quant.watch_interventions WHERE created_at >= CURRENT_DATE"
                )).scalar() or 0)
        except Exception as e:
            logger.warning("介入计数读取失败（按 0 处理）", error=str(e))
            return 0

    def record(self, symbol: str, intent: Optional[str] = None, rule_id: Optional[int] = None,
               trigger_kind: str = "price", outcome: str = "escalated",
               trigger_ids: Optional[List[int]] = None, tokens: Optional[int] = None,
               cost_yuan: float = 0.0, decision_audit_id: Optional[str] = None) -> None:
        from infrastructure.persistence.database.engine import get_engine
        from sqlalchemy import text
        try:
            with get_engine().begin() as conn:
                conn.execute(text("""
                    INSERT INTO quant.watch_interventions
                      (rule_id, symbol, intent, trigger_kind, outcome, trigger_ids, tokens, cost_yuan, decision_audit_id)
                    VALUES (:rid, :sym, :intent, :kind, :outcome, :tids, :tokens, :cost, :audit)
                """), {"rid": rule_id, "sym": symbol, "intent": intent, "kind": trigger_kind,
                       "outcome": outcome,
                       "tids": ",".join(str(i) for i in (trigger_ids or [])),
                       "tokens": tokens, "cost": cost_yuan, "audit": decision_audit_id})
                if rule_id is not None:
                    conn.execute(text("""
                        UPDATE quant.watch_rules
                           SET interventions = COALESCE(interventions, 0) + 1,
                               tokens_cost = COALESCE(tokens_cost, 0) + :cost,
                               last_value_at = CASE WHEN :valuable THEN NOW() ELSE last_value_at END
                         WHERE id = :rid
                    """), {"cost": cost_yuan, "valuable": outcome in ("handled", "reviewed"), "rid": rule_id})
        except Exception as e:
            logger.error("介入记账失败", error=str(e), symbol=symbol)

    def summary_today(self) -> Dict[str, Any]:
        """当日介入概览（复盘用：单位唤醒产出 = 有价值动作 / 介入次数）"""
        from infrastructure.persistence.database.engine import get_engine
        from sqlalchemy import text
        try:
            with get_engine().connect() as conn:
                rows = conn.execute(text(
                    "SELECT outcome, count(*) FROM quant.watch_interventions "
                    "WHERE created_at >= CURRENT_DATE GROUP BY 1"
                )).fetchall()
            by_outcome = {r[0]: int(r[1]) for r in rows}
            total = sum(by_outcome.values())
            valuable = by_outcome.get("handled", 0) + by_outcome.get("reviewed", 0)
            return {"interventions_today": total, "by_outcome": by_outcome,
                    "valuable_actions": valuable,
                    "yield_per_wake": round(valuable / total, 3) if total else None}
        except Exception as e:
            logger.warning("介入概览读取失败", error=str(e))
            return {"interventions_today": 0, "by_outcome": {}, "valuable_actions": 0, "yield_per_wake": None}
