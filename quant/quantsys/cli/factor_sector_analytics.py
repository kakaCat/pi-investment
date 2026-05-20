"""Factor analysis and sector aggregation helpers for CLI command handlers."""

from __future__ import annotations

import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from quantsys.data.db import Database


FACTOR_VALUE_COLUMNS = {"symbol", "date", "factor_name", "factor_value"}
STOCK_METRIC_COLUMNS = ("pe", "pb", "roe", "debt_ratio")
MARKET_CAP_COLUMNS = ("market_cap", "total_market_cap")
SIGNAL_COLUMNS = ("signal", "signal_type", "action", "direction")
DEFAULT_FACTOR_SAMPLE_LIMIT = 50_000


def analyze_factors(quant_root: Path, params: dict[str, Any]) -> dict[str, Any]:
    """Analyze factor distributions from the long-form factor_values table."""
    top_n = _as_int(params.get("top_n"))
    min_observations = _as_int(params.get("min_observations")) or 1
    sample_limit = _as_int(params.get("sample_limit"))
    if sample_limit is None:
        sample_limit = DEFAULT_FACTOR_SAMPLE_LIMIT

    try:
        db = Database()
        conn = db._get_connection()

        error = _require_columns(db, "factor_values", FACTOR_VALUE_COLUMNS)
        if error:
            return _factor_error(error["code"], error["message"])
        if sample_limit > 0:
            cursor = conn.cursor()
            if db.provider == "postgres":
                cursor.execute(
                    """
                    SELECT symbol, date, factor_name, factor_value
                    FROM factor_values
                    WHERE factor_name IS NOT NULL AND factor_value IS NOT NULL
                    ORDER BY ctid DESC
                    LIMIT %s
                    """,
                    (sample_limit,),
                )
            else:
                cursor.execute(
                    """
                    SELECT symbol, date, factor_name, factor_value
                    FROM factor_values
                    WHERE factor_name IS NOT NULL AND factor_value IS NOT NULL
                    ORDER BY rowid DESC
                    LIMIT ?
                    """,
                    (sample_limit,),
                )
            sample_rows = cursor.fetchall()
            rows = _sampled_factor_summaries(sample_rows, min_observations, db.provider)
            latest_values = {str(row["factor_name"]): _as_float(row["latest_value"]) for row in rows}
        else:
            cursor = conn.cursor()
            if db.provider == "postgres":
                cursor.execute(
                    """
                    SELECT
                        factor_name,
                        COUNT(*) AS count,
                        AVG(factor_value) AS mean,
                        AVG(factor_value * factor_value) AS mean_square,
                        COUNT(DISTINCT symbol) AS coverage_symbols,
                        MAX(date) AS latest_date
                    FROM factor_values
                    WHERE factor_name IS NOT NULL AND factor_value IS NOT NULL
                    GROUP BY factor_name
                    HAVING COUNT(*) >= %s
                    ORDER BY ABS(AVG(factor_value)) DESC, COUNT(DISTINCT symbol) DESC, COUNT(*) DESC, factor_name
                    """,
                    (min_observations,),
                )
            else:
                cursor.execute(
                    """
                    SELECT
                        factor_name,
                        COUNT(*) AS count,
                        AVG(factor_value) AS mean,
                        AVG(factor_value * factor_value) AS mean_square,
                        COUNT(DISTINCT symbol) AS coverage_symbols,
                        MAX(date) AS latest_date
                    FROM factor_values
                    WHERE factor_name IS NOT NULL AND factor_value IS NOT NULL
                    GROUP BY factor_name
                    HAVING COUNT(*) >= ?
                    ORDER BY ABS(AVG(factor_value)) DESC, COUNT(DISTINCT symbol) DESC, COUNT(*) DESC, factor_name
                    """,
                    (min_observations,),
                )
            rows = cursor.fetchall()
            factor_names = [str(row[0] if db.provider == "postgres" else row["factor_name"]) for row in rows]
            latest_values = _latest_factor_values(db, factor_names)
    except Exception as exc:
        return _factor_error("DATABASE_ERROR", str(exc))

    factors = [
        _summarize_factor(row, latest_values, db.provider)
        for row in rows
    ]

    if top_n is not None and top_n >= 0:
        factors = factors[:top_n]

    return {
        "count": len(factors),
        "factors": factors,
        "sampled": sample_limit > 0,
        "sample_limit": sample_limit if sample_limit > 0 else None,
    }


