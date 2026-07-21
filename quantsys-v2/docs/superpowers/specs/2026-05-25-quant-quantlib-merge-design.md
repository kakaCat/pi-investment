# Quant-Quantlib Merge Design

**Date**: 2026-05-25
**Status**: Approved
**Scope**: Merge `quant/` and `quantlib/` into a single `quantlib/` package in quantsys-v2

## Motivation

The project has two parallel quantitative Python packages with zero cross-imports but significant functional overlap:

- **quant** (92 `.py` files): Strategy engine, factor calculation, backtesting, adapters, pipeline stages. Chinese comments, `sys.path.insert` hacks, depends on `docs/interfaces/`.
- **quantlib** (92 `.py` files): Cleaner architecture via `BaseCalculator` inheritance, English docs, better input validation. Fixed income, portfolio optimization, factor models, more complete derivatives and risk.

## Design Decisions

### Naming: Keep `quantlib`

`quant/` content merges into `quantlib/`. All imports change from `from quant.xxx` to `from quantlib.xxx`.

### Overlap Resolution

| Overlapping Domain | Decision | Rationale |
|---|---|---|
| Greeks | Keep quantlib `greeks.py` | More complete (2nd-order Greeks, dividend support, validation) |
| Option Strategies | Keep BOTH | quant's are trading strategies (Δ-neutral, vol arb); quantlib's are analysis tools (payoff profiles, breakevens) |
| VaR | Keep quantlib `var.py` + `cvar.py` | Extra Cornish-Fisher method, time horizon scaling, better CVaR formula. Port `calculate_risk_metrics()` convenience function from quant |
| Risk Attribution | Keep quantlib `attribution.py` | Covariance-based MCR/CCR, group attribution, concentration metrics |
| Risk Monitor | Keep quant `risk_monitor.py` | Unique live monitoring/alerting functionality not in quantlib |
| ML | Keep BOTH | quantlib has XGBoost/LightGBM/LSTM ensemble + feature engineering; quant has PyTorch LSTM/Transformer DL models |
| Time Series | Keep quantlib | quant's `timeseries/` is empty |

### quantlib Internal Dedup

`quantlib/portfolio/` and `quantlib/portfolio_optimization/` are two overlapping implementations of the same concepts (mean-variance, Black-Litterman, efficient frontier, risk parity). Merge into a single `portfolio/` directory.

## Target Directory Structure

```
quantlib/
├── __init__.py
├── base_calculator.py
├── data_validator.py
├── exceptions.py
├── rate_calculations.py
│
├── derivatives/              ← quantlib base + quant option_trading_strategies
│   ├── greeks.py
│   ├── advanced_greeks.py
│   ├── black_scholes.py
│   ├── implied_volatility.py
│   ├── binomial_tree.py
│   ├── monte_carlo.py
│   ├── stochastic_vol.py
│   ├── volatility_surface.py
│   ├── forward_futures.py
│   ├── rate_derivatives.py
│   ├── exotic_options.py
│   ├── option_strategies.py         ← quantlib: payoff analysis
│   ├── option_trading_strategies.py ← quant: Δ-neutral, vol arb
│   ├── examples.py
│   └── arbitrage.py
│
├── risk/                     ← quantlib base + quant risk_monitor
│   ├── var.py               ← + quant convenience functions
│   ├── cvar.py
│   ├── drawdown.py
│   ├── market_risk.py
│   ├── aggregation.py
│   ├── attribution.py
│   ├── scenario_analysis.py
│   ├── stress_test.py
│   ├── stress_testing.py
│   ├── copula.py
│   ├── extreme_value.py
│   ├── counterparty_risk.py
│   ├── liquidity_risk.py
│   ├── margining.py
│   ├── regulatory.py
│   ├── backtesting.py
│   ├── reporting.py
│   ├── risk_monitor.py      ← quant: live monitoring/alerting
│   └── examples.py
│
├── ml/                       ← quantlib base + quant DL models
│   ├── return_prediction.py
│   ├── feature_engineering.py
│   ├── factor_mining.py
│   ├── risk_prediction.py
│   ├── anomaly_detection.py
│   ├── lstm_predictor.py         ← quant
│   ├── transformer_predictor.py  ← quant
│   ├── mlflow_manager.py         ← quant
│   └── examples.py
│
├── timeseries/               ← quantlib (empty quant dir dropped)
│   ├── arima.py
│   ├── garch.py
│   ├── kalman.py
│   ├── cointegration.py
│   ├── causality.py
│   └── examples.py
│
├── fixed_income/             ← quantlib
├── portfolio/                ← quantlib merged (portfolio/ + portfolio_optimization/)
├── factor_models/            ← quantlib
├── prediction_markets/       ← quantlib
│
├── engine/                   ← quant: strategy engine (moved whole)
│   ├── strategy_base.py
│   ├── enhanced_strategy_base.py
│   ├── strategy_runner.py
│   ├── strategy_factory.py
│   ├── strategy_combiner.py
│   ├── smart_backtest_engine.py
│   ├── backtest_report.py
│   ├── config_driven_strategy.py
│   ├── indicator_strategy_executor.py
│   ├── script_strategy_executor.py
│   ├── param_parser.py
│   ├── position_sizing.py
│   ├── risk_rules.py
│   ├── commission.py
│   ├── slippage.py
│   ├── factor_cache.py
│   ├── code_validator.py
│   ├── stress_test.py
│   ├── indicators/           ← technical indicator adapters
│   ├── mixins/               ← factor/indicator/ml mixins
│   ├── [10+ strategy files: ma_cross, rsi_reversal, bollinger_breakout, ...]
│   └── IMPLEMENTATION_SUMMARY.py / STRATEGY_PARAMS_GUIDE.py
│
├── adapters/                 ← quant: data source adapters
├── factors/                  ← quant: factor calculations
├── factor_analysis/          ← quant: IC analysis, layering, orthogonalization
├── stages/                   ← quant: pipeline stages
├── backtest/                 ← quant: walk-forward, market impact
├── futures/                  ← quant: futures pricing
├── hft_strategies/           ← quant: HFT
├── cross_asset_strategies/   ← quant: cross-asset
├── gpu_acceleration/         ← quant: GPU
├── alternative_factors/      ← quant: alt factors
├── statistics/               ← quant: statistics
│
├── tests/                    ← merged test suites
└── examples/                 ← merged examples
```

