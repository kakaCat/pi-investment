"""Watch 状态类适配器（REQ-f08def P4，2026-09-11，w-c8cae280）

实现 domain/watch/ports.py 的两个端口：
  · IWatchDigestStateRepository   摘要门状态（上次唤醒/当日次数）
  · IWatchInterventionRepository  介入记账（agent 被唤醒介入的留痕与统计）

按 ADR-001（六边形架构）：**裸 SQL/ORM 只允许出现在适配器层**——应用层此前直接
get_engine()/text() 写这两张表属违规，2026-09-11 重构上收于此。
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy import text

logger = structlog.get_logger(__name__)


class WatchDigestStateRepository:
    """摘要门状态（quant.watch_digest_state，单行 id=1）"""

    def load_state(self) -> Dict[str, Any]:
        from infrastructure.persistence.database.engine import get_engine
        try:
            with get_engine().connect() as conn:
                row = conn.execute(text(
                    "SELECT last_wake_at, wake_date, wake_count "
                    "FROM quant.watch_digest_state WHERE id = 1"
                )).fetchone()
            if row is None:
                return {"last_wake_at": None, "wake_date": None, "wake_count": 0}
            return {"last_wake_at": row[0], "wake_date": row[1], "wake_count": int(row[2] or 0)}
        except Exception as e:
            logger.warning("摘要状态读取失败（按未唤醒处理）", error=str(e))
            return {"last_wake_at": None, "wake_date": None, "wake_count": 0}

    def save_wake(self, now: datetime) -> None:
        from infrastructure.persistence.database.engine import get_engine
        try:
            with get_engine().begin() as conn:
                conn.execute(text(
                    "INSERT INTO quant.watch_digest_state (id, last_wake_at, wake_date, wake_count, updated_at) "
                    "VALUES (1, :ts, :d, 1, NOW()) "
                    "ON CONFLICT (id) DO UPDATE SET "
                    "  last_wake_at = :ts, "
                    "  wake_count = CASE WHEN quant.watch_digest_state.wake_date = :d "
                    "                    THEN quant.watch_digest_state.wake_count + 1 ELSE 1 END, "
                    "  wake_date = :d, updated_at = NOW()"
                ), {"ts": now, "d": now.date()})
        except Exception as e:
            logger.error("摘要状态写入失败", error=str(e))


class WatchInterventionRepository:
    """介入记账（quant.watch_interventions + 规则价值账本计数）"""

    def count_today(self) -> int:
        from infrastructure.persistence.database.engine import get_engine
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
        try:
            with get_engine().begin() as conn:
                conn.execute(text(
                    "INSERT INTO quant.watch_interventions "
                    "(rule_id, symbol, intent, trigger_kind, outcome, trigger_ids, tokens, cost_yuan, decision_audit_id) "
                    "VALUES (:rid, :sym, :intent, :kind, :outcome, :tids, :tokens, :cost, :audit)"
                ), {"rid": rule_id, "sym": symbol, "intent": intent, "kind": trigger_kind,
                    "outcome": outcome,
                    "tids": ",".join(str(i) for i in (trigger_ids or [])),
                    "tokens": tokens, "cost": cost_yuan, "audit": decision_audit_id})
                if rule_id is not None:
                    conn.execute(text(
                        "UPDATE quant.watch_rules SET "
                        "  interventions = COALESCE(interventions, 0) + 1, "
                        "  tokens_cost = COALESCE(tokens_cost, 0) + :cost, "
                        "  last_value_at = CASE WHEN :valuable THEN NOW() ELSE last_value_at END "
                        "WHERE id = :rid"
                    ), {"cost": cost_yuan, "valuable": outcome in ("handled", "reviewed"), "rid": rule_id})
        except Exception as e:
            logger.error("介入记账失败", error=str(e), symbol=symbol)

    def summary_today(self) -> Dict[str, Any]:
        from infrastructure.persistence.database.engine import get_engine
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