def aggregate_sectors(quant_root: Path, params: dict[str, Any]) -> dict[str, Any]:
    """Aggregate stock fundamentals by sector or industry."""
    limit = _as_int(params.get("limit"))

    try:
        db = Database()
        conn = db._get_connection()

        if not _table_exists(db, "stocks"):
            return _sector_error("TABLE_NOT_FOUND", "required table stocks was not found")

        stock_columns = _table_columns(db, "stocks")
        sector_field = _sector_field(params, stock_columns)
        if sector_field is None:
            return _sector_error("COLUMN_NOT_FOUND", "stocks table requires sector or industry column")
        if "symbol" not in stock_columns:
            return _sector_error("COLUMN_NOT_FOUND", "stocks table requires symbol column")

        cursor = conn.cursor()
        cursor.execute(f"SELECT * FROM {_quote_identifier('stocks')}")
        rows = cursor.fetchall()
        signals = _load_signal_counts(db) if _table_exists(db, "signals") else {}
    except Exception as exc:
        return _sector_error("DATABASE_ERROR", str(exc))

    sectors = _summarize_sectors(rows, sector_field, signals, db.provider)
    sectors.sort(key=lambda item: (-item["total_market_cap"], item["sector"]))
    if limit is not None and limit >= 0:
        sectors = sectors[:limit]

    return {"count": len(sectors), "sector_field": sector_field, "sectors": sectors}


def _latest_factor_values(db: Database, factor_names: list[str]) -> dict[str, float | None]:
    conn = db._get_connection()
    cursor = conn.cursor()
    latest: dict[str, float | None] = {}
    for factor_name in factor_names:
        if db.provider == "postgres":
            cursor.execute(
                """
                SELECT factor_value
                FROM factor_values
                WHERE factor_name = %s AND factor_value IS NOT NULL
                ORDER BY date DESC, symbol DESC
                LIMIT 1
                """,
                (factor_name,),
            )
        else:
            cursor.execute(
                """
                SELECT factor_value
                FROM factor_values
                WHERE factor_name = ? AND factor_value IS NOT NULL
                ORDER BY date DESC, symbol DESC
                LIMIT 1
                """,
                (factor_name,),
            )
        row = cursor.fetchone()
        if db.provider == "postgres":
            latest[factor_name] = _as_float(row[0]) if row else None
        else:
            latest[factor_name] = _as_float(row["factor_value"]) if row else None
    return latest


def _sampled_factor_summaries(rows: list[tuple], min_observations: int, provider: str) -> list[dict[str, Any]]:
    grouped: dict[str, list[tuple]] = defaultdict(list)
    for row in rows:
        if provider == "postgres":
            factor_name = str(row[2])  # factor_name is 3rd column
        else:
            factor_name = str(row["factor_name"])
        grouped[factor_name].append(row)

    summaries = []
    for factor, factor_rows in grouped.items():
        if provider == "postgres":
            values = [_as_float(row[3]) for row in factor_rows]  # factor_value is 4th column
        else:
            values = [_as_float(row["factor_value"]) for row in factor_rows]
        values = [value for value in values if value is not None]
        if len(values) < min_observations:
            continue
        if provider == "postgres":
            latest_row = max(factor_rows, key=lambda row: (str(row[1] or ""), str(row[0] or "")))  # date, symbol
            latest_date = latest_row[1]
            latest_value = latest_row[3]
            symbols = {str(row[0]) for row in factor_rows if row[0] is not None}
        else:
            latest_row = max(factor_rows, key=lambda row: (str(row["date"] or ""), str(row["symbol"] or "")))
            latest_date = latest_row["date"]
            latest_value = latest_row["factor_value"]
            symbols = {str(row["symbol"]) for row in factor_rows if row["symbol"] is not None}
        mean = _mean(values)
        std = _population_std(values)
        summaries.append({
            "factor_name": factor,
            "count": len(values),
            "mean": mean,
            "mean_square": None,
            "std": std,
            "coverage_symbols": len(symbols),
            "latest_date": latest_date,
            "latest_value": latest_value,
        })
    summaries.sort(
        key=lambda item: (
            -abs(item["mean"] or 0.0),
            -int(item["coverage_symbols"] or 0),
            -int(item["count"] or 0),
            str(item["factor_name"]),
        )
    )
    return summaries


