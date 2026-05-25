"""Stock scoring and screening helpers for CLI command handlers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quantsys.data.db import Database


SCORE_FIELDS = (
    "technical_score",
    "fundamental_score",
    "momentum_score",
    "quality_score",
    "valuation_score",
)
FACTOR_FIELDS = (
    "pe",
    "pb",
    "roe",
    "debt_ratio",
    "rsi",
    "momentum",
    "revenue_growth",
    "profit_margin",
)
FILTER_FIELDS = {
    "pe_max": ("pe", "<="),
    "pe_min": ("pe", ">="),
    "pb_max": ("pb", "<="),
    "pb_min": ("pb", ">="),
    "roe_min": ("roe", ">="),
    "debt_ratio_max": ("debt_ratio", "<="),
    "rsi_max": ("rsi", "<="),
    "rsi_min": ("rsi", ">="),
}


def score_stock(quant_root: Path, params: dict[str, Any]) -> dict[str, Any]:
    """Score one stock using available PostgreSQL factor data."""
    symbol = str(params.get("symbol") or "").strip()
    if not symbol:
        return _error("", "MISSING_SYMBOL", "symbol is required")

    source = _load_source(quant_root)
    if "error" in source:
        return _error(symbol, source["error"]["code"], source["error"]["message"])

    schema = source["schema"]
    table_name = source["table"]
    columns = source["columns"]
    table_ref = f"{_quote_identifier(schema)}.{_quote_identifier(table_name)}" if schema else _quote_identifier(table_name)

    try:
        with Database() as db:
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT * FROM {table_ref} WHERE symbol = %s LIMIT 1",
                (symbol,),
            )
            row = cursor.fetchone()
            if row:
                col_names = [desc[0] for desc in cursor.description]
                row = dict(zip(col_names, row))
    except Exception as exc:
        return _error(symbol, "DATABASE_ERROR", str(exc))

    if row is None:
        return _error(symbol, "STOCK_NOT_FOUND", f"symbol {symbol} was not found")

    return _score_row(row, columns)


def screen_stocks(quant_root: Path, params: dict[str, Any]) -> dict[str, Any]:
    """Screen stocks by factor thresholds, score each match, and sort results."""
    source = _load_source(quant_root)
    if "error" in source:
        return {"count": 0, "stocks": [], "error": source["error"]}

    schema = source["schema"]
    table_name = source["table"]
    columns = source["columns"]
    table_ref = f"{_quote_identifier(schema)}.{_quote_identifier(table_name)}" if schema else _quote_identifier(table_name)

    try:
        with Database() as db:
            conn = db.get_connection()
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table_ref}")
            rows = cursor.fetchall()
            col_names = [desc[0] for desc in cursor.description]
            rows = [dict(zip(col_names, row)) for row in rows]
    except Exception as exc:
        return {
            "count": 0,
            "stocks": [],
            "error": {"code": "DATABASE_ERROR", "message": str(exc)},
        }

    scored = []
    for row in rows:
        stock = _score_row(row, columns)
        if _matches_filters(stock, params):
            scored.append(stock)

    min_score = _as_float(params.get("min_score"))
    if min_score is not None:
        scored = [stock for stock in scored if stock["total_score"] >= min_score]

    sort_by = str(params.get("sort_by") or "total_score")
    reverse = sort_by not in {"pe", "pb", "debt_ratio", "rsi"}
    scored.sort(key=lambda stock: _sort_value(stock, sort_by, reverse), reverse=reverse)

    limit = _as_int(params.get("limit"))
    if limit is not None and limit >= 0:
        scored = scored[:limit]

    return {"count": len(scored), "stocks": scored}


def _load_source(quant_root: Path) -> dict[str, Any]:
    try:
        with Database() as db:
            conn = db.get_connection()
            cursor = conn.cursor()
            schema = db.schema
            table_name = _find_symbol_table(cursor, schema)
            if table_name is None:
                return {
                    "error": {
                        "code": "TABLE_NOT_FOUND",
                        "message": "no table with a symbol column was found",
                    }
                }
            columns = _table_columns(cursor, table_name, schema)
    except Exception as exc:
        return {"error": {"code": "DATABASE_ERROR", "message": str(exc)}}

    return {"schema": schema, "table": table_name, "columns": columns}


def _find_symbol_table(cursor, schema: str | None) -> str | None:
    if schema:
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s AND table_type = 'BASE TABLE'
            ORDER BY table_name
            """,
            (schema,),
        )
    else:
        # SQLite fallback: use sqlite_master
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    rows = cursor.fetchall()
    candidates: list[tuple[int, int, str]] = []
    for (table,) in rows:
        columns = _table_columns(cursor, table, schema)
        if "symbol" in columns:
            score_field_count = sum(1 for field in FACTOR_FIELDS if field in columns)
            name_priority = 0 if str(table).lower() == "stocks" else 1
            candidates.append((-score_field_count, name_priority, str(table)))
    if not candidates:
        return None
    candidates.sort()
    return candidates[0][2]


