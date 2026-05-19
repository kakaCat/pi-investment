# Quant Web Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a professional quant management dashboard for `quant-web` that makes platform health, signals, backtests, model quality, data quality, and task operations visible from the first screen.

**Architecture:** Keep the existing Vite + React + Ant Design app. Add a focused dashboard module with pure metric helpers, panel components, and a grouped navigation shell while preserving existing detail pages as drill-down destinations.

**Tech Stack:** React 18, TypeScript, Vite, Ant Design 5, Recharts where useful, Vitest for pure dashboard metric tests.

---

## Scope

This plan implements phase 1 from `docs/superpowers/specs/2026-05-19-quant-web-dashboard-design.md`.

In scope:

- Add dashboard metric helpers and tests.
- Add a professional default dashboard page.
- Add grouped sidebar navigation.
- Add reusable dashboard panels for signals, backtests, model, data quality, platform health, task actions, and job queue.
- Keep existing pages reachable.
- Verify with tests and build.

Out of scope:

- New backend aggregation endpoint.
- Full redesign of every existing detail page.
- Portfolio exposure or risk workflows without stable APIs.
- Authentication redesign.

## File Structure

Create:

- `quant-web/src/dashboard/dashboardTypes.ts`
  - Shared TypeScript types for dashboard API payloads and normalized records.
- `quant-web/src/dashboard/dashboardMetrics.ts`
  - Pure metric calculations for signals, backtests, jobs, training, and data quality.
- `quant-web/src/dashboard/dashboardMetrics.test.ts`
  - Unit tests for metric helpers.
- `quant-web/src/components/dashboard/MetricCard.tsx`
  - Small reusable metric card for first-row dashboard KPIs.
- `quant-web/src/components/dashboard/DashboardOverview.tsx`
  - Default dashboard page, data fetching, refresh behavior, and layout composition.
- `quant-web/src/components/dashboard/SignalSummaryPanel.tsx`
  - Signal counts, latest/high-confidence signal table.
- `quant-web/src/components/dashboard/BacktestSummaryPanel.tsx`
  - Backtest summary metrics and top rows.
- `quant-web/src/components/dashboard/ModelSummaryPanel.tsx`
  - Latest training/model status.
- `quant-web/src/components/dashboard/DataQualityPanel.tsx`
  - Data completeness status.
- `quant-web/src/components/dashboard/TaskActionPanel.tsx`
  - Common quant task launch buttons.
- `quant-web/src/components/dashboard/JobQueuePanel.tsx`
  - Recent jobs, retry/cancel actions, logs preview.
- `quant-web/src/components/dashboard/PlatformStatusPanel.tsx`
  - Platform checks from `/api/platform/status`.

Modify:

- `quant-web/package.json`
  - Add `test` script and Vitest dev dependency.
- `quant-web/package-lock.json`
  - Update after installing Vitest.
- `quant-web/src/App.tsx`
  - Add grouped navigation, default dashboard key, updated layout shell, lazy import for dashboard.
- `quant-web/src/index.css`
  - Add workspace-level styles and dashboard utility classes.

## Task 1: Add Test Runner And Metric Helper Tests

**Files:**

- Modify: `quant-web/package.json`
- Modify: `quant-web/package-lock.json`
- Create: `quant-web/src/dashboard/dashboardTypes.ts`
- Create: `quant-web/src/dashboard/dashboardMetrics.ts`
- Create: `quant-web/src/dashboard/dashboardMetrics.test.ts`

- [ ] **Step 1: Install Vitest**

Run:

```bash
cd quant-web
npm install -D vitest
```

Expected:

- `quant-web/package.json` includes `vitest` in `devDependencies`.
- `quant-web/package-lock.json` updates.

- [ ] **Step 2: Add test script**

Edit `quant-web/package.json`:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "test": "vitest run"
  }
}
```

- [ ] **Step 3: Create dashboard types**

Create `quant-web/src/dashboard/dashboardTypes.ts` with exported interfaces:

```ts
export type SignalDirection = 'BUY' | 'SELL';

