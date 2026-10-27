"""On-demand daily K-line backfill and factor refresh for read APIs.

This is intentionally a *read-through* layer:
- only one symbol (or a tiny bounded batch) per request;
- a per-symbol single-flight lock prevents duplicate provider calls;
- a process-wide semaphore caps concurrent upstream fetches;
- empty/stale local data is filled from the existing multi-source fetcher;
- the latest factor snapshot is then computed from local bars.

Full-market repair remains the responsibility of the scheduled evening pipeline.
"""
from __future__ import annotations

import os
import threading
from datetime import date, datetime, time as dtime, timedelta
from typing import Any, Callable, Dict, Optional

import structlog

logger = structlog.get_logger(__name__)

_MAX_LOOKBACK_DAYS = 730
_DEFAULT_LOCK_TIMEOUT = 8.0
_DEFAULT_FETCH_SLOTS = 2
_FETCH_SLOT_TIMEOUT = 2.0

_LOCKS: Dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _enabled() -> bool:
    return _env_bool("ON_DEMAND_MARKET_DATA_ENABLED", True)


def _fetch_slots() -> int:
    try:
        return max(1, int(os.getenv("ON_DEMAND_FETCH_SLOTS", str(_DEFAULT_FETCH_SLOTS))))
    except (TypeError, ValueError):
        return _DEFAULT_FETCH_SLOTS


_FETCH_SEMAPHORE = threading.BoundedSemaphore(_fetch_slots())


def _lock_for(key: str) -> threading.Lock:
    with _LOCKS_GUARD:
        lock = _LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _LOCKS[key] = lock
        return lock


def _safe_is_trading_day(day: date) -> bool:
    try:
        from qs_ops.application.services.trading_day_guard import TradingDayGuard

        return bool(TradingDayGuard.is_trading_day(day))
    except Exception:  # noqa: BLE001 - calendar unavailable must not block the read path
        return day.weekday() < 5


def completed_trading_day(now: Optional[datetime] = None) -> date:
    """Latest trading day whose EOD bar should exist at *now*.

    Before 15:00 (or on a non-trading day) the latest completed bar belongs to
    the previous trading day. After 15:00 on a trading day it is today.
    """
    now = now or datetime.now()
    candidate = now.date()
    if not (_safe_is_trading_day(candidate) and now.time() >= dtime(15, 0)):
        candidate -= timedelta(days=1)
    for _ in range(30):
        if _safe_is_trading_day(candidate):
            return candidate
        candidate -= timedelta(days=1)
    return candidate


def _parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _to_rows(data: Any):
    if data is None:
        return []
    if hasattr(data, "to_dicts"):
        return list(data.to_dicts())
    if hasattr(data, "to_dict"):
        try:
            return list(data.to_dict("records"))
        except TypeError:
            return []
    if isinstance(data, list):
        return data
    return []


def _base_meta(target: date, as_of: Optional[str], *, fresh: bool, source: str,
               degraded: bool = False, reason: str = "", fetched_bars: int = 0,
               requested_start: Optional[date] = None,
               requested_end: Optional[date] = None) -> Dict[str, Any]:
    return {
        "fresh": fresh,
        "freshness": "fresh" if fresh else ("degraded" if degraded else "stale"),
        "degraded": degraded,
        "source": source,
        "target_date": target.isoformat(),
        "as_of": as_of,
        "fetched_bars": fetched_bars,
        "reason": reason or None,
        "requested_start": requested_start.isoformat() if requested_start else None,
        "requested_end": requested_end.isoformat() if requested_end else None,
    }


def _latest_date(repo, symbol: str) -> Optional[date]:
    try:
        return _parse_date(repo.get_latest_trade_date(symbol))
    except Exception:  # noqa: BLE001
        logger.warning("on_demand_latest_date_failed", symbol=symbol, exc_info=True)
        return None


