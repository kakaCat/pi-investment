"""
Session 服务 — agent session 事件摄入、查询与诊断

设计原则：返回洞察而非原始数据（diagnosis 附解读）
"""
import json
import structlog
from typing import Dict, Any, List, Optional
from infrastructure.persistence.database.base_repository import BaseRepository

logger = structlog.get_logger(__name__)

# 事件类型 → 会话计数器字段
_COUNTER_MAP = {
    "user_message": "message_count",
    "tool_call": "tool_call_count",
    "error": "error_count",
}


class SessionService:
    """Agent session 事件摄入与诊断服务"""

    def ingest_events(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """批量摄入事件（幂等：UNIQUE(session_key, seq)）

        Args:
            events: [{session_key, seq, event_type, payload, created_at}]

        Returns:
            {accepted, duplicates, skipped}
        """
        repo = BaseRepository()
        cursor = repo._get_cursor()
        accepted = duplicates = skipped = 0

        for ev in events:
            try:
                key = ev["session_key"]
                seq = int(ev["seq"])
                etype = ev["event_type"]
            except (KeyError, TypeError, ValueError):
                skipped += 1
                continue

            payload = ev.get("payload") or {}
            created_at = ev.get("created_at")

            # 先确保 session 行存在（事件表有外键）
            channel = payload.get("channel", "unknown")
            peer_id = str(payload.get("peerId", ""))
            agent_id = payload.get("agentId", "main")
            cursor.execute(
                """
                INSERT INTO quant.agent_sessions (session_key, channel, peer_id, agent_id, last_active_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (session_key) DO UPDATE SET
                  last_active_at = GREATEST(quant.agent_sessions.last_active_at, EXCLUDED.last_active_at)
                """,
                (key, channel, peer_id, agent_id, created_at),
            )

            cursor.execute(
                """
                INSERT INTO quant.agent_session_events (session_key, seq, event_type, payload, created_at)
                VALUES (%s, %s, %s, %s::jsonb, %s)
                ON CONFLICT (session_key, seq) DO NOTHING
                RETURNING id
                """,
                (key, seq, etype, json.dumps(payload), created_at),
            )
            row = cursor.fetchone()
            if row is None:
                duplicates += 1
                continue

            accepted += 1
            counter = _COUNTER_MAP.get(etype)
            if counter:
                cursor.execute(
                    f"UPDATE quant.agent_sessions SET {counter} = {counter} + 1 WHERE session_key = %s",
                    (key,),
                )

        repo.db.commit()
        return {"accepted": accepted, "duplicates": duplicates, "skipped": skipped}

    def list_sessions(self, channel: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        repo = BaseRepository()
        cursor = repo._get_cursor()
        if channel:
            cursor.execute(
                "SELECT * FROM quant.agent_sessions WHERE channel = %s ORDER BY last_active_at DESC LIMIT %s",
                (channel, limit),
            )
        else:
            cursor.execute(
                "SELECT * FROM quant.agent_sessions ORDER BY last_active_at DESC LIMIT %s",
                (limit,),
            )
        return [dict(r) for r in cursor.fetchall()]

    def get_session(self, session_key: str) -> Optional[Dict[str, Any]]:
        repo = BaseRepository()
        cursor = repo._get_cursor()
        cursor.execute("SELECT * FROM quant.agent_sessions WHERE session_key = %s", (session_key,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_events(self, session_key: str, event_type: Optional[str] = None,
                   limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        repo = BaseRepository()
        cursor = repo._get_cursor()
        if event_type:
            cursor.execute(
                """SELECT seq, event_type, payload, created_at FROM quant.agent_session_events
                   WHERE session_key = %s AND event_type = %s ORDER BY seq LIMIT %s OFFSET %s""",
                (session_key, event_type, limit, offset),
            )
        else:
            cursor.execute(
                """SELECT seq, event_type, payload, created_at FROM quant.agent_session_events
                   WHERE session_key = %s ORDER BY seq LIMIT %s OFFSET %s""",
                (session_key, limit, offset),
            )
        return [dict(r) for r in cursor.fetchall()]

    def get_diagnosis(self, session_key: str) -> Dict[str, Any]:
        """诊断：工具成功率、耗时、错误聚类、关联决策 + 洞察解读"""
        repo = BaseRepository()
        cursor = repo._get_cursor()

        cursor.execute(
            """SELECT
                 COUNT(*) FILTER (WHERE (payload->>'success')::boolean) AS ok,
                 COUNT(*) AS total,
                 COALESCE(AVG((payload->>'durationMs')::numeric), 0) AS avg_ms,
                 COALESCE(MAX((payload->>'durationMs')::numeric), 0) AS max_ms
               FROM quant.agent_session_events
               WHERE session_key = %s AND event_type = 'tool_call'""",
            (session_key,),
        )
        tool = dict(cursor.fetchone())
        total = int(tool.get("total") or 0)
        ok = int(tool.get("ok") or 0)
        success_rate = (ok / total) if total else None

        cursor.execute(
            """SELECT payload->>'message' AS message, COUNT(*) AS cnt
               FROM quant.agent_session_events
               WHERE session_key = %s AND event_type = 'error'
               GROUP BY message ORDER BY cnt DESC LIMIT 5""",
            (session_key,),
        )
        errors = [dict(r) for r in cursor.fetchall()]

        decisions: List[Dict[str, Any]] = []
        try:
            cursor.execute(
                """SELECT decision_id, decision_type, reasoning, evaluation_status, success
                   FROM quant.agent_decisions WHERE session_key = %s ORDER BY created_at DESC LIMIT 20""",
                (session_key,),
            )
            decisions = [dict(r) for r in cursor.fetchall()]
        except Exception as e:
            logger.warning(f"查询关联决策失败（不影响诊断）: {e}")
            repo.db.rollback()

        insight = self._build_insight(success_rate, total, tool, errors)

        return {
            "session_key": session_key,
            "tool_success_rate": success_rate,
            "tool_call_count": total,
            "avg_tool_duration_ms": round(float(tool.get("avg_ms") or 0)),
            "max_tool_duration_ms": int(tool.get("max_ms") or 0),
            "error_count": sum(int(e["cnt"]) for e in errors),
            "top_errors": errors,
            "decisions": decisions,
            "insight": insight,
        }

    @staticmethod
    def _build_insight(success_rate, total, tool, errors) -> str:
        if total == 0:
            return "本会话无工具调用记录。"
        parts = []
        if success_rate is not None and success_rate < 0.8:
            parts.append(f"工具成功率偏低（{success_rate:.0%}），建议检查失败工具的参数或数据源。")
        if float(tool.get("max_ms") or 0) > 10000:
            parts.append(f"存在慢工具调用（最大 {int(tool['max_ms'])}ms），建议排查超时原因。")
        if errors:
            parts.append(f"最高频错误：{errors[0]['message']}（{errors[0]['cnt']} 次）。")
        return " ".join(parts) if parts else f"会话健康：{total} 次工具调用，成功率 {success_rate:.0%}。"