export interface DashboardSignal {
  symbol: string;
  name?: string;
  signal: SignalDirection;
  strategy?: string;
  reason?: string;
  confidence?: number;
  price?: number;
  date?: string;
  created_at?: string;
}

export interface BacktestSummary {
  symbol: string;
  date: string;
  best_strategy: string;
  best_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
}

export type JobStatus = 'queued' | 'running' | 'success' | 'failed' | 'cancelled';

export interface JobRecord {
  id: string;
  type: string;
  status: JobStatus;
  params: Record<string, unknown>;
  logs: string[];
  attempts: number;
  createdAt: string;
  updatedAt: string;
  startedAt?: string;
  finishedAt?: string;
  result?: unknown;
  error?: string;
}

export interface TrainingRecord {
  timestamp: string;
  start_time?: string;
  end_time?: string;
  duration_seconds?: number;
  model_type: string;
  n_features: number;
  total_samples: number;
  cv_accuracy: number;
  cv_auc: number;
  test_accuracy: number;
  test_auc: number;
  class_balance: number;
}

export interface StockDataStatus {
  total_stocks: number;
  complete_stocks: number;
  incomplete_stocks: number;
  stocks: Array<{
    symbol: string;
    name: string;
    market: string;
    latest_date: string;
    data_complete: boolean;
  }>;
}
```

- [ ] **Step 4: Write failing metric tests**

Create `quant-web/src/dashboard/dashboardMetrics.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import {
  calculateBacktestMetrics,
  calculateDataQualityMetrics,
  calculateJobMetrics,
  calculateSignalMetrics,
  getLatestTrainingRecord,
} from './dashboardMetrics';

describe('dashboardMetrics', () => {
  it('counts buy, sell, and high-confidence signals', () => {
    const metrics = calculateSignalMetrics([
      { symbol: '000001', signal: 'BUY', confidence: 0.91 },
      { symbol: '000002', signal: 'SELL', confidence: 0.72 },
      { symbol: '000003', signal: 'BUY', confidence: 0.5 },
    ]);

    expect(metrics.total).toBe(3);
    expect(metrics.buyCount).toBe(2);
    expect(metrics.sellCount).toBe(1);
    expect(metrics.highConfidenceCount).toBe(1);
    expect(metrics.buyRatio).toBeCloseTo(2 / 3);
  });

  it('calculates average backtest metrics and worst drawdown', () => {
    const metrics = calculateBacktestMetrics([
      { symbol: '000001', date: '2026-05-18', best_strategy: 's1', best_return: 0.12, sharpe_ratio: 1.4, max_drawdown: -0.08, win_rate: 0.6 },
      { symbol: '000002', date: '2026-05-18', best_strategy: 's2', best_return: -0.02, sharpe_ratio: 0.4, max_drawdown: -0.18, win_rate: 0.45 },
    ]);

    expect(metrics.count).toBe(2);
    expect(metrics.averageReturn).toBeCloseTo(0.05);
    expect(metrics.averageSharpe).toBeCloseTo(0.9);
    expect(metrics.averageWinRate).toBeCloseTo(0.525);
    expect(metrics.worstDrawdown).toBeCloseTo(-0.18);
  });

  it('counts running and failed jobs', () => {
    const metrics = calculateJobMetrics([
      { id: 'a', type: 'data_update', status: 'running', params: {}, logs: [], attempts: 1, createdAt: '', updatedAt: '2026-05-19T10:00:00Z' },
      { id: 'b', type: 'model_train', status: 'queued', params: {}, logs: [], attempts: 1, createdAt: '', updatedAt: '2026-05-19T10:01:00Z' },
      { id: 'c', type: 'backtest_run', status: 'failed', params: {}, logs: [], attempts: 2, createdAt: '', updatedAt: '2026-05-19T10:02:00Z' },
    ]);

    expect(metrics.total).toBe(3);
    expect(metrics.activeCount).toBe(2);
    expect(metrics.failedCount).toBe(1);
    expect(metrics.latestJob?.id).toBe('c');
  });

  it('calculates data completeness', () => {
    const metrics = calculateDataQualityMetrics({
      total_stocks: 10,
      complete_stocks: 7,
      incomplete_stocks: 3,
      stocks: [
        { symbol: '000001', name: 'A', market: 'CN', latest_date: '2026-05-18', data_complete: true },
        { symbol: '000002', name: 'B', market: 'CN', latest_date: '2026-05-17', data_complete: false },
      ],
    });

    expect(metrics.completenessRate).toBeCloseTo(0.7);
    expect(metrics.latestDataDate).toBe('2026-05-18');
  });

  it('selects the newest training record by timestamp', () => {
    const latest = getLatestTrainingRecord([
      { timestamp: '2026-05-18T10:00:00Z', model_type: 'xgboost', n_features: 49, total_samples: 100, cv_accuracy: 0.7, cv_auc: 0.72, test_accuracy: 0.68, test_auc: 0.7, class_balance: 0.5 },
      { timestamp: '2026-05-19T10:00:00Z', model_type: 'lightgbm', n_features: 52, total_samples: 120, cv_accuracy: 0.75, cv_auc: 0.78, test_accuracy: 0.71, test_auc: 0.74, class_balance: 0.5 },
    ]);

    expect(latest?.model_type).toBe('lightgbm');
  });
});
```

- [ ] **Step 5: Run tests to verify RED**

Run:

```bash
cd quant-web
npm test -- dashboardMetrics
```

Expected:

- FAIL because `dashboardMetrics.ts` exports are missing.

- [ ] **Step 6: Implement metric helpers**

Create `quant-web/src/dashboard/dashboardMetrics.ts` with minimal implementations:

```ts
import type {
  BacktestSummary,
  DashboardSignal,
  JobRecord,
  StockDataStatus,
  TrainingRecord,
} from './dashboardTypes';

