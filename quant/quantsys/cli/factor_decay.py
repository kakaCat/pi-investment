"""Factor decay helpers for CLI command handlers."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from quantsys.data.db import Database


DEFAULT_HORIZONS = [5, 10, 20, 60]


def analyze_factor_decay(quant_root: Path, params: dict[str, Any]) -> dict[str, Any]:
    """Analyze factor IC decay across forward-return horizons."""
    factor = str(params.get("factor") or "").strip() or None
    horizons = _parse_horizons(params.get("horizons"))

    try:
        db = Database()
        conn = db._get_connection()

        if not _table_exists(db, "factor_values"):
            return _error(factor, "TABLE_NOT_FOUND", "required table factor_values was not found")
        if factor is None:
            return {
                "factor": None,
                "decay": [],
                "available_factors": _available_factors(db),
                "error": {"code": "MISSING_FACTOR", "message": "factor is required"},
            }
        if not _table_exists(db, "factor_returns"):
            return _error(factor, "TABLE_NOT_FOUND", "required table factor_returns was not found")

        decay = [_decay_for_horizon(db, factor, horizon) for horizon in horizons]
    except Exception as exc:
        return _error(factor, "DATABASE_ERROR", str(exc))

    known = [item for item in decay if item["ic"] is not None]
    return {
        "factor": factor,
        "horizons": horizons,
        "decay": decay,
        "half_life_days": _half_life(known),
    }


def _decay_for_horizon(db: Database, factor: str, horizon: int) -> dict[str, Any]:
    conn = db._get_connection()
    cursor = conn.cursor()

    if db.provider == "postgres":
        cursor.execute(
            """
            SELECT fv.factor_value, fr.return_pct
            FROM factor_values fv
            JOIN factor_returns fr
              ON fv.symbol = fr.symbol AND fv.date = fr.date
            WHERE fv.factor_name = %s
              AND fr.forward_days = %s
              AND fv.factor_value IS NOT NULL
              AND fr.return_pct IS NOT NULL
            """,
            (factor, horizon),
        )
    else:
        cursor.execute(
            """
            SELECT fv.factor_value, fr.return_pct
            FROM factor_values fv
            JOIN factor_returns fr
              ON fv.symbol = fr.symbol AND fv.date = fr.date
            WHERE fv.factor_name = ?
              AND fr.forward_days = ?
              AND fv.factor_value IS NOT NULL
              AND fr.return_pct IS NOT NULL
            """,
            (factor, horizon),
        )

    rows = cursor.fetchall()

    if db.provider == "postgres":
        factor_values = [_to_float(row[0]) for row in rows]
        returns = [_to_float(row[1]) for row in rows]
    else:
        factor_values = [_to_float(row["factor_value"]) for row in rows]
        returns = [_to_float(row["return_pct"]) for row in rows]
    pairs = [
        (factor_value, return_value)
        for factor_value, return_value in zip(factor_values, returns)
        if factor_value is not None and return_value is not None
    ]
    ic = _pearson([pair[0] for pair in pairs], [pair[1] for pair in pairs])
    return {
        "horizon": horizon,
        "ic": _round(ic),
        "abs_ic": _round(abs(ic)) if ic is not None else None,
        "observations": len(pairs),
    }


def _available_factors(db: Database) -> list[str]:
    conn = db._get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT DISTINCT factor_name
        FROM factor_values
        WHERE factor_name IS NOT NULL
        ORDER BY factor_name
        """
    )
    rows = cursor.fetchall()
    if db.provider == "postgres":
        return [str(row[0]) for row in rows]
    else:
        return [str(row["factor_name"]) for row in rows]


def _half_life(decay: list[dict[str, Any]]) -> int | None:
    if not decay:
        return None
    initial = decay[0]["abs_ic"]
    if initial is None:
        return None
    threshold = initial / 2
    for item in decay[1:]:
        if item["abs_ic"] is not None and item["abs_ic"] <= threshold:
            return int(item["horizon"])
    return int(decay[-1]["horizon"])


def _parse_horizons(value: Any) -> list[int]:
    if value in (None, ""):
        return DEFAULT_HORIZONS[:]
    if isinstance(value, str):
        raw = value.split(",")
    elif isinstance(value, list | tuple):
        raw = value
    else:
        raw = [value]
    horizons = []
    for item in raw:
        try:
            parsed = int(item)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            horizons.append(parsed)
    return horizons or DEFAULT_HORIZONS[:]


def _table_exists(db: Database, table: str) -> bool:
    conn = db._get_connection()
    cursor = conn.cursor()

    if db.provider == "postgres":
        cursor.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = %s LIMIT 1",
            (table,),
        )
    else:
        cursor.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ? LIMIT 1",
            (table,),
        )

    row = cursor.fetchone()
    return row is not None


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
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


def _error(factor: str | None, code: str, message: str) -> dict[str, Any]:
    return {
        "factor": factor,
        "decay": [],
        "error": {"code": code, "message": message},
    }
