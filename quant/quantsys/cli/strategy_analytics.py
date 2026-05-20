"""Strategy analytics helpers for CLI command handlers."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


HOLD_MARGIN = 0.10


def analyze_performance(quant_root: Path, params: dict[str, Any]) -> dict[str, Any]:
    """Analyze strategy performance from generated signal JSON files."""
    strategy_id = str(params.get("strategy_id", "all"))
    days = int(params.get("days", 30))
    signals = _load_signals_from_dir(_signals_dir(quant_root, params), days=days)

    if strategy_id != "all":
        signals = [
            signal
            for signal in signals
            if _strategy_id(signal) == strategy_id
        ]

    buy_signals = sum(1 for signal in signals if _direction(signal) == "BUY")
    sell_signals = sum(1 for signal in signals if _direction(signal) == "SELL")
    dated_signals = sorted(
        (signal for signal in signals if _signal_date(signal)),
        key=lambda signal: _signal_date(signal) or "",
    )
    returns = [_return_pct(signal) for signal in signals]
    known_returns = [value for value in returns if value is not None]

    return {
        "strategy_id": strategy_id,
        "period_days": days,
        "total_signals": len(signals),
        "buy_signals": buy_signals,
        "sell_signals": sell_signals,
        "win_rate": _win_rate(known_returns),
        "avg_profit_pct": _average(known_returns),
        "max_drawdown_pct": _max_drawdown_pct(known_returns),
        "sharpe_ratio": _sharpe_ratio(known_returns),
        "first_signal_date": _signal_date(dated_signals[0]) if dated_signals else None,
        "last_signal_date": _signal_date(dated_signals[-1]) if dated_signals else None,
    }


def arbitrate_signals(quant_root: Path, params: dict[str, Any]) -> dict[str, Any]:
    """Arbitrate trading signals by symbol using confidence-weighted scores."""
    if isinstance(params.get("signals"), list):
        signals = [signal for signal in params["signals"] if isinstance(signal, dict)]
        source = "params"
    else:
        signals = _load_signals_for_date(_signals_dir(quant_root, params), str(params.get("date", "")))
        source = "file"

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for signal in signals:
        symbol = signal.get("symbol")
        direction = _direction(signal)
        if symbol and direction in {"BUY", "SELL"}:
            grouped[str(symbol)].append(signal)

    decisions = [_arbitrate_symbol(symbol, grouped[symbol]) for symbol in sorted(grouped)]
    result: dict[str, Any] = {
        "source": source,
        "total_symbols": len(decisions),
        "decisions": decisions,
    }
    if params.get("date") is not None:
        result["date"] = str(params["date"])
    return result


def _signals_dir(quant_root: Path, params: dict[str, Any]) -> Path:
    raw = params.get("signals_dir")
    if raw:
        path = Path(str(raw))
        return path if path.is_absolute() else quant_root / path
    return quant_root / ".pi-invest"


def _load_signals_from_dir(signals_dir: Path, days: int | None = None) -> list[dict[str, Any]]:
    if not signals_dir.exists():
        return []

    signals: list[dict[str, Any]] = []
    for file in sorted(signals_dir.glob("*.json")):
        signals.extend(_read_signal_file(file))

    if days is None or days <= 0:
        return signals

    max_day = _max_signal_day(signals)
    if max_day is None:
        return signals

    cutoff = max_day - timedelta(days=days - 1)
    return [
        signal
        for signal in signals
        if (parsed := _parse_signal_day(signal)) is None or parsed >= cutoff
    ]


def _load_signals_for_date(signals_dir: Path, target_date: str) -> list[dict[str, Any]]:
    if not target_date:
        return []

    candidates = [
        signals_dir / f"{target_date}.json",
        signals_dir / f"signals_{target_date}.json",
        signals_dir / f"signals-{target_date}.json",
    ]
    for file in candidates:
        if file.exists():
            return _read_signal_file(file)
    return []


def _read_signal_file(file: Path) -> list[dict[str, Any]]:
    try:
        payload = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    if isinstance(payload, list):
        items = payload
        file_date = file.stem
    elif isinstance(payload, dict):
        items = payload.get("signals", [])
        file_date = payload.get("date") or file.stem
    else:
        return []

    signals = [item.copy() for item in items if isinstance(item, dict)]
    for signal in signals:
        signal.setdefault("date", file_date)
    return signals


def _arbitrate_symbol(symbol: str, signals: list[dict[str, Any]]) -> dict[str, Any]:
    buy_score = sum(_confidence(signal) for signal in signals if _direction(signal) == "BUY")
    sell_score = sum(_confidence(signal) for signal in signals if _direction(signal) == "SELL")
    conflicts = buy_score > 0 and sell_score > 0
    diff = buy_score - sell_score

    if conflicts and abs(diff) <= HOLD_MARGIN:
        decision = "HOLD"
        confidence = abs(diff)
        reason = f"Conflict between BUY and SELL signals; score difference {abs(diff):.2f} is too small."
    elif diff > 0:
        decision = "BUY"
        confidence = diff if conflicts else buy_score
        reason = _decision_reason(signals, "BUY", conflicts)
    elif diff < 0:
        decision = "SELL"
        confidence = abs(diff) if conflicts else sell_score
        reason = _decision_reason(signals, "SELL", conflicts)
    else:
        decision = "HOLD"
        confidence = 0.0
        reason = "No directional score advantage."

    return {
        "symbol": symbol,
        "decision": decision,
        "confidence": _round_metric(confidence),
        "reason": reason,
        "buy_score": _round_metric(buy_score),
        "sell_score": _round_metric(sell_score),
        "conflicts": conflicts,
    }


def _decision_reason(signals: list[dict[str, Any]], direction: str, conflicts: bool) -> str:
    reasons = [
        str(signal.get("reason"))
        for signal in signals
        if _direction(signal) == direction and signal.get("reason")
    ]
    prefix = "Conflict resolved by confidence-weighted score" if conflicts else f"{direction} signals only"
    if not reasons:
        return f"{prefix}."
    return f"{prefix}: {'; '.join(reasons[:3])}"


def _strategy_id(signal: dict[str, Any]) -> str:
    return str(signal.get("strategy_id") or signal.get("strategy") or signal.get("strategy_name") or "")


def _direction(signal: dict[str, Any]) -> str:
    raw = signal.get("signal") or signal.get("signal_type") or signal.get("action") or signal.get("direction")
    return str(raw or "").upper()


def _confidence(signal: dict[str, Any]) -> float:
    value = _to_float(signal.get("confidence"))
    if value is None:
        return 1.0
    return max(0.0, min(1.0, value))


def _return_pct(signal: dict[str, Any]) -> float | None:
    for key in ("profit_pct", "return_pct"):
        value = _to_float(signal.get(key))
        if value is not None:
            return value
    return None


def _signal_date(signal: dict[str, Any]) -> str | None:
    value = signal.get("date") or signal.get("signal_date")
    if value is None:
        timestamp = signal.get("timestamp")
        if timestamp:
            return str(timestamp)[:10]
        return None
    return str(value)[:10]


def _parse_signal_day(signal: dict[str, Any]) -> date | None:
    raw = _signal_date(signal)
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _max_signal_day(signals: list[dict[str, Any]]) -> date | None:
    days = [_parse_signal_day(signal) for signal in signals]
    known_days = [day for day in days if day is not None]
    return max(known_days) if known_days else None


def _win_rate(values: list[float]) -> float | None:
    if not values:
        return None
    return _round_metric(sum(1 for value in values if value > 0) / len(values))


def _average(values: list[float]) -> float | None:
    if not values:
        return None
    return _round_metric(sum(values) / len(values))


def _max_drawdown_pct(values: list[float]) -> float:
    if not values:
        return 0.0

    equity = 1.0
    peak = 1.0
    max_drawdown = 0.0
    for value in values:
        equity *= 1 + value / 100.0
        peak = max(peak, equity)
        if peak > 0:
            max_drawdown = max(max_drawdown, (peak - equity) / peak)
    return _round_metric(max_drawdown * 100.0)


def _sharpe_ratio(values: list[float]) -> float | None:
    if len(values) < 2:
        return None

    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    stddev = math.sqrt(variance)
    if stddev == 0:
        return None
    return _round_metric((mean / stddev) * math.sqrt(len(values)))


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _round_metric(value: float) -> float:
    return round(float(value), 6)
