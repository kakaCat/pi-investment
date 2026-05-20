#!/usr/bin/env python3
"""Runtime smoke checks for the PostgreSQL-backed quant platform."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUANT_ROOT = PROJECT_ROOT / "quant"
sys.path.insert(0, str(QUANT_ROOT))


def _ensure_postgres_env(pg_database: str) -> None:
    os.environ["QUANT_DB_PROVIDER"] = "postgres"
    os.environ.setdefault("PGDATABASE", pg_database)


def _check_database(symbol: str) -> dict[str, Any]:
    from quantsys.data.db import Database

    database = Database()
    try:
        kline_stats = database.get_kline_stats()
        factor_stats = database.get_factor_stats()
        coverage = database.get_kline_coverage(symbol)
    finally:
        database.close()

    if kline_stats["records"] <= 0:
        raise RuntimeError("No PostgreSQL kline rows found")
    if factor_stats["records"] <= 0:
        raise RuntimeError("No PostgreSQL factor rows found")
    if coverage["existing_days"] <= 0:
        raise RuntimeError(f"No PostgreSQL kline coverage for {symbol}")

    return {
        "kline_records": kline_stats["records"],
        "kline_symbols": kline_stats["symbols"],
        "kline_max_date": kline_stats["max_date"],
        "factor_records": factor_stats["records"],
        "factor_dates": factor_stats["dates"],
        "factor_max_date": factor_stats["max_date"],
        "symbol_coverage": coverage,
    }


def _check_quant_api(symbol: str) -> dict[str, Any]:
    from api.quant_api import QuantAPI

    api = QuantAPI()
    klines = api.get_klines(symbol, limit=3)
    factors = api.get_stock_factors(symbol)

    if klines.get("count", 0) <= 0:
        raise RuntimeError(f"QuantAPI returned no klines for {symbol}")
    if "error" in factors or not factors.get("factors"):
        raise RuntimeError(f"QuantAPI returned no factors for {symbol}: {factors}")

    return {
        "klines": klines["count"],
        "latest_kline_date": klines["klines"][0]["date"],
        "factor_date": factors["date"],
        "factor_count": len(factors["factors"]),
    }


def _check_weekly_backtest(symbol: str) -> dict[str, Any]:
    from scripts.weekly_backtest import WeeklyBacktester

    backtester = WeeklyBacktester(str(QUANT_ROOT))
    try:
        frame = backtester.load_kline_data(symbol, days=5)
    finally:
        backtester.close()

    if frame is None or frame.empty:
        raise RuntimeError(f"WeeklyBacktester returned no kline frame for {symbol}")

    return {
        "rows": int(len(frame.index)),
        "columns": list(frame.columns),
        "start": str(frame.iloc[0]["timestamp"].date()),
        "end": str(frame.iloc[-1]["timestamp"].date()),
    }


def _check_confidence_calibrator(args: argparse.Namespace) -> dict[str, Any]:
    from quantsys.ml.confidence_calibrator import ConfidenceCalibrator

    calibrator = ConfidenceCalibrator(
        db_path=str(PROJECT_ROOT / ".pi-invest" / "stock-db" / "stocks.db"),
        forward_days=args.calibration_forward_days,
        return_threshold=0.02,
        min_samples_per_bin=args.calibration_min_samples_per_bin,
        max_symbols=args.calibration_symbols,
        lookback_days=args.calibration_lookback_days,
    )
    config = calibrator.calibrate_all()
    factors = config.get("factors", {})

    if not factors:
        raise RuntimeError("Confidence calibration returned no factor config")

    return {
        "factor_count": len(factors),
        "factors": sorted(factors.keys()),
        "samples": config.get("total_samples", 0),
        "data_range": config.get("meta", {}).get("data_range"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke-test PostgreSQL quant runtime paths")
    parser.add_argument("--pg-database", default="quant_investment")
    parser.add_argument("--symbol", default="000001")
    parser.add_argument("--skip-calibration", action="store_true")
    parser.add_argument("--calibration-symbols", type=int, default=20)
    parser.add_argument("--calibration-lookback-days", type=int, default=20)
    parser.add_argument("--calibration-forward-days", type=int, default=1)
    parser.add_argument("--calibration-min-samples-per-bin", type=int, default=5)
    args = parser.parse_args()

    _ensure_postgres_env(args.pg_database)

    results: dict[str, Any] = {
        "provider": os.environ["QUANT_DB_PROVIDER"],
        "pg_database": os.environ.get("PGDATABASE"),
        "symbol": args.symbol,
    }

    checks = [
        ("database", lambda: _check_database(args.symbol)),
        ("quant_api", lambda: _check_quant_api(args.symbol)),
        ("weekly_backtest", lambda: _check_weekly_backtest(args.symbol)),
    ]
    if not args.skip_calibration:
        checks.append(("confidence_calibration", lambda: _check_confidence_calibrator(args)))

    for name, check in checks:
        print(f"[smoke] running {name}...", file=sys.stderr)
        results[name] = check()
        print(f"[smoke] {name}: ok", file=sys.stderr)

    print(json.dumps({"success": True, "results": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
