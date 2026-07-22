import { apiClient } from './client'

// ---- 类型（对齐 v2 多账户域契约，snake_case 直传） ----
export interface AccountSummary {
  account_name: string
  display_name: string | null
  strategy_name: string | null
  status: string
  cash_available: number
  cash_frozen: number
  position_value: number
  total_value: number
  cumulative_return: number
  positions_count: number
}

export interface PositionItem {
  symbol: string
  name?: string
  shares_total: number
  shares_available: number
  avg_cost: number | null
  current_price: number | null
  market_value: number | null
  profit_total: number | null
  profit_total_rate: number | null
  profit_today: number | null
}

export interface AccountStatus {
  account_name: string
  display_name: string | null
  strategy_name: string | null
  cash_available: number
  cash_frozen: number
  position_value: number
  total_value: number
  initial_capital: number
  cumulative_return: number
  last_rebalance_date: string | null
  positions_count: number
  positions: PositionItem[]
}

export interface TradeItem {
  symbol: string
  name: string | null
  action: 'BUY' | 'SELL'
  shares: number
  price: number | null
  amount: number | null
  timestamp: string | null
  commission: number
  stamp_duty: number
  realized_pnl: number | null
  realized_pnl_rate: number | null
  reason: string | null
}

export interface EquityPoint {
  date: string
  total_value: number
  cash: number
  market_value: number
  return: number
}

export interface PerformanceData {
  equity_curve: EquityPoint[]
  initial_capital: number
  current_value: number
  cumulative_return: number
  max_drawdown: number
}

export interface CreateAccountRequest {
  account_name: string
  display_name?: string
  initial_capital: number
  strategy_name?: string
}

export interface TradeRequest {
  action: 'buy' | 'sell'
  symbol: string
  shares?: number
  amount?: number
  price_limit?: number
  reason: string
}

interface Envelope<T> { success: boolean; data: T; error?: string }

export const simulationApi = {
  listAccounts(status = 'active') {
    return apiClient.get<any, Envelope<{ accounts: AccountSummary[]; total: number }>>(
      '/api/simulation/accounts', { params: { status } })
  },

  createAccount(req: CreateAccountRequest) {
    return apiClient.post<any, Envelope<{ account_name: string }>>(
      '/api/simulation/accounts', { ...req, strategy_name: req.strategy_name })
  },

  getAccount(accountName: string) {
    return apiClient.get<any, Envelope<AccountStatus>>(`/api/simulation/accounts/${accountName}`)
  },

  trade(accountName: string, req: TradeRequest) {
    return apiClient.post<any, Envelope<any>>(`/api/simulation/accounts/${accountName}/trade`, req)
  },

  getTrades(accountName: string, limit = 50) {
    return apiClient.get<any, Envelope<TradeItem[]>>(
      '/api/simulation/trades', { params: { account_name: accountName, limit } })
  },

  getPerformance(accountName: string) {
    return apiClient.get<any, Envelope<PerformanceData>>(
      '/api/simulation/performance', { params: { account_name: accountName } })
  },

  getExecutionHistory(accountName: string, limit = 50) {
    return apiClient.get<any, Envelope<any[]>>(
      '/api/simulation/execution-history', { params: { account_name: accountName, limit } })
  },

  runStrategy(strategyId: string, accountName: string) {
    return apiClient.post<any, Envelope<any>>(
      '/api/simulation/run', { strategy_id: strategyId, account_name: accountName })
  },

  getStrategyInfo(strategyId: string) {
    return apiClient.get<any, Envelope<any>>(`/api/simulation/strategies/${strategyId}`)
  }
}
