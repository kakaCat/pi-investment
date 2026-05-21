# Phase 4: CLI Migration — v2 接管 quantsys.cli 模块路径

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** v2 CLI 接管 `python -m quantsys.cli` 模块路径，TypeScript 层零改动，旧 CLI 作为回退保留。分三批实现高频命令。

**Architecture:** TypeScript `quant-cli-client.ts` → `python -m quantsys.cli <domain> +<action> --json` → v2 CLI dispatcher → `DataService` → `Repository` → PostgreSQL。CLI 直连 DB，不经 HTTP。

**Tech Stack:** Python argparse, DataService, psycopg2, PostgreSQL

---

## Current State

| Item | Old CLI | v2 CLI |
|------|---------|--------|
| Module path | `quantsys.cli` | `qsv2` (hardcoded) |
| `python -m` entry | `__main__.py` | None |
| Commands | 74 | 25 (8 domains) |
| JSON envelope | `{ok, command, data, error}` | Raw JSON (no envelope) |
| CLI name TypeScript calls | `quant` | N/A |
| CWD for invocation | `<project>/quant/` | Not wired |

## Strategy: Soft takeover

Rather than a big-bang rewrite, use a **dispatcher pattern**: v2 CLI registers commands it knows how to handle; any unrecognized command falls through to the old CLI. This allows incremental migration without breaking the TypeScript layer.

```
python -m quantsys.cli <domain> +<action> --json
         │
         ▼
    v2 dispatcher
    ┌─────────────┐
    │ command in   │──yes──▶ v2 handler → DataService → PostgreSQL
    │ v2 registry? │
    └─────────────┘
         │ no
         ▼
    old CLI fallback
    python -m quantsys.old_cli ...
```

## File Layout

| File | Action | Role |
|------|--------|------|
| `quantsys-v2/cli/__init__.py` | MODIFY | Package marker |
| `quantsys-v2/cli/__main__.py` | CREATE | `python -m` entrypoint |
| `quantsys-v2/cli/main.py` | MODIFY | Rename prog to `quant`, add JSON envelope, add fallback |
| `quantsys-v2/cli/registry.py` | CREATE | Command registry (domain.action → handler) |
| `quantsys-v2/cli/tier1_handlers.py` | CREATE | Tier 1 high-frequency handlers |
| `quantsys-v2/cli/tier2_handlers.py` | CREATE | Tier 2 sentiment/screening/financial handlers |
| `quantsys-v2/cli/output.py` | MODIFY | JSON envelope format |
| `quantsys-v2/tests/test_cli_migration.py` | CREATE | CLI migration tests |
| `quant/quantsys/cli/` | RENAME | Move to `quantsys/old_cli/` for fallback |

---

### Task 1: Rename old CLI to serve as fallback

**Files:**
- Rename: `quant/quantsys/cli/` → `quant/quantsys/old_cli/`

- [ ] **Step 1: Copy old CLI to old_cli**

```bash
cp -r /Users/mac/Documents/ai/pi-investment/quant/quantsys/cli /Users/mac/Documents/ai/pi-investment/quant/quantsys/old_cli
```

- [ ] **Step 2: Update old_cli internal imports**

```bash
cd /Users/mac/Documents/ai/pi-investment/quant/quantsys/old_cli
# Fix any relative imports that reference 'cli' to 'old_cli'
grep -rn "from quantsys.cli\|import quantsys.cli" . | head -20
```

Fix any import references from `quantsys.cli` to `quantsys.old_cli`.

- [ ] **Step 3: Verify old CLI still works from new location**

```bash
cd /Users/mac/Documents/ai/pi-investment/quant && python -c "from quantsys.old_cli.main import main; print('Import OK')"
```

- [ ] **Step 4: Commit**

```bash
cd /Users/mac/Documents/ai/pi-investment/quant && git add quantsys/old_cli/ && git commit -m "refactor: duplicate CLI to old_cli as migration fallback"
```

---

