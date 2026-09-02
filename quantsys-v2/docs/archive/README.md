# Archive

This directory contains legacy files that are kept for reference only. They are no longer used in production and should not be imported or modified in new code.

## Archived Files

- `v13_strategy_legacy.py` — Original V13 strategy implementation (`domain/strategies/v13_strategy.py`).
  - Replaced by:
    - `domain/strategies/xgboost_strategy.py` (pure algorithm)
    - `application/strategies/v13_use_case.py` (V13 orchestration)

- `v14_strategy_legacy.py` — Original V14 strategy implementation (`domain/strategies/v14_strategy.py`).
  - Replaced by:
    - `domain/strategies/xgboost_strategy.py` (pure algorithm)
    - `application/strategies/v14_use_case.py` (V14 orchestration)

## Reason

During the strategy refactor (Part 6.1), the monolithic V13/V14 strategy files were split into a reusable XGBoost algorithm in the domain layer and dedicated use-case orchestrators in the application layer. These legacy files are preserved so the original logic remains available for historical comparison and audit.

Archived on: 2026-09-02
