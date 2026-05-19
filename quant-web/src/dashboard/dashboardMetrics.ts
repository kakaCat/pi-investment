import type {
  BacktestSummary,
  DashboardSignal,
  JobRecord,
  StockDataStatus,
  TrainingRecord,
} from './dashboardTypes';

const average = (values: number[]): number | undefined => {
  if (values.length === 0) {
    return undefined;
  }

  return values.reduce((sum, value) => sum + value, 0) / values.length;
};

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
    buyRatio: total > 0 ? buyCount / total : undefined,
    sellRatio: total > 0 ? sellCount / total : undefined,
  };
}

export function calculateBacktestMetrics(summary: BacktestSummary[]) {
  return {
    count: summary.length,
    averageReturn: average(summary.map((item) => item.best_return)),
    averageSharpe: average(summary.map((item) => item.sharpe_ratio)),
    averageWinRate: average(summary.map((item) => item.win_rate)),
    worstDrawdown:
      summary.length > 0 ? Math.min(...summary.map((item) => item.max_drawdown)) : undefined,
  };
}

export function calculateJobMetrics(jobs: JobRecord[]) {
  const latestJob = [...jobs].sort(
    (first, second) => new Date(second.updatedAt).getTime() - new Date(first.updatedAt).getTime(),
  )[0];

  return {
    total: jobs.length,
    activeCount: jobs.filter((job) => job.status === 'queued' || job.status === 'running').length,
    failedCount: jobs.filter((job) => job.status === 'failed').length,
    latestJob,
  };
}

export function calculateDataQualityMetrics(status?: StockDataStatus) {
  const totalStocks = status?.total_stocks ?? 0;
  const latestDataDate = status?.stocks
    .map((stock) => stock.latest_date)
    .filter(Boolean)
    .sort((first, second) => new Date(second).getTime() - new Date(first).getTime())[0];

  return {
    totalStocks,
    completeStocks: status?.complete_stocks ?? 0,
    incompleteStocks: status?.incomplete_stocks ?? 0,
    completenessRate: totalStocks > 0 ? (status?.complete_stocks ?? 0) / totalStocks : undefined,
    latestDataDate: totalStocks > 0 ? latestDataDate : undefined,
  };
}

export function getLatestTrainingRecord(history: TrainingRecord[]) {
  return [...history].sort(
    (first, second) => new Date(second.timestamp).getTime() - new Date(first.timestamp).getTime(),
  )[0];
}
