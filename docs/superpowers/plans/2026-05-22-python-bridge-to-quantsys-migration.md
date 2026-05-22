# Python Bridge Daemon to QuantSys Migration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify all Python backend calls through a single QuantSys CLI daemon process, removing the old akshare_bridge.py and all CLI adapter files.

**Architecture:** Add `--daemon` mode to `quantsys.cli` that runs a JSON-RPC 2.0 server over stdin/stdout. TypeScript connects via a new `quantsys-daemon-adapter.ts` client. All function calls (including ML) go through this single daemon path, replacing both the old bridge-to-cli routing and the legacy akshare_bridge daemon.

**Tech Stack:** Python (QuantSys CLI, JSON-RPC), TypeScript (Node.js child_process, readline)

---

## File Structure

**Create:**
- `quant/quantsys/cli/daemon.py` — JSON-RPC 2.0 server, method routing
- `quant/quantsys/cli/ml_query.py` — 7 ML/viz handler functions
- `src/infrastructure/quant/quantsys-daemon-adapter.ts` — TypeScript daemon client

**Modify:**
- `quant/quantsys/cli/main.py` — add `--daemon` flag
- `quant/quantsys/cli/registry.py` — add daemon method map and resolve method
- `quant/quantsys/cli/__init__.py` — expose daemon entry
- `src/infrastructure/tools/shared/python-caller-resilient-adapter.ts` — replace callBridgeOrCli import
- `src/infrastructure/tools/agent/restart-agent-tool.ts` — update pgrep string
- `src/infrastructure/tools/index.ts` — remove old exports
- `src/infrastructure/tools/core/quant-cli-tool.ts` — remove old bridge-only comment

**Delete:**
- `src/infrastructure/tools/core/python-bridge.ts`
- `src/infrastructure/quant/bridge-to-cli-adapter.ts`
- `src/infrastructure/quant/market-query-cli-adapter.ts`
- `src/infrastructure/quant/stock-query-cli-adapter.ts`
- `src/infrastructure/quant/financial-query-cli-adapter.ts`
- `src/infrastructure/quant/analysis-query-cli-adapter.ts`
- `src/infrastructure/quant/sentiment-query-cli-adapter.ts`
- `src/infrastructure/quant/risk-query-cli-adapter.ts`
- `quant/quantsys/bridge/` directory

---

### Task 1: Create QuantSys CLI Daemon Server

**Files:**
- Create: `quant/quantsys/cli/daemon.py`

- [ ] **Step 1: Write daemon.py**

```python
"""
QuantSys CLI Daemon — JSON-RPC 2.0 server over stdin/stdout.

Usage: python -m quantsys.cli --daemon

Receives JSON-RPC requests line-by-line on stdin, dispatches to registered
handler functions via the DAEMON_METHOD_MAP, and writes JSON-RPC responses
to stdout.
"""

from __future__ import annotations

import json
import sys
import traceback
from typing import Any, Callable, Dict

DaemonHandler = Callable[[Dict[str, Any]], Any]

DAEMON_METHOD_MAP: Dict[str, DaemonHandler] = {}


def register_daemon_method(method: str, handler: DaemonHandler) -> None:
    """Register a handler for a JSON-RPC method name."""
    DAEMON_METHOD_MAP[method] = handler


def _resolve_handler(method: str) -> DaemonHandler | None:
    """Look up handler by method name."""
    return DAEMON_METHOD_MAP.get(method)


def handle_request(request: dict) -> dict:
    """Process a single JSON-RPC request and return the response dict."""
    method = request.get("method", "")
    params = request.get("params", {})
    request_id = request.get("id")

    handler = _resolve_handler(method)
    if handler is None:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32601,
                "message": f"Method not found: {method}",
            },
        }

    try:
        result = handler(params)
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": json.dumps(result, default=str, ensure_ascii=False),
        }
    except Exception:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32000,
                "message": traceback.format_exc(),
            },
        }


def run_daemon() -> None:
    """Main loop: read stdin, dispatch, write stdout."""
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            error_response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            }
            print(json.dumps(error_response, ensure_ascii=False), flush=True)
            continue

        response = handle_request(request)
        print(json.dumps(response, ensure_ascii=False), flush=True)
```

- [ ] **Step 2: Verify syntax**

```bash
python3 -c "import py_compile; py_compile.compile('quant/quantsys/cli/daemon.py', doraise=True)"
```

Expected: No output (syntax OK)

---

### Task 2: Create ML Query Handlers

**Files:**
- Create: `quant/quantsys/cli/ml_query.py`

- [ ] **Step 1: Write ml_query.py**

