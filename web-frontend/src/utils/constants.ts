// ========== API常量 ==========

// 直连 quantsys-v2 Flask 后端 (127.0.0.1:5001)
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:5001'
export const WS_URL = import.meta.env.VITE_WS_URL || 'ws://127.0.0.1:5001'

// API超时时间（毫秒）
export const API_TIMEOUT = 30000

// ========== 分页常量 ==========

export const DEFAULT_PAGE_SIZE = 20
export const PAGE_SIZE_OPTIONS = [10, 20, 50, 100]

// ========== 日期格式 ==========

export const DATE_FORMAT = 'YYYY-MM-DD'
export const DATETIME_FORMAT = 'YYYY-MM-DD HH:mm:ss'
export const TIME_FORMAT = 'HH:mm:ss'

// ========== 颜色常量 ==========

export const COLORS = {
  // 涨跌颜色
  UP: '#26a69a',      // 绿色（涨）
  DOWN: '#ef5350',    // 红色（跌）

  // 信号类型颜色
  BUY: '#67C23A',     // 买入
  SELL: '#F56C6C',    // 卖出
  HOLD: '#909399',    // 观望

  // 状态颜色
  SUCCESS: '#67C23A',
  WARNING: '#E6A23C',
  DANGER: '#F56C6C',
  INFO: '#909399',
  PRIMARY: '#409EFF',

  // 风险等级颜色
  RISK_LOW: '#67C23A',
  RISK_MEDIUM: '#E6A23C',
  RISK_HIGH: '#F56C6C',
  RISK_CRITICAL: '#C71585',

  // 图表颜色
  CHART_COLORS: [
    '#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de',
    '#3ba272', '#fc8452', '#9a60b4', '#ea7ccc'
  ]
}

// ========== 市场常量 ==========

export const MARKETS = {
  CN_A: { label: 'A股', value: 'cn_a' },
  CN_HK: { label: '港股', value: 'cn_hk' },
  US: { label: '美股', value: 'us' },
  CRYPTO: { label: '加密货币', value: 'crypto' }
}

// ========== 时间周期 ==========

export const TIME_FRAMES = [
  { label: '1分钟', value: '1min' },
  { label: '5分钟', value: '5min' },
  { label: '15分钟', value: '15min' },
  { label: '30分钟', value: '30min' },
  { label: '1小时', value: '1hour' },
  { label: '日线', value: 'day' },
  { label: '周线', value: 'week' },
  { label: '月线', value: 'month' }
]

// ========== 技术指标 ==========

export const INDICATORS = {
  MA: { label: '移动平均线', value: 'ma' },
  EMA: { label: '指数移动平均', value: 'ema' },
  MACD: { label: 'MACD', value: 'macd' },
  RSI: { label: 'RSI', value: 'rsi' },
  KDJ: { label: 'KDJ', value: 'kdj' },
  BOLL: { label: '布林带', value: 'boll' },
  VOL: { label: '成交量', value: 'vol' },
  OBV: { label: 'OBV', value: 'obv' }
}

// ========== 策略类型 ==========

export const STRATEGY_TYPES = [
  { label: '趋势跟踪', value: 'trend' },
  { label: '均值回归', value: 'mean_reversion' },
  { label: '动量策略', value: 'momentum' },
  { label: '套利策略', value: 'arbitrage' }
]

// ========== 信号状态 ==========

export const SIGNAL_STATUS = {
  PENDING: { label: '待审批', color: 'warning', value: 'pending' },
  APPROVED: { label: '已批准', color: 'success', value: 'approved' },
  REJECTED: { label: '已拒绝', color: 'danger', value: 'rejected' },
  EXECUTED: { label: '已执行', color: 'info', value: 'executed' }
}

// ========== 订单状态 ==========

export const ORDER_STATUS = {
  PENDING: { label: '待成交', color: 'warning', value: 'pending' },
  FILLED: { label: '已成交', color: 'success', value: 'filled' },
  CANCELLED: { label: '已取消', color: 'info', value: 'cancelled' },
  REJECTED: { label: '已拒绝', color: 'danger', value: 'rejected' }
}

// ========== 风险等级 ==========

export const RISK_LEVELS = {
  LOW: { label: '低风险', color: 'success', value: 'low' },
  MEDIUM: { label: '中风险', color: 'warning', value: 'medium' },
  HIGH: { label: '高风险', color: 'danger', value: 'high' },
  CRITICAL: { label: '极高风险', color: 'danger', value: 'critical' }
}

// ========== 本地存储键 ==========

export const STORAGE_KEYS = {
  TOKEN: 'auth_token',
  USER: 'user_info',
  SETTINGS: 'user_settings',
  THEME: 'theme',
  LANGUAGE: 'language',
  FAVORITES: 'favorite_stocks',
  RECENT_SEARCHES: 'recent_searches'
}

// ========== WebSocket事件 ==========

export const WS_EVENTS = {
  CONNECT: 'connect',
  DISCONNECT: 'disconnect',
  ERROR: 'error',
  QUOTE: 'quote',
  SIGNAL: 'signal',
  ORDER: 'order',
  AGENT_LOG: 'agent:log',
  NOTIFICATION: 'notification'
}

// ========== 正则表达式 ==========

export const REGEX = {
  EMAIL: /^[^\s@]+@[^\s@]+\.[^\s@]+$/,
  PHONE: /^1[3-9]\d{9}$/,
  STOCK_CODE: /^[0-9]{6}$/,
  PASSWORD: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)[a-zA-Z\d]{8,}$/
}

// ========== 数字格式化 ==========

export const NUMBER_FORMAT = {
  DECIMAL_PLACES: {
    PRICE: 2,
    PERCENT: 2,
    QUANTITY: 0,
    AMOUNT: 2
  }
}
