# Quant-Quantlib Merge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Merge 184 Python files from `quant/` and `quantlib/` into a single `quantlib/` package, eliminating duplication, cleaning up import hacks, and ensuring all tests pass.

**Architecture:** Move quant's unique modules (engine, adapters, factors, etc.) into quantlib. Merge overlapping modules (derivatives, risk, ML) keeping quantlib's cleaner implementations as primary, porting quant's unique features. Delete quant's empty shells and duplicated code. Update all imports from `from quant.xxx` to `from quantlib.xxx`.

**Tech Stack:** Python 3.14, numpy, scipy, pandas, scikit-learn, PyTorch (optional)

---

### Task 1: Internal portfolio dedup — merge into single `portfolio/`

**Files:**
- Delete: `quantlib/portfolio/` (entire directory — 7 `.py` files)
- Rename: `quantlib/portfolio_optimization/` → `quantlib/portfolio/`
- Modify: `quantlib/__init__.py`

- [ ] **Step 1: Delete old `quantlib/portfolio/` directory**

```bash
rm -rf quantlib/portfolio/
```

- [ ] **Step 2: Rename `portfolio_optimization/` to `portfolio/`**

```bash
mv quantlib/portfolio_optimization quantlib/portfolio
```

- [ ] **Step 3: Update `quantlib/__init__.py` to reference renamed module**

Read `quantlib/__init__.py`, replace any `portfolio_optimization` reference with `portfolio`. If no reference exists, skip.

- [ ] **Step 4: Update any imports in quantlib files that reference `portfolio_optimization`**

```bash
grep -rl "portfolio_optimization" quantlib/ --include="*.py" | grep -v __pycache__
```

For each file found, change `from quantlib.portfolio_optimization` to `from quantlib.portfolio`. Also update any `from .portfolio_optimization` to `from .portfolio` within quantlib internal files.

- [ ] **Step 5: Update imports in tests and services that reference `portfolio_optimization`**

```bash
grep -rl "portfolio_optimization" . --include="*.py" | grep -v __pycache__ | grep -v quantlib/
```

Same replacements.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: merge portfolio_optimization into portfolio, remove duplicate portfolio dir"
```

---

### Task 2: Move quant unique modules into quantlib

**Files to move (directories):**
- `quant/engine/` → `quantlib/engine/`
- `quant/adapters/` → `quantlib/adapters/`
- `quant/factors/` → `quantlib/factors/`
- `quant/factor_analysis/` → `quantlib/factor_analysis/`
- `quant/stages/` → `quantlib/stages/`
- `quant/backtest/` → `quantlib/backtest/`
- `quant/futures/` → `quantlib/futures/`
- `quant/hft_strategies/` → `quantlib/hft_strategies/`
- `quant/cross_asset_strategies/` → `quantlib/cross_asset_strategies/`
- `quant/gpu_acceleration/` → `quantlib/gpu_acceleration/`
- `quant/alternative_factors/` → `quantlib/alternative_factors/`
- `quant/statistics/` → `quantlib/statistics/`

- [ ] **Step 1: Move all unique directories from quant to quantlib**

```bash
for dir in engine adapters factors factor_analysis stages backtest futures hft_strategies cross_asset_strategies gpu_acceleration alternative_factors statistics; do
  mv quant/$dir quantlib/$dir
done
```

- [ ] **Step 2: Update all `from quant.` imports in moved modules to `from quantlib.`**

```bash
# Find all internal imports in moved files
find quantlib/engine quantlib/adapters quantlib/factors quantlib/factor_analysis \
  quantlib/stages quantlib/backtest quantlib/futures quantlib/hft_strategies \
  quantlib/cross_asset_strategies quantlib/gpu_acceleration quantlib/alternative_factors \
  quantlib/statistics -name "*.py" -exec sed -i '' \
  's/from quant\./from quantlib./g; s/import quant\./import quantlib./g' {} +
