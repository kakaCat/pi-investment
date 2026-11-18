"""持仓与非持仓共用的普通条件及两段式伏击求值。"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import structlog

from ..rules.conditions import evaluate
from .staged_break_manager import OUTCOME_CONFIRMED, OUTCOME_EXPIRED

logger = structlog.get_logger(__name__)


@dataclass
class ConditionBatch:
    hits: List[Dict[str, Any]] = field(default_factory=list)
    suppressed: List[Dict[str, Any]] = field(default_factory=list)
    degraded: bool = False
    distance_ratio: Optional[float] = None

    def capture_distance(self, result) -> None:
        distance = getattr(result, 'distance_ratio', None)
        if distance is not None:
            self.distance_ratio = (distance if self.distance_ratio is None
                                   else min(self.distance_ratio, distance))


def evaluate_conditions(rule, quote, ctx, now: Optional[datetime] = None,
                        staged_manager=None) -> ConditionBatch:
    now = now or datetime.now()
    batch = ConditionBatch()
    for idx, cond in enumerate(getattr(rule, 'conditions', None) or []):
        if isinstance(cond, dict) and cond.get('type') == 'staged_break':
            if staged_manager is None:
                batch.degraded = True
                continue
            try:
                outcome, result = staged_manager.process(
                    getattr(rule, 'id', None), idx, cond, quote, ctx, now)
            except Exception as exc:  # noqa: BLE001
                logger.warning('v2.staged_condition_eval_failed',
                               rule_id=getattr(rule, 'id', None), error=str(exc))
                batch.degraded = True
                continue
            batch.capture_distance(result)
            if outcome == OUTCOME_CONFIRMED and getattr(result, 'triggered', False):
                batch.hits.append({
                    'condition': cond,
                    'value': getattr(result, 'value', None),
                    'message': getattr(result, 'message', ''),
                })
            elif outcome == OUTCOME_EXPIRED:
                batch.suppressed.append({
                    'condition': cond,
                    'value': getattr(result, 'value', None),
                    'message': getattr(result, 'message', ''),
                })
            continue
        try:
            result = evaluate(cond, quote, ctx, now)
        except Exception as exc:  # noqa: BLE001
            logger.warning('v2.condition_eval_failed',
                           rule_id=getattr(rule, 'id', None), error=str(exc))
            batch.degraded = True
            continue
        batch.capture_distance(result)
        if getattr(result, 'degraded', False):
            batch.degraded = True
        if getattr(result, 'triggered', False):
            batch.hits.append({
                'condition': cond,
                'value': getattr(result, 'value', None),
                'message': getattr(result, 'message', ''),
            })
    return batch
