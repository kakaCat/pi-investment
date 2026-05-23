/**
 * 性能监控工具
 * 用于监控页面加载时间、API请求时间等性能指标
 */

interface PerformanceMetrics {
  // 页面加载指标
  pageLoadTime?: number
  domContentLoadedTime?: number
  firstPaintTime?: number
  firstContentfulPaintTime?: number

  // 资源加载指标
  resourceLoadTime?: number

  // 自定义指标
  customMetrics?: Record<string, number>
}

interface APIPerformanceRecord {
  url: string
  method: string
  duration: number
  timestamp: number
  status?: number
}

class PerformanceMonitor {
  private metrics: PerformanceMetrics = {}
  private apiRecords: APIPerformanceRecord[] = []
  private maxRecords = 100 // 最多保存100条API记录

  constructor() {
    this.init()
  }

  /**
   * 初始化性能监控
   */
  private init() {
    if (typeof window === 'undefined') return

    // 页面加载完成后收集性能指标
    if (document.readyState === 'complete') {
      this.collectPageMetrics()
    } else {
      window.addEventListener('load', () => {
        // 延迟收集，确保所有资源加载完成
        setTimeout(() => this.collectPageMetrics(), 0)
      })
    }
  }

  /**
   * 收集页面性能指标
   */
  private collectPageMetrics() {
    if (!window.performance || !window.performance.timing) return

    const timing = window.performance.timing

    // 计算各项指标
    this.metrics.pageLoadTime = timing.loadEventEnd - timing.navigationStart
    this.metrics.domContentLoadedTime = timing.domContentLoadedEventEnd - timing.navigationStart
    this.metrics.resourceLoadTime = timing.loadEventEnd - timing.domContentLoadedEventEnd

    // 获取 Paint Timing
    if (window.performance.getEntriesByType) {
      const paintEntries = window.performance.getEntriesByType('paint')
      paintEntries.forEach((entry) => {
        if (entry.name === 'first-paint') {
          this.metrics.firstPaintTime = entry.startTime
        } else if (entry.name === 'first-contentful-paint') {
          this.metrics.firstContentfulPaintTime = entry.startTime
        }
      })
    }

    // 在开发环境下输出性能指标
    if (import.meta.env.DEV) {
      console.group('📊 页面性能指标')
      console.log('页面加载时间:', this.formatTime(this.metrics.pageLoadTime))
      console.log('DOM加载时间:', this.formatTime(this.metrics.domContentLoadedTime))
      console.log('资源加载时间:', this.formatTime(this.metrics.resourceLoadTime))
      if (this.metrics.firstPaintTime) {
        console.log('首次绘制时间:', this.formatTime(this.metrics.firstPaintTime))
      }
      if (this.metrics.firstContentfulPaintTime) {
        console.log('首次内容绘制时间:', this.formatTime(this.metrics.firstContentfulPaintTime))
      }
      console.groupEnd()
    }
  }

  /**
   * 记录API请求性能
   */
  recordAPICall(url: string, method: string, duration: number, status?: number) {
    const record: APIPerformanceRecord = {
      url,
      method,
      duration,
      timestamp: Date.now(),
      status
    }

    this.apiRecords.push(record)

    // 限制记录数量
    if (this.apiRecords.length > this.maxRecords) {
      this.apiRecords.shift()
    }

    // 慢请求警告（超过3秒）
    if (duration > 3000 && import.meta.env.DEV) {
      console.warn(`⚠️ 慢API请求: ${method} ${url} - ${this.formatTime(duration)}`)
    }
  }

  /**
   * 开始计时
   */
  startTimer(label: string): () => void {
    const startTime = performance.now()

    return () => {
      const duration = performance.now() - startTime
      this.recordCustomMetric(label, duration)

      if (import.meta.env.DEV) {
        console.log(`⏱️ ${label}: ${this.formatTime(duration)}`)
      }

      return duration
    }
  }

  /**
   * 记录自定义指标
   */
  recordCustomMetric(name: string, value: number) {
    if (!this.metrics.customMetrics) {
      this.metrics.customMetrics = {}
    }
    this.metrics.customMetrics[name] = value
  }

  /**
   * 获取所有性能指标
   */
  getMetrics(): PerformanceMetrics {
    return { ...this.metrics }
  }

  /**
   * 获取API性能记录
   */
  getAPIRecords(): APIPerformanceRecord[] {
    return [...this.apiRecords]
  }

  /**
   * 获取API性能统计
   */
  getAPIStats() {
    if (this.apiRecords.length === 0) {
      return null
    }

    const durations = this.apiRecords.map(r => r.duration)
    const sum = durations.reduce((a, b) => a + b, 0)
    const avg = sum / durations.length
    const max = Math.max(...durations)
    const min = Math.min(...durations)

    return {
      total: this.apiRecords.length,
      avgDuration: avg,
      maxDuration: max,
      minDuration: min
    }
  }

  /**
   * 清除API记录
   */
  clearAPIRecords() {
    this.apiRecords = []
  }

  /**
   * 格式化时间
   */
  private formatTime(ms?: number): string {
    if (ms === undefined) return 'N/A'
    if (ms < 1000) return `${ms.toFixed(2)}ms`
    return `${(ms / 1000).toFixed(2)}s`
  }

  /**
   * 获取内存使用情况（如果浏览器支持）
   */
  getMemoryUsage() {
    if ('memory' in performance) {
      const memory = (performance as any).memory
      return {
        usedJSHeapSize: this.formatBytes(memory.usedJSHeapSize),
        totalJSHeapSize: this.formatBytes(memory.totalJSHeapSize),
        jsHeapSizeLimit: this.formatBytes(memory.jsHeapSizeLimit)
      }
    }
    return null
  }

  /**
   * 格式化字节
   */
  private formatBytes(bytes: number): string {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i]
  }

  /**
   * 打印性能报告
   */
  printReport() {
    console.group('📊 性能监控报告')

    // 页面性能
    console.group('页面性能')
    console.table(this.metrics)
    console.groupEnd()

    // API性能统计
    const apiStats = this.getAPIStats()
    if (apiStats) {
      console.group('API性能统计')
      console.table({
        '总请求数': apiStats.total,
        '平均耗时': this.formatTime(apiStats.avgDuration),
        '最长耗时': this.formatTime(apiStats.maxDuration),
        '最短耗时': this.formatTime(apiStats.minDuration)
      })
      console.groupEnd()
    }

    // 内存使用
    const memory = this.getMemoryUsage()
    if (memory) {
      console.group('内存使用')
      console.table(memory)
      console.groupEnd()
    }

    console.groupEnd()
  }
}

// 创建全局实例
export const performanceMonitor = new PerformanceMonitor()

// 在开发环境下暴露到 window 对象
if (import.meta.env.DEV && typeof window !== 'undefined') {
  (window as any).__PERFORMANCE_MONITOR__ = performanceMonitor
  console.log('💡 性能监控已启用，使用 window.__PERFORMANCE_MONITOR__.printReport() 查看报告')
}

export default performanceMonitor