def ensure_daily_klines(
    symbol: str,
    start_date: Any,
    end_date: Any,
    *,
    kline_repo,
    now: Optional[datetime] = None,
    allow_fetch: Optional[bool] = None,
    fetcher_factory: Optional[Callable[[], Any]] = None,
) -> Dict[str, Any]:
    """Ensure daily bars for *symbol* cover the requested end (bounded by EOD).

    Never fetches the whole market. Returns freshness metadata even when the
    upstream is unavailable; callers decide whether to serve cached rows.
    """
    symbol = str(symbol or "").strip().split(".")[0]
    target = completed_trading_day(now)
    requested_start = _parse_date(start_date)
    requested_end = _parse_date(end_date)
    if requested_end is None:
        requested_end = target
    target_end = min(requested_end, target)
    if requested_start is None:
        requested_start = target_end - timedelta(days=420)

    latest = _latest_date(kline_repo, symbol)
    if latest is not None and latest >= target_end:
        return _base_meta(
            target, latest.isoformat(), fresh=True, source="db_cache",
            requested_start=requested_start, requested_end=requested_end,
        )

    allow = _enabled() if allow_fetch is None else allow_fetch
    if not allow:
        return _base_meta(
            target, latest.isoformat() if latest else None, fresh=False,
            source="disabled", degraded=True, reason="on_demand_disabled",
            requested_start=requested_start, requested_end=requested_end,
        )

    key = f"kline:{symbol}"
    lock = _lock_for(key)
    try:
        acquired = lock.acquire(timeout=float(
            os.getenv("ON_DEMAND_LOCK_TIMEOUT_SECONDS", str(_DEFAULT_LOCK_TIMEOUT))
        ))
    except (TypeError, ValueError):
        acquired = lock.acquire(timeout=_DEFAULT_LOCK_TIMEOUT)
    if not acquired:
        return _base_meta(
            target, latest.isoformat() if latest else None, fresh=False,
            source="lock_timeout", degraded=True, reason="same_symbol_refresh_in_progress",
            requested_start=requested_start, requested_end=requested_end,
        )

    try:
        # Double-check after acquiring single-flight lock: another request may
        # have completed the backfill while we waited.
        latest = _latest_date(kline_repo, symbol)
        if latest is not None and latest >= target_end:
            return _base_meta(
                target, latest.isoformat(), fresh=True, source="db_cache",
                requested_start=requested_start, requested_end=requested_end,
            )

        earliest = target_end - timedelta(days=_MAX_LOOKBACK_DAYS)
        fetch_start = max(requested_start, earliest)
        if latest is not None:
            fetch_start = max(fetch_start, latest + timedelta(days=1))
        if fetch_start > target_end:
            return _base_meta(
                target, latest.isoformat() if latest else None, fresh=False,
                source="db_cache", degraded=True, reason="no_completed_session_in_range",
                requested_start=requested_start, requested_end=requested_end,
            )

        if not _FETCH_SEMAPHORE.acquire(timeout=_FETCH_SLOT_TIMEOUT):
            return _base_meta(
                target, latest.isoformat() if latest else None, fresh=False,
                source="busy", degraded=True, reason="upstream_fetch_slots_busy",
                requested_start=requested_start, requested_end=requested_end,
            )
        fetched_rows = 0
        try:
            factory = fetcher_factory
            if factory is None:
                from qs_market_data.adapters.outbound.datasources.multi_source_data_fetcher import (
                    MultiSourceDataFetcher,
                )
                factory = MultiSourceDataFetcher
            fetcher = factory()
            payload = fetcher.fetch_klines(
                symbol, fetch_start.isoformat(), target_end.isoformat()
            )
            rows = _to_rows(payload)
            fetched_rows = len(rows)
            if rows:
                kline_repo.save_daily_klines(rows)
        finally:
            _FETCH_SEMAPHORE.release()

        latest_after = _latest_date(kline_repo, symbol)
        fresh = bool(latest_after and latest_after >= target_end)
        meta = _base_meta(
            target, latest_after.isoformat() if latest_after else None,
            fresh=fresh,
            source="lazy_fetch" if fetched_rows else "upstream_empty",
            degraded=not fresh,
            reason="" if fresh else "target_date_not_reached",
            fetched_bars=fetched_rows,
            requested_start=requested_start,
            requested_end=requested_end,
        )
        logger.info(
            "on_demand_kline_refresh", symbol=symbol,
            requested_start=fetch_start.isoformat(), requested_end=target_end.isoformat(),
            fetched_bars=fetched_rows, fresh=fresh, as_of=meta["as_of"],
        )
        return meta
    except Exception as exc:  # noqa: BLE001 - return stale cache rather than break the tool
        logger.warning(
            "on_demand_kline_refresh_failed", symbol=symbol, error=str(exc)[:300],
        )
        return _base_meta(
            target, latest.isoformat() if latest else None, fresh=False,
            source="fetch_failed", degraded=True,
            reason=f"{type(exc).__name__}: {exc}"[:300],
            requested_start=requested_start, requested_end=requested_end,
        )
    finally:
        lock.release()