export function calculateSignalMetrics(signals: DashboardSignal[]) {
  const total = signals.length;
  const buyCount = signals.filter((signal) => signal.signal === 'BUY').length;
  const sellCount = signals.filter((signal) => signal.signal === 'SELL').length;
  const highConfidenceCount = signals.filter((signal) => (signal.confidence ?? 0) >= 0.8).length;

  return {
    total,
    buyCount,
    sellCount,
    highConfidenceCount,
    buyRatio: total === 0 ? 0 : buyCount / total,
    sellRatio: total === 0 ? 0 : sellCount / total,
  };
}

export function calculateBacktestMetrics(summary: BacktestSummary[]) {
  const count = summary.length;
  if (count === 0) {
    return {
      count,
      averageReturn: undefined,
      averageSharpe: undefined,
      averageWinRate: undefined,
      worstDrawdown: undefined,
    };
  }

  return {
    count,
    averageReturn: average(summary.map((item) => item.best_return)),
    averageSharpe: average(summary.map((item) => item.sharpe_ratio)),
    averageWinRate: average(summary.map((item) => item.win_rate)),
    worstDrawdown: Math.min(...summary.map((item) => item.max_drawdown)),
  };
}

export function calculateJobMetrics(jobs: JobRecord[]) {
  const sortedJobs = [...jobs].sort((left, right) => Date.parse(right.updatedAt) - Date.parse(left.updatedAt));

  return {
    total: jobs.length,
    activeCount: jobs.filter((job) => job.status === 'queued' || job.status === 'running').length,
    failedCount: jobs.filter((job) => job.status === 'failed').length,
    latestJob: sortedJobs[0],
    recentJobs: sortedJobs.slice(0, 5),
  };
}

export function calculateDataQualityMetrics(status?: StockDataStatus) {
  if (!status || status.total_stocks === 0) {
    return {
      totalStocks: status?.total_stocks ?? 0,
      completeStocks: status?.complete_stocks ?? 0,
      incompleteStocks: status?.incomplete_stocks ?? 0,
      completenessRate: undefined,
      latestDataDate: undefined,
    };
  }

  const latestDataDate = status.stocks
    .map((stock) => stock.latest_date)
    .filter(Boolean)
    .sort()
    .at(-1);

  return {
    totalStocks: status.total_stocks,
    completeStocks: status.complete_stocks,
    incompleteStocks: status.incomplete_stocks,
    completenessRate: status.complete_stocks / status.total_stocks,
    latestDataDate,
  };
}