```python
"""
ML query handlers for the QuantSys CLI daemon.

Migrated from the legacy akshare_bridge.py. These functions handle model
training, prediction, signal combination, and visualization.
"""

from typing import Any, Dict

from .daemon import register_daemon_method


def _run_confidence_calibration(params: Dict[str, Any]) -> Any:
    """Calibrate prediction confidence scores."""
    from quantsys.ml.confidence_calibrator import ConfidenceCalibrator

    calibrator = ConfidenceCalibrator()
    return calibrator.run(
        forward_days=params.get("forward_days", 5),
        return_threshold=params.get("return_threshold", 0.02),
        max_symbols=params.get("max_symbols", 500),
        lookback_days=params.get("lookback_days", 180),
    )


def _predict_signal_confidence(params: Dict[str, Any]) -> Any:
    """Predict signal confidence for a given stock."""
    from quantsys.ml.signal_predictor import SignalPredictor

    predictor = SignalPredictor()
    return predictor.predict(
        symbol=params.get("symbol"),
        model_name=params.get("model_name"),
        features=params.get("features"),
    )


def _combine_strategy_signals(params: Dict[str, Any]) -> Any:
    """Combine signals from multiple strategies."""
    from .strategy_analytics import arbitrate_signals
    from .context import CliContext

    ctx = CliContext(db_path=None, output_dir=None, python="python3")
    return arbitrate_signals(ctx, params)


def _plot_model_accuracy_trend(params: Dict[str, Any]) -> Any:
    """Generate model accuracy trend chart."""
    from quantsys.ml.visualizer import plot_model_accuracy_trend

    return plot_model_accuracy_trend(
        model_name=params.get("model_name"),
        output_path=params.get("output_path"),
    )


def _plot_equity_curve(params: Dict[str, Any]) -> Any:
    """Generate equity curve chart."""
    from quantsys.ml.visualizer import plot_equity_curve

    return plot_equity_curve(
        portfolio_history=params.get("portfolio_history"),
        benchmark=params.get("benchmark"),
        output_path=params.get("output_path"),
    )


def _plot_strategy_comparison(params: Dict[str, Any]) -> Any:
    """Generate strategy comparison chart."""
    from quantsys.ml.visualizer import plot_strategy_comparison

    return plot_strategy_comparison(
        strategy_results=params.get("strategy_results"),
        output_path=params.get("output_path"),
    )


def _plot_feature_importance(params: Dict[str, Any]) -> Any:
    """Generate feature importance chart."""
    from quantsys.ml.visualizer import plot_feature_importance

    return plot_feature_importance(
        feature_importance=params.get("feature_importance"),
        model_name=params.get("model_name"),
        top_n=params.get("top_n", 20),
        output_path=params.get("output_path"),
    )


# Register all ML handlers with the daemon method map
def register_all() -> None:
    register_daemon_method("run_confidence_calibration", _run_confidence_calibration)
    register_daemon_method("predict_signal_confidence", _predict_signal_confidence)
    register_daemon_method("combine_strategy_signals", _combine_strategy_signals)
    register_daemon_method("plot_model_accuracy_trend", _plot_model_accuracy_trend)
    register_daemon_method("plot_equity_curve", _plot_equity_curve)
    register_daemon_method("plot_strategy_comparison", _plot_strategy_comparison)
    register_daemon_method("plot_feature_importance", _plot_feature_importance)
```

- [ ] **Step 2: Verify syntax**

```bash
python3 -c "import py_compile; py_compile.compile('quant/quantsys/cli/ml_query.py', doraise=True)"
```

Expected: No output (syntax OK)

---

### Task 3: Modify CLI Entry to Support --daemon

**Files:**
- Modify: `quant/quantsys/cli/main.py`

- [ ] **Step 1: Add --daemon argument parsing and routing**

In `main()` function, before the existing CLI logic, add daemon mode detection.

Read `quant/quantsys/cli/main.py` lines 114-117 (the `main` function start).

Change from:
```python
def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return a stable process exit code."""
    raw_args = list(argv) if argv is not None else sys.argv[1:]
    command_name = _extract_command_name(raw_args)
    wants_json = "--json" in raw_args
```

To:
```python
def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return a stable process exit code."""
    raw_args = list(argv) if argv is not None else sys.argv[1:]

    # Daemon mode: start JSON-RPC server over stdin/stdout
    if "--daemon" in raw_args:
        # Register all daemon handlers before starting
        from .daemon import run_daemon
        from .market_query import register_daemon_handlers as reg_market
        from .stock_query import register_daemon_handlers as reg_stock
        from .financial_query import register_daemon_handlers as reg_financial
        from .analysis_query import register_daemon_handlers as reg_analysis
        from .sentiment_query import register_daemon_handlers as reg_sentiment
        from .risk_query import register_daemon_handlers as reg_risk
        from .screening_query import register_daemon_handlers as reg_screening
        from .hk_query import register_daemon_handlers as reg_hk
        from .ml_query import register_all as reg_ml

        reg_market()
        reg_stock()
        reg_financial()
        reg_analysis()
        reg_sentiment()
        reg_risk()
        reg_screening()
        reg_hk()
        reg_ml()

        run_daemon()
        return 0

    command_name = _extract_command_name(raw_args)
    wants_json = "--json" in raw_args
```

