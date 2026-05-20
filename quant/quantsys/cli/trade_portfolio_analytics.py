"""Trade verification and portfolio correlation helpers for CLI command handlers."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any


def verify_trades(quant_root: Path, params: dict[str, Any]) -> dict[str, Any]:
    """Compare real trades against backtest trades by symbol and action."""
    del quant_root
    trades = _parse_items(params.get("trades"), params.get("trades_json"))
    backtest = _parse_items(params.get("backtest"), params.get("backtest_json"))
    remaining = backtest.copy()
    matched = []
    missing = []

    for trade in trades:
        match_index = _find_trade(remaining, trade)
        if match_index is None:
            missing.append(_trade_summary(trade))
            continue
        backtest_trade = remaining.pop(match_index)
        trade_price = _to_float(trade.get("price"))
        backtest_price = _to_float(backtest_trade.get("price"))
        slippage = None
        if trade_price is not None and backtest_price not in (None, 0):
            slippage = trade_price / backtest_price - 1.0
        matched.append({
            "symbol": _symbol(trade),
            "action": _action(trade),
            "trade_price": trade_price,
            "backtest_price": backtest_price,
            "slippage_pct": slippage,
        })

    slippages = [item["slippage_pct"] for item in matched if item["slippage_pct"] is not None]
    return {
        "matched_count": len(matched),
        "matched": matched,
        "missing_in_backtest": [_trade_summary(item) for item in missing],
        "extra_backtest": [_trade_summary(item) for item in remaining],
        "avg_slippage_pct": sum(slippages) / len(slippages) if slippages else None,
        "summary": f"matched {len(matched)} of {len(trades)} trades",
    }


def correlate_portfolio(quant_root: Path, params: dict[str, Any]) -> dict[str, Any]:
    """Calculate a Pearson correlation matrix from supplied price series."""
    del quant_root
    prices = _parse_prices(params.get("prices"), params.get("prices_json"))
    threshold = _to_float(params.get("threshold"))
    if threshold is None:
        threshold = 0.7

    symbols = sorted(prices)
    matrix: dict[str, dict[str, float | None]] = {symbol: {} for symbol in symbols}
    high_pairs = []
    for i, left in enumerate(symbols):
        for j, right in enumerate(symbols):
            if i == j:
                corr = 1.0 if len(prices[left]) >= 2 else None
            elif right in matrix and left in matrix[right]:
                corr = matrix[right][left]
            else:
                corr = _pearson(prices[left], prices[right])
            matrix[left][right] = _round(corr)
            if i < j and corr is not None and abs(corr) >= threshold:
                high_pairs.append({"symbols": [left, right], "correlation": _round(corr)})

    return {
        "symbols": symbols,
        "correlation_matrix": matrix,
        "high_correlation_pairs": high_pairs,
        "threshold": threshold,
    }


def _find_trade(candidates: list[dict[str, Any]], trade: dict[str, Any]) -> int | None:
    symbol = _symbol(trade)
    action = _action(trade)
    for index, candidate in enumerate(candidates):
        if _symbol(candidate) == symbol and _action(candidate) == action:
            return index
    return None


def _trade_summary(trade: dict[str, Any]) -> dict[str, Any]:
    summary = {"symbol": _symbol(trade), "action": _action(trade)}
    price = _to_float(trade.get("price"))
    if price is not None:
        summary["price"] = price
    return summary


def _symbol(trade: dict[str, Any]) -> str:
    return str(trade.get("symbol") or "")


def _action(trade: dict[str, Any]) -> str:
    return str(trade.get("action") or trade.get("signal") or trade.get("signal_type") or "").upper()


def _parse_items(items: Any, items_json: Any) -> list[dict[str, Any]]:
    if isinstance(items, list):
        return [item for item in items if isinstance(item, dict)]
    if items_json:
        try:
            parsed = json.loads(str(items_json))
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, dict)]
    return []


def _parse_prices(prices: Any, prices_json: Any) -> dict[str, list[float]]:
    payload = prices
    if payload is None and prices_json:
        try:
            payload = json.loads(str(prices_json))
        except json.JSONDecodeError:
            payload = {}
    if not isinstance(payload, dict):
        return {}
    parsed: dict[str, list[float]] = {}
    for symbol, values in payload.items():
        if not isinstance(values, list):
            continue
        parsed[str(symbol)] = [value for value in (_to_float(item) for item in values) if value is not None]
    return parsed


def _pearson(left: list[float], right: list[float]) -> float | None:
    length = min(len(left), len(right))
    if length < 2:
        return None
    xs = left[-length:]
    ys = right[-length:]
    mean_x = sum(xs) / length
    mean_y = sum(ys) / length
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    denom_x = math.sqrt(sum((x - mean_x) ** 2 for x in xs))
    denom_y = math.sqrt(sum((y - mean_y) ** 2 for y in ys))
    if denom_x == 0 or denom_y == 0:
        return None
    return numerator / (denom_x * denom_y)


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)
