/**
 * 指标相关的类型定义
 */

/**
 * K线数据
 */
export interface KlineData {
  /** 日期 */
  date: string
  /** 开盘价 */
  open: number
  /** 最高价 */
  high: number
  /** 最低价 */
  low: number
  /** 收盘价 */
  close: number
  /** 成交量 */
  volume: number
}

/**
 * 指标序列数据
 * 键为指标名称，值为指标值数组
 */
export interface IndicatorSeries {
  [indicatorName: string]: (number | null)[]
}

/**
 * 指标运行结果
 */
export interface IndicatorRunResult {
  /** 股票代码 */
  symbol: string
  /** 最新信号 */
  latestSignal: 'buy' | 'sell' | 'hold'
  /** 置信度 */
  confidence: number
  /** 当前价格 */
  price: number
  /** 日期 */
  date: string
  /** 指标因子值（最新值） */
  indicators: Record<string, number | null>
  /** K线数据（用于图表显示） */
  klineData?: KlineData[]
  /** 指标序列数据（用于在K线图上叠加） */
  indicatorSeries?: IndicatorSeries
  /** 买卖信号序列（用于在K线图上标记） */
  signalSeries?: {
    buy?: (boolean | number | null)[]
    sell?: (boolean | number | null)[]
  }
}

/**
 * 策略记事本
 */
export interface StrategyNotebook {
  /** 策略优点 */
  pros: string
  /** 策略缺点 */
  cons: string
  /** 观察记录 */
  observations: string
  /** 后续优化 */
  nextSteps: string
}

/**
 * 指标信息
 */
export interface IndicatorInfo {
  /** 指标ID */
  id: number
  /** 指标名称 */
  name: string
  /** 策略名称（后端字段） */
  strategyName?: string
  /** 描述 */
  description?: string
  /** 策略记事本 */
  notebook?: StrategyNotebook
  /** 代码类型 */
  codeType: 'indicator' | 'script'
  /** 策略类型 */
  strategyType: 'custom' | 'builtin' | 'system'
  /** 指标代码内容 */
  codeContent?: string
  /** 是否公开 */
  isPublic?: boolean
  /** 是否启用 */
  isActive?: boolean
  /** 分类 */
  category?: 'trend' | 'momentum' | 'volatility' | 'volume' | 'custom'
  /** 作者 */
  author?: string
  /** 创建时间 */
  createdAt?: string
  /** 更新时间 */
  updatedAt?: string
}

/**
 * 指标列表响应
 */
export interface IndicatorListResponse {
  /** 总数 */
  total: number
  /** 当前页 */
  page: number
  /** 每页大小 */
  pageSize: number
  /** 指标列表 */
  items: IndicatorInfo[]
}

/**
 * 指标运行参数
 */
export interface IndicatorRunParams {
  /** 股票代码 */
  symbol: string
  /** K线周期 */
  period?: 'daily' | '1min' | '5min' | '15min' | '30min' | '60min'
  /** K线数量 */
  limit?: number
  /** 图表显示的K线数量 */
  chartLimit?: number
}