## Files to Delete

### From `quant/` (replaced by quantlib equivalents)
- `quant/options/` — entire directory, merged into `derivatives/`
- `quant/derivatives/` — entire directory, merged into `derivatives/`
- `quant/risk/var_calculator.py` — replaced by `risk/var.py` + `risk/cvar.py`
- `quant/risk/risk_attribution.py` — replaced by `risk/attribution.py`
- `quant/timeseries/` — empty shell
- `quant/ml/` — 3 files moved into `ml/`, then directory removed

### From `quantlib/` (internal dedup)
- `quantlib/portfolio/` — superseded by `portfolio_optimization/` which is more complete (2,900 vs 2,000 lines, has `constraints.py`, `markowitz.py` covers mean-variance + min-variance). Discarded.
- `quantlib/portfolio_optimization/` — renamed to `portfolio/` as the merged single directory

## Import Migration

All internal `quant/` imports must change:

```
from quant.engine.xxx import YYY    →    from quantlib.engine.xxx import YYY
from quant.risk.var_calculator import VaRCalculator  →  from quantlib.risk.var import VaRCalculator
from quant.factors.xxx import YYY   →    from quantlib.factors.xxx import YYY
...
```

Affected files:
- All 92 files inside `quant/` (internal imports)
- ~30 test files in `tests/` that import from `quant`
- `scripts/diagnostics/test_strategy_engine.py`, `scripts/diagnostics/test_validator_fix.py`, `scripts/diagnostics/create_builtin_indicators_direct.py` (root-level scripts)
- `services/prediction_market_service.py` (imports from quantlib)

## Risks

1. **quant depends on `docs/interfaces/`**: `quant/risk/var_calculator.py` imports `IRiskCalculator`, `quant/risk/risk_monitor.py` imports `IRiskMonitor`, `quant/risk/risk_attribution.py` imports `IRiskAttribution`, `quant/ml/lstm_predictor.py` and `transformer_predictor.py` import `IModelPredictor`. Since quantlib already uses `BaseCalculator` as its base class, these interface imports should be replaced with `BaseCalculator` inheritance during migration.
2. **quant's `sys.path.insert` hacks**: Need to be cleaned up during migration — proper relative imports instead.
3. **Test breakage**: ~60 test files reference either quant or quantlib. All need import updates.
4. **quantlib test file location**: quantlib tests currently live inside `quantlib/tests/`. Should move to project-level `tests/quantlib/`.

## Success Criteria

- All 184 Python files accounted for (merged, moved, or intentionally deleted)
- Zero `from quant.` imports remaining in the project
- All existing tests pass after import updates
- No duplicate module functionality (except the intentional dual option strategy files)
- `quantlib/portfolio/` directory contains merged content from both old portfolio dirs
