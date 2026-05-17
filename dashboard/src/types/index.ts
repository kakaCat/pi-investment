// 策略相关类型
export interface QuantStrategy {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  screening: {
    filters: Record<string, any>;
  };
  entry: {
    conditions: Array<{
      indicator: string;
      operator: string;
      value: number;
    }>;
    logic: 'AND' | 'OR';
  };
  exit: {
    conditions: Array<{
      indicator: string;
      operator: string;
      value: number;
    }>;
  };
  position: {
    max_position_pct: number;
    max_stocks: number;
  };
  created_at: string;
}

// 信号相关类型
export interface Signal {
  symbol: string;
  name: string;
  signal: 'buy' | 'sell' | 'hold';
  confidence: number;
  strategy_id: string;
  strategy_name: string;
  reasons: string[];
  price: number;
  timestamp: string;
}

// 回测结果类型
export interface BacktestResult {
  total_return: number;
  annual_return: number;
  max_drawdown: number;
  win_rate: number;
  sharpe_ratio: number;
  profit_loss_ratio: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  daily_equity?: Array<{ date: string; equity: number }>;
}

// 性能指标类型
export interface PerformanceMetrics {
  strategy_id: string;
  strategy_name: string;
  total_signals: number;
  win_rate: number;
  avg_profit_pct: number;
  max_profit_pct: number;
  max_loss_pct: number;
  sharpe_ratio: number | null;
  max_drawdown_pct: number;
}

// 图表数据类型
export interface ChartData {
  chart_path: string;
  stats?: Record<string, any>;
}
