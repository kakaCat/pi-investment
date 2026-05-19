# Quant Web Professional Dashboard Design

Date: 2026-05-19

## Goal

Refactor `quant-web` from a feature-list frontend into a professional quant management workspace.

The product should answer five operational questions:

1. Is the data reliable?
2. Is the strategy effective?
3. Are the signals trustworthy?
4. Is risk visible and controllable?
5. Are background quant jobs running normally?

The first implementation phase should prioritize a high-quality dashboard and navigation model while preserving the existing detail pages.

## Users

Primary users are quant operators and research users who need to inspect signals, model quality, data freshness, and batch jobs during daily research operations.

The UI should optimize for repeated use, scanning, comparison, and quick action. It should not behave like a marketing site or documentation page.

## Product Principles

- Show actionable metrics instead of long system descriptions.
- Every metric should indicate good, bad, or needs attention.
- Every abnormal state should offer the next operation where possible.
- Keep observation and execution in one workflow.
- Use a compact professional operations layout, not a decorative large-screen dashboard.
- Preserve existing pages as drill-down views before broader refactoring.

## Information Architecture

Recommended sidebar groups:

- Overview
  - Quant Dashboard
- Research
  - Signal Center
  - Strategy Backtest
  - Stock Analysis
  - Stock Comparison
- Model
  - Model Training
  - Factor Analysis
  - Training History
- Data
  - Stock Data
  - Data Quality
- Operations
  - Task Center
  - Platform Status

The default route should be the Quant Dashboard. Existing pages remain available, but their labels and grouping should reflect this workflow rather than a flat list of tools.

## Dashboard First Screen

The dashboard should combine system state, quant metrics, and task controls.

Header:

- Product title: Quant Management Console / 量化管理台
- Current data date when available
- Last refreshed timestamp
- Platform health tag
- Global refresh button

Primary metric row:

- Platform health
- High-confidence signal count
- Buy / sell signal ratio
- Average backtest return
- Average Sharpe ratio
- Latest model AUC or accuracy
- Data completeness rate

Main content row:

- Signal Radar
  - Buy and sell counts
  - High-confidence signal list
  - Latest signals
  - Links into the Signal Center
- Strategy Performance
  - Top backtest rows
  - Return, Sharpe, drawdown, and win rate
  - Links into Strategy Backtest
- Task Control
  - Common task buttons
  - Running job count
  - Failed job count
  - Retry and cancel affordances where valid

Supporting row:

- Data Quality
  - Total stocks
  - Complete stocks
  - Incomplete stocks
  - Latest data date
- Model Summary
  - Latest model type
  - AUC / accuracy
  - Feature count
  - Sample count
  - Training duration when available
- Recent Job Logs
  - Recent jobs
  - Status
  - Latest error message

## Core Modules

### 1. Quant Dashboard

Purpose: answer whether the system is usable today and what needs attention.

Functions:

- Aggregate platform, signal, backtest, model, data, and job status.
- Surface partial failures without blocking the whole dashboard.
- Provide quick actions for data update, factor computation, signal generation, backtest, model training, daily report, and risk check.
- Show empty states that explain the next useful operation.

### 2. Signal Center

Purpose: answer which stocks are worth attention and why.

Functions:

- List signal records with symbol, name, direction, price, confidence, strategy, reason, and date.
- Filter by direction, confidence, strategy, date, and symbol.
- Separate signals into high confidence, new, repeated, and low-confidence groups when the data supports it.
- Show signal detail with trigger reason, key factors, related strategy, related backtest metrics, and current price.
- Support single-stock signal generation and batch market scanning when API support is available.

### 3. Strategy And Backtest

Purpose: answer whether a strategy is reliable enough to use for research.

Functions:

- Rank strategies or backtest rows by return, Sharpe, drawdown, win rate, and trade count.
- Show backtest result table with symbol, strategy, return, Sharpe, max drawdown, win rate, and date.
- Provide a strategy detail page for equity curve, drawdown curve, monthly returns, buy/sell points, parameters, and applicable universe when data exists.
- Support strategy comparison.
- Provide run-backtest entry points and result export when available.

### 4. Model And Factor

Purpose: answer whether model quality is acceptable and what explains predictions.

Functions:

- Model training form with days, model type, cross-validation splits, and feature engineering switch.
- Latest model card with AUC, accuracy, sample count, feature count, and duration.
- Training history with metric comparison across runs.
- Factor importance list with top factors, contribution, and factor category where available.
- Stock-level factor explanation with positive and negative contributions.
- Model risk warnings for sample shortage, AUC decline, stale data, and abnormal feature count.

