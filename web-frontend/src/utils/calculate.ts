/**
 * 计算技术指标
 */

// ========== 移动平均线 (MA) ==========

/**
 * 计算简单移动平均线
 * @param data 价格数据
 * @param period 周期
 */
export function calculateMA(data: number[], period: number): number[] {
  const result: number[] = []

  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push(NaN)
    } else {
      const sum = data.slice(i - period + 1, i + 1).reduce((a, b) => a + b, 0)
      result.push(sum / period)
    }
  }

  return result
}

/**
 * 计算指数移动平均线
 * @param data 价格数据
 * @param period 周期
 */
export function calculateEMA(data: number[], period: number): number[] {
  const result: number[] = []
  const multiplier = 2 / (period + 1)

  // 第一个EMA值使用SMA
  let ema = data.slice(0, period).reduce((a, b) => a + b, 0) / period
  result.push(ema)

  for (let i = period; i < data.length; i++) {
    ema = (data[i] - ema) * multiplier + ema
    result.push(ema)
  }

  return result
}

// ========== RSI ==========

/**
 * 计算RSI
 * @param data 价格数据
 * @param period 周期（默认14）
 */
export function calculateRSI(data: number[], period = 14): number[] {
  const result: number[] = []
  const gains: number[] = []
  const losses: number[] = []

  // 计算涨跌
  for (let i = 1; i < data.length; i++) {
    const change = data[i] - data[i - 1]
    gains.push(change > 0 ? change : 0)
    losses.push(change < 0 ? -change : 0)
  }

  // 计算平均涨跌
  let avgGain = gains.slice(0, period).reduce((a, b) => a + b, 0) / period
  let avgLoss = losses.slice(0, period).reduce((a, b) => a + b, 0) / period

  result.push(NaN) // 第一个值无法计算

  for (let i = period; i < data.length; i++) {
    avgGain = (avgGain * (period - 1) + gains[i - 1]) / period
    avgLoss = (avgLoss * (period - 1) + losses[i - 1]) / period

    const rs = avgGain / avgLoss
    const rsi = 100 - 100 / (1 + rs)
    result.push(rsi)
  }

  return result
}

// ========== MACD ==========

/**
 * 计算MACD
 * @param data 价格数据
 * @param fastPeriod 快线周期（默认12）
 * @param slowPeriod 慢线周期（默认26）
 * @param signalPeriod 信号线周期（默认9）
 */
export function calculateMACD(
  data: number[],
  fastPeriod = 12,
  slowPeriod = 26,
  signalPeriod = 9
): { macd: number[]; signal: number[]; histogram: number[] } {
  const fastEMA = calculateEMA(data, fastPeriod)
  const slowEMA = calculateEMA(data, slowPeriod)

  // MACD线 = 快线 - 慢线
  const macd = fastEMA.map((fast, i) => fast - slowEMA[i])

  // 信号线 = MACD的EMA
  const signal = calculateEMA(macd, signalPeriod)

  // 柱状图 = MACD - 信号线
  const histogram = macd.map((m, i) => m - signal[i])

  return { macd, signal, histogram }
}

// ========== 布林带 (Bollinger Bands) ==========

/**
 * 计算布林带
 * @param data 价格数据
 * @param period 周期（默认20）
 * @param stdDev 标准差倍数（默认2）
 */
export function calculateBollingerBands(
  data: number[],
  period = 20,
  stdDev = 2
): { upper: number[]; middle: number[]; lower: number[] } {
  const middle = calculateMA(data, period)
  const upper: number[] = []
  const lower: number[] = []

  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      upper.push(NaN)
      lower.push(NaN)
    } else {
      const slice = data.slice(i - period + 1, i + 1)
      const mean = middle[i]
      const variance = slice.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / period
      const std = Math.sqrt(variance)

      upper.push(mean + stdDev * std)
      lower.push(mean - stdDev * std)
    }
  }

  return { upper, middle, lower }
}

// ========== KDJ ==========

