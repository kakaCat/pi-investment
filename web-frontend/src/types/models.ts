// ========== 基础类型 ==========

import type { SignalType, SignalStatus, OperatorType } from './enums'

// ========== 交易信号 ==========

export interface TradingSignal {
  id: string
  symbol: string
  symbolName: string
  type: SignalType
  price: number
  time?: string // Legacy field, use createdAt
  triggerPrice?: number // Alias for price
  triggerTime?: string // Alias for createdAt
  confidence: number
  reasons: string[]
  status: SignalStatus
  operator: OperatorType
  createdAt: string
  updatedAt: string
  executedAt?: string
  analysis?: SignalAnalysis
  execution?: SignalExecution
  pnl?: SignalPnL
}

export interface SignalAnalysis {
  technical: {
    rsi: number
    macd: { value: number; signal: number; histogram: number }
    ma: { ma5: number; ma20: number; ma60: number }
    bollinger: { upper: number; middle: number; lower: number }
  }
  fundamental: {
    pe: number
    roe: number
    grossMargin: number
    debtRatio: number
  }
  sentiment: {
    fundFlow: number
    dragonTiger: boolean
    institutionalHolding: number
  }
  risk: {
    positionLimit: number
    volatility: number
    industryConcentration: number
  }
}

export interface SignalExecution {
  orderId: string
  executedPrice: number
  executedQuantity: number
  executedAt: string
}

export interface SignalPnL {
  unrealizedPnL: number
  unrealizedPnLPercent: number
  realizedPnL?: number
  realizedPnLPercent?: number
}

export interface SignalFilters {
  type?: SignalType
  status?: SignalStatus
  operator?: OperatorType
  symbol?: string
  startDate?: string
  endDate?: string
  minConfidence?: number
}

export interface SignalStatistics {
  total: number
  pending: number
  approved: number
  rejected: number
  executed: number
  avgConfidence: number
  buyAccuracy: number
  sellAccuracy: number
  avgHoldingDays: number
  avgReturn: number
}

// ========== K线数据 ==========

export interface KLineData {
  date: string
  open: number
  close: number
  high: number
  low: number
  volume: number
  amount: number
}

// ========== 股票信息 ==========

export interface StockInfo {
  symbol: string
  code?: string // Alias for symbol
  name: string
  industry: string
  sector: string
  market?: string // Market identifier (e.g., 'SH', 'SZ')
  marketCap: number
  pe: number
  pb: number
  roe: number
  currentPrice: number
  price?: number // Alias for currentPrice
  change: number
  changePercent: number
  klineDays?: number // Number of K-line days available
  factorCount?: number // Number of factors calculated
  dataStatus?: string // Data completeness status: 'complete' | 'incomplete' | 'unknown'
}

// ========== 持仓信息 ==========

export interface Position {
  id: string
  symbol: string
  symbolName: string
  name: string
  quantity: number
  avgCost: number
  currentPrice: number
  marketValue: number
  totalCost: number
  unrealizedPnL: number
  unrealizedPnLPercent: number
  profit: number
  profitPercent: number
  weight: number
  buyDate: string
  addedDate: string
  market: string
  sector: string | null
  stopLoss?: number
  targetPrice?: number
  reason?: string
}

// ========== 止损规则 ==========

export interface StopLossRule {
  id: string
  symbol: string
  symbolName?: string
  type: 'price' | 'percent' | 'trailing'
  triggerPrice?: number
  triggerPercent?: number
  trailingPercent?: number
  status: 'active' | 'triggered' | 'cancelled'
  createdAt: string
  updatedAt: string
  triggeredAt?: string
}

export interface CreateStopLossRequest {
  symbol: string
  type: 'price' | 'percent' | 'trailing'
  triggerPrice?: number
  triggerPercent?: number
  trailingPercent?: number
}

export interface UpdateStopLossRequest {
  id: string
  triggerPrice?: number
  triggerPercent?: number
  trailingPercent?: number
}

// ========== 自选股 ==========

export interface WatchlistItem {
  id: string
  symbol: string
  symbolName: string
  groupId?: string
  groupName?: string
  addedAt: string
  note?: string
}

export interface WatchlistGroup {
  id: string
  name: string
  description?: string
  itemCount: number
  createdAt: string
}

// ========== 订单信息 ==========

export interface Order {
  id: string
  symbol: string
  symbolName: string
  type: 'buy' | 'sell' | 'BUY' | 'SELL'
  direction?: 'buy' | 'sell' // Alias for type
  price: number
  quantity: number
  status: 'pending' | 'filled' | 'cancelled' | 'rejected'
  createdAt: string
  filledAt?: string
  operator: OperatorType
}

// ========== 交易记录 ==========

export interface Trade {
  id: string
  symbol: string
  symbolName: string
  type: 'buy' | 'sell'
  price: number
  quantity: number
  amount: number
  commission: number
  createdAt: string
  operator: OperatorType
}

// ========== Agent日志 ==========

export interface AgentLog {
  id: string
  timestamp: string
  action: string
  description: string
  status: 'success' | 'failed' | 'pending'
  details?: any
  signalId?: string
}

// ========== 实时行情 ==========

export interface RealtimeQuote {
  symbol: string
  price: number
  change: number
  changePercent: number
  volume: number
  amount: number
  timestamp: string
}

// ========== 策略信息 ==========

export interface Strategy {
  id: string
  name: string
  type: string
  status: 'running' | 'stopped' | 'paused' | 'error'
  description?: string
  code?: string
  params?: Record<string, any>
  performance?: any
  positions?: number
  createdAt?: string
  updatedAt?: string
  lastExecuted?: string
}

// ========== API响应 ==========

export type { ApiResponse, PaginatedResponse } from './api'

// ===== Agent Session 可视化（2026-07-26）=====

export interface AgentSession {
  session_key: string
  channel: 'wake' | 'feishu' | 'cli' | string
  peer_id: string
  agent_id: string
  started_at: string
  last_active_at: string
  status: 'active' | 'idle' | string
  message_count: number
  tool_call_count: number
  error_count: number
}

export interface SessionEvent {
  seq: number
  event_type: 'session_start' | 'user_message' | 'tool_call' | 'assistant_reply' | 'error' | 'session_idle' | 'legacy_note' | string
  payload: Record<string, any>
  created_at: string
}

export interface SessionDiagnosis {
  session_key: string
  tool_success_rate: number | null
  tool_call_count: number
  avg_tool_duration_ms: number
  max_tool_duration_ms: number
  error_count: number
  top_errors: Array<{ message: string; cnt: number }>
  decisions: Array<{
    decision_id: string
    decision_type: string
    reasoning: string | null
    evaluation_status: string
    success: boolean | null
  }>
  insight: string
}

export interface AiDiagnosis {
  analysis: string
  generated_at: string
  cached: boolean
}