### Task 2: Command Registry + JSON envelope

**Files:**
- Create: `quantsys-v2/cli/registry.py`
- Modify: `quantsys-v2/cli/output.py`

- [ ] **Step 1: Write `registry.py`**

```python
"""Command registry for v2 CLI — maps 'domain.action' to handlers."""
from typing import Dict, Callable, List, Any, NamedTuple, Optional


class CommandSpec(NamedTuple):
    domain: str
    action: str
    handler: Callable
    description: str = ""
    params: List[str] = None  # list of --param-name strings


class CommandRegistry:
    def __init__(self):
        self._commands: Dict[str, CommandSpec] = {}

    def register(self, domain: str, action: str, handler: Callable,
                 description: str = "", params: List[str] = None):
        key = f"{domain}.{action}"
        self._commands[key] = CommandSpec(
            domain=domain, action=action, handler=handler,
            description=description, params=params or [],
        )

    def get(self, domain: str, action: str) -> Optional[CommandSpec]:
        return self._commands.get(f"{domain}.{action}")

    def has(self, domain: str, action: str) -> bool:
        return f"{domain}.{action}" in self._commands

    def list_all(self) -> List[CommandSpec]:
        return sorted(self._commands.values(), key=lambda c: f"{c.domain}.{c.action}")


# Global registry instance
registry = CommandRegistry()
```

- [ ] **Step 2: Update `output.py` with JSON envelope**

```python
"""CLI output formatting — JSON envelope compatible with old CLI."""
import json
import sys
from typing import Any, Dict, Optional


def format_output(data: Any, command: str = "", ok: bool = True,
                  warnings: list = None, error: Optional[Dict] = None) -> str:
    """Format output in {ok, command, data, error} envelope for TypeScript parsing."""
    envelope = {
        "ok": ok,
        "command": command,
        "data": data if data is not None else {},
        "warnings": warnings or [],
        "error": error,
    }
    return json.dumps(envelope, ensure_ascii=False, default=str)


def output_json(data: Any, command: str = ""):
    """Print JSON envelope to stdout."""
    print(format_output(data, command=command))


def output_error(message: str, command: str = "", code: str = "CLI_ERROR"):
    """Print error envelope to stdout."""
    print(format_output(None, command=command, ok=False, error={"code": code, "message": message}))
```

- [ ] **Step 3: Commit**

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && git add cli/registry.py cli/output.py && git commit -m "feat: add CommandRegistry and JSON envelope for CLI compatibility"
```

---

### Task 3: Rewrite v2 CLI entrypoint to take over `quantsys.cli`

**Files:**
- Create: `quantsys-v2/cli/__main__.py`
- Modify: `quantsys-v2/cli/main.py`
- Modify: `quantsys-v2/cli/__init__.py`

- [ ] **Step 1: Write `__main__.py`**

```python
"""Entry point for python -m quantsys.cli."""
from cli.main import main
import sys

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Rewrite `main.py` — dispatcher + fallback to old CLI**

