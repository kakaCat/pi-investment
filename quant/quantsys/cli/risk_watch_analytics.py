"""Risk watch helpers for CLI command handlers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def price_alert(quant_root: Path, params: dict[str, Any]) -> dict[str, Any]:
    """Evaluate price alert thresholds from provided quote values."""
    del quant_root
    symbol = str(params.get("symbol") or "")
    price = _to_float(params.get("price")) or 0.0
    alerts = []

    above = _to_float(params.get("above"))
    if above is not None and price >= above:
        alerts.append({"type": "above", "threshold": above, "price": price})

    below = _to_float(params.get("below"))
    if below is not None and price <= below:
        alerts.append({"type": "below", "threshold": below, "price": price})

    change_threshold = _to_float(params.get("change_pct"))
    last_price = _to_float(params.get("last_price"))
    if change_threshold is not None and last_price not in (None, 0):
        change_pct = price / last_price - 1.0
        if (change_threshold >= 0 and change_pct >= change_threshold) or (
            change_threshold < 0 and change_pct <= change_threshold
        ):
            alerts.append({
                "type": "change_pct",
                "threshold": change_threshold,
                "change_pct": change_pct,
                "last_price": last_price,
                "price": price,
            })

    return {
        "symbol": symbol,
        "price": price,
        "triggered": bool(alerts),
        "alerts": alerts,
    }


def stress_test(quant_root: Path, params: dict[str, Any]) -> dict[str, Any]:
    """Apply a uniform price shock to portfolio positions."""
    del quant_root
    positions = _parse_items(params.get("positions"), params.get("positions_json"))
    shock_pct = _to_float(params.get("shock_pct")) or 0.0
    cash = _to_float(params.get("cash")) or 0.0

    details = []
    before_positions = 0.0
    after_positions = 0.0
    for position in positions:
        before = _position_value(position)
        after = before * (1.0 + shock_pct)
        before_positions += before
        after_positions += after
        details.append({
            "symbol": str(position.get("symbol") or ""),
            "before_value": before,
            "after_value": after,
            "loss_amount": before - after,
        })

    before_value = before_positions + cash
    after_value = after_positions + cash
    loss_amount = before_value - after_value
    return {
        "shock_pct": shock_pct,
        "cash": cash,
        "before_value": before_value,
        "after_value": after_value,
        "loss_amount": loss_amount,
        "loss_pct": loss_amount / before_value if before_value else 0.0,
        "positions": details,
    }


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


def _position_value(position: dict[str, Any]) -> float:
    market_value = _to_float(position.get("market_value"))
    if market_value is not None:
        return market_value
    quantity = _to_float(position.get("quantity")) or 0.0
    price = _to_float(position.get("price")) or 0.0
    return quantity * price


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