- [ ] **Step 2: Verify syntax**

```bash
python3 -c "import py_compile; py_compile.compile('quant/quantsys/cli/main.py', doraise=True)"
```

Expected: No output (syntax OK)

---

### Task 4: Register Daemon Methods in CLI Query Modules

**Files:**
- Modify: `quant/quantsys/cli/market_query.py` — add register_daemon_handlers()
- Modify: `quant/quantsys/cli/stock_query.py` — add register_daemon_handlers()
- Modify: `quant/quantsys/cli/financial_query.py` — add register_daemon_handlers()
- Modify: `quant/quantsys/cli/analysis_query.py` — add register_daemon_handlers()
- Modify: `quant/quantsys/cli/sentiment_query.py` — add register_daemon_handlers()
- Modify: `quant/quantsys/cli/risk_query.py` — add register_daemon_handlers()
- Modify: `quant/quantsys/cli/screening_query.py` — add register_daemon_handlers()
- Modify: `quant/quantsys/cli/hk_query.py` — add register_daemon_handlers()

- [ ] **Step 1: Add register_daemon_handlers to market_query.py**

Read `quant/quantsys/cli/market_query.py` to find the exported function names and their signatures. Then append at end of file:

```python
# === Daemon handler registration ===

from .daemon import register_daemon_method
from .context import CliContext

def _daemon_context():
    return CliContext(db_path=None, output_dir=None, python="python3")

def register_daemon_handlers() -> None:
    ctx = _daemon_context()

    def _get_market_overview(params):
        return get_market_overview(ctx, {})

    def _get_sector_list(params):
        return get_sector_list(ctx, {})

    def _get_concept_list(params):
        return get_concept_list(ctx, {})

    def _get_concept_stocks(params):
        return get_concept_stocks(ctx, {"concept": params.get("concept")})

    def _get_hot_stocks(params):
        return get_hot_stocks(ctx, {"count": params.get("count", 20)})

    def _get_north_flow(params):
        return get_north_flow(ctx, {"days": params.get("days", 1)})

    def _get_sector_fund_flow(params):
        return get_sector_fund_flow(ctx, {"days": params.get("days", 1)})

    def _get_market_margin(params):
        return get_market_margin(ctx, {"days": params.get("days", 1)})

    def _get_macro_data(params):
        return get_macro_data(ctx, {"indicators": params.get("indicators")})

    def _get_market_news(params):
        return get_market_news(ctx, {"limit": params.get("limit", 20)})

    def _get_market_sentiment(params):
        return get_market_sentiment(ctx, {})

    def _get_index_history(params):
        return get_index_history(ctx, {
            "index_code": params.get("index_code"),
            "period": params.get("period", "daily"),
            "start_date": params.get("start_date"),
            "end_date": params.get("end_date"),
        })

    register_daemon_method("get_market_overview", _get_market_overview)
    register_daemon_method("get_sector_list", _get_sector_list)
    register_daemon_method("get_concept_list", _get_concept_list)
    register_daemon_method("get_concept_stocks", _get_concept_stocks)
    register_daemon_method("get_hot_stocks", _get_hot_stocks)
    register_daemon_method("get_north_flow", _get_north_flow)
    register_daemon_method("get_sector_fund_flow", _get_sector_fund_flow)
    register_daemon_method("get_market_margin", _get_market_margin)
    register_daemon_method("get_macro_data", _get_macro_data)
    register_daemon_method("get_market_news", _get_market_news)
    register_daemon_method("test_market_sentiment", _get_market_sentiment)
    register_daemon_method("get_index_history", _get_index_history)
```

- [ ] **Step 2: Add register_daemon_handlers to stock_query.py**

```python
# === Daemon handler registration ===

from .daemon import register_daemon_method
from .context import CliContext

def register_daemon_handlers() -> None:
    ctx = CliContext(db_path=None, output_dir=None, python="python3")

    def _get_stock_info(params):
        return get_stock_info(ctx, {"symbol": params.get("symbol")})

    def _get_stock_quote(params):
        return get_stock_quote(ctx, {"symbols": [params.get("symbol")]})

    def _get_stock_history(params):
        return get_stock_history(ctx, {
            "symbol": params.get("symbol"),
            "period": params.get("period", "daily"),
            "start_date": params.get("start_date"),
            "end_date": params.get("end_date"),
            "limit": params.get("limit"),
        })

    def _get_stock_news(params):
        return get_stock_news(ctx, {"symbol": params.get("symbol"), "limit": params.get("limit", 10)})

    def _get_stock_announcements(params):
        return get_stock_announcements(ctx, {"symbol": params.get("symbol"), "limit": params.get("limit", 10)})

    register_daemon_method("get_stock_info", _get_stock_info)
    register_daemon_method("get_stock_price", _get_stock_quote)
    register_daemon_method("get_stock_realtime_price", _get_stock_quote)
    register_daemon_method("get_stock_history", _get_stock_history)
    register_daemon_method("get_stock_news", _get_stock_news)
    register_daemon_method("get_announcements", _get_stock_announcements)
```

