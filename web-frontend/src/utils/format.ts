import dayjs from 'dayjs'
import { DATE_FORMAT, DATETIME_FORMAT, TIME_FORMAT } from './constants'

// ========== 数字格式化 ==========

/**
 * 格式化价格
 * @param value 价格值
 * @param decimals 小数位数
 */
export function formatPrice(value: number | string, decimals = 2): string {
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(num)) return '--'
  return num.toFixed(decimals)
}

/**
 * 格式化带方向的人民币金额
 * @param value 金额值
 */
export function formatSignedCurrency(value: number | string): string {
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(num)) return '--'

  const sign = num > 0 ? '+' : num < 0 ? '-' : ''
  return `${sign}¥${Math.abs(num).toLocaleString('zh-CN')}`
}

/**
 * 格式化百分比
 * @param value 百分比值（0-100）
 * @param decimals 小数位数
 * @param showSign 是否显示正负号
 */
export function formatPercent(value: number | string, decimals = 2, showSign = true): string {
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(num)) return '--'

  const formatted = num.toFixed(decimals)
  if (showSign && num > 0) {
    return `+${formatted}%`
  }
  return `${formatted}%`
}

/**
 * 格式化金额（带千分位）
 * @param value 金额值
 * @param decimals 小数位数
 */
export function formatAmount(value: number | string, decimals = 2): string {
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(num)) return '--'

  return num.toLocaleString('zh-CN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  })
}

/**
 * 格式化大数字（万、亿）
 * @param value 数值
 */
export function formatLargeNumber(value: number | string): string {
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(num)) return '--'

  if (num >= 100000000) {
    return `${(num / 100000000).toFixed(2)}亿`
  } else if (num >= 10000) {
    return `${(num / 10000).toFixed(2)}万`
  }
  return num.toFixed(2)
}

/**
 * 格式化成交量
 * @param value 成交量
 */
export function formatVolume(value: number | string): string {
  const num = typeof value === 'string' ? parseFloat(value) : value
  if (isNaN(num)) return '--'

  if (num >= 100000000) {
    return `${(num / 100000000).toFixed(2)}亿`
  } else if (num >= 10000) {
    return `${(num / 10000).toFixed(2)}万`
  }
  return num.toString()
}

// ========== 日期格式化 ==========

/**
 * 格式化日期
 * @param date 日期
 * @param format 格式
 */
export function formatDate(date: string | Date, format = DATE_FORMAT): string {
  if (!date) return '--'
  return dayjs(date).format(format)
}

/**
 * 格式化日期时间
 * @param date 日期时间
 */
export function formatDateTime(date: string | Date): string {
  if (!date) return '--'
  return dayjs(date).format(DATETIME_FORMAT)
}

/**
 * 格式化时间
 * @param date 时间
 */
export function formatTime(date: string | Date): string {
  if (!date) return '--'
  return dayjs(date).format(TIME_FORMAT)
}

/**
 * 格式化相对时间
 * @param date 日期
 */
export function formatRelativeTime(date: string | Date): string {
  if (!date) return '--'

  const now = dayjs()
  const target = dayjs(date)
  const diff = now.diff(target, 'second')

  if (diff < 60) {
    return '刚刚'
  } else if (diff < 3600) {
    return `${Math.floor(diff / 60)}分钟前`
  } else if (diff < 86400) {
    return `${Math.floor(diff / 3600)}小时前`
  } else if (diff < 2592000) {
    return `${Math.floor(diff / 86400)}天前`
  } else {
    return formatDate(date)
  }
}

// ========== 股票代码格式化 ==========

/**
 * 格式化股票代码（添加市场前缀）
 * @param code 股票代码
 */
export function formatStockCode(code: string): string {
  if (!code) return '--'

  // 如果已经有前缀，直接返回
  if (code.includes('.')) return code

  // 根据代码判断市场
  if (code.startsWith('6')) {
    return `${code}.SH` // 上海
  } else if (code.startsWith('0') || code.startsWith('3')) {
    return `${code}.SZ` // 深圳
  } else if (code.startsWith('8') || code.startsWith('4')) {
    return `${code}.BJ` // 北京
  }

  return code
}

/**
 * 解析股票代码（移除市场前缀）
 * @param code 完整股票代码
 */
export function parseStockCode(code: string): string {
  if (!code) return ''
  return code.split('.')[0]
}

// ========== 颜色工具 ==========

/**
 * 获取涨跌颜色
 * @param value 涨跌值
 */
