"""Thread-local numpy cache for factor calculation.

Pre-extracts OHLCV arrays from klines once per batch, so 64 factors
don't each re-extract the same data 20+ times.

Usage — automatic via FactorRegistry.calculate_batch::

    with FactorCache.activate(klines):
        # all _closes(), _highs() etc. return cached numpy arrays
        ma5(klines)  # uses cache, not klines

Manual::

    cache = FactorCache.pre_extract(klines)
    with FactorCache.use(cache):
        ...
"""
from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any

import numpy as np

_thread_local = threading.local()


class FactorCache:
    """Pre-extracted numpy arrays for factor calculation.

    Avoids 20+ redundant _closes() / _highs() / _lows() / _volumes()
    extractions per batch.
    """

    @staticmethod
    def pre_extract(klines: list[dict]) -> dict[str, np.ndarray]:
        """Convert klines to numpy arrays once.

        Returns a cache dict with keys: closes, highs, lows, opens, volumes.
        """
        n = len(klines)
        closes = np.empty(n, dtype=np.float64)
        highs = np.empty(n, dtype=np.float64)
        lows = np.empty(n, dtype=np.float64)
        opens = np.empty(n, dtype=np.float64)
        volumes = np.empty(n, dtype=np.float64)

        for i, k in enumerate(klines):
            closes[i] = float(k['close'])
            highs[i] = float(k['high'])
            lows[i] = float(k['low'])
            opens[i] = float(k['open'])
            volumes[i] = float(k.get('volume', 0))

        cache = {
            'closes': closes,
            'highs': highs,
            'lows': lows,
            'opens': opens,
            'volumes': volumes,
            '_klines': klines,
            '_n': n,
        }
        return cache

    @classmethod
    def get_cache(cls) -> dict | None:
        """Return the current thread-local cache, or None."""
        return getattr(_thread_local, 'cache', None)

    @classmethod
    def set_cache(cls, cache: dict | None):
        _thread_local.cache = cache

    @classmethod
    @contextmanager
    def activate(cls, klines: list[dict]):
        """Context manager: pre-extract and set as thread-local cache."""
        cache = cls.pre_extract(klines)
        prev = cls.get_cache()
        cls.set_cache(cache)
        try:
            yield cache
        finally:
            cls.set_cache(prev)

    @classmethod
    @contextmanager
    def use(cls, cache: dict):
        """Context manager: use an existing cache dict."""
        prev = cls.get_cache()
        cls.set_cache(cache)
        try:
            yield
        finally:
            cls.set_cache(prev)


def _cached_array(klines: list[dict], key: str) -> np.ndarray | None:
    """Return cached numpy array if available, else None."""
    cache = FactorCache.get_cache()
    if cache is not None and cache.get('_klines') is klines:
        return cache.get(key)
    return None


def cached_closes(klines: list[dict]) -> np.ndarray:
    """Get closes as numpy array — from cache or by extraction."""
    arr = _cached_array(klines, 'closes')
    if arr is not None:
        return arr
    return np.array([float(k['close']) for k in klines], dtype=np.float64)


def cached_highs(klines: list[dict]) -> np.ndarray:
    arr = _cached_array(klines, 'highs')
    if arr is not None:
        return arr
    return np.array([float(k['high']) for k in klines], dtype=np.float64)


def cached_lows(klines: list[dict]) -> np.ndarray:
    arr = _cached_array(klines, 'lows')
    if arr is not None:
        return arr
    return np.array([float(k['low']) for k in klines], dtype=np.float64)


def cached_volumes(klines: list[dict]) -> np.ndarray:
    arr = _cached_array(klines, 'volumes')
    if arr is not None:
        return arr
    return np.array([float(k.get('volume', 0)) for k in klines], dtype=np.float64)
