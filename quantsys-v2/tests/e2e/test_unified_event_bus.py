"""P2.4 e2e tests for UnifiedEventBus."""
import pytest
from infrastructure.events.unified_event_bus import (
    UnifiedEventBus,
    EventType,
    Event,
    get_event_bus,
)


@pytest.fixture
def bus():
    b = UnifiedEventBus(max_history=100)
    yield b
    b.clear_history()


@pytest.fixture
def fresh_bus():
    return UnifiedEventBus(max_history=50)


# ── Event Schema ────────────────────────────────────────────

class TestEventSchema:
    def test_event_types_are_strings(self):
        for t in EventType:
            assert isinstance(t.value, str)

    def test_event_creation(self):
        e = Event(type=EventType.SIGNALS_READY, data={"signals": []})
        assert e.id
        assert e.type == EventType.SIGNALS_READY.value
        assert e.source == "quantsys-v2"
        assert e.data == {"signals": []}
        assert e.timestamp

    def test_event_to_dict(self):
        e = Event(type=EventType.DAILY_REVIEW, data={"date": "2026-09-04"})
        d = e.to_dict()
        assert isinstance(d, dict)
        assert d["type"] == EventType.DAILY_REVIEW.value
        assert d["data"]["date"] == "2026-09-04"

    def test_event_from_dict(self):
        raw = {
            "id": "test-123",
            "type": "signals_ready",
            "source": "agent-os",
            "timestamp": "2026-09-04T12:00:00Z",
            "version": "1.0",
            "data": {"count": 5},
            "metadata": {"env": "test"},
        }
        e = Event.from_dict(raw)
        assert e.id == "test-123"
        assert e.type == "signals_ready"
        assert e.source == "agent-os"
        assert e.data == {"count": 5}
        assert e.metadata == {"env": "test"}


# ── Publish & Subscribe ─────────────────────────────────────

class TestPublishSubscribe:
    def test_publish_returns_event_id(self, bus):
        eid = bus.publish(EventType.SIGNALS_READY, {"count": 1})
        assert isinstance(eid, str)
        assert len(eid) > 0

    def test_subscribe_receives_events(self, bus):
        received = []
        bus.subscribe(EventType.SIGNALS_READY, lambda e: received.append(e))
        bus.publish(EventType.SIGNALS_READY, {"count": 1})
        assert len(received) == 1
        assert received[0].type == EventType.SIGNALS_READY.value

    def test_wildcard_receives_all(self, bus):
        received = []
        bus.subscribe("*", lambda e: received.append(e))
        bus.publish(EventType.SIGNALS_READY, {})
        bus.publish(EventType.DAILY_REVIEW, {})
        assert len(received) == 2

    def test_unsubscribe_stops_delivery(self, bus):
        received = []
        handler = lambda e: received.append(e)
        bus.subscribe(EventType.SIGNALS_READY, handler)
        bus.publish(EventType.SIGNALS_READY, {})
        assert len(received) == 1
        bus.unsubscribe(EventType.SIGNALS_READY, handler)
        bus.publish(EventType.SIGNALS_READY, {})
        assert len(received) == 1

    def test_multiple_subscribers(self, bus):
        r1, r2 = [], []
        bus.subscribe(EventType.TRADE_EXECUTED, lambda e: r1.append(e))
        bus.subscribe(EventType.TRADE_EXECUTED, lambda e: r2.append(e))
        bus.publish(EventType.TRADE_EXECUTED, {"symbol": "600519.SH"})
        assert len(r1) == 1
        assert len(r2) == 1

    def test_handler_error_does_not_break_bus(self, bus):
        def bad_handler(e):
            raise ValueError("boom")

        good_received = []
        bus.subscribe(EventType.SIGNALS_READY, bad_handler)
        bus.subscribe(EventType.SIGNALS_READY, lambda e: good_received.append(e))
        bus.publish(EventType.SIGNALS_READY, {})
        assert len(good_received) == 1


# ── History & Replay ────────────────────────────────────────

class TestHistoryReplay:
    def test_history_returns_events(self, bus):
        bus.publish(EventType.SIGNALS_READY, {"a": 1})
        bus.publish(EventType.DAILY_REVIEW, {"b": 2})
        bus.publish(EventType.SIGNALS_READY, {"c": 3})
        history = bus.get_history()
        assert len(history) == 3

    def test_history_filter_by_type(self, bus):
        bus.publish(EventType.SIGNALS_READY, {})
        bus.publish(EventType.DAILY_REVIEW, {})
        bus.publish(EventType.SIGNALS_READY, {})
        history = bus.get_history(event_type=EventType.SIGNALS_READY)
        assert len(history) == 2

    def test_history_filter_by_source(self, bus):
        bus.publish(EventType.SIGNALS_READY, {}, source="quantsys-v2")
        bus.publish(EventType.SIGNALS_READY, {}, source="agent-os")
        history = bus.get_history(source="agent-os")
        assert len(history) == 1

    def test_history_limit(self, bus):
        for i in range(10):
            bus.publish(EventType.SIGNALS_READY, {"i": i})
        history = bus.get_history(limit=3)
        assert len(history) == 3

    def test_replay(self, bus):
        for i in range(5):
            bus.publish(EventType.SIGNALS_READY, {"i": i})
        replayed = bus.replay(event_type=EventType.SIGNALS_READY, start_index=1, count=3)
        assert len(replayed) == 3
        assert replayed[0]["data"]["i"] == 1

    def test_clear_history(self, bus):
        bus.publish(EventType.SIGNALS_READY, {})
        assert bus.event_count == 1
        bus.clear_history()
        assert bus.event_count == 0


# ── Stats ───────────────────────────────────────────────────

class TestStats:
    def test_event_count(self, bus):
        assert bus.event_count == 0
        bus.publish(EventType.SIGNALS_READY, {})
        assert bus.event_count == 1

    def test_subscriber_count(self, bus):
        assert bus.get_subscriber_count() == 0
        bus.subscribe(EventType.SIGNALS_READY, lambda e: None)
        bus.subscribe(EventType.DAILY_REVIEW, lambda e: None)
        assert bus.get_subscriber_count() == 2

    def test_subscriber_count_by_type(self, bus):
        bus.subscribe(EventType.SIGNALS_READY, lambda e: None)
        bus.subscribe(EventType.SIGNALS_READY, lambda e: None)
        assert bus.get_subscriber_count(EventType.SIGNALS_READY) == 2
        assert bus.get_subscriber_count(EventType.DAILY_REVIEW) == 0

    def test_max_history_overflow(self):
        b = UnifiedEventBus(max_history=3)
        for i in range(5):
            b.publish(EventType.SIGNALS_READY, {"i": i})
        assert b.event_count == 3
        history = b.get_history()
        assert history[0]["data"]["i"] == 2


# ── Singleton ───────────────────────────────────────────────

class TestSingleton:
    def test_get_event_bus_returns_same_instance(self):
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2