```

- [ ] **Step 3: Clean up `sys.path.insert(0, ...)` hacks from moved files**

These 12 files have the hack:
- `quantlib/engine/smart_backtest_engine.py`
- `quantlib/factor_analysis/factor_monitor.py`
- `quantlib/futures/futures_pricing.py`
- `quantlib/backtest/walk_forward.py`
- `quantlib/backtest/market_impact.py`

In each file, remove the lines:
```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
```

The remaining files with the hack (old options/, risk/, ml/) will be handled in Task 3 (merge/delete).

- [ ] **Step 4: Replace `docs.interfaces` imports with `BaseCalculator` inheritance**

Files to fix:
- `quantlib/engine/smart_backtest_engine.py` (if it imports from docs.interfaces)

```bash
# Check which moved files still reference docs.interfaces
grep -rl "docs.interfaces" quantlib/engine/ quantlib/adapters/ quantlib/factors/ quantlib/factor_analysis/ quantlib/stages/ quantlib/backtest/ quantlib/futures/ quantlib/hft_strategies/ quantlib/cross_asset_strategies/ quantlib/gpu_acceleration/ quantlib/alternative_factors/ quantlib/statistics/ --include="*.py"
```

For each file, remove `from docs.interfaces.xxx import YYY` and any `class Foo(ISomething)` → `class Foo:` (remove interface inheritance). The abstract methods are already implemented in the classes.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: move quant unique modules (engine, adapters, factors, etc.) into quantlib"
```

---

### Task 3: Merge overlapping modules — Derivatives

**Files:**
- Delete: `quant/options/` (greeks_calculator.py, option_strategies.py)
- Move: `quant/options/option_strategies.py` → `quantlib/derivatives/option_trading_strategies.py`
- Delete: `quant/derivatives/` (if any files remain)
- Modify: `quantlib/derivatives/option_trading_strategies.py` — clean up imports

- [ ] **Step 1: Check what's in `quant/derivatives/`**

```bash
ls quant/derivatives/
```

If files exist besides `__init__.py`, compare with quantlib/derivatives/ equivalents. If no additional files, proceed.

- [ ] **Step 2: Move quant's option trading strategies**

```bash
mv quant/options/option_strategies.py quantlib/derivatives/option_trading_strategies.py
```

- [ ] **Step 3: Fix imports in `option_trading_strategies.py`**

Remove:
```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))
```

Change:
```python
from .greeks_calculator import GreeksCalculator
```
to:
```python
from quantlib.derivatives.greeks import GreeksCalculator
```

