// ========== 枚举类型 ==========

// 信号类型
export enum SignalType {
  BUY = 'buy',
  SELL = 'sell'
}

// 信号状态
export enum SignalStatus {
  PENDING = 'pending',
  APPROVED = 'approved',
  REJECTED = 'rejected',
  EXECUTED = 'executed'
}

// 操作者类型
export enum OperatorType {
  AGENT = 'agent',
  MANUAL = 'manual'
}

// 订单状态
export enum OrderStatus {
  PENDING = 'pending',
  FILLED = 'filled',
  CANCELLED = 'cancelled',
  REJECTED = 'rejected'
}

// 订单类型
export enum OrderType {
  BUY = 'buy',
  SELL = 'sell'
}

// Agent日志状态
export enum AgentLogStatus {
  SUCCESS = 'success',
  FAILED = 'failed',
  PENDING = 'pending'
}

// 时间周期
export enum TimeFrame {
  MIN_1 = '1min',
  MIN_5 = '5min',
  MIN_15 = '15min',
  MIN_30 = '30min',
  HOUR_1 = '1hour',
  DAY = 'day',
  WEEK = 'week',
  MONTH = 'month'
}

// 市场类型
export enum MarketType {
  CN_A = 'cn_a',      // A股
  CN_HK = 'cn_hk',    // 港股
  US = 'us',          // 美股
  CRYPTO = 'crypto'   // 加密货币
}

// 策略状态
export enum StrategyStatus {
  RUNNING = 'running',
  PAUSED = 'paused',
  STOPPED = 'stopped',
  ERROR = 'error'
}

// 风险等级
export enum RiskLevel {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
  CRITICAL = 'critical'
}
