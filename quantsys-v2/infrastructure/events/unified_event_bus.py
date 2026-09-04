"""Unified Event Bus — Schema definitions and core event types.

P2.4: Consolidates event handling across quantsys-v2, agent-os, and agent-ts
into a single typed event system with history, replay, and admin APIs.
"""
from __future__ import annotations

import logging
import uuid
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    SIGNALS_READY = "signals_ready"
    WATCH_TRIGGERED = "watch_triggered"
    DAILY_REVIEW = "daily_review"
    PHASE_CHANGE = "phase_change"
    POOL_CHANGED = "pool_changed"
    DECISION_SCORED = "decision_scored"
    TRADE_EXECUTED = "trade_executed"
    DATA_UPDATED = "data_updated"
    FACTOR_COMPUTED = "factor_computed"
    JOB_COMPLETED = "job_completed"
    JOB_FAILED = "job_failed"
    SYSTEM_ERROR = "system_error"
    CUSTOM = "custom"


@dataclass
class Event:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = EventType.CUSTOM
    source: str = "quantsys-v2"
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    version: str = "1.0"
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Event":
        return cls(
            id=d.get("id", str(uuid.uuid4())),
            type=d.get("type", EventType.CUSTOM),
            source=d.get("source", "unknown"),
            timestamp=d.get("timestamp", datetime.now(timezone.utc).isoformat()),
            version=d.get("version", "1.0"),
            data=d.get("data", {}),
            metadata=d.get("metadata", {}),
        )


class UnifiedEventBus:
    """In-process unified event bus with typed events, history, and replay.

    Drop-in replacement for the existing EventBus with schema enforcement
    and admin features. No external dependencies (Redis optional future step).
    """

    def __init__(self, max_history: int = 10000):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._history: deque[Event] = deque(maxlen=max_history)
        self._source_filters: Dict[str, List[str]] = {}

    def publish(
        self,
        event_type: str,
        data: Dict[str, Any],
        source: str = "quantsys-v2",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        event = Event(
            type=event_type,
            source=source,
            data=data,
            metadata=metadata or {},
        )
        self._history.append(event)
        self._dispatch(event)
        return event.id

    def subscribe(self, event_type: str, handler: Callable):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: str, handler: Callable):
        if event_type in self._subscribers:
            try:
                self._subscribers[event_type].remove(handler)
            except ValueError:
                pass

    def _dispatch(self, event: Event):
        handlers = self._subscribers.get(event.type, [])
        wildcard_handlers = self._subscribers.get("*", [])
        all_handlers = handlers + wildcard_handlers

        for handler in all_handlers:
            try:
                handler(event)
            except Exception as exc:
                logger.error("Event handler error: %s — %s", handler.__name__, exc)

    def get_history(
        self,
        event_type: Optional[str] = None,
        source: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        items = list(self._history)
        if event_type:
            items = [e for e in items if e.type == event_type]
        if source:
            items = [e for e in items if e.source == source]
        return [e.to_dict() for e in items[-limit:]]

    def replay(
        self,
        event_type: Optional[str] = None,
        start_index: int = 0,
        count: int = 100,
    ) -> List[Dict[str, Any]]:
        items = list(self._history)
        if event_type:
            items = [e for e in items if e.type == event_type]
        sliced = items[start_index : start_index + count]
        return [e.to_dict() for e in sliced]

    def clear_history(self):
        self._history.clear()

    def get_subscriber_count(self, event_type: Optional[str] = None) -> int:
        if event_type:
            return len(self._subscribers.get(event_type, []))
        return sum(len(h) for h in self._subscribers.values())

    @property
    def event_count(self) -> int:
        return len(self._history)


_event_bus_instance: Optional[UnifiedEventBus] = None


def get_event_bus(max_history: int = 10000) -> UnifiedEventBus:
    global _event_bus_instance
    if _event_bus_instance is None:
        _event_bus_instance = UnifiedEventBus(max_history=max_history)
    return _event_bus_instance