- [ ] **Step 3: Add register_daemon_handlers to financial_query.py**

```python
# === Daemon handler registration ===

from .daemon import register_daemon_method
from .context import CliContext

def register_daemon_handlers() -> None:
    ctx = CliContext(db_path=None, output_dir=None, python="python3")

    def _get_financial_indicators(params):
        return get_financial_indicators(ctx, {"symbol": params.get("symbol")})

    def _get_financial_statements(params):
        return get_financial_statements(ctx, {
            "symbol": params.get("symbol"),
            "statement_type": params.get("statement_type", "all"),
            "recent_n": params.get("recent_n", 4),
        })

    def _get_income_statement(params):
        return get_income_statement(ctx, {
            "symbol": params.get("symbol"),
            "recent_n": params.get("recent_n", 4),
        })

    def _get_cash_flow(params):
        return get_cash_flow(ctx, {
            "symbol": params.get("symbol"),
            "recent_n": params.get("recent_n", 4),
        })

    def _get_stock_valuation(params):
        return get_stock_valuation(ctx, {"symbol": params.get("symbol")})

    def _get_pe_percentile(params):
        return get_pe_percentile(ctx, {
            "symbol": params.get("symbol"),
            "years": params.get("years", 5),
        })

    def _get_hk_financials(params):
        return get_hk_financials(ctx, {"symbol": params.get("symbol")})

    def _get_hk_analysis(params):
        return get_hk_analysis(ctx, {"symbol": params.get("symbol")})

    register_daemon_method("get_financial_indicators", _get_financial_indicators)
    register_daemon_method("get_financial_statements", _get_financial_statements)
    register_daemon_method("get_financial_data", _get_financial_statements)
    register_daemon_method("get_income_statement", _get_income_statement)
    register_daemon_method("get_cash_flow", _get_cash_flow)
    register_daemon_method("get_stock_valuation", _get_stock_valuation)
    register_daemon_method("get_valuation", _get_stock_valuation)
    register_daemon_method("get_pe_percentile", _get_pe_percentile)
    register_daemon_method("get_hk_financials", _get_hk_financials)
    register_daemon_method("get_hk_analysis", _get_hk_analysis)
```

- [ ] **Step 4: Add register_daemon_handlers to analysis_query.py**

```python
# === Daemon handler registration ===

from .daemon import register_daemon_method
from .context import CliContext

def register_daemon_handlers() -> None:
    ctx = CliContext(db_path=None, output_dir=None, python="python3")

    def _calculate_technical(params):
        return calculate_technical_indicators(ctx, {
            "symbol": params.get("symbol"),
            "period": params.get("period", "daily"),
        })

    def _analyze_candlestick(params):
        return analyze_candlestick(ctx, {"symbol": params.get("symbol")})

    def _analyze_price_action(params):
        return analyze_price_action(ctx, {"symbol": params.get("symbol")})

    def _calculate_buy_range(params):
        return calculate_buy_range(ctx, {"symbol": params.get("symbol")})

    def _get_exit_plan(params):
        return get_exit_plan(ctx, {"symbol": params.get("symbol")})

    def _compare_peers(params):
        return compare_peers(ctx, {"symbol": params.get("symbol")})

    def _get_quality_score(params):
        return get_quality_score(ctx, {"symbol": params.get("symbol")})

    register_daemon_method("calculate_technical_indicators", _calculate_technical)
    register_daemon_method("analyze_technical", _calculate_technical)
    register_daemon_method("analyze_candlestick", _analyze_candlestick)
    register_daemon_method("analyze_price_action", _analyze_price_action)
    register_daemon_method("calculate_buy_range", _calculate_buy_range)
    register_daemon_method("get_buy_range", _calculate_buy_range)
    register_daemon_method("get_exit_plan", _get_exit_plan)
    register_daemon_method("compare_peers", _compare_peers)
    register_daemon_method("get_quality_score", _get_quality_score)
```

- [ ] **Step 5: Add register_daemon_handlers to sentiment_query.py**

