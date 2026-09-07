"""Memory Distiller - 记忆蒸馏服务（W1.5a）

从 memory_entries + agent_decisions 产出 rule 候选（status=testing）。
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, TYPE_CHECKING
import structlog

from infrastructure.persistence.orm import get_session
from domain.memory.service import MemoryService
from domain.memory.models import MemoryEntry, MemoryKind, MemoryStatus

if TYPE_CHECKING:
    from domain.ports import IMemoryRepository, IAgentIntelligenceRepository

logger = structlog.get_logger(__name__)


class MemoryDistiller:
    """记忆蒸馏器：收集原始数据 → LLM 蒸馏（agent侧） → 写回候选"""

    def __init__(self, memory_repo: 'IMemoryRepository'):
        """
        Initialize memory distiller.

        Args:
            memory_repo: Memory repository (must be injected by infrastructure layer)

        Raises:
            TypeError: If memory_repo is None
        """
        if memory_repo is None:
            raise TypeError(
                "MemoryDistiller requires memory_repo injection. "
                "Domain layer cannot create adapters directly. "
                "Please inject IMemoryRepository implementation from infrastructure layer."
            )
        self._memory_repo = memory_repo

    def collect_inputs(self, days: int = 7) -> Dict[str, Any]:
        """收集近 N 天的记忆条目和决策记录

        Args:
            days: 回溯天数

        Returns:
            {"episodes": [...], "decisions": [...]}
        """
        from datetime import timezone
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        # 收集 episode 类型的记忆条目（排除已被 recall 的）
        all_episodes = self._memory_repo.list_filtered(kind='episode', max_rows=200)

        # 过滤：排除 last_recalled_at 非空且 source='recall' 的条目
        episodes = []
        for ep in all_episodes:
            created_at_str = ep.get('created_at')
            if not created_at_str:
                continue

            # 解析 created_at（ISO 格式字符串）
            try:
                created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                continue

            if created_at < cutoff:
                continue

            # 排除规则：last_recalled_at 非空 且 source='recall'
            if ep.get('last_recalled_at') and ep.get('source') == 'recall':
                continue

            episodes.append(ep)

        # 收集 agent_decisions（近 N 天，限 100 行）
        # Note: Direct ORM query here is acceptable as this is infrastructure concern
        # TODO: Consider moving to a proper repository method
        session = get_session()
        try:
            from adapters.outbound.repositories.agent_intelligence_repository import AgentDecision

            rows = (session.query(AgentDecision)
                    .filter(AgentDecision.created_at >= cutoff)
                    .order_by(AgentDecision.created_at.desc())
                    .limit(100)
                    .all())

            decisions = [
                {
                    'id': r.id,
                    'decision_type': r.decision_type,
                    'reasoning': r.reasoning,
                    'success': r.success,
                }
                for r in rows
            ]
        except ImportError:
            # AgentDecision model not available
            logger.warning("AgentDecision model not available, skipping decisions")
            decisions = []
        finally:
            session.close()

        logger.info(f"collect_inputs: {len(episodes)} episodes, {len(decisions)} decisions")
        return {"episodes": episodes, "decisions": decisions}

    def build_prompt(self, inputs: Dict[str, Any]) -> str:
        """构建蒸馏 prompt

        要求 LLM 输出 JSON 数组，每条包含：
        - title: 规则标题
        - content: 规则内容
        - evidence_ids: 证据 ID 列表（必须引用输入中的条目 id 或 decision id）

        Args:
            inputs: collect_inputs 的返回值

        Returns:
            prompt 字符串
        """
        episodes = inputs.get('episodes', [])
        decisions = inputs.get('decisions', [])

        prompt = """你是一个记忆蒸馏专家，负责从原始记忆条目和决策记录中提炼出可复用的规则。

## 输入数据

### Episode 记忆条目
"""

        for ep in episodes:
            prompt += f"\n[ID: {ep['id']}]\n"
            prompt += f"标题: {ep.get('title', 'N/A')}\n"
            prompt += f"内容: {ep.get('content', 'N/A')}\n"

        prompt += "\n### 决策记录\n"

        for dec in decisions:
            prompt += f"\n[ID: {dec['id']}]\n"
            prompt += f"类型: {dec.get('decision_type', 'N/A')}\n"
            prompt += f"推理: {dec.get('reasoning', 'N/A')}\n"
            prompt += f"成功: {dec.get('success', 'N/A')}\n"

        prompt += """

## 任务要求

请从以上数据中提炼出可复用的投资规则。每条规则必须：

1. **有明确的证据支持**：evidence_ids 必须引用上述输入中的条目 ID 或决策 ID
2. **具有可操作性**：规则应该清晰、具体，能够指导未来的决策
3. **避免过拟合**：规则应该具有一定的普适性，不是单一事件的总结

## 输出格式

请输出 JSON 数组，每条规则包含：

```json
[
  {
    "title": "规则标题（简短明确）",
    "content": "规则内容（详细描述规则的适用场景、判断标准、执行步骤）",
    "evidence_ids": [1, 5, 12]  // 必须引用输入中的 ID
  }
]
```

**重要**：
- 如果没有足够证据支持的规则，不要输出
- evidence_ids 为空的条目将被自动跳过
- 优先提炼成功的经验，但也要总结失败的教训
"""

        return prompt

    def save_candidates(self, items: List[Dict[str, Any]], session=None) -> Dict[str, Any]:
        """保存蒸馏出的候选规则

        Args:
            items: 候选规则列表，每条包含 {title, content, evidence_ids}
            session: 数据库 session（可选）

        Returns:
            {"saved": count, "skipped": count}
        """
        saved = 0
        skipped = 0

        # 使用外部 session 或创建新的
        if session is None:
            session = get_session()
            close_session = True
        else:
            close_session = False

        try:
            memory_service = MemoryService(MemoryRepository())

            for item in items:
                evidence_ids = item.get('evidence_ids', [])

                # 跳过无证据的候选
                if not evidence_ids:
                    skipped += 1
                    logger.warning(f"skip candidate without evidence: {item.get('title')}")
                    continue

                # 构建 MemoryEntry
                entry = MemoryEntry(
                    kind=MemoryKind.RULE,
                    scope='global',
                    title=item['title'],
                    content=item['content'],
                    status=MemoryStatus.TESTING,
                    source='distiller',
                    evidence={"refs": evidence_ids},
                    provenance={
                        "session_kind": "distiller",
                        "channel": "weekly_memory_distill"
                    }
                )

                memory_service.create(entry)
                saved += 1
                logger.info(f"saved candidate rule: {item['title']}")

        finally:
            if close_session:
                session.close()

        logger.info(f"save_candidates: saved={saved}, skipped={skipped}")
        return {"saved": saved, "skipped": skipped}
