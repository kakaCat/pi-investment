from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from quantsys.watch.quote_sources import FallbackRealtimeQuoteSource


class RecordingSource:
    def __init__(self, name: str, quotes: dict | None = None, error: Exception | None = None):
        self.name = name
        self.quotes = quotes or {}
        self.error = error
        self.calls = []

    def fetch_realtime_quote(self, symbol: str) -> dict:
        self.calls.append(symbol)
        if self.error:
            raise self.error
        quote = dict(self.quotes[symbol])
        quote["source"] = self.name
        return quote


def test_fallback_realtime_quote_source_uses_next_source_when_primary_fails():
    sina = RecordingSource("sina", error=RuntimeError("sina timeout"))
    akshare = RecordingSource("akshare", {"600036": {"symbol": "600036", "price": 35.2}})
    source = FallbackRealtimeQuoteSource([sina, akshare])

    quote = source.fetch_realtime_quote("600036")

    assert quote["price"] == 35.2
    assert quote["source"] == "akshare"
    assert sina.calls == ["600036"]
    assert akshare.calls == ["600036"]


def test_fallback_realtime_quote_source_raises_combined_error_when_all_sources_fail():
    source = FallbackRealtimeQuoteSource(
        [
            RecordingSource("sina", error=RuntimeError("sina timeout")),
            RecordingSource("akshare", error=RuntimeError("akshare timeout")),
        ]
    )

    try:
        source.fetch_realtime_quote("600036")
    except RuntimeError as exc:
        message = str(exc)
    else:
        raise AssertionError("expected RuntimeError")

    assert "sina timeout" in message
    assert "akshare timeout" in message


def test_fallback_realtime_quote_source_retries_before_falling_back():
    primary = RecordingSource("sina", error=RuntimeError("temporary failure"))
    fallback = RecordingSource("akshare", {"600036": {"symbol": "600036", "price": 35.2}})
    source = FallbackRealtimeQuoteSource([primary, fallback], retry_count=2)

    quote = source.fetch_realtime_quote("600036")

    assert quote["price"] == 35.2
    assert primary.calls == ["600036", "600036", "600036"]
    assert fallback.calls == ["600036"]


def test_fallback_realtime_quote_source_opens_circuit_after_failures():
    primary = RecordingSource("sina", error=RuntimeError("sina down"))
    fallback = RecordingSource("akshare", {"600036": {"symbol": "600036", "price": 35.2}})
    source = FallbackRealtimeQuoteSource(
        [primary, fallback],
        retry_count=0,
        circuit_breaker_failures=1,
        circuit_breaker_cooldown_seconds=60,
        clock=lambda: 1000.0,
    )

    first = source.fetch_realtime_quote("600036")
    second = source.fetch_realtime_quote("600036")

    assert first["source"] == "akshare"
    assert second["source"] == "akshare"
    assert primary.calls == ["600036"]
    assert fallback.calls == ["600036", "600036"]