```python
# === Daemon handler registration ===

from .daemon import register_daemon_method
from .context import CliContext

def register_daemon_handlers() -> None:
    ctx = CliContext(db_path=None, output_dir=None, python="python3")

    def _get_stock_fund_flow(params):
        return get_stock_fund_flow(ctx, {
            "symbol": params.get("symbol"),
            "days": params.get("days", 5),
        })

    def _get_lhb(params):
        return get_lhb(ctx, {"days": params.get("days", 1)})

    def _get_margin_data(params):
        return get_margin_data(ctx, {"symbol": params.get("symbol")})

    def _get_top_holders(params):
        return get_top_holders(ctx, {"symbol": params.get("symbol")})

    def _get_holder_changes(params):
        return get_holder_changes(ctx, {"symbol": params.get("symbol")})

    def _get_fund_holdings(params):
        return get_fund_holdings(ctx, {"symbol": params.get("symbol")})

    def _get_top_fund_stocks(params):
        return get_top_fund_stocks(ctx, {"limit": params.get("limit", 50)})

    def _get_insider_trades(params):
        return get_insider_trades(ctx, {"symbol": params.get("symbol")})

    register_daemon_method("get_stock_fund_flow", _get_stock_fund_flow)
    register_daemon_method("get_lhb", _get_lhb)
    register_daemon_method("get_margin_data", _get_margin_data)
    register_daemon_method("get_top_holders", _get_top_holders)
    register_daemon_method("get_holder_changes", _get_holder_changes)
    register_daemon_method("get_fund_holdings", _get_fund_holdings)
    register_daemon_method("get_top_fund_stocks", _get_top_fund_stocks)
    register_daemon_method("get_insider_trades", _get_insider_trades)
```

- [ ] **Step 6: Add register_daemon_handlers to risk_query.py**

```python
# === Daemon handler registration ===

from .daemon import register_daemon_method
from .context import CliContext

def register_daemon_handlers() -> None:
    ctx = CliContext(db_path=None, output_dir=None, python="python3")

    def _check_trade_risk(params):
        return check_trade_risk(ctx, {
            "symbol": params.get("symbol"),
            "action": params.get("action"),
            "price": params.get("price"),
            "shares": params.get("shares"),
        })

    def _calculate_position_size(params):
        return calculate_position_size(ctx, {
            "symbol": params.get("symbol"),
            "price": params.get("price"),
            "signal_strength": params.get("signal_strength", 1.0),
        })

    def _calculate_stop_loss(params):
        return calculate_stop_loss(ctx, {
            "symbol": params.get("symbol"),
            "entry_price": params.get("entry_price"),
            "current_price": params.get("current_price"),
            "highest_price": params.get("highest_price"),
        })

    register_daemon_method("check_trade_risk", _check_trade_risk)
    register_daemon_method("calculate_position_size", _calculate_position_size)
    register_daemon_method("calculate_stop_loss", _calculate_stop_loss)
```

- [ ] **Step 7: Add register_daemon_handlers to screening_query.py**

```python
# === Daemon handler registration ===

from .daemon import register_daemon_method
from .context import CliContext

def register_daemon_handlers() -> None:
    ctx = CliContext(db_path=None, output_dir=None, python="python3")

    def _screen_stocks(params):
        return screen_stocks_by_sector(ctx, {
            "sector": params.get("sector"),
            "criteria": params.get("criteria"),
            "limit": params.get("limit", 100),
        })

    def _screen_stocks_quality(params):
        return screen_stocks_quality(ctx, {
            "min_score": params.get("min_score", 70),
            "limit": params.get("limit", 50),
        })

    register_daemon_method("screen_stocks_by_sector", _screen_stocks)
    register_daemon_method("screen_stocks", _screen_stocks)
    register_daemon_method("screen_stocks_quality", _screen_stocks_quality)
```

- [ ] **Step 8: Add register_daemon_handlers to hk_query.py**

```python
# === Daemon handler registration ===

from .daemon import register_daemon_method
from .context import CliContext

def register_daemon_handlers() -> None:
    ctx = CliContext(db_path=None, output_dir=None, python="python3")

    def _get_hk_market_overview(params):
        return get_hk_market_overview(ctx, {})

    def _get_hk_hot_rank(params):
        return get_hk_hot_rank(ctx, {"limit": params.get("limit", 20)})

    def _get_hk_south_flow(params):
        return get_hk_south_flow(ctx, {"days": params.get("days", 1)})

    def _get_hk_technical(params):
        return get_hk_technical(ctx, {"symbol": params.get("symbol")})

    register_daemon_method("get_hk_market_overview", _get_hk_market_overview)
    register_daemon_method("get_hk_hot_rank", _get_hk_hot_rank)
    register_daemon_method("get_hk_south_flow", _get_hk_south_flow)
    register_daemon_method("get_hk_technical", _get_hk_technical)
```