/**
 * 计算KDJ
 * @param high 最高价数组
 * @param low 最低价数组
 * @param close 收盘价数组
 * @param period 周期（默认9）
 */
export function calculateKDJ(
  high: number[],
  low: number[],
  close: number[],
  period = 9
): { k: number[]; d: number[]; j: number[] } {
  const rsv: number[] = []
  const k: number[] = []
  const d: number[] = []
  const j: number[] = []

  // 计算RSV
  for (let i = 0; i < close.length; i++) {
    if (i < period - 1) {
      rsv.push(NaN)
    } else {
      const highestHigh = Math.max(...high.slice(i - period + 1, i + 1))
      const lowestLow = Math.min(...low.slice(i - period + 1, i + 1))
      const rsvValue = ((close[i] - lowestLow) / (highestHigh - lowestLow)) * 100
      rsv.push(rsvValue)
    }
  }

  // 计算K、D、J
  let prevK = 50
  let prevD = 50

  for (let i = 0; i < rsv.length; i++) {
    if (isNaN(rsv[i])) {
      k.push(NaN)
      d.push(NaN)
      j.push(NaN)
    } else {
      const kValue = (2 / 3) * prevK + (1 / 3) * rsv[i]
      const dValue = (2 / 3) * prevD + (1 / 3) * kValue
      const jValue = 3 * kValue - 2 * dValue

      k.push(kValue)
      d.push(dValue)
      j.push(jValue)

      prevK = kValue
      prevD = dValue
    }
  }

  return { k, d, j }
}

// ========== ATR (Average True Range) ==========

/**
 * 计算ATR
 * @param high 最高价数组
 * @param low 最低价数组
 * @param close 收盘价数组
 * @param period 周期（默认14）
 */
export function calculateATR(
  high: number[],
  low: number[],
  close: number[],
  period = 14
): number[] {
  const tr: number[] = []

  // 计算真实波幅
  for (let i = 0; i < close.length; i++) {
    if (i === 0) {
      tr.push(high[i] - low[i])
    } else {
      const trValue = Math.max(
        high[i] - low[i],
        Math.abs(high[i] - close[i - 1]),
        Math.abs(low[i] - close[i - 1])
      )
      tr.push(trValue)
    }
  }

  // 计算ATR（使用EMA）
  return calculateEMA(tr, period)
}

// ========== 收益率计算 ==========

/**
 * 计算简单收益率
 * @param startValue 起始值
 * @param endValue 结束值
 */
export function calculateReturn(startValue: number, endValue: number): number {
  return ((endValue - startValue) / startValue) * 100
}

/**
 * 计算年化收益率
 * @param totalReturn 总收益率
 * @param days 天数
 */
export function calculateAnnualizedReturn(totalReturn: number, days: number): number {
  return (totalReturn / days) * 365
}

/**
 * 计算夏普比率
 * @param returns 收益率数组
 * @param riskFreeRate 无风险利率（默认3%）
 */
export function calculateSharpeRatio(returns: number[], riskFreeRate = 3): number {
  const avgReturn = returns.reduce((a, b) => a + b, 0) / returns.length
  const variance = returns.reduce((sum, r) => sum + Math.pow(r - avgReturn, 2), 0) / returns.length
  const stdDev = Math.sqrt(variance)

  return (avgReturn - riskFreeRate) / stdDev
}

/**
 * 计算最大回撤
 * @param equityCurve 权益曲线
 */
export function calculateMaxDrawdown(equityCurve: number[]): number {
  let maxDrawdown = 0
  let peak = equityCurve[0]

  for (const value of equityCurve) {
    if (value > peak) {
      peak = value
    }
    const drawdown = ((peak - value) / peak) * 100
    if (drawdown > maxDrawdown) {
      maxDrawdown = drawdown
    }
  }

  return maxDrawdown
}

/**
 * 计算胜率
 * @param trades 交易数组（包含盈亏）
 */
export function calculateWinRate(trades: Array<{ pnl: number }>): number {
  const winningTrades = trades.filter(t => t.pnl > 0).length
  return (winningTrades / trades.length) * 100
}
