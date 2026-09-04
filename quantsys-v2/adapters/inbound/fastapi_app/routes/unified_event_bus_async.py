"""Unified Event Bus Admin API — event publishing, history, replay, and stats."""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Query
import structlog

from adapters.inbound.fastapi_app.shared import (
    api_response,
    error_response,
    handle_api_error,
)
from infrastructure.events.unified_event_bus import (
    EventType,
    UnifiedEventBus,
    get_event_bus,
)

logger = structlog.get_logger(__name__)

router = APIRouter(tags=["UnifiedEventBus - 统一事件总线"])

_bus: Optional[UnifiedEventBus] = None


def _get_bus() -> UnifiedEventBus:
    global _bus
    if _bus is None:
        _bus = get_event_bus()
    return _bus


@router.get("/api/event-bus/events")
@handle_api_error
def list_events(
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    source: Optional[str] = Query(None, description="Filter by source"),
    limit: int = Query(50, ge=1, le=500),
):
    bus = _get_bus()
    events = bus.get_history(event_type=event_type, source=source, limit=limit)
    return api_response({"success": True, "events": events, "count": len(events)})


@router.post("/api/event-bus/publish")
@handle_api_error
def publish_event(payload: Dict[str, Any] = Body(...)):
    bus = _get_bus()
    event_type = payload.get("type", EventType.CUSTOM)
    data = payload.get("data", {})
    source = payload.get("source", "quantsys-v2")
    metadata = payload.get("metadata", {})

    event_id = bus.publish(
        event_type=event_type,
        data=data,
        source=source,
        metadata=metadata,
    )
    return api_response({"success": True, "event_id": event_id})


@router.get("/api/event-bus/replay")
@handle_api_error
def replay_events(
    event_type: Optional[str] = Query(None),
    start_index: int = Query(0, ge=0),
    count: int = Query(50, ge=1, le=500),
):
    bus = _get_bus()
    events = bus.replay(event_type=event_type, start_index=start_index, count=count)
    return api_response({"success": True, "events": events, "count": len(events)})


@router.get("/api/event-bus/stats")
@handle_api_error
def event_bus_stats():
    bus = _get_bus()
    return api_response({
        "success": True,
        "total_events": bus.event_count,
        "total_subscribers": bus.get_subscriber_count(),
    })


@router.get("/api/event-bus/types")
@handle_api_error
def list_event_types():
    types = [{"value": t.value, "name": t.name} for t in EventType]
    return api_response({"success": True, "types": types})


@router.delete("/api/event-bus/history")
@handle_api_error
def clear_history():
    bus = _get_bus()
    bus.clear_history()
    return api_response({"success": True, "message": "Event history cleared"})
