"""QuantSys CLI entrypoint."""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# Load .env from project root to override inherited environment variables
_ENV_PATH = Path(__file__).resolve().parent.parent.parent.parent / ".env"
if _ENV_PATH.exists():
    with open(_ENV_PATH) as _ef:
        for _line in _ef:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _val = _line.split("=", 1)
                os.environ[_key] = _val

from api.quant_api import QuantAPI

from .analysis_query import (
    analyze_candlestick,
    analyze_price_action,
    calculate_buy_range,
    calculate_technical_indicators,
    compare_peers,
    get_exit_plan,
    get_quality_score,
)
from ..analysis.indicators import (
    calculate_technical_indicators as calculate_indicators_v2,
    analyze_candlestick_patterns,
)
from ..analysis.trading_strategy import (
    analyze_price_action as analyze_price_action_v2,
    compare_peers as compare_peers_v2,
    get_exit_plan as get_exit_plan_v2,
)
from .context import CliContext, build_context
from .errors import CliError, UnknownCommandError
from .factor_decay import analyze_factor_decay
from .factor_sector_analytics import analyze_factors, aggregate_sectors
from .financial_query import (
    get_cash_flow,
    get_financial_indicators,
    get_financial_statements,
    get_hk_analysis,
    get_hk_financials,
    get_income_statement,
    get_pe_percentile,
    get_stock_valuation,
)
from .hk_query import (
    get_hk_hot_rank,
    get_hk_market_overview,
    get_hk_south_flow,
    get_hk_technical,
)
from .market_query import (
    get_concept_list,
    get_concept_stocks,
    get_hot_stocks,
    get_index_history,
    get_macro_data,
    get_market_margin,
    get_market_news,
    get_market_overview,
    get_market_sentiment,
    get_north_flow,
    get_sector_fund_flow,
    get_sector_list,
)
from .output import error_payload, print_json, success_payload
from .portfolio_analytics import compare_benchmark, optimize_portfolio
from .registry import CommandRegistry, CommandSpec
from .risk_watch_analytics import price_alert, stress_test
from .risk_query import (
    calculate_position_size,
    calculate_stop_loss,
    check_trade_risk,
)
from .screening_query import screen_stocks_by_sector, screen_stocks_quality
from .sentiment_query import (
    get_fund_holdings,
    get_holder_changes,
    get_insider_trades,
    get_lhb,
    get_margin_data,
    get_stock_fund_flow,
    get_top_fund_stocks,
    get_top_holders,
)
from .stock_analytics import score_stock, screen_stocks
from .stock_query import (
    get_batch_stock_quotes,
    get_stock_list,
    get_stock_announcements,
    get_stock_history,
    get_stock_info,
    get_stock_news,
    get_stock_quote,
)
from .strategy_analytics import analyze_performance, arbitrate_signals
from .strategy_optimizer import optimize_strategy
from .trade_portfolio_analytics import correlate_portfolio, verify_trades


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return a stable process exit code."""
    raw_args = list(argv) if argv is not None else sys.argv[1:]

    # Daemon mode: start JSON-RPC server over stdin/stdout
    if "--daemon" in raw_args:
        from .daemon import run_daemon
        from .market_query import register_daemon_handlers as reg_market
        from .stock_query import register_daemon_handlers as reg_stock
        from .financial_query import register_daemon_handlers as reg_financial
        from .analysis_query import register_daemon_handlers as reg_analysis
        from .global_macro_query import register_daemon_handlers as reg_global_macro
        from .sentiment_query import register_daemon_handlers as reg_sentiment
        from .risk_query import register_daemon_handlers as reg_risk
        from .screening_query import register_daemon_handlers as reg_screening
        from .hk_query import register_daemon_handlers as reg_hk
        from .ml_query import register_all as reg_ml
        from .crypto_factors_query import register_daemon_handlers as reg_crypto_factors
        from .auxiliary_tools_query import register_daemon_handlers as reg_auxiliary_tools

        reg_market()
        reg_stock()
        reg_financial()
        reg_analysis()
        reg_global_macro()
        reg_sentiment()
        reg_risk()
        reg_screening()
        reg_hk()
        reg_ml()
        reg_crypto_factors()
        reg_auxiliary_tools()

        run_daemon()
        return 0

    command_name = _extract_command_name(raw_args)
    wants_json = "--json" in raw_args

    try:
        registry = build_registry()
        parsed = parse_args(raw_args)
        context = build_context(
            db_path=parsed.pop("db_path", None),
            output_dir=parsed.pop("output_dir", None),
            python=parsed.pop("python", None),
        )

        command_name = _command_name(parsed.pop("domain"), parsed.pop("cli_action"))
        spec = registry.get(command_name)
        if not spec:
            raise UnknownCommandError(command_name)

        result = spec.handler(context, parsed)
        payload = success_payload(
            command=spec.name,
            params=result.get("params", {}),
            data=result.get("data"),
            artifacts=result.get("artifacts", []),
            warnings=result.get("warnings", []),
        )
        _emit(payload, wants_json)
        return 0
    except CliError as exc:
        _emit(error_payload(command_name, exc), wants_json)
        return exc.exit_code
    except argparse.ArgumentError as exc:
        error = CliError("ARGUMENT_ERROR", str(exc), exit_code=2)
        _emit(error_payload(command_name, error), wants_json)
        return error.exit_code


def build_registry() -> CommandRegistry:
    """Create the first-version QuantSys command registry."""
    registry = CommandRegistry()

    registry.register(
        CommandSpec(
            name="tools.list",
            domain="tools",
            action="list",
            description="List all available QuantSys CLI commands.",
            params={},
            examples=["quant tools +list --json"],
            handler=lambda context, params: {
                "data": {
                    "commands": [
                        _describe_command(spec, include_params=False)
                        for spec in registry.list()
                    ]
                }
            },
        )
    )
    registry.register(
        CommandSpec(
            name="tools.describe",
            domain="tools",
            action="describe",
            description="Describe one QuantSys CLI command and its parameters.",
            params={"name": {"type": "string", "required": True}},
            examples=["quant tools +describe backtest.run --json"],
            handler=lambda context, params: _handle_tools_describe(registry, params),
        )
    )
    registry.register(
        CommandSpec(
            name="data.status",
            domain="data",
            action="status",
            description="Show local market database status.",
            params={"db_path": {"type": "string", "required": False}},
            examples=["quant data +status --json"],
            handler=_handle_data_status,
        )
    )
    registry.register(
        CommandSpec(
            name="market.overview",
            domain="market",
            action="overview",
            description="Get major A-share index snapshot.",
            params={},
            examples=["quant market +overview --json"],
            handler=_handle_market_overview,
        )
    )
    registry.register(
        CommandSpec(
            name="market.sectors",
            domain="market",
            action="sectors",
            description="List A-share industry sectors.",
            params={},
            examples=["quant market +sectors --json"],
            handler=_handle_market_sectors,
        )
    )
    registry.register(
        CommandSpec(
            name="market.concept_stocks",
            domain="market",
            action="concept-stocks",
            description="List stocks in a concept or theme.",
            params={"concept": {"type": "string", "required": True}},
            examples=["quant market +concept-stocks --concept 人工智能 --json"],
            handler=_handle_market_concept_stocks,
        )
    )
    registry.register(
        CommandSpec(
            name="market.concepts",
            domain="market",
            action="concepts",
            description="List concept or theme sectors.",
            params={},
            examples=["quant market +concepts --json"],
            handler=_handle_market_concepts,
        )
    )
    registry.register(
        CommandSpec(
            name="market.macro",
            domain="market",
            action="macro",
            description="Get selected China macro indicators.",
            params={"indicators": {"type": "array", "required": False}},
            examples=["quant market +macro --indicators pmi,cpi --json"],
            handler=_handle_market_macro,
        )
    )
    registry.register(
        CommandSpec(
            name="market.north_flow",
            domain="market",
            action="north-flow",
            description="Get northbound capital flow data.",
            params={},
            examples=["quant market +north-flow --json"],
            handler=_handle_market_north_flow,
        )
    )
    registry.register(
        CommandSpec(
            name="market.sector_flow",
            domain="market",
            action="sector-flow",
            description="Get sector fund flow ranking.",
            params={},
            examples=["quant market +sector-flow --json"],
            handler=_handle_market_sector_flow,
        )
    )
    registry.register(
        CommandSpec(
            name="market.margin",
            domain="market",
            action="margin",
            description="Get market margin financing balance trend.",
            params={},
            examples=["quant market +margin --json"],
            handler=_handle_market_margin,
        )
    )
    registry.register(
        CommandSpec(
            name="market.news",
            domain="market",
            action="news",
            description="Get broad market news.",
            params={"num": {"type": "integer", "required": False}},
            examples=["quant market +news --num 20 --json"],
            handler=_handle_market_news,
        )
    )
    registry.register(
        CommandSpec(
            name="market.hot_stocks",
            domain="market",
            action="hot-stocks",
            description="Get hot-search stock ranking.",
            params={"market": {"type": "string", "required": False}},
            examples=["quant market +hot-stocks --market A股 --json"],
            handler=_handle_market_hot_stocks,
        )
    )
    registry.register(
        CommandSpec(
            name="market.sentiment",
            domain="market",
            action="sentiment",
            description="Analyze market sentiment indicators and return composite fear/greed score (0-100).",
            params={},
            examples=["quant market +sentiment --json"],
            handler=_handle_market_sentiment,
        )
    )
    registry.register(
        CommandSpec(
            name="market.index_history",
            domain="market",
            action="index-history",
            description="Get historical OHLCV data for a major China index.",
            params={
                "symbol": {"type": "string", "required": True},
                "start_date": {"type": "string", "required": True},
                "end_date": {"type": "string", "required": True},
            },
            examples=["quant market +index-history --symbol sh000001 --start-date 2026-01-01 --end-date 2026-05-20 --json"],
            handler=_handle_market_index_history,
        )
    )
    registry.register(
        CommandSpec(
            name="stock.klines",
            domain="stock",
            action="klines",
            description="Read stock K-line data from the local quant database.",
            params={
                "symbol": {"type": "string", "required": True},
                "start_date": {"type": "string", "required": False},
                "end_date": {"type": "string", "required": False},
                "limit": {"type": "integer", "required": False},
            },
            examples=["quant stock +klines --symbol 600519 --limit 100 --json"],
            handler=_handle_stock_klines,
        )
    )
    registry.register(
        CommandSpec(
            name="stock.quote",
            domain="stock",
            action="quote",
            description="Get real-time A-share or HK stock quote through the quant backend.",
            params={"symbol": {"type": "string", "required": True}},
            examples=["quant stock +quote --symbol 600519 --json"],
            handler=_handle_stock_quote,
        )
    )
    registry.register(
        CommandSpec(
            name="stock.batch_quotes",
            domain="stock",
            action="batch-quotes",
            description="Get real-time prices for multiple A-share or HK stocks.",
            params={"symbols": {"type": "array", "required": True}},
            examples=["quant stock +batch-quotes --symbols 600519,000001 --json"],
            handler=_handle_stock_batch_quotes,
        )
    )
    registry.register(
        CommandSpec(
            name="stock.info",
            domain="stock",
            action="info",
            description="Get basic A-share or HK stock profile through the quant backend.",
            params={"symbol": {"type": "string", "required": True}},
            examples=["quant stock +info --symbol 600519 --json"],
            handler=_handle_stock_info,
        )
    )
    registry.register(
        CommandSpec(
            name="stock.history",
            domain="stock",
            action="history",
            description="Get recent A-share or HK OHLCV history through the quant backend.",
            params={
                "symbol": {"type": "string", "required": True},
                "period": {"type": "string", "required": False},
                "start_date": {"type": "string", "required": False},
                "end_date": {"type": "string", "required": False},
                "limit": {"type": "integer", "required": False},
            },
            examples=["quant stock +history --symbol 600519 --period daily --limit 60 --json"],
            handler=_handle_stock_history,
        )
    )
    registry.register(
        CommandSpec(
            name="stock.news",
            domain="stock",
            action="news",
            description="Get recent A-share stock news through the quant backend.",
            params={
                "symbol": {"type": "string", "required": True},
                "num": {"type": "integer", "required": False},
            },
            examples=["quant stock +news --symbol 600519 --num 10 --json"],
            handler=_handle_stock_news,
        )
    )
    registry.register(
        CommandSpec(
            name="stock.announcements",
            domain="stock",
            action="announcements",
            description="Get recent A-share company announcements through the quant backend.",
            params={"symbol": {"type": "string", "required": True}},
            examples=["quant stock +announcements --symbol 600519 --json"],
            handler=_handle_stock_announcements,
        )
    )
    registry.register(
        CommandSpec(
            name="analysis.technical",
            domain="analysis",
            action="technical",
            description="Run technical analysis with MA, MACD, RSI, Bollinger Bands, and signals.",
            params={"symbol": {"type": "string", "required": True}},
            examples=["quant analysis +technical --symbol 600519 --json"],
            handler=_handle_analysis_technical,
        )
    )
    registry.register(
        CommandSpec(
            name="analysis.price_action",
            domain="analysis",
            action="price-action",
            description="Analyze recent price action: trend, momentum, support/resistance, volatility, volume, and 52-week range.",
            params={
                "symbol": {"type": "string", "required": True},
                "period": {"type": "integer", "required": False},
            },
            examples=["quant analysis +price-action --symbol 600519 --period 80 --json"],
            handler=_handle_analysis_price_action,
        )
    )
    registry.register(
        CommandSpec(
            name="analysis.candlestick",
            domain="analysis",
            action="candlestick",
            description="Analyze candlestick patterns, trend lines, Fibonacci levels, and price gaps.",
            params={"symbol": {"type": "string", "required": True}},
            examples=["quant analysis +candlestick --symbol 600519 --json"],
            handler=_handle_analysis_candlestick,
        )
    )
    registry.register(
        CommandSpec(
            name="analysis.buy_range",
            domain="analysis",
            action="buy-range",
            description="Calculate reference buy range from technical support and PE-derived fair support.",
            params={
                "symbol": {"type": "string", "required": True},
                "current_price": {"type": "number", "required": False},
            },
            examples=["quant analysis +buy-range --symbol 600519 --current-price 100.5 --json"],
            handler=_handle_analysis_buy_range,
        )
    )
    registry.register(
        CommandSpec(
            name="analysis.valuation",
            domain="analysis",
            action="valuation",
            description="Analyze absolute valuation using PE, PB, and Graham-style fair value.",
            params={"symbol": {"type": "string", "required": True}},
            examples=["quant analysis +valuation --symbol 600519 --json"],
            handler=_handle_analysis_valuation,
        )
    )
    registry.register(
        CommandSpec(
            name="analysis.pe_percentile",
            domain="analysis",
            action="pe-percentile",
            description="Estimate current PE percentile in the stock's own history.",
            params={
                "symbol": {"type": "string", "required": True},
                "years": {"type": "integer", "required": False},
            },
            examples=["quant analysis +pe-percentile --symbol 600519 --years 3 --json"],
            handler=_handle_analysis_pe_percentile,
        )
    )
    registry.register(
        CommandSpec(
            name="analysis.quality",
            domain="analysis",
            action="quality",
            description="Score company quality from ROE, debt ratio, gross margin, net margin, and trend.",
            params={"symbol": {"type": "string", "required": True}},
            examples=["quant analysis +quality --symbol 600519 --json"],
            handler=_handle_analysis_quality,
        )
    )
    registry.register(
        CommandSpec(
            name="analysis.exit_plan",
            domain="analysis",
            action="exit-plan",
            description="Calculate three-tier profit-taking targets and current P&L for a position.",
            params={
                "symbol": {"type": "string", "required": True},
                "buy_price": {"type": "number", "required": True},
                "shares": {"type": "integer", "required": False},
            },
            examples=["quant analysis +exit-plan --symbol 600519 --buy-price 90 --shares 200 --json"],
            handler=_handle_analysis_exit_plan,
        )
    )
    registry.register(
        CommandSpec(
            name="analysis.peers",
            domain="analysis",
            action="peers",
            description="Return target stock metrics and sector name for peer comparison workflow.",
            params={"symbol": {"type": "string", "required": True}},
            examples=["quant analysis +peers --symbol 600519 --json"],
            handler=_handle_analysis_peers,
        )
    )
    registry.register(
        CommandSpec(
            name="screening.sector",
            domain="screening",
            action="sector",
            description="Screen stocks in an industry sector with optional ROE, PE, and limit filters.",
            params={
                "sector": {"type": "string", "required": True},
                "min_roe": {"type": "number", "required": False},
                "max_pe": {"type": "number", "required": False},
                "limit": {"type": "integer", "required": False},
            },
            examples=["quant screening +sector --sector 白酒 --max-pe 30 --limit 20 --json"],
            handler=_handle_screening_sector,
        )
    )
    registry.register(
        CommandSpec(
            name="screening.quality",
            domain="screening",
            action="quality",
            description="Screen sector stocks and rank candidates by fundamental quality score.",
            params={
                "sector": {"type": "string", "required": True},
                "min_score": {"type": "integer", "required": False},
                "max_pe": {"type": "number", "required": False},
                "limit": {"type": "integer", "required": False},
            },
            examples=["quant screening +quality --sector 白酒 --min-score 65 --max-pe 30 --limit 10 --json"],
            handler=_handle_screening_quality,
        )
    )
    registry.register(
        CommandSpec(
            name="stock.technical",
            domain="stock",
            action="technical",
            description="Calculate technical indicators for one stock.",
            params={
                "symbol": {"type": "string", "required": True},
                "indicators": {"type": "array", "required": False},
            },
            examples=["quant stock +technical --symbol 600519 --indicators RSI,MACD --json"],
            handler=_handle_stock_technical,
        )
    )
    registry.register(
        CommandSpec(
            name="stock.list",
            domain="stock",
            action="list",
            description="List stocks in the local quant database.",
            params={
                "market": {"type": "string", "required": False},
                "has_data": {"type": "boolean", "required": False},
                "source": {"type": "string", "required": False},
            },
            examples=["quant stock +list --market A --source live --json"],
            handler=_handle_stock_list,
        )
    )
    registry.register(
        CommandSpec(
            name="stock.ml_predict",
            domain="stock",
            action="ml-predict",
            description="Run local ML prediction for one stock using the trained model.",
            params={"symbol": {"type": "string", "required": True}},
            examples=["quant stock +ml-predict --symbol 600519 --json"],
            handler=_handle_stock_ml_predict,
        )
    )
    registry.register(
        CommandSpec(
            name="stock.score",
            domain="stock",
            action="score",
            description="Calculate a multi-factor quality score for one stock.",
            params={"symbol": {"type": "string", "required": True}},
            examples=["quant stock +score --symbol 600519 --json"],
            handler=_handle_stock_score,
        )
    )
    registry.register(
        CommandSpec(
            name="stock.screen",
            domain="stock",
            action="screen",
            description="Screen stocks by valuation, quality, leverage, RSI, and composite score.",
            params={
                "limit": {"type": "integer", "required": False},
                "pe_max": {"type": "number", "required": False},
                "pe_min": {"type": "number", "required": False},
                "pb_max": {"type": "number", "required": False},
                "pb_min": {"type": "number", "required": False},
                "roe_min": {"type": "number", "required": False},
                "debt_ratio_max": {"type": "number", "required": False},
                "rsi_max": {"type": "number", "required": False},
                "rsi_min": {"type": "number", "required": False},
                "min_score": {"type": "number", "required": False},
                "sort_by": {"type": "string", "required": False},
            },
            examples=["quant stock +screen --pe-max 20 --roe-min 0.15 --limit 20 --json"],
            handler=_handle_stock_screen,
        )
    )
    registry.register(
        CommandSpec(
            name="signal.list",
            domain="signal",
            action="list",
            description="Read generated trading signals with optional filters.",
            params={
                "date": {"type": "string", "required": False},
                "signal_type": {"type": "string", "required": False},
                "min_confidence": {"type": "number", "required": False},
            },
            examples=["quant signal +list --signal-type BUY --min-confidence 0.7 --json"],
            handler=_handle_signal_list,
        )
    )
    registry.register(
        CommandSpec(
            name="signal.arbitrate",
            domain="signal",
            action="arbitrate",
            description="Resolve conflicting BUY and SELL signals by symbol.",
            params={
                "date": {"type": "string", "required": False},
                "signals_dir": {"type": "string", "required": False},
                "signals_json": {"type": "string", "required": False},
                "min_confidence_gap": {"type": "number", "required": False},
            },
            examples=["quant signal +arbitrate --date 2026-05-20 --json"],
            handler=_handle_signal_arbitrate,
        )
    )
    registry.register(
        CommandSpec(
            name="performance.analyze",
            domain="performance",
            action="analyze",
            description="Analyze generated signal performance for a strategy.",
            params={
                "strategy_id": {"type": "string", "required": False},
                "days": {"type": "integer", "required": False},
                "signals_dir": {"type": "string", "required": False},
            },
            examples=["quant performance +analyze --strategy-id rsi-strategy --days 90 --json"],
            handler=_handle_performance_analyze,
        )
    )
    registry.register(
        CommandSpec(
            name="report.read_daily",
            domain="report",
            action="read-daily",
            description="Read the latest or dated daily quant report.",
            params={"date": {"type": "string", "required": False}},
            examples=["quant report +read-daily --json"],
            handler=_handle_report_read_daily,
        )
    )
    registry.register(
        CommandSpec(
            name="backtest.results",
            domain="backtest",
            action="results",
            description="Read generated backtest report files.",
            params={
                "symbol": {"type": "string", "required": False},
                "date": {"type": "string", "required": False},
            },
            examples=["quant backtest +results --symbol 600519 --json"],
            handler=_handle_backtest_results,
        )
    )
    registry.register(
        CommandSpec(
            name="ml.history",
            domain="ml",
            action="history",
            description="Read model training history reports.",
            params={},
            examples=["quant ml +history --json"],
            handler=_handle_ml_history,
        )
    )
    registry.register(
        CommandSpec(
            name="data.full_status",
            domain="data",
            action="full-status",
            description="Read data completeness status for stocks with factor coverage.",
            params={},
            examples=["quant data +full-status --json"],
            handler=_handle_data_full_status,
        )
    )
    registry.register(
        CommandSpec(
            name="factor.analyze",
            domain="factor",
            action="analyze",
            description="Analyze factor distributions, coverage, and IC readiness from factor_values.",
            params={
                "top_n": {"type": "integer", "required": False},
                "min_observations": {"type": "integer", "required": False},
                "sample_limit": {"type": "integer", "required": False},
            },
            examples=["quant factor +analyze --top-n 20 --min-observations 30 --sample-limit 50000 --json"],
            handler=_handle_factor_analyze,
        )
    )
    registry.register(
        CommandSpec(
            name="sector.aggregate",
            domain="sector",
            action="aggregate",
            description="Aggregate stock fundamentals and signal counts by sector or industry.",
            params={
                "sector_field": {"type": "string", "required": False},
                "limit": {"type": "integer", "required": False},
            },
            examples=["quant sector +aggregate --sector-field industry --limit 20 --json"],
            handler=_handle_sector_aggregate,
        )
    )
    registry.register(
        CommandSpec(
            name="benchmark.compare",
            domain="benchmark",
            action="compare",
            description="Compare strategy return against a benchmark and calculate alpha.",
            params={
                "strategy_return": {"type": "number", "required": False},
                "benchmark_return": {"type": "number", "required": False},
                "strategy_name": {"type": "string", "required": False},
                "benchmark_name": {"type": "string", "required": False},
                "equity": {"type": "string", "required": False},
                "benchmark": {"type": "string", "required": False},
            },
            examples=["quant benchmark +compare --strategy-return 0.12 --benchmark-return 0.08 --json"],
            handler=_handle_benchmark_compare,
        )
    )
    registry.register(
        CommandSpec(
            name="portfolio.optimize",
            domain="portfolio",
            action="optimize",
            description="Optimize portfolio weights with equal weight, risk parity, or simplified max Sharpe.",
            params={
                "symbols": {"type": "string", "required": True},
                "method": {"type": "string", "required": False},
                "expected_returns": {"type": "string", "required": False},
                "volatilities": {"type": "string", "required": False},
            },
            examples=["quant portfolio +optimize --symbols 600519,000001 --method risk_parity --json"],
            handler=_handle_portfolio_optimize,
        )
    )
    registry.register(
        CommandSpec(
            name="strategy.optimize",
            domain="strategy",
            action="optimize",
            description="Search strategy parameters for RSI, MA cross, or Bollinger strategies.",
            params={
                "strategy": {"type": "string", "required": True},
                "metric": {"type": "string", "required": False},
                "trials": {"type": "integer", "required": False},
                "param_grid_json": {"type": "string", "required": False},
            },
            examples=["quant strategy +optimize --strategy rsi --metric sharpe --trials 9 --json"],
            handler=_handle_strategy_optimize,
        )
    )
    registry.register(
        CommandSpec(
            name="watch.price_alert",
            domain="watch",
            action="price-alert",
            description="Evaluate price alert thresholds from supplied quote values.",
            params={
                "symbol": {"type": "string", "required": True},
                "price": {"type": "number", "required": True},
                "above": {"type": "number", "required": False},
                "below": {"type": "number", "required": False},
                "change_pct": {"type": "number", "required": False},
                "last_price": {"type": "number", "required": False},
            },
            examples=["quant watch +price-alert --symbol 600519 --price 105 --above 100 --json"],
            handler=_handle_watch_price_alert,
        )
    )
    registry.register(
        CommandSpec(
            name="stress.test",
            domain="stress",
            action="test",
            description="Apply a uniform market shock to supplied portfolio positions.",
            params={
                "positions_json": {"type": "string", "required": True},
                "shock_pct": {"type": "number", "required": True},
                "cash": {"type": "number", "required": False},
            },
            examples=["quant stress +test --positions-json '[{\"symbol\":\"600519\",\"market_value\":10000}]' --shock-pct -0.2 --json"],
            handler=_handle_stress_test,
        )
    )
    registry.register(
        CommandSpec(
            name="risk.trade_check",
            domain="risk",
            action="trade-check",
            description="Run pre-trade risk checks for one A-share order.",
            params={
                "symbol": {"type": "string", "required": True},
                "action": {"type": "string", "required": True},
                "price": {"type": "number", "required": True},
                "shares": {"type": "integer", "required": True},
            },
            examples=["quant risk +trade-check --symbol 600519 --action buy --price 100 --shares 300 --json"],
            handler=_handle_risk_trade_check,
        )
    )
    registry.register(
        CommandSpec(
            name="risk.position_size",
            domain="risk",
            action="position-size",
            description="Calculate Kelly-style position size for one A-share trade idea.",
            params={
                "symbol": {"type": "string", "required": True},
                "price": {"type": "number", "required": True},
                "signal_strength": {"type": "number", "required": False},
            },
            examples=["quant risk +position-size --symbol 600519 --price 100 --signal-strength 0.8 --json"],
            handler=_handle_risk_position_size,
        )
    )
    registry.register(
        CommandSpec(
            name="risk.stop_loss",
            domain="risk",
            action="stop-loss",
            description="Calculate fixed or trailing stop-loss price for one A-share position.",
            params={
                "symbol": {"type": "string", "required": True},
                "entry_price": {"type": "number", "required": True},
                "current_price": {"type": "number", "required": False},
                "highest_price": {"type": "number", "required": False},
            },
            examples=["quant risk +stop-loss --symbol 600519 --entry-price 90 --current-price 100 --highest-price 110 --json"],
            handler=_handle_risk_stop_loss,
        )
    )
    registry.register(
        CommandSpec(
            name="hk.market_overview",
            domain="hk",
            action="market-overview",
            description="Get real-time snapshots for major HK indices.",
            params={},
            examples=["quant hk +market-overview --json"],
            handler=_handle_hk_market_overview,
        )
    )
    registry.register(
        CommandSpec(
            name="hk.south_flow",
            domain="hk",
            action="south-flow",
            description="Get recent southbound capital flow data.",
            params={},
            examples=["quant hk +south-flow --json"],
            handler=_handle_hk_south_flow,
        )
    )
    registry.register(
        CommandSpec(
            name="hk.technical",
            domain="hk",
            action="technical",
            description="Run technical analysis for one HK stock.",
            params={"symbol": {"type": "string", "required": True}},
            examples=["quant hk +technical --symbol 9988 --json"],
            handler=_handle_hk_technical,
        )
    )
    registry.register(
        CommandSpec(
            name="hk.hot_rank",
            domain="hk",
            action="hot-rank",
            description="Get Eastmoney HK stock popularity ranking.",
            params={},
            examples=["quant hk +hot-rank --json"],
            handler=_handle_hk_hot_rank,
        )
    )
    registry.register(
        CommandSpec(
            name="sentiment.stock_fund_flow",
            domain="sentiment",
            action="stock-fund-flow",
            description="Get recent stock-level fund flow records.",
            params={
                "symbol": {"type": "string", "required": True},
                "days": {"type": "integer", "required": False},
            },
            examples=["quant sentiment +stock-fund-flow --symbol 600519 --days 5 --json"],
            handler=_handle_sentiment_stock_fund_flow,
        )
    )
    registry.register(
        CommandSpec(
            name="sentiment.lhb",
            domain="sentiment",
            action="lhb",
            description="Get Dragon-Tiger List data by date or recent stock appearances.",
            params={
                "symbol": {"type": "string", "required": False},
                "date": {"type": "string", "required": False},
            },
            examples=["quant sentiment +lhb --date 20260519 --json"],
            handler=_handle_sentiment_lhb,
        )
    )
    registry.register(
        CommandSpec(
            name="sentiment.insider_trades",
            domain="sentiment",
            action="insider-trades",
            description="Get recent insider trading records.",
            params={"symbol": {"type": "string", "required": True}},
            examples=["quant sentiment +insider-trades --symbol 600519 --json"],
            handler=_handle_sentiment_insider_trades,
        )
    )
    registry.register(
        CommandSpec(
            name="sentiment.fund_holdings",
            domain="sentiment",
            action="fund-holdings",
            description="Get funds holding one stock.",
            params={"symbol": {"type": "string", "required": True}},
            examples=["quant sentiment +fund-holdings --symbol 600519 --json"],
            handler=_handle_sentiment_fund_holdings,
        )
    )
    registry.register(
        CommandSpec(
            name="sentiment.top_fund_stocks",
            domain="sentiment",
            action="top-fund-stocks",
            description="Get top fund-heavy stocks if the upstream interface is available.",
            params={},
            examples=["quant sentiment +top-fund-stocks --json"],
            handler=_handle_sentiment_top_fund_stocks,
        )
    )
    registry.register(
        CommandSpec(
            name="sentiment.top_holders",
            domain="sentiment",
            action="top-holders",
            description="Get top 10 shareholders for one stock.",
            params={
                "symbol": {"type": "string", "required": True},
                "date": {"type": "string", "required": False},
            },
            examples=["quant sentiment +top-holders --symbol 600519 --json"],
            handler=_handle_sentiment_top_holders,
        )
    )
    registry.register(
        CommandSpec(
            name="sentiment.holder_changes",
            domain="sentiment",
            action="holder-changes",
            description="Get recent shareholder count changes.",
            params={"symbol": {"type": "string", "required": True}},
            examples=["quant sentiment +holder-changes --symbol 600519 --json"],
            handler=_handle_sentiment_holder_changes,
        )
    )
    registry.register(
        CommandSpec(
            name="sentiment.margin_data",
            domain="sentiment",
            action="margin-data",
            description="Get recent stock-level margin financing and securities lending data.",
            params={"symbol": {"type": "string", "required": True}},
            examples=["quant sentiment +margin-data --symbol 600519 --json"],
            handler=_handle_sentiment_margin_data,
        )
    )
    registry.register(
        CommandSpec(
            name="financial.indicators",
            domain="financial",
            action="indicators",
            description="Get recent A-share financial ratios.",
            params={"symbol": {"type": "string", "required": True}},
            examples=["quant financial +indicators --symbol 600519 --json"],
            handler=_handle_financial_indicators,
        )
    )
    registry.register(
        CommandSpec(
            name="financial.statements",
            domain="financial",
            action="statements",
            description="Get A-share income, balance sheet, cashflow, or all statements.",
            params={
                "symbol": {"type": "string", "required": True},
                "statement": {"type": "string", "required": False},
                "recent_n": {"type": "integer", "required": False},
            },
            examples=["quant financial +statements --symbol 600519 --statement income --recent-n 4 --json"],
            handler=_handle_financial_statements,
        )
    )
    registry.register(
        CommandSpec(
            name="financial.hk_financials",
            domain="financial",
            action="hk-financials",
            description="Get HK stock annual income and balance-sheet summary.",
            params={"symbol": {"type": "string", "required": True}},
            examples=["quant financial +hk-financials --symbol 00700 --json"],
            handler=_handle_financial_hk_financials,
        )
    )
    registry.register(
        CommandSpec(
            name="financial.hk_analysis",
            domain="financial",
            action="hk-analysis",
            description="Get HK stock price, technical summary, and available financial data.",
            params={"symbol": {"type": "string", "required": True}},
            examples=["quant financial +hk-analysis --symbol 00700 --json"],
            handler=_handle_financial_hk_analysis,
        )
    )
    registry.register(
        CommandSpec(
            name="financial.valuation",
            domain="financial",
            action="valuation",
            description="Get stock valuation data: PE, PB, valuation status, fair value estimate.",
            params={"symbol": {"type": "string", "required": True}},
            examples=["quant financial +valuation --symbol 600519 --json"],
            handler=_handle_financial_valuation,
        )
    )
    registry.register(
        CommandSpec(
            name="financial.pe_percentile",
            domain="financial",
            action="pe-percentile",
            description="Get PE historical percentile: current PE position in past N years.",
            params={
                "symbol": {"type": "string", "required": True},
                "years": {"type": "integer", "required": False},
            },
            examples=["quant financial +pe-percentile --symbol 600519 --years 3 --json"],
            handler=_handle_financial_pe_percentile,
        )
    )
    registry.register(
        CommandSpec(
            name="financial.income_statement",
            domain="financial",
            action="income-statement",
            description="Get income statement: revenue, cost, net profit, margins.",
            params={
                "symbol": {"type": "string", "required": True},
                "recent_n": {"type": "integer", "required": False},
            },
            examples=["quant financial +income-statement --symbol 600519 --recent-n 8 --json"],
            handler=_handle_financial_income_statement,
        )
    )
    registry.register(
        CommandSpec(
            name="financial.cash_flow",
            domain="financial",
            action="cash-flow",
            description="Get cash flow statement: operating, investing, financing cash flows.",
            params={
                "symbol": {"type": "string", "required": True},
                "recent_n": {"type": "integer", "required": False},
            },
            examples=["quant financial +cash-flow --symbol 600519 --recent-n 8 --json"],
            handler=_handle_financial_cash_flow,
        )
    )
    registry.register(
        CommandSpec(
            name="indicator.technical",
            domain="indicator",
            action="technical",
            description="Calculate technical indicators: MA, MACD, RSI, Bollinger Bands with signals.",
            params={
                "symbol": {"type": "string", "required": True},
                "indicators": {"type": "string", "required": False},
            },
            examples=["quant indicator +technical --symbol 600519 --json"],
            handler=_handle_indicator_technical,
        )
    )
    registry.register(
        CommandSpec(
            name="indicator.candlestick",
            domain="indicator",
            action="candlestick",
            description="Analyze candlestick patterns, gaps, and chart formations.",
            params={
                "symbol": {"type": "string", "required": True},
                "lookback": {"type": "integer", "required": False},
            },
            examples=["quant indicator +candlestick --symbol 600519 --lookback 120 --json"],
            handler=_handle_indicator_candlestick,
        )
    )
    registry.register(
        CommandSpec(
            name="analysis.price_action",
            domain="analysis",
            action="price-action",
            description="Analyze price action: trend, support/resistance, volume, breakout signals, momentum, volatility.",
            params={
                "symbol": {"type": "string", "required": True},
                "period": {"type": "integer", "required": False},
            },
            examples=["quant analysis +price-action --symbol 600519 --period 60 --json"],
            handler=_handle_analysis_price_action,
        )
    )
    registry.register(
        CommandSpec(
            name="analysis.peer_comparison",
            domain="analysis",
            action="peer-comparison",
            description="Compare stock with peers in the same sector: PE, PB, ROE, market cap.",
            params={
                "symbol": {"type": "string", "required": True},
            },
            examples=["quant analysis +peer-comparison --symbol 600519 --json"],
            handler=_handle_analysis_peer_comparison,
        )
    )
    registry.register(
        CommandSpec(
            name="analysis.exit_plan",
            domain="analysis",
            action="exit-plan",
            description="Calculate profit-taking targets and sell recommendations based on entry price.",
            params={
                "symbol": {"type": "string", "required": True},
                "entry_price": {"type": "number", "required": True},
                "position_size": {"type": "integer", "required": False},
            },
            examples=["quant analysis +exit-plan --symbol 600519 --entry-price 1200 --position-size 100 --json"],
            handler=_handle_analysis_exit_plan,
        )
    )
    registry.register(
        CommandSpec(
            name="financial.hk_analysis",
            domain="financial",
            action="hk-analysis",
            description="Get HK stock price, technical summary, and available financial data.",
            params={"symbol": {"type": "string", "required": True}},
            examples=["quant financial +hk-analysis --symbol 9988 --json"],
            handler=_handle_financial_hk_analysis,
        )
    )
    registry.register(
        CommandSpec(
            name="trade.verify",
            domain="trade",
            action="verify",
            description="Compare live trades against backtest trades by symbol and action.",
            params={
                "trades_json": {"type": "string", "required": True},
                "backtest_json": {"type": "string", "required": True},
            },
            examples=["quant trade +verify --trades-json '[{\"symbol\":\"600519\",\"action\":\"BUY\",\"price\":101}]' --backtest-json '[{\"symbol\":\"600519\",\"action\":\"BUY\",\"price\":100}]' --json"],
            handler=_handle_trade_verify,
        )
    )
    registry.register(
        CommandSpec(
            name="portfolio.correlation",
            domain="portfolio",
            action="correlation",
            description="Calculate a Pearson correlation matrix from supplied price series.",
            params={
                "prices_json": {"type": "string", "required": True},
                "threshold": {"type": "number", "required": False},
            },
            examples=["quant portfolio +correlation --prices-json '{\"600519\":[1,2,3],\"000001\":[1,2,4]}' --json"],
            handler=_handle_portfolio_correlation,
        )
    )
    registry.register(
        CommandSpec(
            name="factor.decay",
            domain="factor",
            action="decay",
            description="Analyze factor IC decay across forward-return horizons.",
            params={
                "factor": {"type": "string", "required": True},
                "horizons": {"type": "string", "required": False},
            },
            examples=["quant factor +decay --factor momentum --horizons 5,10,20 --json"],
            handler=_handle_factor_decay,
        )
    )
    registry.register(
        CommandSpec(
            name="position.list",
            domain="position",
            action="list",
            description="List all positions",
            params={
                "account_id": {"type": "string", "required": False, "default": "default"},
                "status": {"type": "string", "required": False, "default": "open"}
            },
            examples=["quant position +list --json", "quant position +list --status closed --json"],
            handler=_handle_position_list,
        )
    )
    registry.register(
        CommandSpec(
            name="position.get",
            domain="position",
            action="get",
            description="Get single position detail",
            params={
                "symbol": {"type": "string", "required": True},
                "account_id": {"type": "string", "required": False, "default": "default"}
            },
            examples=["quant position +get --symbol 600036 --json"],
            handler=_handle_position_get,
        )
    )
    registry.register(
        CommandSpec(
            name="position.update",
            domain="position",
            action="update",
            description="Update position fields",
            params={
                "symbol": {"type": "string", "required": True},
                "account_id": {"type": "string", "required": False, "default": "default"},
                "quantity": {"type": "integer", "required": False},
                "price": {"type": "number", "required": False},
                "stop_loss": {"type": "number", "required": False},
                "take_profit": {"type": "number", "required": False},
                "notes": {"type": "string", "required": False}
            },
            examples=["quant position +update --symbol 600036 --price 38.5 --json"],
            handler=_handle_position_update,
        )
    )
    registry.register(
        CommandSpec(
            name="position.close",
            domain="position",
            action="close",
            description="Close position",
            params={
                "symbol": {"type": "string", "required": True},
                "account_id": {"type": "string", "required": False, "default": "default"},
                "reason": {"type": "string", "required": False}
            },
            examples=["quant position +close --symbol 600036 --reason 'Stop loss triggered' --json"],
            handler=_handle_position_close,
        )
    )
    registry.register(
        CommandSpec(
            name="position.summary",
            domain="position",
            action="summary",
            description="Get position statistics",
            params={
                "account_id": {"type": "string", "required": False, "default": "default"}
            },
            examples=["quant position +summary --json"],
            handler=_handle_position_summary,
        )
    )

    for spec in _script_command_specs():
        registry.register(spec)

    return registry


def parse_args(raw_args: list[str]) -> dict[str, Any]:
    """Parse the common `quant <domain> +<action>` command shape."""
    parser = argparse.ArgumentParser(prog="quant", add_help=True)
    parser.add_argument("domain")
    parser.add_argument("cli_action")
    parser.add_argument("name", nargs="?")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--db-path")
    parser.add_argument("--output-dir")
    parser.add_argument("--python")
    parser.add_argument("--symbol")
    parser.add_argument("--symbols")
    parser.add_argument("--concept")
    parser.add_argument("--indicators")
    parser.add_argument("--period")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--num", type=int)
    parser.add_argument("--date")
    parser.add_argument("--signal-type")
    parser.add_argument("--min-confidence", type=float)
    parser.add_argument("--market")
    parser.add_argument("--source")
    parser.add_argument("--has-data", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--days", type=int)
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--capital", type=float)
    parser.add_argument("--commission", type=float)
    parser.add_argument("--slippage", type=float)
    parser.add_argument("--model")
    parser.add_argument("--future-days", type=int)
    parser.add_argument("--threshold", type=float)
    parser.add_argument("--tune", action="store_true")
    parser.add_argument("--trials", type=int)
    parser.add_argument("--cv-splits", type=int)
    parser.add_argument("--use-feature-engineering", action="store_true")
    parser.add_argument("--account-value", type=float)
    parser.add_argument("--strategy-id")
    parser.add_argument("--signals-dir")
    parser.add_argument("--signals-json")
    parser.add_argument("--pe-max", type=float)
    parser.add_argument("--max-pe", type=float, dest="max_pe")
    parser.add_argument("--pe-min", type=float)
    parser.add_argument("--pb-max", type=float)
    parser.add_argument("--pb-min", type=float)
    parser.add_argument("--roe-min", type=float)
    parser.add_argument("--debt-ratio-max", type=float)
    parser.add_argument("--rsi-max", type=float)
    parser.add_argument("--rsi-min", type=float)
    parser.add_argument("--min-score", type=float)
    parser.add_argument("--sort-by")
    parser.add_argument("--min-confidence-gap", type=float)
    parser.add_argument("--top-n", type=int)
    parser.add_argument("--min-observations", type=int)
    parser.add_argument("--sample-limit", type=int)
    parser.add_argument("--sector-field")
    parser.add_argument("--strategy-return", type=float)
    parser.add_argument("--benchmark-return", type=float)
    parser.add_argument("--strategy-name")
    parser.add_argument("--benchmark-name")
    parser.add_argument("--equity")
    parser.add_argument("--benchmark")
    parser.add_argument("--method")
    parser.add_argument("--expected-returns")
    parser.add_argument("--volatilities")
    parser.add_argument("--strategy")
    parser.add_argument("--metric")
    parser.add_argument("--param-grid-json")
    parser.add_argument("--price", type=float)
    parser.add_argument("--action")
    parser.add_argument("--above", type=float)
    parser.add_argument("--below", type=float)
    parser.add_argument("--change-pct", type=float)
    parser.add_argument("--last-price", type=float)
    parser.add_argument("--positions-json")
    parser.add_argument("--cash", type=float)
    parser.add_argument("--shock-pct", type=float)
    parser.add_argument("--trades-json")
    parser.add_argument("--backtest-json")
    parser.add_argument("--prices-json")
    parser.add_argument("--horizons")
    parser.add_argument("--factor")
    parser.add_argument("--current-price", type=float)
    parser.add_argument("--years", type=int)
    parser.add_argument("--buy-price", type=float)
    parser.add_argument("--shares", type=int)
    parser.add_argument("--signal-strength", type=float)
    parser.add_argument("--entry-price", type=float)
    parser.add_argument("--highest-price", type=float)
    parser.add_argument("--sector")
    parser.add_argument("--min-roe", type=float)
    parser.add_argument("--statement")
    parser.add_argument("--recent-n", type=int)
    parser.add_argument("--account-id")
    parser.add_argument("--status")
    parser.add_argument("--quantity", type=int)
    parser.add_argument("--stop-loss", type=float)
    parser.add_argument("--take-profit", type=float)
    parser.add_argument("--notes")
    parser.add_argument("--reason")

    namespace = parser.parse_args(raw_args)
    parsed = vars(namespace)
    parsed.pop("json", None)
    return {key: value for key, value in parsed.items() if value is not None and value is not False}


def _handle_tools_describe(registry: CommandRegistry, params: dict[str, Any]) -> dict[str, Any]:
    name = params.get("name")
    if not name:
        raise CliError("MISSING_PARAMETER", "tools.describe requires a command name.", exit_code=2)

    spec = registry.get(str(name))
    if not spec:
        raise UnknownCommandError(str(name))

    return {"data": _describe_command(spec, include_params=True)}


def _handle_data_status(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    db_path = context.db_path
    exists = db_path.exists()

    data: dict[str, Any] = {
        "path": str(db_path),
        "exists": exists,
        "size_bytes": db_path.stat().st_size if exists else 0,
    }

    if exists:
        data["is_sqlite"] = _is_sqlite_database(db_path)

    return {"params": {"db_path": str(db_path)}, "data": data}


def _handle_market_overview(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    return {"params": params, "data": get_market_overview()}


def _handle_market_sectors(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    return {"params": params, "data": get_sector_list()}


def _handle_market_concept_stocks(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    concept = _require_param(params, "concept")
    return {"params": params, "data": get_concept_stocks(concept)}


def _handle_market_concepts(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    return {"params": params, "data": get_concept_list()}


def _handle_market_macro(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    return {"params": params, "data": get_macro_data(indicators=_parse_csv(params.get("indicators")))}


def _handle_market_north_flow(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    return {"params": params, "data": get_north_flow()}


def _handle_market_sector_flow(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    return {"params": params, "data": get_sector_fund_flow()}


def _handle_market_margin(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    return {"params": params, "data": get_market_margin()}


def _handle_market_news(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    return {"params": params, "data": get_market_news(num=int(params.get("num", 20)))}


def _handle_market_hot_stocks(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    return {"params": params, "data": get_hot_stocks(market=str(params.get("market") or "A股"))}


def _handle_market_sentiment(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    return {"params": params, "data": get_market_sentiment()}


def _handle_market_index_history(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    start_date = _require_param(params, "start_date")
    end_date = _require_param(params, "end_date")
    return {"params": params, "data": get_index_history(symbol, start_date, end_date)}


def _handle_stock_klines(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    data = QuantAPI().get_klines(
        symbol=symbol,
        start_date=params.get("start_date"),
        end_date=params.get("end_date"),
        limit=int(params.get("limit", 100)),
    )
    return {"params": params, "data": data}


def _handle_stock_quote(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    return {"params": params, "data": get_stock_quote(symbol)}


def _handle_stock_batch_quotes(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbols = _parse_csv(params.get("symbols"))
    if not symbols:
        raise CliError("MISSING_PARAMETER", "Missing required parameter: symbols", exit_code=2)
    return {"params": params, "data": get_batch_stock_quotes(symbols)}


def _handle_stock_info(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    return {"params": params, "data": get_stock_info(symbol)}


def _handle_stock_history(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    return {
        "params": params,
        "data": get_stock_history(
            symbol,
            period=str(params.get("period") or "daily"),
            start_date=params.get("start_date"),
            end_date=params.get("end_date"),
            limit=int(params.get("limit", 60)),
        ),
    }


def _handle_stock_news(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    return {
        "params": params,
        "data": get_stock_news(symbol, num=int(params.get("num", 10))),
    }


def _handle_stock_announcements(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    return {"params": params, "data": get_stock_announcements(symbol)}


def _handle_analysis_technical(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    return {"params": params, "data": calculate_technical_indicators(symbol)}


def _handle_analysis_price_action(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    return {"params": params, "data": analyze_price_action(symbol, period=int(params.get("period", 60)))}


def _handle_analysis_candlestick(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    return {"params": params, "data": analyze_candlestick(symbol)}


def _handle_analysis_buy_range(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    return {
        "params": params,
        "data": calculate_buy_range(
            symbol,
            current_price=params.get("current_price"),
        ),
    }


def _handle_analysis_valuation(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    return {"params": params, "data": get_stock_valuation(symbol)}


def _handle_analysis_pe_percentile(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    return {"params": params, "data": get_pe_percentile(symbol, years=int(params.get("years", 5)))}


def _handle_analysis_quality(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    framework = params.get("framework", "auto")
    return {"params": params, "data": get_quality_score(symbol, framework=str(framework))}


def _handle_analysis_exit_plan(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    buy_price = params.get("buy_price")
    if buy_price is None:
        raise CliError("MISSING_PARAMETER", "Missing required parameter: buy_price", exit_code=2)
    return {
        "params": params,
        "data": get_exit_plan(symbol, buy_price=float(buy_price), shares=int(params.get("shares", 100))),
    }


def _handle_analysis_peers(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    return {"params": params, "data": compare_peers(symbol)}


def _handle_screening_sector(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    sector = _require_param(params, "sector")
    return {
        "params": params,
        "data": screen_stocks_by_sector(
            sector,
            min_roe=params.get("min_roe"),
            max_pe=params.get("max_pe"),
            limit=int(params.get("limit", 20)),
        ),
    }


def _handle_screening_quality(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    sector = _require_param(params, "sector")
    return {
        "params": params,
        "data": screen_stocks_quality(
            sector,
            min_score=int(params.get("min_score", 50)),
            max_pe=params.get("max_pe"),
            limit=int(params.get("limit", 10)),
        ),
    }


def _handle_stock_technical(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    indicators = _parse_csv(params.get("indicators"))
    data = QuantAPI().calculate_technical_indicators(symbol=symbol, indicators=indicators)
    if data.get("indicators") and data.get("price") is None:
        latest = QuantAPI().get_klines(symbol=symbol, limit=1).get("klines", [])
        if latest:
            data["price"] = latest[0].get("close")
    return {"params": params, "data": data}


def _handle_stock_list(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    if str(params.get("source") or "local").lower() == "live":
        return {
            "params": params,
            "data": get_stock_list(market=str(params.get("market") or "A")),
        }

    data = QuantAPI().get_stock_list(
        market=params.get("market"),
        has_data=bool(params.get("has_data", False)),
    )
    return {"params": params, "data": data}


def _handle_stock_ml_predict(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    return {"params": params, "data": predict_stock_ml(symbol)}


def _handle_stock_score(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    _require_param(params, "symbol")
    return {"params": params, "data": score_stock(context.db_path, params)}


def _handle_stock_screen(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    return {"params": params, "data": screen_stocks(context.db_path, params)}


def _handle_signal_list(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    data = QuantAPI().get_signals(
        date=params.get("date"),
        signal_type=params.get("signal_type"),
        min_confidence=float(params.get("min_confidence", 0.0)),
    )
    return {"params": params, "data": data}


def _handle_signal_arbitrate(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    parsed = dict(params)
    if "signals_json" in parsed:
        try:
            parsed["signals"] = json.loads(str(parsed.pop("signals_json")))
        except json.JSONDecodeError as exc:
            raise CliError("INVALID_SIGNALS_JSON", str(exc), exit_code=2) from exc
    return {"params": params, "data": arbitrate_signals(context.output_dir, parsed)}


def _handle_performance_analyze(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    return {"params": params, "data": analyze_performance(context.output_dir, params)}


def _handle_report_read_daily(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    data = QuantAPI().get_daily_report(date=params.get("date"))
    return {"params": params, "data": data}


def _handle_backtest_results(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    data = _read_backtest_results(context.quant_root / ".pi-invest", params)
    return {"params": params, "data": data}


def _handle_ml_history(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    models_dir = context.quant_root / "quantsys" / "ml" / "models"
    files = sorted(
        (Path(file) for file in glob.glob(str(models_dir / "training_report_*.json")) if "latest" not in file),
        reverse=True,
    )
    history = []
    for file in files:
        report = json.loads(file.read_text(encoding="utf-8"))
        history.append({
            "timestamp": report.get("timestamp"),
            "model_type": report.get("model_type"),
            "n_features": report.get("data", {}).get("n_features"),
            "total_samples": report.get("data", {}).get("total_samples"),
            "cv_accuracy": report.get("cv_results", {}).get("mean_scores", {}).get("accuracy"),
            "cv_auc": report.get("cv_results", {}).get("mean_scores", {}).get("auc"),
            "test_accuracy": report.get("test_metrics", {}).get("accuracy"),
            "test_auc": report.get("test_metrics", {}).get("auc"),
            "class_balance": report.get("data", {}).get("class_balance"),
        })
    return {"params": params, "data": {"count": len(history), "history": history}}


def _handle_data_full_status(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    api = QuantAPI()
    connection = api.db._get_connection()
    cursor = connection.execute(
        """
        SELECT symbol, COUNT(DISTINCT date) as factor_days, COUNT(DISTINCT factor_name) as factor_count
        FROM factor_values
        GROUP BY symbol
        HAVING COUNT(DISTINCT factor_name) >= 30
        """
    )
    factor_stats = {row[0]: {"factor_days": row[1], "factor_count": row[2]} for row in cursor.fetchall()}
    if not factor_stats:
        return {"params": params, "data": {"total_stocks": 0, "complete_stocks": 0, "incomplete_stocks": 0, "stocks": []}}

    placeholders = ",".join("?" * len(factor_stats))
    query = f"""
        SELECT s.symbol, s.name, s.market, COUNT(DISTINCT k.date), MIN(k.date), MAX(k.date)
        FROM stocks s
        LEFT JOIN daily_klines k ON s.symbol = k.symbol
        WHERE s.symbol IN ({placeholders})
        GROUP BY s.symbol, s.name, s.market
        ORDER BY s.symbol
    """
    rows = connection.execute(query, list(factor_stats.keys())).fetchall()
    stocks = []
    for row in rows:
        factor_info = factor_stats.get(row[0], {"factor_days": 0, "factor_count": 0})
        stocks.append({
            "symbol": row[0],
            "name": row[1],
            "market": row[2],
            "kline_days": row[3],
            "earliest_date": row[4],
            "latest_date": row[5],
            "factor_days": factor_info["factor_days"],
            "factor_count": factor_info["factor_count"],
            "data_complete": row[3] > 0 and factor_info["factor_days"] > 0 and factor_info["factor_count"] >= 30,
        })
    complete = sum(1 for stock in stocks if stock["data_complete"])
    return {
        "params": params,
        "data": {
            "total_stocks": len(stocks),
            "complete_stocks": complete,
            "incomplete_stocks": len(stocks) - complete,
            "stocks": stocks,
        },
    }


def _handle_factor_analyze(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    return {"params": params, "data": analyze_factors(context.db_path, params)}


def _handle_sector_aggregate(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    return {"params": params, "data": aggregate_sectors(context.db_path, params)}


def _handle_benchmark_compare(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    return {"params": params, "data": compare_benchmark(context.output_dir, params)}


def _handle_portfolio_optimize(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    return {"params": params, "data": optimize_portfolio(context.output_dir, params)}


def _handle_strategy_optimize(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    try:
        data = optimize_strategy(context.output_dir, params)
    except ValueError as exc:
        raise CliError("INVALID_STRATEGY_OPTIMIZATION", str(exc), exit_code=2) from exc
    return {"params": params, "data": data}


def _handle_watch_price_alert(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    return {"params": params, "data": price_alert(context.output_dir, params)}


def _handle_stress_test(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    return {"params": params, "data": stress_test(context.output_dir, params)}


def _handle_risk_trade_check(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    action = _require_param(params, "action")
    price = params.get("price")
    shares = params.get("shares")
    if price is None:
        raise CliError("MISSING_PARAMETER", "Missing required parameter: price", exit_code=2)
    if shares is None:
        raise CliError("MISSING_PARAMETER", "Missing required parameter: shares", exit_code=2)
    return {
        "params": params,
        "data": check_trade_risk(symbol, action, float(price), int(shares)),
    }


def _handle_risk_position_size(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    price = params.get("price")
    if price is None:
        raise CliError("MISSING_PARAMETER", "Missing required parameter: price", exit_code=2)
    return {
        "params": params,
        "data": calculate_position_size(
            symbol,
            float(price),
            signal_strength=float(params.get("signal_strength", 1.0)),
        ),
    }


def _handle_risk_stop_loss(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    entry_price = params.get("entry_price")
    if entry_price is None:
        raise CliError("MISSING_PARAMETER", "Missing required parameter: entry_price", exit_code=2)
    return {
        "params": params,
        "data": calculate_stop_loss(
            symbol,
            float(entry_price),
            current_price=params.get("current_price"),
            highest_price=params.get("highest_price"),
        ),
    }


def _handle_hk_market_overview(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    return {"params": params, "data": get_hk_market_overview()}


def _handle_hk_south_flow(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    return {"params": params, "data": get_hk_south_flow()}


def _handle_hk_technical(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    return {"params": params, "data": get_hk_technical(symbol)}


def _handle_hk_hot_rank(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    return {"params": params, "data": get_hk_hot_rank()}


def _handle_sentiment_stock_fund_flow(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    return {
        "params": params,
        "data": get_stock_fund_flow(symbol, days=int(params.get("days", 10))),
    }


def _handle_sentiment_lhb(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    return {
        "params": params,
        "data": get_lhb(
            symbol=params.get("symbol"),
            date=params.get("date"),
        ),
    }


def _handle_sentiment_insider_trades(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    return {"params": params, "data": get_insider_trades(symbol)}


def _handle_sentiment_fund_holdings(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    return {"params": params, "data": get_fund_holdings(symbol)}


def _handle_sentiment_top_fund_stocks(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    return {"params": params, "data": get_top_fund_stocks()}


def _handle_sentiment_top_holders(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    if params.get("date"):
        return {"params": params, "data": get_top_holders(symbol, date=params.get("date"))}
    return {"params": params, "data": get_top_holders(symbol)}


def _handle_sentiment_holder_changes(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    return {"params": params, "data": get_holder_changes(symbol)}


def _handle_sentiment_margin_data(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    return {"params": params, "data": get_margin_data(symbol)}


def _handle_financial_indicators(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    return {"params": params, "data": get_financial_indicators(symbol)}


def _handle_financial_statements(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    return {
        "params": params,
        "data": get_financial_statements(
            symbol,
            statement=str(params.get("statement") or "all"),
            recent_n=int(params.get("recent_n", 8)),
        ),
    }


def _handle_financial_hk_financials(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    return {"params": params, "data": get_hk_financials(symbol)}


def _handle_financial_hk_analysis(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    return {"params": params, "data": get_hk_analysis(symbol)}


def _handle_financial_valuation(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    return {"params": params, "data": get_stock_valuation(symbol)}


def _handle_financial_pe_percentile(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    years = int(params.get("years", 3))
    return {"params": params, "data": get_pe_percentile(symbol, years)}


def _handle_financial_income_statement(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    recent_n = int(params.get("recent_n", 8))
    return {"params": params, "data": get_income_statement(symbol, recent_n)}


def _handle_financial_cash_flow(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    symbol = _require_param(params, "symbol")
    recent_n = int(params.get("recent_n", 8))
    return {"params": params, "data": get_cash_flow(symbol, recent_n)}


def _handle_indicator_technical(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    """技术指标分析"""
    symbol = _require_param(params, "symbol")
    indicators = params.get("indicators")  # 可选，默认全部
    if indicators and isinstance(indicators, str):
        indicators = [i.strip() for i in indicators.split(",")]
    return {"params": params, "data": calculate_indicators_v2(symbol, indicators)}


def _handle_indicator_candlestick(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    """K线形态识别"""
    symbol = _require_param(params, "symbol")
    lookback = int(params.get("lookback", 120))
    return {"params": params, "data": analyze_candlestick_patterns(symbol, lookback)}


def _handle_analysis_price_action(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    """价格行为分析"""
    symbol = _require_param(params, "symbol")
    period = int(params.get("period", 60))
    return {"params": params, "data": analyze_price_action_v2(symbol, period)}


def _handle_analysis_peer_comparison(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    """同行对比"""
    symbol = _require_param(params, "symbol")
    return {"params": params, "data": compare_peers_v2(symbol)}


def _handle_analysis_exit_plan(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    """止盈计划"""
    symbol = _require_param(params, "symbol")
    entry_price = float(_require_param(params, "entry_price"))
    position_size = int(params.get("position_size", 100))
    return {"params": params, "data": get_exit_plan_v2(symbol, entry_price, position_size)}


def _handle_trade_verify(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    return {"params": params, "data": verify_trades(context.output_dir, params)}


def _handle_portfolio_correlation(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    return {"params": params, "data": correlate_portfolio(context.output_dir, params)}


def _handle_factor_decay(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    return {"params": params, "data": analyze_factor_decay(context.db_path, params)}


def _handle_position_list(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    """处理 position.list 命令"""
    from ..db.dao import PositionDAO

    dao = PositionDAO()
    account_id = params.get('account_id', 'default')
    status = params.get('status', 'open')

    positions = dao.list_positions(account_id=account_id, status=status)

    return {
        "params": params,
        "data": {
            "total": len(positions),
            "positions": positions
        }
    }


def _handle_position_get(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    """处理 position.get 命令"""
    from ..db.dao import PositionDAO

    symbol = _require_param(params, "symbol")
    account_id = params.get('account_id', 'default')

    dao = PositionDAO()
    position = dao.get_position(symbol=symbol, account_id=account_id)

    if not position:
        return {
            "params": params,
            "data": {
                "error": f"Position not found for symbol {symbol} in account {account_id}"
            }
        }

    return {
        "params": params,
        "data": position
    }


def _handle_position_update(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    """处理 position.update 命令"""
    from ..db.dao import PositionDAO

    symbol = _require_param(params, "symbol")
    account_id = params.get('account_id', 'default')

    # 构建更新数据字典
    update_data = {}
    if 'quantity' in params:
        update_data['quantity'] = params['quantity']
    if 'price' in params:
        update_data['current_price'] = params['price']
    if 'stop_loss' in params:
        update_data['stop_loss'] = params['stop_loss']
    if 'take_profit' in params:
        update_data['take_profit'] = params['take_profit']
    if 'notes' in params:
        update_data['notes'] = params['notes']

    if not update_data:
        raise CliError("MISSING_PARAMETER", "No update fields provided", exit_code=2)

    dao = PositionDAO()
    rows_updated = dao.update_position(symbol=symbol, data=update_data, account_id=account_id)

    return {
        "params": params,
        "data": {
            "symbol": symbol,
            "account_id": account_id,
            "rows_updated": rows_updated,
            "updated_fields": list(update_data.keys())
        }
    }


def _handle_position_close(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    """处理 position.close 命令"""
    from ..db.dao import PositionDAO

    symbol = _require_param(params, "symbol")
    account_id = params.get('account_id', 'default')
    reason = params.get('reason')

    dao = PositionDAO()
    rows_updated = dao.close_position(symbol=symbol, reason=reason, account_id=account_id)

    return {
        "params": params,
        "data": {
            "symbol": symbol,
            "account_id": account_id,
            "rows_updated": rows_updated,
            "status": "closed" if rows_updated > 0 else "not_found"
        }
    }


def _handle_position_summary(context: CliContext, params: dict[str, Any]) -> dict[str, Any]:
    """处理 position.summary 命令"""
    from ..db.dao import PositionDAO

    account_id = params.get('account_id', 'default')

    dao = PositionDAO()
    summary = dao.get_position_summary(account_id=account_id)

    return {
        "params": params,
        "data": summary
    }


def _script_command_specs() -> list[CommandSpec]:
    return [
        _script_spec(
            name="data.update_klines",
            domain="data",
            action="update-klines",
            description="Update daily K-line data through the market data pipeline.",
            script=Path("quantsys/data/pipeline.py"),
            base_args=["update-klines"],
            params={"symbols": "--symbols", "days": "--days"},
            examples=["quant data +update-klines --symbols 600519,000001 --days 365 --json"],
        ),
        _script_spec(
            name="factor.compute",
            domain="factor",
            action="compute",
            description="Compute factor values using the existing factor script.",
            script=Path("scripts/calculate_factors.py"),
            base_args=[],
            params={},
            examples=["quant factor +compute --json"],
        ),
        _script_spec(
            name="signal.generate",
            domain="signal",
            action="generate",
            description="Generate trading signals from latest factor values.",
            script=Path("scripts/generate_signals.py"),
            base_args=[],
            params={
                "date": "--date",
                "symbols": "--symbols",
            },
            examples=["quant signal +generate --json"],
        ),
        _script_spec(
            name="backtest.run",
            domain="backtest",
            action="run",
            description="Run strategy backtest for one or more symbols.",
            script=Path("scripts/weekly_backtest.py"),
            base_args=[],
            params={
                "symbol": "--symbol",
                "symbols": "--symbols",
                "days": "--days",
                "start": "--start",
                "end": "--end",
                "capital": "--capital",
                "commission": "--commission",
                "slippage": "--slippage",
            },
            examples=["quant backtest +run --symbol 600519 --days 365 --json"],
        ),
        _script_spec(
            name="ml.train",
            domain="ml",
            action="train",
            description="Train or retrain the signal model.",
            script=Path("scripts/ml_retrain.py"),
            base_args=["--json"],
            params={
                "days": "--days",
                "future_days": "--future-days",
                "threshold": "--threshold",
                "model": "--model",
                "tune": "--tune",
                "trials": "--trials",
                "cv_splits": "--cv-splits",
                "db_path": "--db-path",
                "use_feature_engineering": "--use-feature-engineering",
            },
            examples=["quant ml +train --days 730 --model xgboost --json"],
        ),
        _script_spec(
            name="risk.check",
            domain="risk",
            action="check",
            description="Run portfolio risk checks through the quant API client script.",
            script=Path("scripts/risk_check.py"),
            base_args=[],
            params={"symbols": "--symbols", "account_value": "--account-value"},
            examples=["quant risk +check --symbols 600519,000001 --json"],
        ),
        _script_spec(
            name="report.daily",
            domain="report",
            action="daily",
            description="Generate the daily quant report.",
            script=Path("scripts/daily_report.py"),
            base_args=[],
            params={"output_dir": "--output-dir"},
            examples=["quant report +daily --json"],
        ),
    ]


def _script_spec(
    name: str,
    domain: str,
    action: str,
    description: str,
    script: Path,
    base_args: list[str],
    params: dict[str, str],
    examples: list[str],
) -> CommandSpec:
    readable_params = {
        key: {"type": "boolean" if key in {"tune", "use_feature_engineering"} else "string", "required": False}
        for key in params
    }

    def handler(context: CliContext, parsed: dict[str, Any]) -> dict[str, Any]:
        return _run_script(context, name, script, base_args, params, parsed)

    return CommandSpec(
        name=name,
        domain=domain,
        action=action,
        description=description,
        params=readable_params,
        examples=examples,
        handler=handler,
    )


def _run_script(
    context: CliContext,
    command_name: str,
    script: Path,
    base_args: list[str],
    param_flags: dict[str, str],
    params: dict[str, Any],
) -> dict[str, Any]:
    script_path = context.quant_root / script
    if not script_path.exists():
        raise CliError(
            "SCRIPT_NOT_FOUND",
            f"Script not found: {script_path}",
            hint=f"Check the {command_name} command adapter.",
        )

    command = [context.python, str(script_path), *base_args]
    forwarded_params: dict[str, Any] = {}

    for param_name, flag in param_flags.items():
        if param_name not in params:
            continue
        value = params[param_name]
        forwarded_params[param_name] = value
        command.append(flag)
        if value is not True:
            command.append(str(value))

    completed = subprocess.run(command, cwd=context.quant_root, capture_output=True, text=True)
    data = {
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }

    if completed.returncode != 0:
        raise CliError(
            "SCRIPT_FAILED",
            data["stderr"] or data["stdout"] or f"{command_name} failed",
            exit_code=completed.returncode,
        )

    return {"params": forwarded_params, "data": data}


def _describe_command(spec: CommandSpec, include_params: bool) -> dict[str, Any]:
    data: dict[str, Any] = {
        "name": spec.name,
        "description": spec.description,
        "examples": spec.examples,
    }
    if include_params:
        data["params"] = spec.params
    return data


def _is_sqlite_database(path: Path) -> bool:
    try:
        return path.read_bytes()[:16].startswith(b"SQLite format 3")
    except OSError:
        return False


def _require_param(params: dict[str, Any], name: str) -> str:
    value = params.get(name)
    if value is None or value == "":
        raise CliError("MISSING_PARAMETER", f"Missing required parameter: {name}", exit_code=2)
    return str(value)


def _parse_csv(value: Any) -> list[str] | None:
    if value is None:
        return None
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    items = [item.strip() for item in str(value).split(",") if item.strip()]
    return items or None


def _read_backtest_results(backtest_dir: Path, params: dict[str, Any]) -> dict[str, Any]:
    symbol = params.get("symbol")
    date = params.get("date")

    if symbol and date:
        report_file = backtest_dir / f"backtest_report_{symbol}_{date}.json"
        if not report_file.exists():
            return {"error": f"未找到回测报告: {symbol} {date}"}
        return json.loads(report_file.read_text(encoding="utf-8"))

    if symbol:
        files = sorted(backtest_dir.glob(f"backtest_report_{symbol}_*.json"), reverse=True)
        reports = [json.loads(file.read_text(encoding="utf-8")) for file in files]
        return {"symbol": symbol, "count": len(reports), "reports": reports}

    files = list(backtest_dir.glob("backtest_report_*_*.json"))
    summary = []
    for file in files:
        report = json.loads(file.read_text(encoding="utf-8"))
        results = report.get("results", [])
        if not results:
            continue
        best_strategy = max(results, key=lambda item: item.get("total_return", -999))
        summary.append({
            "symbol": report.get("symbol"),
            "date": report.get("report_date"),
            "best_strategy": best_strategy.get("strategy_name"),
            "best_return": best_strategy.get("total_return"),
            "sharpe_ratio": best_strategy.get("sharpe_ratio"),
            "max_drawdown": best_strategy.get("max_drawdown"),
            "win_rate": best_strategy.get("win_rate"),
        })

    summary.sort(key=lambda item: item.get("best_return") or -999, reverse=True)
    return {"count": len(summary), "summary": summary}


def predict_stock_ml(symbol: str) -> dict[str, Any]:
    import joblib
    import numpy as np

    quant_root = Path(__file__).resolve().parents[2]
    model_paths = [
        quant_root / "quantsys" / "ml" / "models" / "xgboost_latest.pkl",
        quant_root / "quantsys" / "ml" / "models" / "xgboost_model.pkl",
        quant_root.parent / ".pi-invest" / "quant" / "models" / "signal_confidence.pkl",
    ]
    model_path = next((path for path in model_paths if path.exists()), None)
    if model_path is None:
        return {"error": "模型未加载"}

    report_paths = [
        quant_root / "quantsys" / "ml" / "models" / "training_report_latest.json",
        quant_root / "quantsys" / "ml" / "models" / "training_report.json",
    ]
    report_path = next((path for path in report_paths if path.exists()), None)
    if report_path is None:
        return {"error": "训练报告文件不存在，请先训练模型"}

    api = QuantAPI()
    connection = api.db._get_connection()
    cursor = connection.execute("SELECT MAX(date) FROM factor_values WHERE symbol = ?", (symbol,))
    row = cursor.fetchone()
    date = row[0] if row else None
    if not date:
        return {"error": f"未找到股票 {symbol} 的数据"}

    factors = {
        row[0]: row[1]
        for row in connection.execute(
            "SELECT factor_name, factor_value FROM factor_values WHERE symbol = ? AND date = ?",
            (symbol, date),
        ).fetchall()
    }
    kline = connection.execute(
        """
        SELECT open, high, low, close, volume, amount, turnover_rate
        FROM daily_klines
        WHERE symbol = ? AND date = ?
        """,
        (symbol, date),
    ).fetchone()
    if not kline:
        kline = connection.execute(
            """
            SELECT open, high, low, close, volume, amount, turnover_rate
            FROM daily_klines
            WHERE symbol = ?
            ORDER BY date DESC LIMIT 1
            """,
            (symbol,),
        ).fetchone()
    if not kline:
        return {"error": "未找到价格数据"}

    report = json.loads(report_path.read_text(encoding="utf-8"))
    feature_names = report.get("feature_names", [])
    feature_dict = {
        "open": kline[0],
        "high": kline[1],
        "low": kline[2],
        "close": kline[3],
        "volume": kline[4],
        "amount": kline[5],
        "turnover_rate": kline[6],
        **factors,
    }
    features = [float(feature_dict.get(name) or 0.0) for name in feature_names]
    model = joblib.load(model_path)
    x = np.array(features).reshape(1, -1)
    if hasattr(model, "predict_proba"):
        up_probability = float(model.predict_proba(x)[0][1])
    else:
        up_probability = float(model.predict(x)[0])

    key_factors = []
    if hasattr(model, "feature_importances_"):
        importances = model.feature_importances_
        contributions = np.array(features) * importances
        for index, name in enumerate(feature_names):
            key_factors.append({
                "name": name,
                "value": float(features[index]),
                "importance": float(importances[index]),
                "contribution": float(contributions[index]),
            })
        key_factors.sort(key=lambda item: abs(item["contribution"]), reverse=True)

    return {
        "symbol": symbol,
        "date": date,
        "price": float(feature_dict["close"]),
        "prediction": {
            "up_probability": up_probability,
            "direction": "UP" if up_probability > 0.5 else "DOWN",
            "confidence": abs(up_probability - 0.5) * 2,
        },
        "key_factors": key_factors[:5],
    }


def _extract_command_name(raw_args: list[str]) -> str:
    if len(raw_args) >= 2:
        return _command_name(raw_args[0], raw_args[1])
    return "unknown"


def _command_name(domain: str, action: str) -> str:
    return f"{domain}.{action.removeprefix('+').replace('-', '_')}"


def _emit(payload: dict[str, Any], wants_json: bool) -> None:
    if wants_json:
        print_json(payload)
        return

    if payload["ok"]:
        print(payload["data"])
    else:
        print(payload["error"]["message"], file=sys.stderr)