def _table_columns(cursor, table: str, schema: str | None) -> set[str]:
    if schema:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            """,
            (schema, table),
        )
    else:
        cursor.execute(f"PRAGMA table_info({_quote_identifier(table)})")
        return {str(row[1]) for row in cursor.fetchall()}
    return {str(row[0]) for row in cursor.fetchall()}


def _score_row(row: dict[str, Any], columns: set[str]) -> dict[str, Any]:
    factors = {field: _as_float(row.get(field)) if field in columns else None for field in FACTOR_FIELDS}
    scores = {
        "technical_score": _score_rsi(factors["rsi"]),
        "fundamental_score": _score_fundamental(factors["roe"], factors["debt_ratio"], factors["revenue_growth"]),
        "momentum_score": _score_momentum(factors["momentum"]),
        "quality_score": _score_quality(factors["roe"], factors["profit_margin"], factors["debt_ratio"]),
        "valuation_score": _score_valuation(factors["pe"], factors["pb"]),
    }
    total_score = round(sum(scores.values()) / len(scores), 2)
    reasons = _reasons(factors, scores)

    return {
        "symbol": str(row.get("symbol") or ""),
        "total_score": total_score,
        **scores,
        "recommendation": _recommendation(total_score),
        "reasons": reasons,
        "factors": factors,
    }


def _score_rsi(rsi: float | None) -> float:
    if rsi is None:
        return 50.0
    if 45 <= rsi <= 60:
        return 82.0
    if 35 <= rsi < 45 or 60 < rsi <= 70:
        return 68.0
    if 25 <= rsi < 35:
        return 58.0
    return 35.0


def _score_fundamental(roe: float | None, debt_ratio: float | None, growth: float | None) -> float:
    score = 50.0
    if roe is not None:
        score += _bounded(roe * 120, -20, 35)
    if debt_ratio is not None:
        score += _bounded((0.55 - debt_ratio) * 50, -20, 20)
    if growth is not None:
        score += _bounded(growth * 80, -15, 20)
    return round(_bounded(score, 0, 100), 2)


def _score_momentum(momentum: float | None) -> float:
    if momentum is None:
        return 50.0
    return round(_bounded(50 + momentum * 250, 0, 100), 2)


def _score_quality(roe: float | None, margin: float | None, debt_ratio: float | None) -> float:
    score = 50.0
    if roe is not None:
        score += _bounded(roe * 100, -15, 30)
    if margin is not None:
        score += _bounded(margin * 70, -10, 25)
    if debt_ratio is not None:
        score += _bounded((0.45 - debt_ratio) * 45, -18, 18)
    return round(_bounded(score, 0, 100), 2)


def _score_valuation(pe: float | None, pb: float | None) -> float:
    score = 50.0
    if pe is not None:
        if pe <= 0:
            score += 0
        elif pe <= 15:
            score += 28
        elif pe <= 25:
            score += 18
        elif pe <= 40:
            score += 4
        else:
            score -= 18
    if pb is not None:
        if pb <= 1.5:
            score += 18
        elif pb <= 3:
            score += 10
        elif pb <= 6:
            score -= 2
        else:
            score -= 15
    return round(_bounded(score, 0, 100), 2)


def _matches_filters(stock: dict[str, Any], params: dict[str, Any]) -> bool:
    factors = stock["factors"]
    for param, (field, operator) in FILTER_FIELDS.items():
        threshold = _as_float(params.get(param))
        value = factors.get(field)
        if threshold is None:
            continue
        if value is None:
            return False
        if operator == "<=" and value > threshold:
            return False
        if operator == ">=" and value < threshold:
            return False
    return True


def _sort_value(stock: dict[str, Any], sort_by: str, reverse: bool) -> float:
    value = stock.get(sort_by)
    if value is None:
        value = stock["factors"].get(sort_by)
    parsed = _as_float(value)
    if parsed is None:
        return float("-inf") if reverse else float("inf")
    return parsed


def _reasons(factors: dict[str, float | None], scores: dict[str, float]) -> list[str]:
    reasons = []
    if factors["roe"] is None:
        reasons.append("roe missing, fundamental score uses neutral baseline")
    elif factors["roe"] >= 0.15:
        reasons.append("roe is strong")
    else:
        reasons.append("roe is below preferred threshold")

    if factors["rsi"] is None:
        reasons.append("rsi missing, technical score uses neutral baseline")
    elif 45 <= factors["rsi"] <= 60:
        reasons.append("rsi is in a balanced range")
    elif factors["rsi"] > 70:
        reasons.append("rsi indicates overbought risk")
    else:
        reasons.append("rsi is outside the preferred range")

    if scores["valuation_score"] >= 70:
        reasons.append("valuation factors are attractive")
    elif scores["valuation_score"] < 45:
        reasons.append("valuation factors are expensive")
    return reasons


def _recommendation(total_score: float) -> str:
    if total_score >= 70:
        return "buy"
    if total_score >= 45:
        return "hold"
    return "sell"


def _error(symbol: str, code: str, message: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "total_score": 0.0,
        "technical_score": 0.0,
        "fundamental_score": 0.0,
        "momentum_score": 0.0,
        "quality_score": 0.0,
        "valuation_score": 0.0,
        "recommendation": "unknown",
        "reasons": [message],
        "factors": {},
        "error": {"code": code, "message": message},
    }


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _bounded(value: float, lower: float, upper: float) -> float:
    return min(max(value, lower), upper)


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'
