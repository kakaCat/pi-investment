"""V2 触发归档：先落触发台账，再回写实际投递结果。"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

import structlog

logger = structlog.get_logger(__name__)

ARCHIVE_ENGINE = 'v2'


@dataclass
class _LatchEntry:
    trigger_id: Any
    condition: Any = None
    notified: Optional[bool] = None
    dirty: bool = False


_LATCH: Dict[tuple, _LatchEntry] = {}


def reset_latch() -> None:
    _LATCH.clear()


def condition_key(condition: Any) -> str:
    import json
    try:
        return json.dumps(condition, sort_keys=True, ensure_ascii=False, default=str)
    except Exception:  # noqa: BLE001
        return repr(condition)


class TriggerArchive:
    """一次扫描的归档编排器；闩锁跨扫描保留，记录投递前后状态。"""

    def __init__(self, trigger_repo, now: Optional[datetime] = None):
        self._repo = trigger_repo
        self._day = (now or datetime.now()).date().isoformat()
        self.written = 0
        self.failed = 0
        self._seen_keys = set()
        self._evaluated_rule_ids = set()
        self._quotes = {}

    def evaluated(self, rule, quote=None) -> None:
        rule_id = getattr(rule, 'id', None)
        self._evaluated_rule_ids.add(rule_id)
        if quote is not None:
            self._quotes[rule_id] = quote

    def record_suppressed(self, rule, judgment) -> bool:
        ok = True
        for item in getattr(judgment, 'suppressed_conditions', None) or []:
            try:
                trigger = self._repo.record(
                    rule_id=getattr(rule, 'id', None),
                    symbol=getattr(rule, 'symbol', None),
                    condition=item.get('condition') or {},
                    trigger_price=item.get('value'),
                    detail={
                        'engine': ARCHIVE_ENGINE,
                        'intent': getattr(judgment, 'intent', None),
                        'message': item.get('message'),
                        'kind': getattr(judgment, 'suppressed_kind', 'staged_expired'),
                    },
                    notified=False,
                    disposition='auto_observed',
                    disposition_by='system',
                    suppressed=True,
                    engine=ARCHIVE_ENGINE,
                )
                if getattr(trigger, 'id', None) is None:
                    raise RuntimeError('suppressed trigger record returned no id')
                self.written += 1
            except Exception as exc:  # noqa: BLE001
                self.failed += 1
                ok = False
                logger.error('v2.suppressed_archive_failed',
                             rule_id=getattr(rule, 'id', None), error=str(exc))
        return ok

    def before_delivery(self, rule, judgment) -> bool:
        entries = []
        has_new = False
        ok = True
        for hit in (getattr(judgment, 'hit_conditions', None) or []):
            condition = hit.get('condition') if isinstance(hit, dict) else None
            key = (self._day, getattr(rule, 'id', None), condition_key(condition))
            self._seen_keys.add(key)
            entry = _LATCH.get(key)
            if entry is None:
                try:
                    trigger = self._repo.record(
                        rule_id=getattr(rule, 'id', None),
                        symbol=getattr(rule, 'symbol', None),
                        condition=condition or {},
                        trigger_price=hit.get('value') if isinstance(hit, dict) else None,
                        detail={
                            'engine': ARCHIVE_ENGINE,
                            'intent': getattr(judgment, 'intent', None),
                            'message': hit.get('message') if isinstance(hit, dict) else None,
                        },
                        notified=False,
                        disposition='pending',
                        disposition_by='system',
                        engine=ARCHIVE_ENGINE,
                    )
                    trigger_id = getattr(trigger, 'id', None)
                    if trigger_id is None:
                        raise RuntimeError('trigger record returned no id')
                    entry = _LatchEntry(trigger_id=trigger_id, condition=condition)
                    _LATCH[key] = entry
                    self.written += 1
                    has_new = True
                except Exception as exc:  # noqa: BLE001
                    self.failed += 1
                    ok = False
                    logger.error('v2.trigger_archive_failed',
                                 rule_id=getattr(rule, 'id', None), error=str(exc))
                    continue
            else:
                self._flush(key, entry)
            entries.append((key, entry))
        judgment._v2_archive_entries = entries
        judgment._v2_new_trigger = has_new
        return ok

    def after_delivery(self, judgment, delivery) -> None:
        if delivery is None or not hasattr(delivery, 'delivered'):
            return
        if getattr(delivery, 'skipped', False):
            return  # 价格门槛等业务跳过不反写 notified，避免覆盖既有成功记录
        notified = bool(getattr(delivery, 'delivered', False))
        for key, entry in getattr(judgment, '_v2_archive_entries', None) or []:
            entry.notified = notified
            entry.dirty = True
            self._flush(key, entry)

    def finish(self) -> None:
        from ..rules.conditions import within_hysteresis_band
        for key in list(_LATCH):
            day, rule_id, _ = key
            if day != self._day:
                _LATCH.pop(key, None)
                continue
            if rule_id not in self._evaluated_rule_ids or key in self._seen_keys:
                continue
            entry = _LATCH[key]
            quote = self._quotes.get(rule_id)
            if (quote is not None and entry.condition is not None
                    and within_hysteresis_band(entry.condition, getattr(quote, 'price', None))):
                continue
            _LATCH.pop(key, None)

    def _flush(self, key, entry: _LatchEntry) -> None:
        if not entry.dirty:
            return
        try:
            self._repo.mark_notified(entry.trigger_id, bool(entry.notified))
        except Exception as exc:  # noqa: BLE001
            self.failed += 1
            logger.error('v2.trigger_notified_update_failed',
                         trigger_id=entry.trigger_id, error=str(exc))
            return
        entry.dirty = False