- [ ] **Step 9: Verify syntax for all modified files**

```bash
for f in quant/quantsys/cli/{market,stock,financial,analysis,sentiment,risk,screening,hk}_query.py; do
  python3 -c "import py_compile; py_compile.compile('$f', doraise=True)" && echo "OK: $f"
done
```

Expected: All files show "OK"

---

### Task 5: Create TypeScript Daemon Adapter

**Files:**
- Create: `src/infrastructure/quant/quantsys-daemon-adapter.ts`

- [ ] **Step 1: Write quantsys-daemon-adapter.ts**

```typescript
/**
 * QuantSys Daemon Adapter — TypeScript client for QuantSys CLI daemon mode.
 *
 * Maintains a long-running `python -m quantsys.cli --daemon` process that
 * communicates via stdin/stdout using JSON-RPC 2.0 protocol.
 * Automatically restarts on crashes.
 *
 * Replaces the old python-bridge.ts (akshare_bridge.py daemon).
 */

import { spawn, ChildProcess } from "child_process";
import { join } from "path";
import { fileURLToPath } from "url";
import { dirname } from "path";
import * as readline from "readline";

const __dirname = dirname(fileURLToPath(import.meta.url));
const QUANT_ROOT = join(__dirname, "..", "..", "..", "quant");
const RESTART_DELAY_MS = 1000;
const REQUEST_TIMEOUT_MS = 150_000;

interface JsonRpcRequest {
  jsonrpc: "2.0";
  id: number;
  method: string;
  params: Record<string, unknown>;
}

interface JsonRpcResponse {
  jsonrpc: "2.0";
  id: number;
  result?: unknown;
  error?: { code: number; message: string; data?: unknown };
}

interface PendingRequest {
  resolve: (value: string) => void;
  reject: (error: Error) => void;
  timer: NodeJS.Timeout;
}

class QuantSysDaemon {
  private process: ChildProcess | null = null;
  private requestId = 0;
  private pendingRequests = new Map<number, PendingRequest>();
  private isShuttingDown = false;
  private restartTimer: NodeJS.Timeout | null = null;
  private rl: readline.Interface | null = null;

  constructor() {
    this.start();
    process.on("exit", () => this.shutdown());
    process.on("SIGINT", () => this.shutdown());
    process.on("SIGTERM", () => this.shutdown());
  }

  private start(): void {
    if (this.isShuttingDown) return;

    try {
      this.process = spawn("python3", ["-m", "quantsys.cli", "--daemon"], {
        cwd: QUANT_ROOT,
        stdio: ["pipe", "pipe", "pipe"],
        env: { ...process.env, PYTHONUNBUFFERED: "1" },
      });

      this.rl = readline.createInterface({
        input: this.process.stdout!,
        crlfDelay: Infinity,
      });

      this.rl.on("line", (line: string) => {
        this.handleResponse(line);
      });

      this.process.stderr?.on("data", (data: Buffer) => {
        const msg = data.toString().trim();
        if (msg) {
          console.error(`[quantsys-daemon stderr] ${msg}`);
        }
      });

      this.process.on("exit", (code, signal) => {
        console.warn(
          `[quantsys-daemon] Process exited (code=${code}, signal=${signal})`
        );
        this.cleanup();

        for (const [id, pending] of this.pendingRequests) {
          clearTimeout(pending.timer);
          pending.reject(new Error("QuantSys daemon process exited unexpectedly"));
          this.pendingRequests.delete(id);
        }

        if (!this.isShuttingDown) {
          console.log(
            `[quantsys-daemon] Restarting in ${RESTART_DELAY_MS}ms...`
          );
          this.restartTimer = setTimeout(() => this.start(), RESTART_DELAY_MS);
        }
      });

      this.process.on("error", (err) => {
        console.error(`[quantsys-daemon] Process error:`, err);
      });

      console.log(`[quantsys-daemon] Started (PID=${this.process.pid})`);
    } catch (error) {
      console.error(`[quantsys-daemon] Failed to start:`, error);
      if (!this.isShuttingDown) {
        this.restartTimer = setTimeout(() => this.start(), RESTART_DELAY_MS);
      }
    }
  }

  private cleanup(): void {
    if (this.rl) {
      this.rl.close();
      this.rl.removeAllListeners();
      this.rl = null;
    }
    if (this.process) {
      this.process.stdin?.removeAllListeners();
      this.process.stdout?.removeAllListeners();
      this.process.stderr?.removeAllListeners();
      this.process.removeAllListeners();
    }
    this.process = null;
  }

  private handleResponse(line: string): void {
    if (!line.trim()) return;

    try {
      const response: JsonRpcResponse = JSON.parse(line);

      if (response.jsonrpc !== "2.0" || typeof response.id !== "number") {
        console.warn(`[quantsys-daemon] Invalid JSON-RPC response:`, line);
        return;
      }

      const pending = this.pendingRequests.get(response.id);
      if (!pending) {
        console.warn(
          `[quantsys-daemon] Received response for unknown request ID ${response.id}`
        );
        return;
      }

      clearTimeout(pending.timer);
      this.pendingRequests.delete(response.id);

      if (response.error) {
        pending.reject(new Error(response.error.message));
      } else {
        const resultStr =
          typeof response.result === "string"
            ? response.result
            : JSON.stringify(response.result);
        pending.resolve(resultStr);
      }
    } catch (error) {
      console.error(
        `[quantsys-daemon] Failed to parse response:`,
        line,
        error
      );
    }
  }

  async call(
    method: string,
    params: Record<string, unknown> = {}
  ): Promise<string> {
    if (!this.process || this.process.exitCode !== null) {
      throw new Error("QuantSys daemon is not running");
    }

    const id = ++this.requestId;
    const request: JsonRpcRequest = {
      jsonrpc: "2.0",
      id,
      method,
      params,
    };

    return new Promise<string>((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pendingRequests.delete(id);
        reject(new Error(`Request timeout after ${REQUEST_TIMEOUT_MS}ms`));
      }, REQUEST_TIMEOUT_MS);

      this.pendingRequests.set(id, { resolve, reject, timer });

      try {
        const requestLine = JSON.stringify(request) + "\n";
        this.process!.stdin!.write(requestLine, "utf8", (err) => {
          if (err) {
            clearTimeout(timer);
            this.pendingRequests.delete(id);
            reject(
              new Error(`Failed to write to QuantSys daemon: ${err.message}`)
            );
          }
        });
      } catch (error) {
        clearTimeout(timer);
        this.pendingRequests.delete(id);
        reject(error instanceof Error ? error : new Error(String(error)));
      }
    });
  }

  shutdown(): void {
    if (this.isShuttingDown) return;
    this.isShuttingDown = true;

    if (this.restartTimer) {
      clearTimeout(this.restartTimer);
      this.restartTimer = null;
    }

    for (const [id, pending] of this.pendingRequests) {
      clearTimeout(pending.timer);
      pending.reject(new Error("QuantSys daemon is shutting down"));
      this.pendingRequests.delete(id);
    }

    if (this.process) {
      try {
        this.process.stdin?.end();
        this.process.kill("SIGTERM");
        setTimeout(() => {
          if (this.process && this.process.exitCode === null) {
            this.process.kill("SIGKILL");
          }
        }, 2000);
      } catch (error) {
        console.error(`[quantsys-daemon] Error during shutdown:`, error);
      }
    }

    this.cleanup();
  }
}

let daemon: QuantSysDaemon | null = null;

export async function callQuantSysDaemon(
  func: string,
  args: Record<string, unknown> = {}
): Promise<string> {
  if (!daemon) {
    daemon = new QuantSysDaemon();
  }
  return daemon.call(func, args);
}

export function shutdownQuantSysDaemon(): void {
  if (daemon) {
    daemon.shutdown();
    daemon = null;
  }
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
npx tsc --noEmit src/infrastructure/quant/quantsys-daemon-adapter.ts
```

