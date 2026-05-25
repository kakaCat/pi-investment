/**
 * 测试 IndicatorIDE 组件
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import IndicatorIDE from '@/views/IndicatorIDE/index.vue'
import type { KlineData, IndicatorRunResult } from '@/types/indicator'

const indicatorApiMock = vi.hoisted(() => ({
  getMyIndicators: vi.fn(),
  getSystemIndicators: vi.fn(),
  deleteIndicator: vi.fn(),
  runIndicator: vi.fn(),
  updateIndicator: vi.fn(),
  createIndicator: vi.fn(),
  publishIndicator: vi.fn(),
  backtestIndicator: vi.fn()
}))

const chartApiMock = vi.hoisted(() => ({
  chartRef: undefined as any,
  setOption: vi.fn(),
  showLoading: vi.fn(),
  hideLoading: vi.fn()
}))

vi.mock('@/services/api/indicator', () => ({
  indicatorApi: indicatorApiMock
}))

vi.mock('@/composables/useChart', async () => {
  const vue = await vi.importActual<typeof import('vue')>('vue')
  chartApiMock.chartRef = vue.ref<HTMLElement>()

  return {
    useChart: vi.fn(() => chartApiMock)
  }
})

vi.mock('element-plus', async () => {
  const actual = await vi.importActual<typeof import('element-plus')>('element-plus')
  return {
    ...actual,
    ElMessage: {
      success: vi.fn(),
      error: vi.fn(),
      warning: vi.fn(),
      info: vi.fn()
    },
    ElMessageBox: {
      confirm: vi.fn(() => Promise.resolve())
    }
  }
})

describe('IndicatorIDE', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    indicatorApiMock.getMyIndicators.mockResolvedValue([])
    indicatorApiMock.getSystemIndicators.mockResolvedValue([])
    indicatorApiMock.deleteIndicator.mockResolvedValue({})
    if (chartApiMock.chartRef) {
      chartApiMock.chartRef.value = undefined
    }
  })

  describe('Component Behavior', () => {
    it('binds the preview chart container to useChart chartRef', async () => {
      mount(IndicatorIDE, {
        global: {
          stubs: {
            'el-icon': true
          }
        }
      })

      expect(chartApiMock.chartRef.value).toBeInstanceOf(HTMLElement)
      expect(chartApiMock.chartRef.value?.classList.contains('chart-container')).toBe(true)
    })

    it('deletes the selected custom indicator and reloads the list', async () => {
      indicatorApiMock.getMyIndicators.mockResolvedValueOnce([
        {
          id: 7,
          name: 'test',
          description: '',
          codeContent: 'df',
          codeType: 'indicator',
          strategyType: 'custom',
          category: 'custom'
        }
      ]).mockResolvedValueOnce([])

      const wrapper = mount(IndicatorIDE, {
        global: {
          stubs: {
            'el-icon': true
          }
        }
      })

      await vi.waitFor(() => {
        expect(wrapper.text()).toContain('test')
      })

      await wrapper.find('[data-test="delete-indicator"]').trigger('click')

      await vi.waitFor(() => {
        expect(indicatorApiMock.deleteIndicator).toHaveBeenCalledWith('7')
      })
      expect(indicatorApiMock.getMyIndicators).toHaveBeenCalledTimes(2)
    })
  })

  describe('Type Safety', () => {
    it('should handle IndicatorRunResult type correctly', () => {
      const mockResult: IndicatorRunResult = {
        symbol: '600519',
        latestSignal: 'buy',
        confidence: 0.85,
        price: 1800.5,
        date: '2024-01-15',
        indicators: {
          ma_short: 1795.2,
          ma_long: 1780.5
        },
        klineData: [
          {
            date: '2024-01-15',
            open: 1790.0,
            high: 1805.0,
            low: 1785.0,
            close: 1800.5,
            volume: 1000000
          }
        ],
        indicatorSeries: {
          ma_short: [1790.0, 1795.2],
          ma_long: [1775.0, 1780.5]
        }
      }

      expect(mockResult.symbol).toBe('600519')
      expect(mockResult.latestSignal).toBe('buy')
      expect(mockResult.klineData).toHaveLength(1)
      expect(mockResult.indicatorSeries?.ma_short).toHaveLength(2)
    })

    it('should handle KlineData type correctly', () => {
      const mockKline: KlineData = {
        date: '2024-01-15',
        open: 1790.0,
        high: 1805.0,
        low: 1785.0,
        close: 1800.5,
        volume: 1000000
      }

      expect(mockKline.date).toBe('2024-01-15')
      expect(mockKline.open).toBe(1790.0)
      expect(mockKline.high).toBe(1805.0)
      expect(mockKline.low).toBe(1785.0)
      expect(mockKline.close).toBe(1800.5)
      expect(mockKline.volume).toBe(1000000)
    })

    it('should handle optional fields in IndicatorRunResult', () => {
      const minimalResult: IndicatorRunResult = {
        symbol: '600519',
        latestSignal: 'hold',
        confidence: 0.5,
        price: 1800.0,
        date: '2024-01-15',
        indicators: {}
      }

      expect(minimalResult.klineData).toBeUndefined()
      expect(minimalResult.indicatorSeries).toBeUndefined()
    })
  })

  describe('K-line Chart Rendering', () => {
    it('should format kline data correctly for ECharts', () => {
      const klineData: KlineData[] = [
        {
          date: '2024-01-01',
          open: 100.0,
          high: 105.0,
          low: 99.0,
          close: 103.0,
          volume: 1000000
        },
        {
          date: '2024-01-02',
          open: 103.0,
          high: 108.0,
          low: 102.0,
          close: 106.0,
          volume: 1100000
        }
      ]

      // 模拟 renderKlineChart 中的数据转换
      const dates = klineData.map(k => k.date)
      const ohlc = klineData.map(k => [k.open, k.close, k.low, k.high])
      const volumes = klineData.map(k => k.volume)

      expect(dates).toEqual(['2024-01-01', '2024-01-02'])
      expect(ohlc).toEqual([
        [100.0, 103.0, 99.0, 105.0],
        [103.0, 106.0, 102.0, 108.0]
      ])
      expect(volumes).toEqual([1000000, 1100000])
    })

    it('should format indicator series correctly for ECharts', () => {
      const indicatorSeries: Record<string, number[]> = {
        ma_short: [100.5, 101.2, 102.0],
        ma_long: [98.0, 99.5, 100.8]
      }

      // 模拟 renderKlineChart 中的指标线转换
      const indicatorLines = Object.entries(indicatorSeries).map(([name, values]) => ({
        name,
        type: 'line' as const,
        data: values,
        smooth: true,
        lineStyle: { width: 2 },
        showSymbol: false
      }))

      expect(indicatorLines).toHaveLength(2)
      expect(indicatorLines[0].name).toBe('ma_short')
      expect(indicatorLines[0].type).toBe('line')
      expect(indicatorLines[0].data).toEqual([100.5, 101.2, 102.0])
      expect(indicatorLines[1].name).toBe('ma_long')
      expect(indicatorLines[1].data).toEqual([98.0, 99.5, 100.8])
    })

    it('should handle empty kline data gracefully', () => {
      const klineData: KlineData[] = []

      const dates = klineData.map(k => k.date)
      const ohlc = klineData.map(k => [k.open, k.close, k.low, k.high])

      expect(dates).toEqual([])
      expect(ohlc).toEqual([])
    })

    it('should handle empty indicator series gracefully', () => {
      const indicatorSeries: Record<string, number[]> = {}

      const indicatorLines = Object.entries(indicatorSeries).map(([name, values]) => ({
        name,
        type: 'line' as const,
        data: values
      }))

      expect(indicatorLines).toEqual([])
    })
  })

  describe('Signal Display', () => {
    it('should correctly identify buy signal', () => {
      const result: IndicatorRunResult = {
        symbol: '600519',
        latestSignal: 'buy',
        confidence: 0.85,
        price: 1800.0,
        date: '2024-01-15',
        indicators: {}
      }

      expect(result.latestSignal).toBe('buy')
      expect(result.latestSignal === 'buy' || result.latestSignal === 'sell').toBe(true)
    })

    it('should correctly identify sell signal', () => {
      const result: IndicatorRunResult = {
        symbol: '600519',
        latestSignal: 'sell',
        confidence: 0.75,
        price: 1800.0,
        date: '2024-01-15',
        indicators: {}
      }

      expect(result.latestSignal).toBe('sell')
      expect(result.latestSignal === 'buy' || result.latestSignal === 'sell').toBe(true)
    })

    it('should correctly identify hold signal', () => {
      const result: IndicatorRunResult = {
        symbol: '600519',
        latestSignal: 'hold',
        confidence: 0.5,
        price: 1800.0,
        date: '2024-01-15',
        indicators: {}
      }

      expect(result.latestSignal).toBe('hold')
      expect(result.latestSignal === 'buy' || result.latestSignal === 'sell').toBe(false)
    })
  })

  describe('Data Validation', () => {
    it('should validate kline data structure', () => {
      const validKline: KlineData = {
        date: '2024-01-15',
        open: 100.0,
        high: 105.0,
        low: 99.0,
        close: 103.0,
        volume: 1000000
      }

      // 验证所有必需字段存在
      expect(validKline).toHaveProperty('date')
      expect(validKline).toHaveProperty('open')
      expect(validKline).toHaveProperty('high')
      expect(validKline).toHaveProperty('low')
      expect(validKline).toHaveProperty('close')
      expect(validKline).toHaveProperty('volume')

      // 验证数据类型
      expect(typeof validKline.date).toBe('string')
      expect(typeof validKline.open).toBe('number')
      expect(typeof validKline.high).toBe('number')
      expect(typeof validKline.low).toBe('number')
      expect(typeof validKline.close).toBe('number')
      expect(typeof validKline.volume).toBe('number')
    })

    it('should validate OHLC relationships', () => {
      const kline: KlineData = {
        date: '2024-01-15',
        open: 100.0,
        high: 105.0,
        low: 99.0,
        close: 103.0,
        volume: 1000000
      }

      // high 应该是最高价
      expect(kline.high).toBeGreaterThanOrEqual(kline.open)
      expect(kline.high).toBeGreaterThanOrEqual(kline.close)
      expect(kline.high).toBeGreaterThanOrEqual(kline.low)

      // low 应该是最低价
      expect(kline.low).toBeLessThanOrEqual(kline.open)
      expect(kline.low).toBeLessThanOrEqual(kline.close)
      expect(kline.low).toBeLessThanOrEqual(kline.high)
    })

    it('should handle numeric string conversion', () => {
      // 模拟后端可能返回字符串数字的情况
      const rawData = {
        date: '2024-01-15',
        open: '100.0',
        high: '105.0',
        low: '99.0',
        close: '103.0',
        volume: '1000000'
      }

      const kline: KlineData = {
        date: rawData.date,
        open: parseFloat(rawData.open),
        high: parseFloat(rawData.high),
        low: parseFloat(rawData.low),
        close: parseFloat(rawData.close),
        volume: parseFloat(rawData.volume)
      }

      expect(kline.open).toBe(100.0)
      expect(kline.high).toBe(105.0)
      expect(kline.low).toBe(99.0)
      expect(kline.close).toBe(103.0)
      expect(kline.volume).toBe(1000000)
    })
  })

  describe('Error Handling', () => {
    it('should handle missing klineData gracefully', () => {
      const result: IndicatorRunResult = {
        symbol: '600519',
        latestSignal: 'hold',
        confidence: 0.5,
        price: 1800.0,
        date: '2024-01-15',
        indicators: {}
        // klineData 缺失
      }

      const klineData = result.klineData || []
      expect(klineData).toEqual([])
    })

    it('should handle missing indicatorSeries gracefully', () => {
      const result: IndicatorRunResult = {
        symbol: '600519',
        latestSignal: 'hold',
        confidence: 0.5,
        price: 1800.0,
        date: '2024-01-15',
        indicators: {}
        // indicatorSeries 缺失
      }

      const indicatorSeries = result.indicatorSeries || {}
      expect(indicatorSeries).toEqual({})
    })

    it('should handle empty indicators object', () => {
      const result: IndicatorRunResult = {
        symbol: '600519',
        latestSignal: 'hold',
        confidence: 0.5,
        price: 1800.0,
        date: '2024-01-15',
        indicators: {}
      }

      expect(Object.keys(result.indicators)).toHaveLength(0)
    })
  })
})