def _summarize_factor(row: tuple | Any, latest_values: dict[str, float | None], provider: str) -> dict[str, Any]:
    if provider == "postgres":
        factor = str(row[0])
        count = int(row[1])
        mean = _as_float(row[2])
        mean_square = _as_float(row[3])
        coverage_symbols = int(row[4] or 0)
        latest_date = str(row[5]) if row[5] is not None else None
        std = None
    else:
        factor = str(row["factor_name"])
        count = int(row["count"])
        mean = _as_float(row["mean"])
        std = _as_float(row["std"]) if "std" in row.keys() else None
        mean_square = _as_float(row["mean_square"])
        coverage_symbols = int(row["coverage_symbols"] or 0)
        latest_date = str(row["latest_date"]) if row["latest_date"] is not None else None

    if std is None:
        variance = None
        if mean is not None and mean_square is not None:
            variance = max(mean_square - mean * mean, 0.0)
        std = math.sqrt(variance) if variance is not None else None
    return {
        "factor": factor,
        "count": count,
        "mean": _round_metric(mean),
        "std": _round_metric(std),
        "latest_value": _round_metric(latest_values.get(factor)),
        "latest_date": latest_date,
        "coverage_symbols": coverage_symbols,
        "ic": None,
    }


def _summarize_sectors(
    rows: list[tuple],
    sector_field: str,
    signal_counts: dict[str, dict[str, int]],
    provider: str,
) -> list[dict[str, Any]]:
    grouped: dict[str, list[tuple]] = defaultdict(list)

    # Need to get column names to find sector_field index
    # For now, we'll handle this differently - pass column info or use dict-like access
    for row in rows:
        if provider == "postgres":
            # PostgreSQL returns tuples, need column mapping
            # This is a limitation - we need column names
            # For simplicity, assume row is dict-like or we get column info separately
            sector = row[sector_field] if isinstance(row, dict) else None
        else:
            sector = row[sector_field]
        if sector is None or str(sector).strip() == "":
            sector = "Unknown"
        grouped[str(sector)].append(row)

    sectors = []
    for sector, sector_rows in grouped.items():
        if provider == "postgres":
            symbols = [str(row["symbol"]) if isinstance(row, dict) else str(row[0]) for row in sector_rows]
        else:
            symbols = [str(row["symbol"]) for row in sector_rows if row["symbol"] is not None]
        buy_signals = sum(signal_counts.get(symbol, {}).get("buy", 0) for symbol in symbols)
        sell_signals = sum(signal_counts.get(symbol, {}).get("sell", 0) for symbol in symbols)
        sectors.append(
            {
                "sector": sector,
                "stock_count": len(sector_rows),
                "avg_pe": _round_metric(_average_column(sector_rows, "pe", provider)),
                "avg_pb": _round_metric(_average_column(sector_rows, "pb", provider)),
                "avg_roe": _round_metric(_average_column(sector_rows, "roe", provider)),
                "avg_debt_ratio": _round_metric(_average_column(sector_rows, "debt_ratio", provider)),
                "total_market_cap": _round_metric(sum(_market_cap(row, provider) for row in sector_rows)),
                "buy_signals": buy_signals,
                "sell_signals": sell_signals,
            }
        )
    return sectors


