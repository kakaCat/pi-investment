/**
 * 测试 IndicatorIDE 组件
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
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

const elementPlusMock = vi.hoisted(() => ({
  ElMessage: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn()
  },
  ElMessageBox: {
    confirm: vi.fn(() => Promise.resolve())
  }
}))

const chartApiMock = vi.hoisted(() => ({
  chartRef: undefined as any,
  setOption: vi.fn(),
  showLoading: vi.fn(),
  hideLoading: vi.fn(),
  resize: vi.fn()
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

vi.mock('echarts', () => ({
  init: vi.fn(() => ({
    setOption: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn()
  }))
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual<typeof import('element-plus')>('element-plus')
  return {
    ...actual,
    ...elementPlusMock
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
    it('renders the lower real-time preview area', async () => {
      const wrapper = mount(IndicatorIDE, {
        global: {
          stubs: {
            'el-icon': true
          }
        }
      })

      expect(wrapper.find('.preview-card').exists()).toBe(true)
      expect(wrapper.find('.lower-grid').exists()).toBe(true)
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

    it('reloads the indicator library from the refresh button', async () => {
      vi.spyOn(Date, 'now').mockReturnValue(123)
      const wrapper = mount(IndicatorIDE, {
        global: {
          stubs: {
            'el-icon': true
          }
        }
      })

      await vi.waitFor(() => {
        expect(indicatorApiMock.getMyIndicators).toHaveBeenCalledTimes(1)
      })

      const source = readFileSync(resolve(process.cwd(), 'src/views/IndicatorIDE/index.vue'), 'utf8')
      expect(source).toContain('data-test="refresh-indicators"')

      await (wrapper.vm as any).refreshIndicators()

      await vi.waitFor(() => {
        expect(indicatorApiMock.getMyIndicators).toHaveBeenLastCalledWith({ _t: 123 })
        expect(indicatorApiMock.getSystemIndicators).toHaveBeenLastCalledWith({ _t: 123 })
      })
    })

    it('does not show refresh success when indicator library reload fails', async () => {
      indicatorApiMock.getMyIndicators
        .mockResolvedValueOnce([])
        .mockRejectedValueOnce(new Error('backend down'))

      const wrapper = mount(IndicatorIDE, {
        global: {
          stubs: {
            'el-icon': true
          }
        }
      })

      await vi.waitFor(() => {
        expect(indicatorApiMock.getMyIndicators).toHaveBeenCalledTimes(1)
      })

      await expect((wrapper.vm as any).refreshIndicators()).rejects.toThrow('backend down')
      expect(elementPlusMock.ElMessage.success).not.toHaveBeenCalledWith(expect.stringContaining('指标库已刷新'))
    })

    it('runs full backtest for all preview stock cards', async () => {
      indicatorApiMock.getMyIndicators.mockResolvedValueOnce([
        {
          id: 7,
          name: 'multi-stock',
          description: '',
          codeContent: 'df',
          codeType: 'indicator',
          strategyType: 'custom',
          category: 'custom'
        }
      ])
      indicatorApiMock.backtestIndicator
        .mockResolvedValueOnce({
          winRate: 0.58,
          totalReturn: 0.11,
          sharpeRatio: 1.2,
          maxDrawdown: -0.06,
          totalTrades: 9
        })
        .mockResolvedValueOnce({
          winRate: 0.62,
          totalReturn: 0.18,
          sharpeRatio: 1.7,
          maxDrawdown: -0.08,
          totalTrades: 12
        })

      const wrapper = mount(IndicatorIDE, {
        global: {
          stubs: {
            'el-icon': true
          }
        }
      })

      await vi.waitFor(() => {
        expect(wrapper.text()).toContain('multi-stock')
      })

      const vm = wrapper.vm as any
      vm.previewResults = [
        {
          symbol: '600600',
          symbolName: '青岛啤酒',
          currentValue: 61.69,
          date: '2026-05-26',
          signalTriggered: false,
          klineData: [],
          indicatorSeries: {}
        },
        {
          symbol: '600519',
          symbolName: '贵州茅台',
          currentValue: 1582.3,
          date: '2026-05-26',
          signalTriggered: false,
          klineData: [],
          indicatorSeries: {}
        }
      ]

      await vm.runAllPreviewBacktests()

      expect(indicatorApiMock.backtestIndicator).toHaveBeenCalledWith(
        expect.objectContaining({
          indicatorId: '7',
          symbol: '600600'
        })
      )
      expect(indicatorApiMock.backtestIndicator).toHaveBeenCalledWith(
        expect.objectContaining({
          indicatorId: '7',
          symbol: '600519'
        })
      )
      expect(indicatorApiMock.backtestIndicator).toHaveBeenCalledTimes(2)
      expect(vm.previewResults[0].backtestResult.totalReturn).toBe(0.11)
      expect(vm.previewResults[1].backtestResult.totalReturn).toBe(0.18)
    })

    it('shows editable dates next to the full backtest button', () => {
      const source = readFileSync(resolve(process.cwd(), 'src/views/IndicatorIDE/index.vue'), 'utf8')

      expect(source).toContain('data-test="preview-backtest-start-date"')
      expect(source).toContain('data-test="preview-backtest-end-date"')
      expect(source).toContain('data-test="preview-backtest-range-90d"')
      expect(source).toContain('data-test="preview-backtest-range-half-year"')
      expect(source).toContain('data-test="preview-backtest-range-one-year"')
      expect(source).toContain('完整回测全部股票')
      expect(source).not.toContain('完整回测全部股票 (90天)')
    })

    it('applies preset ranges to the preview backtest dates', () => {
      const wrapper = mount(IndicatorIDE, {
        global: {
          stubs: {
            'el-icon': true
          }
        }
      })
      const vm = wrapper.vm as any

      vm.backtestForm.endDate = '2026-05-27'
      vm.applyBacktestRange('oneYear')

      expect(vm.backtestForm.startDate).toBe('2025-05-27')
      expect(vm.backtestForm.endDate).toBe('2026-05-27')
    })

    it('uses one year as the default backtest range', () => {
      const source = readFileSync(resolve(process.cwd(), 'src/views/IndicatorIDE/index.vue'), 'utf8')
      const initStart = source.indexOf('const initBacktestDates = () => {')
      const initEnd = source.indexOf('type BacktestRangePreset', initStart)
      const initBacktestDatesSource = source.slice(initStart, initEnd)

      expect(initBacktestDatesSource).toContain("applyBacktestRange('oneYear')")
      expect(initBacktestDatesSource).not.toContain('startDate.setDate(startDate.getDate() - 90)')
    })

    it('requests one year of chart data for the real-time preview', async () => {
      indicatorApiMock.getMyIndicators.mockResolvedValueOnce([
        {
          id: 7,
          name: 'one-year-preview',
          description: '',
          codeContent: 'df',
          codeType: 'indicator',
          strategyType: 'custom',
          category: 'custom'
        }
      ])
      indicatorApiMock.runIndicator.mockResolvedValueOnce({
        symbol: '600519',
        latestSignal: 'hold',
        price: 1582.3,
        date: '2026-05-27',
        klineData: [],
        indicatorSeries: {}
      })

      const wrapper = mount(IndicatorIDE, {
        global: {
          stubs: {
            'el-icon': true
          }
        }
      })

      await vi.waitFor(() => {
        expect(wrapper.text()).toContain('one-year-preview')
      })

      await (wrapper.vm as any).runIndicator()

      expect(indicatorApiMock.runIndicator).toHaveBeenCalledWith('7', {
        symbol: '600519',
        limit: 260,
        chartLimit: 260
      })
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
