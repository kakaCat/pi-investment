// ========== 组件Props类型 ==========

// 表格列配置
export interface TableColumn {
  prop: string
  label: string
  width?: string | number
  minWidth?: string | number
  align?: 'left' | 'center' | 'right'
  sortable?: boolean
  formatter?: (row: any, column: any, cellValue: any) => string
  fixed?: 'left' | 'right'
}

// 图表配置
export interface ChartConfig {
  title?: string
  height?: string
  showLegend?: boolean
  showTooltip?: boolean
  showGrid?: boolean
  theme?: 'light' | 'dark'
}

// 筛选器配置
export interface FilterConfig {
  type: 'input' | 'select' | 'date' | 'daterange' | 'number'
  label: string
  prop: string
  placeholder?: string
  options?: Array<{ label: string; value: any }>
  defaultValue?: any
}

// 模态框配置
export interface ModalConfig {
  title: string
  width?: string
  showClose?: boolean
  closeOnClickModal?: boolean
  closeOnPressEscape?: boolean
}

// ========== 表单类型 ==========

// 表单规则
export interface FormRule {
  required?: boolean
  message?: string
  trigger?: 'blur' | 'change'
  min?: number
  max?: number
  pattern?: RegExp
  validator?: (rule: any, value: any, callback: any) => void
}

export type FormRules = Record<string, FormRule[]>

// ========== 路由Meta类型 ==========

export interface RouteMeta {
  title: string
  icon?: string
  requiresAuth?: boolean
  roles?: string[]
  keepAlive?: boolean
  hidden?: boolean
}

// ========== WebSocket消息类型 ==========

export interface WebSocketMessage {
  type: string
  data: any
  timestamp: string
}

export interface WebSocketConfig {
  url: string
  reconnect?: boolean
  reconnectDelay?: number
  reconnectAttempts?: number
  heartbeat?: boolean
  heartbeatInterval?: number
}

// ========== 通知类型 ==========

export interface Notification {
  id: string
  type: 'info' | 'success' | 'warning' | 'error'
  title: string
  message: string
  duration?: number
  timestamp: string
  read?: boolean
}

// ========== 用户类型 ==========

export interface User {
  id: string
  username: string
  email: string
  avatar?: string
  role: 'admin' | 'trader' | 'viewer'
  createdAt: string
  lastLoginAt?: string
}

export interface UserSettings {
  theme: 'light' | 'dark'
  language: 'zh-CN' | 'en-US'
  notifications: {
    signal: boolean
    order: boolean
    risk: boolean
    agent: boolean
  }
  trading: {
    defaultQuantity: number
    confirmBeforeOrder: boolean
    autoApproveSignals: boolean
  }
}

// ========== 仪表盘类型 ==========

export interface DashboardStats {
  totalValue: number
  totalPnL: number
  totalPnLPercent: number
  todayPnL: number
  todayPnLPercent: number
  positionCount: number
  pendingSignals: number
  runningStrategies: number
}

export interface DashboardChart {
  equityCurve: Array<{ date: string; value: number }>
  allocation: Array<{ name: string; value: number }>
  performance: Array<{ date: string; return: number }>
}

// ========== 策略类型 ==========

export interface Strategy {
  id: string
  name: string
  description: string
  type: 'trend' | 'mean_reversion' | 'momentum' | 'arbitrage'
  status: 'running' | 'paused' | 'stopped' | 'error'
  parameters: Record<string, any>
  performance: {
    totalReturn: number
    sharpeRatio: number
    maxDrawdown: number
    winRate: number
  }
  positions: number
  createdAt: string
  updatedAt: string
}

// ========== 因子类型 ==========

export interface Factor {
  name: string
  value: number
  percentile: number
  score: number
  description: string
}

export interface FactorAnalysis {
  symbol: string
  symbolName: string
  factors: {
    technical: Factor[]
    fundamental: Factor[]
    sentiment: Factor[]
  }
  overallScore: number
  recommendation: 'strong_buy' | 'buy' | 'hold' | 'sell' | 'strong_sell'
}

// ========== 机会雷达类型 ==========

export interface Opportunity {
  id: string
  symbol: string
  symbolName: string
  score: number
  technicalScore: number
  fundamentalScore: number
  sentimentScore: number
  reasons: string[]
  riskLevel: 'low' | 'medium' | 'high'
  expectedReturn: number
  confidence: number
  createdAt: string
}

export interface OpportunityFilters {
  minScore?: number
  maxRiskLevel?: string
  industries?: string[]
  marketCap?: { min?: number; max?: number }
  technical?: Record<string, any>
  fundamental?: Record<string, any>
}

// ========== 指标IDE类型 ==========

export interface Indicator {
  id: string
  name: string
  description: string
  code: string
  codeContent?: string // Legacy field alias for code
  parameters: Array<{
    name: string
    type: 'number' | 'string' | 'boolean'
    defaultValue: any
    description: string
  }>
  category: 'trend' | 'momentum' | 'volatility' | 'volume' | 'custom'
  author: string
  isPublic: boolean
  createdAt: string
  updatedAt: string
}

export interface IndicatorBacktest {
  indicatorId: string
  symbol: string
  startDate: string
  endDate: string
  result: {
    winRate: number
    totalReturn: number
    sharpeRatio: number
    maxDrawdown: number
    trades: number
  }
}