export function getLatestTrainingRecord(history: TrainingRecord[]) {
  return [...history].sort((left, right) => Date.parse(right.timestamp) - Date.parse(left.timestamp))[0];
}

function average(values: number[]) {
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}
```

- [ ] **Step 7: Run tests to verify GREEN**

Run:

```bash
cd quant-web
npm test -- dashboardMetrics
```

Expected:

- PASS.

- [ ] **Step 8: Commit task 1**

Run:

```bash
git add quant-web/package.json quant-web/package-lock.json quant-web/src/dashboard
git commit -m "test(web): add dashboard metric helpers"
```

Expected:

- Commit contains only test runner setup and dashboard helper files.

## Task 2: Add Dashboard UI Components

**Files:**

- Create: `quant-web/src/components/dashboard/MetricCard.tsx`
- Create: `quant-web/src/components/dashboard/SignalSummaryPanel.tsx`
- Create: `quant-web/src/components/dashboard/BacktestSummaryPanel.tsx`
- Create: `quant-web/src/components/dashboard/ModelSummaryPanel.tsx`
- Create: `quant-web/src/components/dashboard/DataQualityPanel.tsx`
- Create: `quant-web/src/components/dashboard/PlatformStatusPanel.tsx`
- Create: `quant-web/src/components/dashboard/TaskActionPanel.tsx`
- Create: `quant-web/src/components/dashboard/JobQueuePanel.tsx`

- [ ] **Step 1: Create `MetricCard`**

Implement a focused wrapper around Ant Design `Card` and `Statistic`.

Required props:

```ts
interface MetricCardProps {
  title: string;
  value: React.ReactNode;
  suffix?: React.ReactNode;
  prefix?: React.ReactNode;
  tone?: 'default' | 'success' | 'warning' | 'danger' | 'info';
  loading?: boolean;
  helper?: React.ReactNode;
}
```

Expected behavior:

- Uses compact padding.
- Applies text color by tone.
- Keeps height stable.

- [ ] **Step 2: Create signal summary panel**

`SignalSummaryPanel` props:

```ts
interface SignalSummaryPanelProps {
  signals: DashboardSignal[];
  loading?: boolean;
  error?: string;
  onOpenSignals: () => void;
}
```

Expected UI:

- Buy/sell counts.
- High-confidence count.
- Table of latest 5 signals.
- Empty state for no signals.
- Error alert if `error` exists.

- [ ] **Step 3: Create backtest summary panel**

`BacktestSummaryPanel` props:

```ts
interface BacktestSummaryPanelProps {
  summary: BacktestSummary[];
  loading?: boolean;
  error?: string;
  onOpenBacktest: () => void;
}
```

Expected UI:

- Top 5 rows sorted by Sharpe or return.
- Compact table columns: symbol, strategy, return, Sharpe, drawdown.
- Empty state with "run backtest" hint.

- [ ] **Step 4: Create model summary panel**

`ModelSummaryPanel` props:

```ts
interface ModelSummaryPanelProps {
  history: TrainingRecord[];
  loading?: boolean;
  error?: string;
  onOpenTraining: () => void;
}
```

Expected UI:

- Latest model type.
- CV AUC / test AUC.
- Feature and sample counts.
- Training duration if available.
- Empty state if no training record exists.

- [ ] **Step 5: Create data quality panel**

`DataQualityPanel` props:

```ts
interface DataQualityPanelProps {
  status?: StockDataStatus;
  loading?: boolean;
  error?: string;
  onOpenData: () => void;
}
```

Expected UI:

- Completion progress.
- Total, complete, incomplete counts.
- Latest data date.
- Empty/missing database state.

- [ ] **Step 6: Create platform status panel**

Define local platform status types in the component or `dashboardTypes.ts`.

Expected UI:

- Overall status tag.
- Check list for database, signals, model, daily report.
- Error and empty states.

- [ ] **Step 7: Create task action panel**

`TaskActionPanel` props:

```ts
interface TaskActionPanelProps {
  activeJobTypes: Set<string>;
  actionLoading?: string | null;
  onRunTask: (type: string, params: Record<string, unknown>) => void;
}
```

Expected UI:

- Buttons for data update, factor compute, signal generate, risk check, model train, backtest run, daily report.
- Disable task button when same type is queued/running.
- Use danger styling only for longer/heavier task if needed, such as backtest.

- [ ] **Step 8: Create job queue panel**

`JobQueuePanel` props:

```ts
interface JobQueuePanelProps {
  jobs: JobRecord[];
  loading?: boolean;
  error?: string;
  actionLoading?: string | null;
  onRetry: (job: JobRecord) => void;
  onCancel: (job: JobRecord) => void;
  onOpenJobs: () => void;
}
```

Expected UI:

- Recent 5 jobs table.
- Status tag.
- Retry enabled only for failed jobs.
- Cancel enabled only for queued/running jobs.
- Expandable logs preview if compact table supports it cleanly.

- [ ] **Step 9: Run TypeScript build**

Run:

```bash
cd quant-web
npm run build
```

Expected:

- Build passes.

- [ ] **Step 10: Commit task 2**

Run:

```bash
git add quant-web/src/components/dashboard
git commit -m "feat(web): add dashboard panels"
```

## Task 3: Implement Dashboard Overview

**Files:**

- Create: `quant-web/src/components/dashboard/DashboardOverview.tsx`
- Modify: `quant-web/src/dashboard/dashboardTypes.ts`

- [ ] **Step 1: Add missing API response types**

Extend `dashboardTypes.ts` for:

```ts
export interface PlatformStatusCheck {
  name: string;
  status: 'healthy' | 'degraded' | 'unavailable';
  message: string;
  details?: Record<string, unknown>;
}

