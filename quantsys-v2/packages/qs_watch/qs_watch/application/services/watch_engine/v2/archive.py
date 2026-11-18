"""V2 触发归档：持久事件闩锁、终态硬停与失败重试节流。

一次 trigger 是一个事件：任一通道成功投递后，同一事件不再进入 10-cycle
重投；只有离开迟滞带并重新武装后的新边沿才创建新 trigger。进程内闩锁丢失时，
从当日同规则、同条件的持久 trigger 恢复，避免重启后重复通知。
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

import structlog

logger = structlog.get_logger(__name__)

ARCHIVE_ENGINE = 'v2'
TERMINAL_DISPOSITIONS = frozenset({
    'ignored', 'handled', 'expired', 'auto_observed',
    'filtered', 'deduped', 'legacy_unknown',
})


@dataclass
class _LatchEntry:
    trigger_id: Any
    condition: Any = None
    notified: Optional[bool] = None
    disposition: str = 'pending'
    triggered_at: Optional[datetime] = None
    attempted: bool = False
    last_attempt_at: Optional[datetime] = None
    dirty: bool = False


_LATCH: Dict[tuple, _LatchEntry] = {}
# finish() 已确认离开迟滞带的键。它只负责区分「本进程已 rearm」与
# 「进程重启导致闩锁丢失」：前者的新边沿必须新建 trigger，后者从持久层恢复。
_REARMED = set()


def reset_latch() -> None:
    _LATCH.clear()
    _REARMED.clear()


def condition_key(condition: Any) -> str:
    import json
    try:
        return json.dumps(condition, sort_keys=True, ensure_ascii=False, default=str)
    except Exception:  # noqa: BLE001
        return repr(condition)


def cooldown_sec(condition: Any) -> float:
    """读取条件级失败重试冷却；兼容顶层与 params，缺省/脏值为 0。"""
    if not isinstance(condition, dict):
        return 0.0
    params = condition.get('params') or {}
    raw = condition.get('cooldown_sec', params.get('cooldown_sec'))
    if raw is None:
        return 0.0
    try:
        return max(0.0, float(raw))
    except (TypeError, ValueError):
        logger.warning('v2.trigger_cooldown_invalid', cooldown_sec=raw)
        return 0.0


class TriggerArchive:
    """一次扫描的归档编排器；投递资格由持久 trigger 状态决定。"""

    def __init__(self, trigger_repo, now: Optional[datetime] = None):
        self._repo = trigger_repo
        self._now = now or datetime.now()
        self._day = self._now.date().isoformat()
        self._day_start = self._now.replace(hour=0, minute=0, second=0, microsecond=0)
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
        hits = getattr(judgment, 'hit_conditions', None) or []
        if not hits:
            # 保留无 hit 明细的旧判定兼容性；正常 trigger 判定总会带 hit_conditions。
            judgment._v2_archive_entries = []
            judgment._v2_delivery_allowed = True
            judgment._v2_delivery_block_reasons = []
            judgment._v2_new_trigger = False
            return True

        deliverable = []
        block_reasons = []
        has_new = False
        ok = True
        for hit in hits:
            condition = hit.get('condition') if isinstance(hit, dict) else None
            key = (self._day, getattr(rule, 'id', None), condition_key(condition))
            self._seen_keys.add(key)
            entry = _LATCH.get(key)
            restored = False
            if entry is None and key not in _REARMED:
                try:
                    entry = self._restore(key, condition or {})
                    restored = entry is not None
                except Exception as exc:  # noqa: BLE001
                    self.failed += 1
                    ok = False
                    logger.error('v2.trigger_restore_failed',
                                 rule_id=getattr(rule, 'id', None), error=str(exc))
                    # 读失败不能当作“历史不存在”，否则重启后必然重复建档/通知。
                    continue
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
                    entry = _LatchEntry(
                        trigger_id=trigger_id,
                        condition=condition,
                        notified=False,
                        disposition='pending',
                        triggered_at=self._now,
                    )
                    _LATCH[key] = entry
                    _REARMED.discard(key)
                    self.written += 1
                    has_new = True
                except Exception as exc:  # noqa: BLE001
                    self.failed += 1
                    ok = False
                    logger.error('v2.trigger_archive_failed',
                                 rule_id=getattr(rule, 'id', None), error=str(exc))
                    continue
            else:
                # 上一次 notified 回写若失败，先重试回写；失败时保持内存成功闩锁，
                # 不得用库里的旧值覆盖它并再次投递。
                if not self._flush(key, entry):
                    ok = False
                    block_reasons.append('notified_flush_failed')
                    continue
                if not restored and not self._refresh(key, entry):
                    self.failed += 1
                    ok = False
                    block_reasons.append('state_read_failed')
                    continue

            reason = self._delivery_block_reason(entry, condition)
            if reason:
                block_reasons.append(reason)
            else:
                deliverable.append((key, entry))

        # 多条件事件只携带仍需投递的 trigger；已通知/终态的 trigger 不随兄弟条件重投。
        judgment._v2_archive_entries = deliverable
        judgment._v2_delivery_allowed = bool(deliverable) and ok
        judgment._v2_delivery_block_reasons = block_reasons
        judgment._v2_new_trigger = has_new
        return ok

    def after_delivery(self, judgment, delivery) -> None:
        if delivery is None or not hasattr(delivery, 'delivered'):
            return
        if getattr(delivery, 'skipped', False):
            return  # 价格门槛等业务跳过不反写 notified，避免覆盖既有成功记录
        notified = bool(getattr(delivery, 'delivered', False))
        for key, entry in getattr(judgment, '_v2_archive_entries', None) or []:
            entry.attempted = True
            entry.last_attempt_at = self._now
            entry.notified = notified
            entry.dirty = True
            self._flush(key, entry)

    def finish(self) -> None:
        from ..rules.conditions import within_hysteresis_band
        for key in list(_REARMED):
            if key[0] != self._day:
                _REARMED.discard(key)
        for key in list(_LATCH):
            day, rule_id, _ = key
            if day != self._day:
                _LATCH.pop(key, None)
                _REARMED.discard(key)
                continue
            if rule_id not in self._evaluated_rule_ids or key in self._seen_keys:
                continue
            entry = _LATCH[key]
            quote = self._quotes.get(rule_id)
            # 行情不可知不能证明 rearm；保留闩锁，避免恢复行情后把旧事件当新边沿。
            if quote is None:
                continue
            if (entry.condition is not None
                    and within_hysteresis_band(entry.condition, getattr(quote, 'price', None))):
                continue
            _LATCH.pop(key, None)
            _REARMED.add(key)

    def _restore(self, key, condition) -> Optional[_LatchEntry]:
        finder = getattr(self._repo, 'find_latest_for_condition', None)
        if not callable(finder):
            return None  # 旧测试/兼容仓储无恢复接口时保持原行为
        _day, rule_id, _condition_key = key
        trigger = finder(
            rule_id=rule_id,
            condition=condition,
            since=self._day_start,
            engine=ARCHIVE_ENGINE,
        )
        if trigger is None:
            return None
        entry = _LatchEntry(
            trigger_id=getattr(trigger, 'id', None),
            condition=getattr(trigger, 'condition', condition),
            notified=bool(getattr(trigger, 'notified', False)),
            disposition=str(getattr(trigger, 'disposition', 'pending') or 'pending'),
            triggered_at=getattr(trigger, 'triggered_at', None),
        )
        if entry.trigger_id is None:
            raise RuntimeError('restored trigger has no id')
        _LATCH[key] = entry
        logger.info('v2.trigger_latch_restored',
                    rule_id=rule_id, trigger_id=entry.trigger_id,
                    notified=entry.notified, disposition=entry.disposition)
        return entry

    def _refresh(self, key, entry: _LatchEntry) -> bool:
        reader = getattr(self._repo, 'get_by_id', None)
        if not callable(reader):
            return True  # 兼容既有内存仓储；生产 BaseORMRepository 总有此方法
        try:
            trigger = reader(entry.trigger_id)
        except Exception as exc:  # noqa: BLE001
            logger.error('v2.trigger_state_read_failed',
                         trigger_id=entry.trigger_id, error=str(exc))
            return False
        if trigger is None:
            logger.error('v2.trigger_state_read_missing', trigger_id=entry.trigger_id)
            return False
        entry.notified = bool(getattr(trigger, 'notified', False))
        entry.disposition = str(getattr(trigger, 'disposition', 'pending') or 'pending')
        entry.triggered_at = getattr(trigger, 'triggered_at', None)
        return True

    def _delivery_block_reason(self, entry: _LatchEntry, condition) -> str:
        if entry.disposition in TERMINAL_DISPOSITIONS:
            return 'disposition_' + entry.disposition
        if entry.notified is True:
            return 'already_notified'
        wait = cooldown_sec(condition)
        if wait > 0 and entry.attempted and entry.last_attempt_at is not None:
            elapsed = (self._now - entry.last_attempt_at).total_seconds()
            if elapsed < wait:
                return 'retry_cooldown'
        return ''

    def _flush(self, key, entry: _LatchEntry) -> bool:
        if not entry.dirty:
            return True
        try:
            self._repo.mark_notified(entry.trigger_id, bool(entry.notified))
        except Exception as exc:  # noqa: BLE001
            self.failed += 1
            logger.error('v2.trigger_notified_update_failed',
                         trigger_id=entry.trigger_id, error=str(exc))
            return False
        entry.dirty = False
        return True
