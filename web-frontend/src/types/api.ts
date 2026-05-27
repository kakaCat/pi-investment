// ========== API 请求/响应类型 ==========

// 通用API响应
export interface ApiResponse<T = any> {
  code: number
  message: string
  data: T
  timestamp?: string
}

// 分页响应
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

// 分页请求参数
export interface PaginationParams {
  page?: number
  pageSize?: number
  sortBy?: string
  sortOrder?: 'asc' | 'desc'
}

// ========== 市场数据API ==========

export interface MarketDataRequest {
  symbol: string
  startDate?: string
  endDate?: string
  timeFrame?: string
  limit?: number
}

export interface MarketDataResponse {
  symbol: string
  data: any[]
  indicators?: Record<string, any>
}

// ========== 股票API ==========

export interface StockListRequest extends PaginationParams {
  market?: string
  industry?: string
  keyword?: string
}

export interface StockDetailRequest {
  symbol: string
  includeKLine?: boolean
  includeSignals?: boolean
  includeFundamentals?: boolean
}

// ========== 交易API ==========

export interface CreateOrderRequest {
  symbol: string
  type: 'buy' | 'sell'
  priceType?: string
  price?: number
  quantity: number
  stopLoss?: number
  takeProfit?: number
}

export interface OrderListRequest extends PaginationParams {
  symbol?: string
  type?: 'buy' | 'sell'
  status?: string
  startDate?: string
  endDate?: string
}

// ========== 信号API ==========

export interface SignalListRequest extends PaginationParams {
  type?: 'buy' | 'sell'
  status?: string
  operator?: 'agent' | 'manual'
  symbol?: string
  startDate?: string
  endDate?: string
  minConfidence?: number
}

export interface ApproveSignalRequest {
  signalId: string
  adjustedPrice?: number
  adjustedQuantity?: number
  note?: string
}

export interface RejectSignalRequest {
  signalId: string
  reason: string
}

// ========== 回测API ==========

export interface BacktestRequest {
  symbol: string
  strategy: string
  startDate: string
  endDate: string
  initialCapital: number
  commission?: number
  slippage?: number
  parameters: Record<string, any>
}

export interface BacktestResponse {
  id: string
  symbol: string
  strategy: string
  startDate: string
  endDate: string
  initialCapital: number
  finalCapital: number
  totalReturn: number
  totalReturnPercent: number
  sharpeRatio: number
  maxDrawdown: number
  winRate: number
  trades: any[]
  equityCurve: any[]
}

// ========== Agent API ==========

export interface AgentLogRequest extends PaginationParams {
  startDate?: string
  endDate?: string
  action?: string
  status?: string
}

export interface AgentPerformanceRequest {
  startDate: string
  endDate: string
  metrics?: string[]
}

export interface AgentPerformanceResponse {
  totalSignals: number
  approvedSignals: number
  executedSignals: number
  accuracy: number
  avgReturn: number
  sharpeRatio: number
  maxDrawdown: number
  winRate: number
  avgHoldingDays: number
}

// ========== 策略API ==========

export interface StrategyListRequest extends PaginationParams {
  status?: string
  type?: string
}

export interface CreateStrategyRequest {
  name: string
  description?: string
  type?: string
  code: string
  parameters?: Record<string, any>
  riskLevel?: string
}

export interface UpdateStrategyRequest {
  id: string
  name?: string
  description?: string
  parameters?: Record<string, any>
  status?: string
}

// ========== 持仓API ==========

export interface PortfolioSummaryResponse {
  totalValue: number
  totalCost: number
  totalMarketValue: number
  totalPnl: number
  totalPnlPct: number
  dailyChange: number
  positions: number
  cash: number
  liquidAssets: number
}

// ========== 风控API ==========

export interface RiskCheckRequest {
  accountValue?: number
  symbols?: string[]
}

export interface RiskCheckItem {
  type: 'concentration' | 'sector_concentration' | 'var'
  level: 'high' | 'medium' | 'low'
  message: string
  suggestion: string
}

export interface RiskCheckPosition {
  symbol: string
  position_value: number
  current_price: number
  var_95: number
  volatility: number
  max_drawdown: number
  checks: RiskCheckItem[]
}

export interface RiskCheckResponse {
  total_holdings: number
  checks: RiskCheckPosition[]
  risk_level: 'high' | 'medium' | 'low'
  riskLevel?: string  // camelCase alias for compatibility
  totalHoldings?: number  // camelCase alias for compatibility
}