Expected: No errors

---

### Task 6: Update Resilient Adapter

**Files:**
- Modify: `src/infrastructure/tools/shared/python-caller-resilient-adapter.ts`

- [ ] **Step 1: Replace import**

Change line 8 from:
```typescript
import { callBridgeOrCli } from "../../quant/bridge-to-cli-adapter.js";
```
To:
```typescript
import { callQuantSysDaemon } from "../../quant/quantsys-daemon-adapter.js";
```

- [ ] **Step 2: Replace function call in callPythonWithTimeout**

Change line 211 from:
```typescript
    callBridgeOrCli(func, args),
```
To:
```typescript
    callQuantSysDaemon(func, args),
```

- [ ] **Step 3: Verify TypeScript compiles**

```bash
npx tsc --noEmit src/infrastructure/tools/shared/python-caller-resilient-adapter.ts
```

Expected: No errors

---

### Task 7: Update restart-agent-tool

**Files:**
- Modify: `src/infrastructure/tools/agent/restart-agent-tool.ts`

- [ ] **Step 1: Update pgrep pattern and comments**

Read `src/infrastructure/tools/agent/restart-agent-tool.ts` lines 104-109.

Change from:
```typescript
 * 查找 Python akshare_bridge 进程并终止
 * 只匹配通过本项目启动的 akshare_bridge.py --daemon 进程
```

To:
```typescript
 * 查找 QuantSys CLI daemon 进程并终止
 * 只匹配通过本项目启动的 quantsys.cli --daemon 进程
```