def _latest_factor_date(factor_repo, symbol: str) -> Optional[date]:
    try:
        rows = factor_repo.get_latest_factors(symbol) or []
    except Exception:  # noqa: BLE001
        return None
    dates = []
    for row in rows:
        value = getattr(row, "factor_date", None)
        if value is None and isinstance(row, dict):
            value = row.get("factor_date")
        parsed = _parse_date(value)
        if parsed is not None:
            dates.append(parsed)
    return max(dates) if dates else None


def ensure_factor_freshness(
    symbol: str,
    *,
    kline_repo,
    factor_repo,
    now: Optional[datetime] = None,
    allow_fetch: Optional[bool] = None,
    fetcher_factory: Optional[Callable[[], Any]] = None,
    compute_func: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Ensure the latest factor snapshot is for the completed trading day."""
    symbol = str(symbol or "").strip().split(".")[0]
    target = completed_trading_day(now)
    latest = _latest_factor_date(factor_repo, symbol)
    if latest is not None and latest >= target:
        return _base_meta(target, latest.isoformat(), fresh=True, source="db_cache")

    key = f"factor:{symbol}"
    lock = _lock_for(key)
    if not lock.acquire(timeout=float(
        os.getenv("ON_DEMAND_LOCK_TIMEOUT_SECONDS", str(_DEFAULT_LOCK_TIMEOUT))
    )):
        return _base_meta(
            target, latest.isoformat() if latest else None, fresh=False,
            source="lock_timeout", degraded=True, reason="same_factor_refresh_in_progress",
        )
    try:
        latest = _latest_factor_date(factor_repo, symbol)
        if latest is not None and latest >= target:
            return _base_meta(target, latest.isoformat(), fresh=True, source="db_cache")

        if not (_enabled() if allow_fetch is None else allow_fetch):
            return _base_meta(
                target, latest.isoformat() if latest else None, fresh=False,
                source="disabled", degraded=True, reason="on_demand_disabled",
            )

        kline_meta = ensure_daily_klines(
            symbol,
            (target - timedelta(days=500)).isoformat(),
            target.isoformat(),
            kline_repo=kline_repo,
            now=now,
            allow_fetch=allow_fetch,
            fetcher_factory=fetcher_factory,
        )
        compute = compute_func
        if compute is None:
            from qs_ops.application.services.scheduler_tasks_factors import (
                handle_factor_compute,
            )
            compute = handle_factor_compute
        result = compute({"symbols": [symbol], "workers": 1})
        after = _latest_factor_date(factor_repo, symbol)
        fresh = bool(after and after >= target)
        return _base_meta(
            target, after.isoformat() if after else None,
            fresh=fresh,
            source="lazy_compute",
            degraded=not fresh,
            reason="" if fresh else (
                (result or {}).get("error") or
                "factor_compute_returned_no_fresh_date"
            ),
            fetched_bars=kline_meta.get("fetched_bars", 0),
        ) | {"kline": kline_meta, "compute": result}
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "on_demand_factor_refresh_failed", symbol=symbol, error=str(exc)[:300],
        )
        return _base_meta(
            target, latest.isoformat() if latest else None, fresh=False,
            source="compute_failed", degraded=True,
            reason=f"{type(exc).__name__}: {exc}"[:300],
        )
    finally:
        lock.release()