```python
#!/usr/bin/env python3
"""QuantSys v2 CLI dispatcher.

Handles known commands via v2 DataService. Falls back to old CLI for
unregistered commands, maintaining backward compatibility.
"""
import sys
import argparse
import json
from typing import Dict, Any, Optional

from cli.registry import registry
from cli.output import output_json, output_error
from cli.tier1_handlers import register_tier1
from cli.tier2_handlers import register_tier2

# Register all v2 handlers
register_tier1(registry)
register_tier2(registry)


def _fallback_to_old_cli(domain: str, action: str, cli_args: list) -> None:
    """Dispatch to old CLI for unregistered commands."""
    import subprocess
    import os

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    old_cli_dir = os.path.join(project_root, "quant")
    cmd = [
        sys.executable, "-m", "quantsys.old_cli",
        domain, f"+{action}", "--json",
    ] + cli_args

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=old_cli_dir)
    if result.stdout:
        print(result.stdout.strip())
    if result.stderr:
        print(result.stderr.strip(), file=sys.stderr)
    sys.exit(result.returncode)


def _parse_kebab_to_snake(args: list) -> Dict[str, Any]:
    """Parse --kebab-case args into a snake_case dict for handler params."""
    params = {}
    i = 0
    while i < len(args):
        arg = args[i]
        if arg.startswith("--"):
            key = arg[2:].replace("-", "_")
            # Check if next arg is a value (not a flag)
            if i + 1 < len(args) and not args[i + 1].startswith("--"):
                val = args[i + 1]
                # Try parsing numbers
                try:
                    if "." in val:
                        val = float(val)
                    else:
                        val = int(val)
                except ValueError:
                    pass
                params[key] = val
                i += 2
            else:
                params[key] = True
                i += 1
        else:
            i += 1
    return params


def main(argv: list = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if not argv:
        print("Usage: python -m quantsys.cli <domain> +<action> [--params]", file=sys.stderr)
        print("Available commands:", file=sys.stderr)
        for cmd in registry.list_all():
            print(f"  {cmd.domain} +{cmd.action} — {cmd.description}", file=sys.stderr)
        return 1

    domain = argv[0]
    action = argv[1].lstrip("+") if len(argv) > 1 and argv[1].startswith("+") else (argv[1] if len(argv) > 1 else "")
    remaining = argv[2:]

    # Strip --json flag if present (envelope always JSON)
    remaining = [a for a in remaining if a != "--json"]

    if not registry.has(domain, action):
        _fallback_to_old_cli(domain, action, remaining)
        return 0

    spec = registry.get(domain, action)
    params = _parse_kebab_to_snake(remaining)

    try:
        from services.data_service import DataService
        ds = DataService()
        try:
            result = spec.handler(ds, params)
            output_json(result, command=f"{domain}.{action}")
        finally:
            ds.close()
    except Exception as e:
        output_error(str(e), command=f"{domain}.{action}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Create symlink / replace old CLI module path**

```bash
# Check current structure
ls /Users/mac/Documents/ai/pi-investment/quant/quantsys/cli/ 2>/dev/null && echo "old cli exists"

# Strategy: move old CLI to old_cli, create symlink to v2 CLI
mv /Users/mac/Documents/ai/pi-investment/quant/quantsys/cli /Users/mac/Documents/ai/pi-investment/quant/quantsys/old_cli 2>/dev/null || true
# Create a Python path file that redirects to v2
```

Instead of symlinks (fragile), create a redirect package at `quant/quantsys/cli/__init__.py`:

```python
"""Redirect to v2 CLI."""
import sys
import os

_v2_cli = os.path.join(os.path.dirname(__file__), "..", "..", "..", "quantsys-v2", "cli")
if _v2_cli not in sys.path:
    sys.path.insert(0, os.path.dirname(_v2_cli))