Change from:
```typescript
    const result = execSync("pgrep -f 'akshare_bridge.py' 2>/dev/null || true", {
```

To:
```typescript
    const result = execSync("pgrep -f 'quantsys.cli.*--daemon' 2>/dev/null || true", {
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
npx tsc --noEmit src/infrastructure/tools/agent/restart-agent-tool.ts
```

Expected: No errors

---

### Task 8: Update quant-cli-tool.ts

**Files:**
- Modify: `src/infrastructure/tools/core/quant-cli-tool.ts`

- [ ] **Step 1: Update comment**

Read `src/infrastructure/tools/core/quant-cli-tool.ts` lines 1097-1101.

Change from:
```typescript
/**
 * Run confidence calibration via Python bridge.
 * This is separate from regular CLI commands because it uses the
 * akshare_bridge.py's run_confidence_calibration endpoint.
 */
```

To:
```typescript
/**
 * Run confidence calibration via QuantSys daemon.
 * Calls the run_confidence_calibration handler registered in ml_query.py.
 */
```

---

### Task 9: Update tools index.ts

**Files:**
- Modify: `src/infrastructure/tools/index.ts`

- [ ] **Step 1: Remove old exports**

Read `src/infrastructure/tools/index.ts`.

Remove the line (near line 50):
```typescript
export { initCompactTool, initBrowserTool, initTaskTools, initBackgroundManager, getBackgroundManager };
```

And replace with (removing references to old bridge init functions):
```typescript
export { initCompactTool, initBrowserTool, initTaskTools };
export { initBackgroundManager, getBackgroundManager } from "./agent/task-tools.js";
```

---

### Task 10: Delete Old Files

**Files:**
- Delete: `src/infrastructure/tools/core/python-bridge.ts`
- Delete: `src/infrastructure/quant/bridge-to-cli-adapter.ts`
- Delete: `src/infrastructure/quant/market-query-cli-adapter.ts`
- Delete: `src/infrastructure/quant/stock-query-cli-adapter.ts`
- Delete: `src/infrastructure/quant/financial-query-cli-adapter.ts`
- Delete: `src/infrastructure/quant/analysis-query-cli-adapter.ts`
- Delete: `src/infrastructure/quant/sentiment-query-cli-adapter.ts`
- Delete: `src/infrastructure/quant/risk-query-cli-adapter.ts`

- [ ] **Step 1: Delete old TypeScript files**

```bash
rm src/infrastructure/tools/core/python-bridge.ts
rm src/infrastructure/quant/bridge-to-cli-adapter.ts
rm src/infrastructure/quant/market-query-cli-adapter.ts
rm src/infrastructure/quant/stock-query-cli-adapter.ts
rm src/infrastructure/quant/financial-query-cli-adapter.ts
rm src/infrastructure/quant/analysis-query-cli-adapter.ts
rm src/infrastructure/quant/sentiment-query-cli-adapter.ts
rm src/infrastructure/quant/risk-query-cli-adapter.ts
```

- [ ] **Step 2: Clean up any remaining test files referencing deleted files**

```bash
find src/ -name "*.test.ts" -exec grep -l "python-bridge\|bridge-to-cli\|query-cli-adapter" {} \; 2>/dev/null
```

If any test files reference deleted files, remove or update those tests.

---

### Task 11: Verify and Test

- [ ] **Step 1: Check for any remaining references to old paths**

```bash
grep -rn "callBridgeOrCli\|callPythonDaemon\|akshare_bridge\|python-bridge\|bridge-to-cli-adapter" src/ --include="*.ts" | grep -v node_modules
```

Expected: No output (all references removed)

- [ ] **Step 2: Full TypeScript compilation check**

```bash
npx tsc --noEmit
```

Fix any compilation errors before proceeding.

- [ ] **Step 3: Test daemon startup**

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"get_sector_list","params":{}}' | timeout 30 python3 -m quantsys.cli --daemon 2>/dev/null | head -1
```

Expected: A JSON-RPC response with the sector list data (or a "Method not found" error if handlers aren't fully registered yet, which is fine for this test).

---

### Task 12: Final Verification

- [ ] **Step 1: Run all existing tests**

```bash
npm test
```

Expected: All tests pass. If any tests reference deleted files, update or remove them.

- [ ] **Step 2: Run full TypeScript check**

```bash
npx tsc --noEmit
```

Expected: No errors.

- [ ] **Step 3: Commit all changes**

```bash
git add -A
git status
```

Review the status to confirm only expected files are changed. Then:

```bash
git commit -m "refactor: migrate Python Bridge to QuantSys CLI daemon

Replace akshare_bridge.py daemon and bridge-to-cli routing with unified
python -m quantsys.cli --daemon entry. All functions (including ML)
now go through a single JSON-RPC daemon. Deletes 8 obsolete files."
```