Update any `calculate_all_greeks` calls (method doesn't exist in quantlib's version — it's called `calculate`):
Change `self.greeks_calculator.calculate_all_greeks(...)` to `self.greeks_calculator.calculate(...)`.
And change `self.greeks_calculator.calculate_greeks` to `self.greeks_calculator.calculate`.

Also update return value access: quant's returns flat dict `greeks['delta']`, quantlib's returns `result['value']['delta']`. Update all such accesses in the trading strategy code.

- [ ] **Step 4: Delete remaining quant options/ and derivatives/ files**

```bash
# After moving option_strategies.py, only greeks_calculator.py remains in options/
# Delete it (replaced by quantlib's derivatives/greeks.py)
rm quant/options/greeks_calculator.py
rmdir quant/options/ 2>/dev/null || true
# Delete derivatives/ if it exists (may be empty or have just __init__.py)
rm -rf quant/derivatives/ 2>/dev/null || true
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: merge derivatives — keep quantlib greeks, move quant trading strategies"
```

---

### Task 4: Merge overlapping modules — Risk

**Files:**
- Keep: `quantlib/risk/var.py`, `quantlib/risk/cvar.py`, `quantlib/risk/attribution.py`
- Move: `quant/risk/risk_monitor.py` → `quantlib/risk/risk_monitor.py`
- Delete: `quant/risk/var_calculator.py`, `quant/risk/risk_attribution.py`
- Modify: `quantlib/risk/var.py` — port `calculate_risk_metrics()` and convenience functions

- [ ] **Step 1: Port `calculate_risk_metrics()` to `quantlib/risk/var.py`**

Add this method to the `VaRCalculator` class:

```python
def calculate_risk_metrics(self, returns: Union[List, np.ndarray, pd.Series]) -> Dict[str, Any]:
    """
    Calculate comprehensive risk metrics including VaR, CVaR, max drawdown, Sharpe.

    Args:
        returns: Historical returns data

    Returns:
        Dictionary with var_95, var_99, cvar_95, cvar_99, max_drawdown, sharpe_ratio, volatility, mean_return
    """
    import pandas as pd
    if not isinstance(returns, pd.Series):
        returns = pd.Series(returns)
    
    var_95 = self.calculate(returns, confidence_level=0.95, method='historical')['value']
    var_99 = self.calculate(returns, confidence_level=0.99, method='historical')['value']
    
    from quantlib.risk.cvar import CVaRCalculator
    cvar_calc = CVaRCalculator()
    cvar_95 = cvar_calc.calculate(returns, confidence_level=0.95, method='historical')['value']
    cvar_99 = cvar_calc.calculate(returns, confidence_level=0.99, method='historical')['value']
    
    # Max drawdown
    cumulative = (1 + returns).cumprod()
    running_max = cumulative.expanding().max()
    drawdown = (cumulative - running_max) / running_max
    max_dd = abs(float(drawdown.min()))
    
    # Sharpe ratio (annualized)
    excess = returns - self.risk_free_rate / 252
    sharpe = float(excess.mean() / excess.std() * np.sqrt(252)) if excess.std() > 0 else 0.0
    
    return {
        'var_95': var_95,
        'var_99': var_99,
        'cvar_95': cvar_95,
        'cvar_99': cvar_99,
        'max_drawdown': max_dd,
        'sharpe_ratio': sharpe,
        'volatility': float(returns.std()),
        'mean_return': float(returns.mean()),
    }
```

- [ ] **Step 2: Add module-level convenience functions to `quantlib/risk/var.py`**

```python
def quick_var(returns, confidence_level: float = 0.95, method: str = 'historical') -> float:
    """Quick VaR calculation convenience function."""
    calc = VaRCalculator()
    return calc.calculate(returns, confidence_level=confidence_level, method=method)['value']

def quick_cvar(returns, confidence_level: float = 0.95, method: str = 'historical') -> float:
    """Quick CVaR calculation convenience function."""
    from quantlib.risk.cvar import CVaRCalculator
    calc = CVaRCalculator()
    return calc.calculate(returns, confidence_level=confidence_level, method=method)['value']
```

- [ ] **Step 3: Move risk_monitor.py and fix imports**

```bash
mv quant/risk/risk_monitor.py quantlib/risk/risk_monitor.py
```

In `quantlib/risk/risk_monitor.py`:
- Remove `sys.path.insert(0, ...)` hack (lines 5-7: `import sys`, `import os`, `sys.path.insert(0, ...)`)
- Change `from docs.interfaces.risk_interface import IRiskMonitor` → delete line
- Change `class RiskMonitorService(IRiskMonitor):` → `class RiskMonitorService:`
- Change `from quant.risk.var_calculator import VaRCalculator` → `from quantlib.risk.var import VaRCalculator`

- [ ] **Step 4: Delete remaining quant risk files**

```bash
rm quant/risk/var_calculator.py quant/risk/risk_attribution.py
# Remove now-empty quant/risk/ directory
rmdir quant/risk 2>/dev/null || true
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: merge risk modules — keep quantlib VaR/CVaR/attribution, port convenience funcs, move risk_monitor"
```

---

### Task 5: Merge overlapping modules — ML

**Files:**
- Move: `quant/ml/lstm_predictor.py` → `quantlib/ml/lstm_predictor.py`
- Move: `quant/ml/transformer_predictor.py` → `quantlib/ml/transformer_predictor.py`
- Move: `quant/ml/mlflow_manager.py` → `quantlib/ml/mlflow_manager.py`
- Delete: `quant/ml/` (after moves)

- [ ] **Step 1: Move quant ML files to quantlib ML**

```bash
mv quant/ml/lstm_predictor.py quantlib/ml/lstm_predictor.py
mv quant/ml/transformer_predictor.py quantlib/ml/transformer_predictor.py
mv quant/ml/mlflow_manager.py quantlib/ml/mlflow_manager.py
```

- [ ] **Step 2: Fix imports in moved ML files**

In `quantlib/ml/lstm_predictor.py`:
- Remove `sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))`
- Change `from docs.interfaces.ml_interface import IModelPredictor` → remove
- Change `class LSTMPredictor(IModelPredictor):` → `class LSTMPredictor:`

In `quantlib/ml/transformer_predictor.py`:
- Same changes as lstm_predictor.py

In `quantlib/ml/mlflow_manager.py`:
- Remove `sys.path.insert(0, ...)` hack
- Update any `from quant.` imports to `from quantlib.`

- [ ] **Step 3: Delete old `quant/ml/`**

```bash
rm -rf quant/ml/
```

- [ ] **Step 4: Update `quantlib/ml/__init__.py`** to export the new classes

Add to existing exports:
```python
from .lstm_predictor import LSTMPredictor
from .transformer_predictor import TransformerPredictor
from .mlflow_manager import MLflowManager
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: merge ML modules — move DL predictors into quantlib ml"
```

---

### Task 6: Clean up remaining quant files and empty quant dir

**Files to check:**
- `quant/timeseries/` — empty shell, delete
- `quant/options/` — already deleted in Task 3
- `quant/derivatives/` — already deleted in Task 3
- `quant/risk/` — already deleted in Task 4
- `quant/ml/` — already deleted in Task 5
- `quant/__init__.py` — delete
- `quant/statistics/` — already moved in Task 2, but original might remain

- [ ] **Step 1: Delete remaining `quant/` directory and its empty subdirectories**

```bash
# Check what's left in quant/
find quant/ -type f -name "*.py" | grep -v __pycache__
```

If only empty dirs or no Python files remain:
```bash
rm -rf quant/
```

- [ ] **Step 2: Delete quantlib's internal `tests/` directory** (tests should be at project level)

```bash
rm -rf quantlib/tests/
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "refactor: remove old quant/ directory and quantlib/tests/"
```

---

### Task 7: Update all project-level imports

**Files affected:**
- All test files in `tests/` (30+ files)
- `scripts/diagnostics/test_strategy_engine.py`, `scripts/diagnostics/test_validator_fix.py`, `scripts/diagnostics/create_builtin_indicators_direct.py` (root)
- `services/prediction_market_service.py`
- Any `api/`, `cli/`, `core/` files that import from quant or quantlib

- [ ] **Step 1: Find all files that import from `quant` (not `quantlib`)**

```bash
grep -rl "from quant \|from quant\.\|import quant \|import quant\." --include="*.py" . | grep -v __pycache__ | grep -v "/quant/" | grep -v "/quantlib/"
```

- [ ] **Step 2: Run batch sed to fix straightforward package imports**

Most imports just need `quant.` → `quantlib.`: all engine, adapters, factors, factor_analysis, stages, backtest, futures, hft_strategies, cross_asset_strategies, gpu_acceleration imports are straightforward.

```bash
# Get the list of affected files
AFFECTED=$(grep -rl "from quant \|from quant\.\|import quant" --include="*.py" tests/ scripts/diagnostics/test_strategy_engine.py scripts/diagnostics/test_validator_fix.py scripts/diagnostics/create_builtin_indicators_direct.py services/ 2>/dev/null | grep -v __pycache__)

# Batch replace package name
for f in $AFFECTED; do
  sed -i '' 's/from quant\./from quantlib./g; s/from quant /from quantlib /g; s/import quant\./import quantlib./g' "$f"
done
```

- [ ] **Step 3: Fix specific import paths where filenames changed**

These imports cannot be fixed by sed alone — the destination file path changed:

In `tests/test_option_strategies.py`:
```python
# OLD
from quantlib.options.option_strategies import (
    OptionStrategy, DeltaNeutralStrategy, VolatilityArbitrageStrategy
)
# NEW
from quantlib.derivatives.option_trading_strategies import (
    OptionStrategy, DeltaNeutralStrategy, VolatilityArbitrageStrategy
)
```

In `tests/test_risk/test_var_calculator.py`:
```python
# OLD
from quantlib.risk.var_calculator import VaRCalculator, quick_var, quick_cvar
# NEW
from quantlib.risk.var import VaRCalculator, quick_var, quick_cvar
```

In `tests/test_risk/test_risk_attribution.py`:
```python
# OLD
from quantlib.risk.risk_attribution import RiskAttribution
# NEW (class name also changed)
from quantlib.risk.attribution import RiskAttributionCalculator as RiskAttribution
```

In `tests/test_risk/test_risk_monitor.py`:
```python
# OLD
from quantlib.risk.risk_monitor import RiskMonitorService
from quantlib.risk.var_calculator import VaRCalculator
# NEW
from quantlib.risk.risk_monitor import RiskMonitorService
from quantlib.risk.var import VaRCalculator
```

In `tests/test_timeseries.py` and `tests/test_timeseries_extended.py`:
```python
# OLD
from quantlib.timeseries import TimeSeriesAnalyzer
# NEW — quant's timeseries was empty; use quantlib's timeseries modules
# Check what TimeSeriesAnalyzer was supposed to be and replace with:
from quantlib.timeseries import arima, garch
# (or remove if TimeSeriesAnalyzer doesn't exist in quantlib)
```

In `tests/test_fusion_framework.py`:
```python
# OLD
from quantlib.derivatives.pricing import DerivativesPricer
# NEW — pricing.py doesn't exist in quantlib; use appropriate replacement:
from quantlib.derivatives.black_scholes import BlackScholesCalculator
```

In `tests/test_ml/test_lstm_predictor.py`:
```python
# OLD
from quantlib.ml.lstm_predictor import LSTMPredictor
# Already correct after sed (path unchanged), just verify
```

In `tests/test_ml/test_mlflow_manager.py`:
```python
# OLD
from quantlib.ml.mlflow_manager import MLflowManager
# Already correct after sed, just verify
```

- [ ] **Step 4: Update `services/prediction_market_service.py`**

This file imports from `quantlib`. Check for `portfolio_optimization` references and update to `portfolio`.

```bash
grep -n "portfolio_optimization" services/prediction_market_service.py
```

If found, change to `portfolio`.

- [ ] **Step 5: Remove `docs/interfaces/` references from test files**

```bash
grep -rl "docs.interfaces" tests/ --include="*.py"
```

If any test files reference these interfaces, update to use quantlib equivalents or test against concrete classes directly.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor: update all project imports from quant to quantlib"
```
```

If any test files reference these interfaces, update to use quantlib equivalents or remove the interface check (test against concrete class directly).

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: update all project imports from quant to quantlib"
```

---

### Task 8: Verify — run tests and fix failures

- [ ] **Step 1: Run the full test suite**

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2 && python -m pytest tests/ -v --tb=short 2>&1 | head -200
```

- [ ] **Step 2: Categorize failures**

For each failing test, determine cause:
1. Import error → fix import path
2. Method name mismatch → update method call (e.g., `calculate_var` → `calculate`)
3. Return format mismatch → update assertions
4. Missing dependency → document or fix

- [ ] **Step 3: Fix import errors**

Common issues:
- `from quant.xxx import` still present → update to `from quantlib.xxx`
- `VaRCalculator` class path changed → update tests to use new path

- [ ] **Step 4: Fix method signature mismatches**

quant's `VaRCalculator.calculate_var(returns, confidence)` → quantlib's `VaRCalculator.calculate(returns, confidence_level=confidence, method='historical')['value']`

quant's `GreeksCalculator.calculate_greeks(S, K, T, r, sigma, option_type)` → quantlib's `GreeksCalculator.calculate(S, K, T, r, sigma, option_type)['value']`

- [ ] **Step 5: Fix return format mismatches**

quant's flat dict returns → quantlib's nested `{'value': ..., 'method': ..., 'parameters': ..., 'metadata': ...}`

Update test assertions accordingly.

- [ ] **Step 6: Run tests again, iterate until green**

```bash
python -m pytest tests/ -v --tb=short
```

- [ ] **Step 7: Commit any fixes**

```bash
git add -A
git commit -m "fix: update tests for quant→quantlib merge"
```

---

### Task 9: Final cleanup and verification

- [ ] **Step 1: Verify no `from quant.` imports remain anywhere**

```bash
grep -r "from quant \|from quant\.\|import quant \|import quant\." --include="*.py" . | grep -v __pycache__ | grep -v "/quantlib/" | grep -v ".git/"
```

Expected: no output (or only false positives in comments/strings).

- [ ] **Step 2: Verify no `sys.path.insert` hacks remain in quantlib**

```bash
grep -r "sys.path.insert" quantlib/ --include="*.py" | grep -v __pycache__
```

Expected: no output.

- [ ] **Step 3: Verify no `docs.interfaces` imports remain**

```bash
grep -r "docs.interfaces" . --include="*.py" | grep -v __pycache__ | grep -v ".git/"
```

Expected: only in original `docs/interfaces/` definition files themselves.

- [ ] **Step 4: Verify quantlib package structure**

```bash
find quantlib/ -type f -name "*.py" | grep -v __pycache__ | sort
```

Expected: all modules present, no unexpected files.

- [ ] **Step 5: Run full test suite one final time**

```bash
python -m pytest tests/ -v
```

- [ ] **Step 6: Final commit**

```bash
git add -A
git commit -m "chore: final verification and cleanup after quant-quantlib merge"
```
