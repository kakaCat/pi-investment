"""
Session 服务 — agent session 事件摄入、查询与诊断

设计原则：返回洞察而非原始数据（diagnosis 附解读）
"""
import json
import structlog
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

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
        from infrastructure.persistence.database.engine import db_cursor
        with db_cursor(commit=True) as cursor:
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

        return {"accepted": accepted, "duplicates": duplicates, "skipped": skipped}

    def list_sessions(self, channel: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        from infrastructure.persistence.database.engine import db_cursor
        with db_cursor() as cursor:
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
        from infrastructure.persistence.database.engine import db_cursor
        with db_cursor() as cursor:
            cursor.execute("SELECT * FROM quant.agent_sessions WHERE session_key = %s", (session_key,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_events(self, session_key: str, event_type: Optional[str] = None,
                   limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        from infrastructure.persistence.database.engine import db_cursor
        with db_cursor() as cursor:
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
        from infrastructure.persistence.database.engine import db_cursor
        with db_cursor() as cursor:
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

    def ai_diagnosis(self, session_key: str, refresh: bool = False) -> Dict[str, Any]:
        """AI 诊断：压缩事件流 → DeepSeek 三段分析 → 缓存到 agent_sessions

        Returns:
            {analysis, generated_at, cached}
        """
        from infrastructure.persistence.database.engine import db_cursor
        
        # 缓存命中
        if not refresh:
            with db_cursor() as cursor:
                cursor.execute(
                    "SELECT ai_diagnosis, ai_diagnosis_at FROM quant.agent_sessions WHERE session_key = %s",
                    (session_key,),
                )
                row = cursor.fetchone()
                if row and row['ai_diagnosis']:
                    return {
                        'analysis': row['ai_diagnosis'].get('analysis', ''),
                        'generated_at': row['ai_diagnosis_at'].isoformat() if row['ai_diagnosis_at'] else None,
                        'cached': True,
                    }

        events = self.get_events(session_key, limit=500)
        prompt = self._build_diagnosis_prompt(session_key, events)

        from application.services.llm_service import chat_completion
        analysis = chat_completion(prompt)

        now = datetime.now(timezone.utc)
        with db_cursor(commit=True) as cursor:
            cursor.execute(
                """UPDATE quant.agent_sessions
                   SET ai_diagnosis = %s::jsonb, ai_diagnosis_at = %s
                   WHERE session_key = %s""",
                (json.dumps({'analysis': analysis}), now, session_key),
            )

        return {'analysis': analysis, 'generated_at': now.isoformat(), 'cached': False}

    @staticmethod
    def _build_diagnosis_prompt(session_key: str, events: List[Dict[str, Any]]) -> str:
        """压缩事件流为 ≤4K token 的诊断 prompt"""
        lines = [f"请诊断以下 AI 投资助手的工作会话（{session_key}）：\n"]
        tool_stats: Dict[str, Dict[str, int]] = {}

        for e in events:
            etype = e['event_type']
            p = e['payload'] or {}
            if etype == 'user_message':
                lines.append(f"用户: {str(p.get('text', ''))[:200]}")
            elif etype == 'assistant_reply':
                lines.append(f"助手回复: {str(p.get('text', ''))[:200]}")
            elif etype == 'tool_call':
                name = p.get('toolName', 'unknown')
                stat = tool_stats.setdefault(name, {'ok': 0, 'fail': 0, 'max_ms': 0})
                stat['ok' if p.get('success') else 'fail'] += 1
                stat['max_ms'] = max(stat['max_ms'], int(p.get('durationMs') or 0))
            elif etype == 'error':
                lines.append(f"错误[{p.get('stage', '')}]: {p.get('message', '')}")

        if tool_stats:
            lines.append("\n工具调用统计:")
            for name, s in tool_stats.items():
                lines.append(f"  {name}: 成功{s['ok']} 失败{s['fail']} 最慢{s['max_ms']}ms")

        lines.append(
            "\n请用中文输出三段分析（每段不超过100字）：\n"
            "1. 做得好的地方\n2. 问题与根因\n3. 下次改进建议"
        )
        return '\n'.join(lines)[:6000]

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