### 5. Operations Task Center

Purpose: answer what the backend is doing and what failed.

Functions:

- Show background jobs with type, status, start time, finish time, duration, attempts, and error.
- Run, cancel, and retry jobs using existing ops endpoints.
- Provide task templates:
  - Data update
  - Factor compute
  - Signal generate
  - Risk check
  - Model train
  - Backtest run
  - Daily report
- Show task details with params, logs, artifact path, and error reason.
- Show platform checks for database, signal file, model artifact, and daily report artifact.

## Existing Data Sources

Initial dashboard implementation can use existing APIs:

- `GET /api/health`
- `GET /api/platform/status`
- `GET /api/jobs`
- `POST /api/jobs/:type/run`
- `POST /api/jobs/:id/retry`
- `POST /api/jobs/:id/cancel`
- `GET /api/signals?days=30`
- `GET /api/backtest/results`
- `GET /api/training/history`
- `GET /api/stocks/data-status`
- `GET /api/feature-importance`

No new backend endpoint is required for the first phase. If performance becomes an issue, a later phase can add a dashboard aggregation endpoint.

## Frontend Structure

Recommended new frontend modules:

- `DashboardOverview`
- `MetricCard`
- `SignalSummaryPanel`
- `BacktestSummaryPanel`
- `ModelSummaryPanel`
- `DataQualityPanel`
- `TaskActionPanel`
- `JobQueuePanel`
- `PlatformStatusPanel`
- `dashboardMetrics.ts`

The `dashboardMetrics.ts` module should contain pure calculation helpers for:

- Buy/sell counts and ratios
- High-confidence signal count
- Average backtest return, Sharpe, and win rate
- Worst or average drawdown
- Running and failed job counts
- Data completeness rate
- Latest model selection

Keeping these calculations outside React components makes the dashboard easier to test and prevents a large monolithic page component.

## State And Refresh Behavior

- Fetch dashboard data in parallel on initial load.
- Use module-level loading and error states.
- Allow partial data rendering if one API fails.
- Refresh all data from a global refresh button.
- Refresh only jobs every 3 seconds while queued or running jobs exist.
- Preserve existing `VITE_OPS_API_TOKEN` behavior for protected job actions.

## Error And Empty States

Partial failures:

- The dashboard remains visible.
- Failed panels show their own error message.
- The header shows a compact "partial data unavailable" state when one or more requests fail.

Empty states:

- No signals: show zero counts and "No signals in the last 30 days."
- No backtests: show metric placeholders and a run-backtest action.
- No training history: show "Model not trained" and a training action.
- Missing database: mark data quality unavailable and surface the platform issue.
- No jobs: show "No background jobs."

## Visual Direction

- Light gray workspace background.
- No large content card wrapping the entire app.
- Compact cards with radius 8px or less.
- Dense tables with key columns visible by default.
- Color communicates status, direction, and risk only.
- Avoid decorative gradients, large emoji headings, and documentation-style copy.
- Buttons should use direct action labels: refresh, run, retry, cancel.
- Use Ant Design components consistently before introducing custom UI primitives.

## Testing Strategy

Follow test-first implementation for behavior changes where practical.

Priority tests:

- Signal metric calculations.
- Backtest metric calculations.
- Job status calculations.
- Data completeness calculation.
- Latest model selection and empty history handling.

If `quant-web` does not already have a test runner, the first implementation should either:

1. Add a minimal Vitest setup for pure calculation helpers, or
2. Keep calculations in standalone TypeScript functions and verify with `npm run build` as the minimum first-phase gate.

The preferred path is to add Vitest for `dashboardMetrics.ts`, because the aggregation logic is the highest-risk part of the new dashboard.

## Phase 1 Scope

Implement:

- New professional dashboard as default page.
- Grouped sidebar navigation.
- Shared dashboard metric helpers.
- Dashboard panels for signals, backtests, model, data, tasks, and platform health.
- Focused tests for metric helpers.
- Build verification.

Do not implement in phase 1:

- New backend aggregation endpoint.
- Full strategy detail charts unless data already exists in a stable API.
- Full visual redesign of every existing detail page.
- Authentication redesign.
- Portfolio/risk exposure workflows that do not yet have reliable data sources.

## Acceptance Criteria

- The first screen clearly shows platform health, signal status, model status, data quality, backtest performance, and job state.
- Common quant jobs can be launched from the dashboard.
- Running jobs refresh automatically.
- Existing pages remain reachable.
- Dashboard works when some APIs return empty data.
- Dashboard works when one panel API fails.
- Frontend build passes.
- Metric helper tests pass if a test runner is added.