export interface PlatformStatus {
  overall_status: 'healthy' | 'degraded' | 'unavailable';
  generated_at: string;
  checks: PlatformStatusCheck[];
}

export interface HealthStatus {
  status: string;
  timestamp: string;
  db_connected: boolean;
  model_loaded: boolean;
  db_info?: {
    path: string;
    size_mb: number;
    size_display: string;
  } | null;
}
```

- [ ] **Step 2: Implement API helpers inside dashboard overview**

Use small local functions:

```ts
async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}
```

Expected:

- Each API load is isolated and can fail independently.
- Store errors in a map keyed by panel name.

- [ ] **Step 3: Implement dashboard data state**

State should include:

- `health`
- `platformStatus`
- `jobs`
- `signals`
- `backtests`
- `trainingHistory`
- `dataStatus`
- `loading`
- `errors`
- `lastRefreshed`
- `actionLoading`

- [ ] **Step 4: Implement initial parallel fetch**

Use `Promise.allSettled` for:

- `/api/health`
- `/api/platform/status`
- `/api/jobs`
- `/api/signals?days=30`
- `/api/backtest/results`
- `/api/training/history`
- `/api/stocks/data-status`

Expected:

- Successful panels render.
- Failed panels show local errors.
- Header shows partial-data warning if any request failed.

- [ ] **Step 5: Implement job polling**

When any job status is `queued` or `running`, refresh `/api/jobs` every 3 seconds.

Expected:

- Polling stops when no active jobs remain.
- Polling does not reset all dashboard loading states.

- [ ] **Step 6: Implement job actions**

Support:

- `POST /api/jobs/:type/run`
- `POST /api/jobs/:id/retry`
- `POST /api/jobs/:id/cancel`

Use existing auth behavior:

```ts
const opsApiToken = import.meta.env.VITE_OPS_API_TOKEN as string | undefined;
```

Headers:

```ts
function buildOpsHeaders(baseHeaders: Record<string, string> = {}) {
  return opsApiToken ? { ...baseHeaders, Authorization: `Bearer ${opsApiToken}` } : baseHeaders;
}
```

- [ ] **Step 7: Compose dashboard layout**

Use:

- First row `MetricCard`s.
- Three-column main row for signals, backtests, tasks.
- Supporting row for platform, model, data, jobs.

Expected:

- No full-page white wrapper.
- Compact Ant Design cards.
- Empty states are visible and useful.

- [ ] **Step 8: Run tests and build**

Run:

```bash
cd quant-web
npm test -- dashboardMetrics
npm run build
```

Expected:

- Tests pass.
- Build passes.

- [ ] **Step 9: Commit task 3**

Run:

```bash
git add quant-web/src/components/dashboard/DashboardOverview.tsx quant-web/src/dashboard/dashboardTypes.ts
git commit -m "feat(web): add quant dashboard overview"
```

## Task 4: Refactor App Shell And Navigation

**Files:**

- Modify: `quant-web/src/App.tsx`
- Modify: `quant-web/src/index.css`

- [ ] **Step 1: Add dashboard lazy import and menu key**

In `App.tsx`:

- Add `dashboard` to `MenuKey`.
- Lazy import `DashboardOverview`.
- Default `selectedMenu` to `dashboard`.
- Render dashboard for `dashboard`.

- [ ] **Step 2: Replace flat menu with grouped menu**

Use Ant Design grouped menu items:

- Overview
  - Dashboard
- Research
  - Signals
  - Backtest
  - Feature Importance
  - Stock Analysis
  - Stock Comparison
- Model
  - Model Training
  - Training History
- Data
  - Stock List
- Operations
  - Ops Center
  - Welcome/System Info, if keeping Welcome reachable

Expected:

- Existing pages still render.
- Dashboard is first/default.

- [ ] **Step 3: Update app visual shell**

Expected shell:

- Header title: `量化管理台`.
- Header subtitle or secondary text: `Quant Management Console`.
- Sider width around 232.
- Content background is workspace gray.
- Content no longer wraps all pages in one large white card.

- [ ] **Step 4: Update global CSS**

Add classes or Ant Design overrides for:

- `.app-shell`
- `.app-header`
- `.app-content`
- `.dashboard-page`
- `.dashboard-panel`
- `.metric-card`

Keep styles compact and avoid broad one-color theme domination.

- [ ] **Step 5: Run build**

Run:

```bash
cd quant-web
npm run build
```

Expected:

- Build passes.

- [ ] **Step 6: Commit task 4**

Run:

```bash
git add quant-web/src/App.tsx quant-web/src/index.css
git commit -m "feat(web): add professional quant navigation"
```

## Task 5: Final Verification

**Files:**

- No planned source edits unless verification finds issues.

- [ ] **Step 1: Run full frontend tests**

Run:

```bash
cd quant-web
npm test
```

Expected:

- All Vitest tests pass.

- [ ] **Step 2: Run frontend build**

Run:

```bash
cd quant-web
npm run build
```

Expected:

- Vite build passes.

- [ ] **Step 3: Start dev server for manual check**

Run:

```bash
cd quant-web
npm run dev -- --host 127.0.0.1
```

Expected:

- Vite prints a local URL, usually `http://127.0.0.1:3000/`.

- [ ] **Step 4: Manually verify first screen**

Open the local URL and check:

- Dashboard is the default page.
- Header and grouped navigation render.
- Metric row renders even if APIs are empty or unavailable.
- Panels render local errors instead of blank page failure.
- Existing pages are reachable from sidebar.
- Task buttons render and disable active job types when data is present.

- [ ] **Step 5: Stop dev server**

Stop the Vite process with `Ctrl+C`.

- [ ] **Step 6: Check git status**

Run:

```bash
git status --short
```

Expected:

- Only intended files are modified.
- Pre-existing unrelated dirty files are not staged unless part of this feature.

- [ ] **Step 7: Final commit if verification fixes were needed**

If changes were made after prior commits:

```bash
git add <intended files>
git commit -m "fix(web): polish quant dashboard"
```

## Completion Criteria

- Dashboard metric tests pass.
- `npm run build` passes in `quant-web`.
- Dashboard is default route.
- Existing pages remain reachable.
- Partial API failures do not blank the dashboard.
- Common quant jobs can be triggered from dashboard UI.
- Running jobs poll every 3 seconds.
