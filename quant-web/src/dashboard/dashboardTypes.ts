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

export type PlatformCheckStatus = 'healthy' | 'degraded' | 'unavailable';

export interface PlatformStatusCheck {
  name: string;
  status: PlatformCheckStatus;
  message: string;
  details?: Record<string, unknown>;
}

export interface PlatformStatus {
  overall_status: PlatformCheckStatus;
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
