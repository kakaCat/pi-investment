"""Realtime quote sources for the watch pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import time
from typing import Protocol

from quantsys.data.data.sources.akshare_adapter import AkShareAdapter


class RealtimeQuoteSource(Protocol):
    """A source that can return a realtime quote snapshot for one symbol."""

    def fetch_realtime_quote(self, symbol: str) -> dict:
        """Return the latest quote for a symbol."""


class FallbackRealtimeQuoteSource:
    """Try realtime quote sources in order until one returns a valid price."""

    def __init__(
        self,
        sources: list[RealtimeQuoteSource],
        retry_count: int = 0,
        circuit_breaker_failures: int = 3,
        circuit_breaker_cooldown_seconds: float = 30.0,
        clock=None,
    ) -> None:
        if not sources:
            raise ValueError("at least one quote source is required")
        self.sources = sources
        self.retry_count = retry_count
        self.circuit_breaker_failures = circuit_breaker_failures
        self.circuit_breaker_cooldown_seconds = circuit_breaker_cooldown_seconds
        self.clock = clock or time.time
        self._failure_counts: dict[int, int] = {}
        self._circuit_opened_at: dict[int, float] = {}

    def fetch_realtime_quote(self, symbol: str) -> dict:
        errors = []
        for index, source in enumerate(self.sources):
            name = source.__class__.__name__
            if self._is_circuit_open(index):
                errors.append(f"{name}: circuit open")
                continue

            for attempt in range(self.retry_count + 1):
                try:
                    quote = source.fetch_realtime_quote(symbol)
                    price = float(quote.get("price", 0) or 0)
                    if price <= 0:
                        raise RuntimeError(f"{name} returned invalid price: {price}")
                    self._record_success(index)
                    quote.setdefault("source", name)
                    return quote
                except Exception as exc:
                    if attempt >= self.retry_count:
                        self._record_failure(index)
                        errors.append(f"{name}: {exc}")

        raise RuntimeError(f"all realtime quote sources failed for {symbol}: {'; '.join(errors)}")

    def _is_circuit_open(self, index: int) -> bool:
        opened_at = self._circuit_opened_at.get(index)
        if opened_at is None:
            return False
        if self.clock() - opened_at >= self.circuit_breaker_cooldown_seconds:
            self._circuit_opened_at.pop(index, None)
            self._failure_counts[index] = 0
            return False
        return True

    def _record_failure(self, index: int) -> None:
        count = self._failure_counts.get(index, 0) + 1
        self._failure_counts[index] = count
        if count >= self.circuit_breaker_failures:
            self._circuit_opened_at[index] = self.clock()

    def _record_success(self, index: int) -> None:
        self._failure_counts[index] = 0
        self._circuit_opened_at.pop(index, None)


@dataclass(frozen=True)
class SinaRealtimeQuoteSource:
    """Fetch realtime quotes directly from Sina via requests."""

    timeout_seconds: int = 10
    http_client: object | None = None

    def fetch_realtime_quote(self, symbol: str) -> dict:
        started = time.perf_counter()
        client = self.http_client or _RequestsHttpClient()
        cleaned = _clean_symbol(symbol)
        sina_symbol = _sina_symbol(cleaned)
        response = client.get(
            f"https://hq.sinajs.cn/list={sina_symbol}",
            headers={"Referer": "https://finance.sina.com.cn", "User-Agent": "Mozilla/5.0"},
            timeout=self.timeout_seconds,
        )
        text = getattr(response, "text", "")
        fields = _parse_sina_realtime(text)
        if not fields or not fields.get("price"):
            raise RuntimeError(f"未找到: {cleaned}")

        price = float(fields["price"])
        prev_close = float(fields["prev_close"]) if fields.get("prev_close") else 0.0
        change_amount = round(price - prev_close, 3)
        change_pct = round((price - prev_close) / prev_close * 100, 2) if prev_close else 0.0
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        return {
            "symbol": cleaned,
            "name": fields["name"],
            "price": price,
            "change_pct": change_pct,
            "change_amount": change_amount,
            "volume": float(fields["volume"] or 0),
            "amount": float(fields["amount"] or 0),
            "high": float(fields["high"] or 0),
            "low": float(fields["low"] or 0),
            "open": float(fields["open"] or 0),
            "prev_close": prev_close,
            "data_date": f"{fields['date']} {fields['time']}",
            "source": "sina",
            "fetched_at": datetime.now().isoformat(timespec="seconds"),
            "latency_ms": latency_ms,
            "stale": False,
        }


class AkShareRealtimeQuoteSource:
    """Fallback realtime quote source using the existing AkShare adapter."""

    def __init__(self, adapter: AkShareAdapter | None = None) -> None:
        self.adapter = adapter or AkShareAdapter()

    def fetch_realtime_quote(self, symbol: str) -> dict:
        started = time.perf_counter()
        result = self.adapter.fetch_realtime_quote(symbol)
        if result.get("price", 0) <= 0:
            raise RuntimeError(f"invalid price returned for {symbol}")
        result.setdefault("source", "akshare")
        result.setdefault("fetched_at", datetime.now().isoformat(timespec="seconds"))
        result.setdefault("latency_ms", round((time.perf_counter() - started) * 1000, 2))
        result.setdefault("stale", False)
        return result


class _RequestsHttpClient:
    def get(self, url: str, params=None, headers=None, timeout=None):
        import requests

        return requests.get(url, params=params, headers=headers, timeout=timeout)


def _clean_symbol(symbol: str) -> str:
    return symbol.replace("sh", "").replace("sz", "").replace("bj", "").strip()


def _sina_symbol(symbol: str) -> str:
    code = _clean_symbol(symbol)
    if code.startswith(("6", "9")):
        return f"sh{code}"
    if code.startswith(("4", "8", "43", "92")):
        return f"bj{code}"
    return f"sz{code}"


def _parse_sina_realtime(raw: str) -> dict:
    import re

    match = re.search(r'"([^"]*)"', raw or "")
    if not match:
        return {}
    fields = match.group(1).strip().split(",")
    if len(fields) < 32:
        return {}
    return {
        "name": fields[0],
        "open": fields[1],
        "prev_close": fields[2],
        "price": fields[3],
        "high": fields[4],
        "low": fields[5],
        "volume": fields[8],
        "amount": fields[9],
        "date": fields[30],
        "time": fields[31],
    }