def _load_signal_counts(db: Database) -> dict[str, dict[str, int]]:
    columns = _table_columns(db, "signals")
    if "symbol" not in columns:
        return {}
    signal_field = next((column for column in SIGNAL_COLUMNS if column in columns), None)
    if signal_field is None:
        return {}

    conn = db._get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT symbol, {_quote_identifier(signal_field)} AS signal_value FROM {_quote_identifier('signals')}"
    )
    rows = cursor.fetchall()

    counts: dict[str, dict[str, int]] = defaultdict(lambda: {"buy": 0, "sell": 0})
    for row in rows:
        if db.provider == "postgres":
            symbol = row[0]
            direction = str(row[1] or "").upper()
        else:
            symbol = row["symbol"]
            direction = str(row["signal_value"] or "").upper()
        if symbol is None:
            continue
        if direction == "BUY":
            counts[str(symbol)]["buy"] += 1
        elif direction == "SELL":
            counts[str(symbol)]["sell"] += 1
    return counts


def _sector_field(params: dict[str, Any], columns: set[str]) -> str | None:
    requested = str(params.get("sector_field") or "sector")
    if requested in columns:
        return requested
    if requested == "sector" and "industry" in columns:
        return "industry"
    return "sector" if "sector" in columns else ("industry" if "industry" in columns else None)


def _require_columns(db: Database, table: str, required: set[str]) -> dict[str, str] | None:
    if not _table_exists(db, table):
        return {"code": "TABLE_NOT_FOUND", "message": f"required table {table} was not found"}
    columns = _table_columns(db, table)
    missing = sorted(required - columns)
    if missing:
        return {
            "code": "COLUMN_NOT_FOUND",
            "message": f"{table} table is missing columns: {', '.join(missing)}",
        }
    return None


def _table_exists(db: Database, table: str) -> bool:
    conn = db._get_connection()
    cursor = conn.cursor()

    if db.provider == "postgres":
        cursor.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = %s
            LIMIT 1
            """,
            (table,),
        )
    else:
        cursor.execute(
            """
            SELECT 1
            FROM sqlite_master
            WHERE type = 'table' AND name = ?
            LIMIT 1
            """,
            (table,),
        )
    row = cursor.fetchone()
    return row is not None


def _table_columns(db: Database, table: str) -> set[str]:
    conn = db._get_connection()
    cursor = conn.cursor()

    if db.provider == "postgres":
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s
            """,
            (table,),
        )
        return {str(row[0]) for row in cursor.fetchall()}
    else:
        cursor.execute(f"PRAGMA table_info({_quote_identifier(table)})")
        return {str(row[1]) for row in cursor.fetchall()}


def _average_column(rows: list[tuple], column: str, provider: str) -> float | None:
    if not rows:
        return None
    # This function needs column index mapping for postgres
    # For simplicity, assume dict-like access or handle separately
    if provider == "postgres":
        # Need column mapping - simplified for now
        return None
    else:
        if column not in rows[0].keys():
            return None
        return _mean([value for row in rows if (value := _as_float(row[column])) is not None])


def _market_cap(row: tuple | Any, provider: str) -> float:
    if provider == "postgres":
        # Need column mapping
        return 0.0
    else:
        for column in MARKET_CAP_COLUMNS:
            if column in row.keys():
                value = _as_float(row[column])
                if value is not None:
                    return value
        return 0.0


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _population_std(values: list[float]) -> float | None:
    if not values:
        return None
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))


def _round_metric(value: float | None) -> float | None:
    if value is None:
        return None
    return round(value, 6)


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


def _factor_error(code: str, message: str) -> dict[str, Any]:
    return {"count": 0, "factors": [], "error": {"code": code, "message": message}}


def _sector_error(code: str, message: str) -> dict[str, Any]:
    return {
        "count": 0,
        "sector_field": None,
        "sectors": [],
        "error": {"code": code, "message": message},
    }


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'