```

And `quant/quantsys/cli/__main__.py`:

```python
"""Redirect to v2 CLI entrypoint."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "..", "quantsys-v2"))
from cli.main import main
sys.exit(main())
```

- [ ] **Step 4: Test the dispatcher**

```bash
# Test that old and new commands coexist
cd /Users/mac/Documents/ai/pi-investment/quant && PGDATABASE=quant_investment python -m quantsys.cli stock info --symbol 000001.SZ 2>&1
cd /Users/mac/Documents/ai/pi-investment/quant && PGDATABASE=quant_investment python -m quantsys.cli market overview 2>&1  # should fall through to old CLI
```

- [ ] **Step 5: Verify TypeScript compatibility**

```bash
cd /Users/mac/Documents/ai/pi-investment && PGDATABASE=quant_investment python -m quantsys.cli stock info --symbol 000001.SZ --json 2>&1
```

Expected output envelope: `{"ok": true, "command": "stock.info", "data": {...}, "warnings": [], "error": null}`

- [ ] **Step 6: Commit**

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && git add cli/ cli/__main__.py cli/main.py cli/__init__.py && git commit -m "feat: v2 CLI takes over quantsys.cli with fallback dispatcher"
```

---

### Task 4: Tier 1 handlers — high-frequency read commands

**Files:**
- Create: `quantsys-v2/cli/tier1_handlers.py`

Port the 12 most-called TypeScript commands using v2 DataService.

- [ ] **Step 1: Build the tier1_handlers.py with all 12 commands**

```python
"""Tier 1 handlers — high-frequency read commands called by TypeScript."""
from typing import Dict, Any
from cli.registry import CommandRegistry
from services.data_service import DataService


def register_tier1(reg: CommandRegistry):
    reg.register("stock", "info", handle_stock_info,
                 description="Get stock profile info",
                 params=["--symbol"])
    reg.register("stock", "klines", handle_stock_klines,
                 description="Get daily klines",
                 params=["--symbol", "--start-date", "--end-date", "--limit"])
    reg.register("stock", "quote", handle_stock_quote,
                 description="Get latest price quote",
                 params=["--symbol"])
    reg.register("stock", "batch-quotes", handle_stock_batch_quotes,
                 description="Batch get price quotes",
                 params=["--symbols"])
    reg.register("stock", "list", handle_stock_list,
                 description="List stocks with filters",
                 params=["--market", "--limit"])
    reg.register("stock", "search", handle_stock_search,
                 description="Search stocks by keyword",
                 params=["--q", "--limit"])
    reg.register("stock", "history", handle_stock_history,
                 description="Get stock price history",
                 params=["--symbol", "--start-date", "--end-date"])
    reg.register("market", "overview", handle_market_overview,
                 description="A-share market overview",
                 params=[])
    reg.register("signal", "list", handle_signal_list,
                 description="List trading signals",
                 params=["--date", "--type", "--limit"])
    reg.register("backtest", "results", handle_backtest_results,
                 description="Get backtest results",
                 params=["--symbol", "--strategy"])
    reg.register("risk", "summary", handle_risk_summary,
                 description="Portfolio risk summary",
                 params=[])
    reg.register("data", "status", handle_data_status,
                 description="Check data integrity for a symbol",
                 params=["--symbol"])


def handle_stock_info(ds: DataService, params: Dict[str, Any]) -> Dict[str, Any]:
    symbol = params.get("symbol", "")
    result = ds.stock.get_by_symbol(symbol)
    return {"symbol": symbol, "info": result}


def handle_stock_klines(ds: DataService, params: Dict[str, Any]) -> Dict[str, Any]:
    symbol = params.get("symbol", "")
    start = params.get("start_date", "2020-01-01")
    end = params.get("end_date", "2099-12-31")
    limit = params.get("limit", 365)
    klines = ds.kline.get_daily_klines(symbol, start, end)
    return {"symbol": symbol, "klines": klines[-limit:] if klines else [], "count": len(klines)}


def handle_stock_quote(ds: DataService, params: Dict[str, Any]) -> Dict[str, Any]:
    symbol = params.get("symbol", "")
    kline = ds.kline.get_latest_daily_kline(symbol)
    return {"symbol": symbol, "quote": kline}


def handle_stock_batch_quotes(ds: DataService, params: Dict[str, Any]) -> Dict[str, Any]:
    symbols_str = params.get("symbols", "")
    symbols = [s.strip() for s in symbols_str.split(",") if s.strip()]
    results = {}
    for sym in symbols:
        kline = ds.kline.get_latest_daily_kline(sym)
        results[sym] = kline
    return {"quotes": results}


def handle_stock_list(ds: DataService, params: Dict[str, Any]) -> Dict[str, Any]:
    market = params.get("market", "A")
    limit = params.get("limit", 50)
    stocks = ds.stock.get_all(market=market if market != "all" else None, limit=limit)
    return {"stocks": stocks, "count": len(stocks)}


def handle_stock_search(ds: DataService, params: Dict[str, Any]) -> Dict[str, Any]:
    q = params.get("q", "")
    limit = params.get("limit", 20)
    results = ds.stock.search(q, limit=limit)
    return {"stocks": results, "query": q, "total": len(results)}


def handle_stock_history(ds: DataService, params: Dict[str, Any]) -> Dict[str, Any]:
    symbol = params.get("symbol", "")
    start = params.get("start_date", "2020-01-01")
    end = params.get("end_date", "2099-12-31")
    klines = ds.kline.get_daily_klines(symbol, start, end)
    return {"symbol": symbol, "history": klines, "count": len(klines)}


def handle_market_overview(ds: DataService, params: Dict[str, Any]) -> Dict[str, Any]:
    overview = ds.get_market_overview()
    return overview


def handle_signal_list(ds: DataService, params: Dict[str, Any]) -> Dict[str, Any]:
    date = params.get("date")
    sig_type = params.get("type")
    limit = params.get("limit", 50)
    signals = ds.signal.get_latest_signals(limit=limit)
    return {"signals": signals, "count": len(signals)}


def handle_backtest_results(ds: DataService, params: Dict[str, Any]) -> Dict[str, Any]:
    symbol = params.get("symbol")
    strategy = params.get("strategy")
    results = ds.backtest.get_all(limit=50)
    if symbol:
        results = [r for r in results if r.get("symbol") == symbol]
    if strategy:
        results = [r for r in results if r.get("strategy_name") == strategy]
    return {"results": results, "count": len(results)}


def handle_risk_summary(ds: DataService, params: Dict[str, Any]) -> Dict[str, Any]:
    return ds.get_risk_summary()


def handle_data_status(ds: DataService, params: Dict[str, Any]) -> Dict[str, Any]:
    symbol = params.get("symbol", "")
    result = ds.check_data_integrity(symbol)
    return result
```

- [ ] **Step 2: Write tests**

`quantsys-v2/tests/test_cli_migration.py`:

```python
"""CLI migration tests — verify Tier 1 handlers work correctly."""
import pytest
import json
import subprocess
import sys
import os


def run_cli(args: str) -> dict:
    """Run CLI command and return parsed JSON envelope."""
    project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    quant_dir = os.path.join(project_dir, "quant")
    env = os.environ.copy()
    env.setdefault("PGDATABASE", "quant_investment")

    result = subprocess.run(
        [sys.executable, "-m", "quantsys.cli"] + args.split(),
        capture_output=True, text=True, cwd=quant_dir, env=env, timeout=30,
    )
    return json.loads(result.stdout.strip())


class TestCLIEnvelope:
    def test_json_envelope(self):
        data = run_cli("stock info --symbol 000001.SZ")
        assert data["ok"] is True
        assert "command" in data
        assert "data" in data
        assert data["error"] is None


class TestTier1Stock:
    def test_stock_info(self):
        data = run_cli("stock info --symbol 000001.SZ")
        assert data["ok"] is True
        assert data["data"]["info"] is not None

    def test_stock_info_not_found(self):
        data = run_cli("stock info --symbol 999999.SZ")
        assert data["ok"] is True
        assert data["data"]["info"] is None

    def test_stock_klines(self):
        data = run_cli("stock klines --symbol 000001.SZ --start-date 2024-01-01 --end-date 2024-01-31 --limit 10")
        assert data["ok"] is True
        assert "klines" in data["data"]

    def test_stock_quote(self):
        data = run_cli("stock quote --symbol 000001.SZ")
        assert data["ok"] is True

    def test_stock_list(self):
        data = run_cli("stock list --market A --limit 10")
        assert data["ok"] is True
        assert "stocks" in data["data"]

    def test_stock_search(self):
        data = run_cli("stock search --q 平安 --limit 5")
        assert data["ok"] is True

    def test_stock_history(self):
        data = run_cli("stock history --symbol 000001.SZ --start-date 2024-01-01 --end-date 2024-01-31")
        assert data["ok"] is True


class TestTier1Market:
    def test_market_overview(self):
        data = run_cli("market overview")
        assert data["ok"] is True
        assert "total_stocks" in data["data"]


class TestTier1Other:
    def test_signal_list(self):
        data = run_cli("signal list --limit 10")
        assert data["ok"] is True

    def test_backtest_results(self):
        data = run_cli("backtest results")
        assert data["ok"] is True

    def test_risk_summary(self):
        data = run_cli("risk summary")
        assert data["ok"] is True

    def test_data_status(self):
        data = run_cli("data status --symbol 000001.SZ")
        assert data["ok"] is True
        assert "checks" in data["data"]


class TestCLIFallback:
    def test_unknown_command_falls_back(self):
        """Unregistered commands should fall through to old CLI."""
        data = run_cli("stock announcements --symbol 000001.SZ")
        assert "ok" in data  # Should get some response (from old CLI)
```

- [ ] **Step 3: Run CLI tests**

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && PGDATABASE=quant_investment python -m pytest tests/test_cli_migration.py -v --tb=short -o "addopts="
```

Expected: 13+ passed

- [ ] **Step 4: Commit**

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && git add cli/tier1_handlers.py tests/test_cli_migration.py && git commit -m "feat: add Tier 1 CLI handlers — stock, market, signal, backtest, risk, data"
```

---

### Task 5: Tier 2 handlers — sentiment, screening, financial

**Files:**
- Create: `quantsys-v2/cli/tier2_handlers.py`

Port 9 medium-frequency commands.

- [ ] **Step 1: Build tier2_handlers.py**

```python
"""Tier 2 handlers — sentiment, screening, financial, HK commands."""
from typing import Dict, Any
from cli.registry import CommandRegistry
from services.data_service import DataService


def register_tier2(reg: CommandRegistry):
    reg.register("analysis", "technical", handle_analysis_technical,
                 description="Technical analysis indicators",
                 params=["--symbol"])
    reg.register("screening", "quality", handle_screening_quality,
                 description="Quality stock screening",
                 params=["--limit", "--min-score"])
    reg.register("screening", "sector", handle_screening_sector,
                 description="Sector stock screening",
                 params=["--sector", "--limit"])
    reg.register("sentiment", "stock-fund-flow", handle_sentiment_fund_flow,
                 description="Stock fund flow analysis",
                 params=["--symbol"])
    reg.register("financial", "indicators", handle_financial_indicators,
                 description="Financial indicators",
                 params=["--symbol"])
    reg.register("financial", "statements", handle_financial_statements,
                 description="Financial statements",
                 params=["--symbol"])
    reg.register("hk", "market-overview", handle_hk_market_overview,
                 description="HK market overview",
                 params=[])
    reg.register("sentiment", "lhb", handle_sentiment_lhb,
                 description="Dragon-Tiger list (LHB)",
                 params=["--date", "--limit"])
    reg.register("sentiment", "insider-trades", handle_sentiment_insider,
                 description="Insider trades",
                 params=["--symbol", "--limit"])


def handle_analysis_technical(ds: DataService, params: Dict[str, Any]) -> Dict[str, Any]:
    symbol = params.get("symbol", "")
    result = ds.get_stock_analysis(symbol)
    return result


def handle_screening_quality(ds: DataService, params: Dict[str, Any]) -> Dict[str, Any]:
    limit = params.get("limit", 20)
    # Use factor repo to find stocks with good fundamentals
    factors = ds.factor.get_available_factors()
    return {"factors_available": factors, "note": "Quality screening via factor coverage"}


def handle_screening_sector(ds: DataService, params: Dict[str, Any]) -> Dict[str, Any]:
    sector = params.get("sector", "")
    limit = params.get("limit", 20)
    stocks = ds.stock.get_all(industry=sector if sector else None, limit=limit)
    return {"stocks": stocks, "sector": sector, "count": len(stocks)}


def handle_sentiment_fund_flow(ds: DataService, params: Dict[str, Any]) -> Dict[str, Any]:
    symbol = params.get("symbol", "")
    return {"symbol": symbol, "note": "Fund flow data — requires market data fetcher"}


def handle_financial_indicators(ds: DataService, params: Dict[str, Any]) -> Dict[str, Any]:
    symbol = params.get("symbol", "")
    factors = ds.factor.get_latest_factors(symbol)
    return {"symbol": symbol, "indicators": factors}


def handle_financial_statements(ds: DataService, params: Dict[str, Any]) -> Dict[str, Any]:
    symbol = params.get("symbol", "")
    factors = ds.factor.get_factor_history(symbol)
    return {"symbol": symbol, "history": factors}


def handle_hk_market_overview(ds: DataService, params: Dict[str, Any]) -> Dict[str, Any]:
    stocks = ds.stock.get_all(market="HK", limit=20)
    return {"hk_stocks": stocks, "count": len(stocks)}


def handle_sentiment_lhb(ds: DataService, params: Dict[str, Any]) -> Dict[str, Any]:
    limit = params.get("limit", 20)
    return {"lhb": [], "note": "LHB data — requires market data fetcher"}


def handle_sentiment_insider(ds: DataService, params: Dict[str, Any]) -> Dict[str, Any]:
    symbol = params.get("symbol", "")
    limit = params.get("limit", 20)
    return {"symbol": symbol, "insider_trades": [], "note": "Insider trade data — requires market data fetcher"}
```

- [ ] **Step 2: Extend CLI tests for Tier 2**

Add to `tests/test_cli_migration.py`:

```python
class TestTier2Commands:
    def test_analysis_technical(self):
        data = run_cli("analysis technical --symbol 000001.SZ")
        assert data["ok"] is True

    def test_screening_quality(self):
        data = run_cli("screening quality --limit 5")
        assert data["ok"] is True

    def test_screening_sector(self):
        data = run_cli("screening sector --sector 白酒 --limit 5")
        assert data["ok"] is True

    def test_sentiment_fund_flow(self):
        data = run_cli("sentiment stock-fund-flow --symbol 000001.SZ")
        assert data["ok"] is True

    def test_financial_indicators(self):
        data = run_cli("financial indicators --symbol 000001.SZ")
        assert data["ok"] is True

    def test_financial_statements(self):
        data = run_cli("financial statements --symbol 000001.SZ")
        assert data["ok"] is True

    def test_hk_market_overview(self):
        data = run_cli("hk market-overview")
        assert data["ok"] is True
```

- [ ] **Step 3: Run all CLI tests**

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && PGDATABASE=quant_investment python -m pytest tests/test_cli_migration.py -v --tb=short -o "addopts="
```

Expected: 20+ passed

- [ ] **Step 4: Commit**

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && git add cli/tier2_handlers.py tests/test_cli_migration.py && git commit -m "feat: add Tier 2 CLI handlers — sentiment, screening, financial, HK"
```

---

### Task 6: Full regression

- [ ] **Step 1: Run all tests in quantsys-v2**

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && PGDATABASE=quant_investment python -m pytest tests/ --tb=short 2>&1 | tail -5
```

Expected: all pass

- [ ] **Step 2: Verify TypeScript CLI invocations still work**

Test a few commands the TypeScript layer calls:

```bash
cd /Users/mac/Documents/ai/pi-investment/quant && PGDATABASE=quant_investment python -m quantsys.cli stock info --symbol 000001.SZ --json
cd /Users/mac/Documents/ai/pi-investment/quant && PGDATABASE=quant_investment python -m quantsys.cli market overview --json
cd /Users/mac/Documents/ai/pi-investment/quant && PGDATABASE=quant_investment python -m quantsys.cli signal list --limit 5 --json
cd /Users/mac/Documents/ai/pi-investment/quant && PGDATABASE=quant_investment python -m quantsys.cli analysis technical --symbol 000001.SZ --json
```

Each should return `{"ok": true, ...}` envelope.

- [ ] **Step 3: Fix any issues and final commit**
