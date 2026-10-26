"""反思报告 → agent_knowledge 沉淀（t13 · FR-8 · D-3 三层分离）

职责：只消费 `plan_reflections.knowledge_updates`，写 `agent_knowledge`。
**结构性只读计划**：本模块不 import 任何 trading_plan 仓储的写方法，
也不提供改计划的路径——进化只影响「下一个计划」的知识底稿（D-3）。

纪律：
- evidence 缺失的条目**跳过并计数**（不沉淀无证据的「教训」——那只是感觉）；
- knowledge_id 幂等（同计划同周期同条 = 同 id，upsert 不重复堆积）；
- 单条失败记日志继续（一条坏条目不拖垮整批）。
"""
from typing import Any, Dict, Iterable, List, Optional

import structlog

logger = structlog.get_logger(__name__)

KNOWLEDGE_TYPE = 'plan_reflection_lesson'


class PlanReflectionConsumer:
    def __init__(self, knowledge_repo=None):
        self._knowledge = knowledge_repo

    def _repo(self):
        if self._knowledge is None:
            from adapters.outbound.repositories.agent_knowledge_repository import (
                AgentKnowledgeORMRepository,
            )
            self._knowledge = AgentKnowledgeORMRepository()
        return self._knowledge

    def consume(self, reflections: Iterable[Any]) -> Dict[str, Any]:
        """消费一批反思行（ORM 行或 dict 均可）。返回计数与跳过原因。"""
        upserted = skipped = failed = 0
        for row in reflections:
            updates = _field(row, 'knowledge_updates') or []
            if not isinstance(updates, list):
                skipped += 1
                continue
            for i, upd in enumerate(updates):
                if not isinstance(upd, dict):
                    skipped += 1
                    continue
                evidence = upd.get('evidence')
                if not evidence:
                    skipped += 1
                    logger.info('反思知识条目缺证据，跳过沉淀',
                                plan_id=_field(row, 'plan_id'),
                                lesson=upd.get('lesson'))
                    continue
                knowledge_id = str(
                    upd.get('knowledge_id')
                    or 'plan-reflect-%s-%s-%s-%d' % (
                        _field(row, 'plan_id'), _field(row, 'period'),
                        _field(row, 'version'), i))[:50]
                try:
                    self._repo().upsert_knowledge(
                        knowledge_id=knowledge_id,
                        domain=str(upd.get('domain') or 'trading_plan'),
                        knowledge_type=KNOWLEDGE_TYPE,
                        content={
                            'lesson': upd.get('lesson'),
                            'source': 'plan_reflection',
                            'plan_id': _field(row, 'plan_id'),
                            'period': _field(row, 'period'),
                            'verdict': _field(row, 'verdict'),
                        },
                        confidence=_confidence(upd),
                        validation_count=1,
                        success_count=0,
                        evidence={'items': evidence} if isinstance(evidence, list)
                        else {'raw': evidence},
                    )
                    upserted += 1
                except Exception as e:  # noqa: BLE001 - 单条失败不拖垮整批
                    failed += 1
                    logger.error('反思知识沉淀失败', knowledge_id=knowledge_id, error=str(e))
        return {'upserted': upserted, 'skipped': skipped, 'failed': failed}


def _field(obj: Any, name: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _confidence(upd: Dict[str, Any]) -> float:
    try:
        value = float(upd.get('confidence', 0.5))
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, value))
