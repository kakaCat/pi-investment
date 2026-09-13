"""
Session 服务 — agent session 事件摄入、查询与诊断

设计原则：返回洞察而非原始数据（diagnosis 附解读）
"""
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

        2026-09-14（w-32314d00，REQ-24e15d B3）：db_cursor + 裸 SQL（含一处 f-string
        拼列名做计数器自增）→ AgentSessionRepository。**事务语义保持单事务**：
        整批成功才提交，中途抛错整体回滚（原 db_cursor(commit=True) 的行为）。
        """
        from adapters.outbound.repositories.session_repository import AgentSessionRepository
        repo = AgentSessionRepository()

        accepted = duplicates = skipped = 0
        try:
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
                repo.upsert_session(
                    session_key=key,
                    channel=payload.get("channel", "unknown"),
                    peer_id=str(payload.get("peerId", "")),
                    agent_id=payload.get("agentId", "main"),
                    last_active_at=created_at,
                )

                inserted = repo.insert_event(key, seq, etype, payload, created_at)
                if not inserted:
                    duplicates += 1
                    continue

                accepted += 1
                counter = _COUNTER_MAP.get(etype)
                if counter:
                    repo.increment_counter(key, counter)
            repo.commit()
        except Exception:
            repo.rollback()
            raise

        return {"accepted": accepted, "duplicates": duplicates, "skipped": skipped}

    @staticmethod
    def _repo():
        # 2026-09-14（w-32314d00，REQ-24e15d B3）：下面几个查询方法原先各自
        # db_cursor + 裸 SQL，现统一走 AgentSessionRepository。
        from adapters.outbound.repositories.session_repository import AgentSessionRepository
        return AgentSessionRepository()

    def list_sessions(self, channel: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        return self._repo().list_sessions(channel=channel, limit=limit)

    def get_session(self, session_key: str) -> Optional[Dict[str, Any]]:
        return self._repo().get_session(session_key)

    def get_events(self, session_key: str, event_type: Optional[str] = None,
                   limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        return self._repo().list_events(session_key, event_type=event_type,
                                        limit=limit, offset=offset)

    def get_diagnosis(self, session_key: str) -> Dict[str, Any]:
        """诊断：工具成功率、耗时、错误聚类、关联决策 + 洞察解读

        2026-09-14（w-32314d00，REQ-24e15d B3）：三段裸 SQL → 仓储方法。
        口径**完全不变**：ok = payload->>'success' 为真、耗时取 payload->>'durationMs'、
        错误按 payload->>'message' 聚类取前 5、关联决策按 created_at 倒序取 20 条；
        关联决策查询失败仍然只告警不影响诊断（仓储内部已 try/except）。
        """
        repo = self._repo()
        tool = repo.get_tool_call_stats(session_key)
        total = int(tool.get('total') or 0)
        ok = int(tool.get('ok') or 0)
        success_rate = (ok / total) if total else None

        errors = repo.get_top_errors(session_key, limit=5)
        decisions: List[Dict[str, Any]] = repo.list_decisions(session_key, limit=20)

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

        2026-09-14（w-32314d00，REQ-24e15d B3）：缓存读写两处裸 SQL → AgentSessionRepository。
        """
        from adapters.outbound.repositories.session_repository import AgentSessionRepository
        repo = AgentSessionRepository()
        
        # 缓存命中
        if not refresh:
            cached = repo.get_ai_diagnosis(session_key)
            if cached:
                analysis, generated_at = cached
                return {
                    'analysis': analysis,
                    'generated_at': generated_at.isoformat() if generated_at else None,
                    'cached': True,
                }

        events = self.get_events(session_key, limit=500)
        prompt = self._build_diagnosis_prompt(session_key, events)

        from application.services.llm_service import chat_completion
        analysis = chat_completion(prompt)

        now = datetime.now(timezone.utc)
        repo.save_ai_diagnosis(session_key, analysis, now)
        repo.commit()

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
