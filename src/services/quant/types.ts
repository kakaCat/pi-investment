// 量化策略类型定义

export interface QuantStrategy {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  created_at: string;

  screening: {
    market?: 'A' | 'HK';
    sector?: string;
    filters: {
      pe_range?: [number, number];
      pb_range?: [number, number];
      market_cap_range?: [number, number];
      volume_min?: number;
    };
  };

  entry: {
    conditions: EntryCondition[];
    logic: 'AND' | 'OR';
  };

  exit: {
    stop_loss?: number;
    take_profit?: number;
    trailing_stop?: number;
    conditions?: ExitCondition[];
  };

  position: {
    max_position_pct: number;
    max_stocks: number;
    rebalance_freq?: 'daily' | 'weekly' | 'monthly';
  };
}

export interface EntryCondition {
  indicator: 'rsi' | 'ma_cross' | 'macd' | 'bollinger' | 'volume';
  params: Record<string, any>;
  operator: '>' | '<' | '>=' | '<=' | '==' | 'cross_above' | 'cross_below';
  value: number | string;
}

export interface ExitCondition extends EntryCondition {}

export interface BacktestOptions {
  strategy_id: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  commission: number;
}

export interface BacktestResult {
  id: string;
  strategy_id: string;
  period: { start: string; end: string };
  performance: {
    total_return: number;
    annual_return: number;
    sharpe_ratio: number;
    max_drawdown: number;
    win_rate: number;
    profit_factor: number;
    total_trades: number;
  };
  trades: Trade[];
  equity_curve: Array<{ date: string; value: number }>;
  created_at: string;
}

export interface Trade {
  date: string;
  symbol: string;
  name: string;
  action: 'buy' | 'sell';
  price: number;
  quantity: number;
  commission: number;
  pnl?: number;
  pnl_pct?: number;
  reason: string;
}

export interface Signal {
  date: string;
  symbol: string;
  name: string;
  action: 'buy' | 'sell';
  strategy_id: string;
  price: number;
  reason: string;
  confidence: number;
  indicators?: Record<string, any>;
}

export interface Position {
  symbol: string;
  name: string;
  quantity: number;
  cost: number;
  entry_date: string;
  current_price?: number;
  pnl?: number;
  pnl_pct?: number;
}