export function getChangeColor(value: number): string {
  if (value > 0) return 'success'
  if (value < 0) return 'danger'
  return 'info'
}

/**
 * 获取涨跌颜色类名
 * @param value 涨跌值
 */
export function getChangeClass(value: number): string {
  if (value > 0) return 'text-green-600'
  if (value < 0) return 'text-red-600'
  return 'text-gray-600'
}

// ========== 文本工具 ==========

/**
 * 截断文本
 * @param text 文本
 * @param maxLength 最大长度
 */
export function truncate(text: string, maxLength: number): string {
  if (!text) return ''
  if (text.length <= maxLength) return text
  return `${text.slice(0, maxLength)}...`
}

/**
 * 高亮关键词
 * @param text 文本
 * @param keyword 关键词
 */
export function highlight(text: string, keyword: string): string {
  if (!text || !keyword) return text
  const regex = new RegExp(`(${keyword})`, 'gi')
  return text.replace(regex, '<mark>$1</mark>')
}

// ========== 数组工具 ==========

/**
 * 数组去重
 * @param arr 数组
 */
export function unique<T>(arr: T[]): T[] {
  return Array.from(new Set(arr))
}

/**
 * 数组分组
 * @param arr 数组
 * @param key 分组键
 */
export function groupBy<T>(arr: T[], key: keyof T): Record<string, T[]> {
  return arr.reduce((result, item) => {
    const groupKey = String(item[key])
    if (!result[groupKey]) {
      result[groupKey] = []
    }
    result[groupKey].push(item)
    return result
  }, {} as Record<string, T[]>)
}

// ========== 对象工具 ==========

/**
 * 深拷贝
 * @param obj 对象
 */
export function deepClone<T>(obj: T): T {
  return JSON.parse(JSON.stringify(obj))
}

/**
 * 移除对象中的空值
 * @param obj 对象
 */
export function removeEmpty(obj: Record<string, any>): Record<string, any> {
  const result: Record<string, any> = {}

  Object.keys(obj).forEach(key => {
    const value = obj[key]
    if (value !== null && value !== undefined && value !== '') {
      result[key] = value
    }
  })

  return result
}

// ========== URL工具 ==========

/**
 * 构建查询字符串
 * @param params 参数对象
 */
export function buildQueryString(params: Record<string, any>): string {
  const cleanParams = removeEmpty(params)
  const searchParams = new URLSearchParams()

  Object.keys(cleanParams).forEach(key => {
    searchParams.append(key, String(cleanParams[key]))
  })

  return searchParams.toString()
}

/**
 * 解析查询字符串
 * @param queryString 查询字符串
 */
export function parseQueryString(queryString: string): Record<string, string> {
  const params = new URLSearchParams(queryString)
  const result: Record<string, string> = {}

  params.forEach((value, key) => {
    result[key] = value
  })

  return result
}

// ========== 防抖节流 ==========

/**
 * 防抖函数
 * @param fn 函数
 * @param delay 延迟时间（毫秒）
 */
export function debounce<T extends (...args: any[]) => any>(
  fn: T,
  delay: number
): (...args: Parameters<T>) => void {
  let timer: ReturnType<typeof setTimeout> | null = null

  return function (this: any, ...args: Parameters<T>) {
    if (timer) clearTimeout(timer)
    timer = setTimeout(() => {
      fn.apply(this, args)
    }, delay)
  }
}

/**
 * 节流函数
 * @param fn 函数
 * @param delay 延迟时间（毫秒）
 */
export function throttle<T extends (...args: any[]) => any>(
  fn: T,
  delay: number
): (...args: Parameters<T>) => void {
  let lastTime = 0

  return function (this: any, ...args: Parameters<T>) {
    const now = Date.now()
    if (now - lastTime >= delay) {
      fn.apply(this, args)
      lastTime = now
    }
  }
}

// ========== 下载工具 ==========

/**
 * 下载文件
 * @param data 数据
 * @param filename 文件名
 * @param type MIME类型
 */
export function downloadFile(data: any, filename: string, type = 'text/plain'): void {
  const blob = new Blob([data], { type })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

/**
 * 导出CSV
 * @param data 数据数组
 * @param filename 文件名
 */
export function exportCSV(data: any[], filename: string): void {
  if (!data || data.length === 0) return

  const headers = Object.keys(data[0])
  const csv = [
    headers.join(','),
    ...data.map(row => headers.map(header => row[header]).join(','))
  ].join('\n')

  downloadFile(csv, filename, 'text/csv')
}
