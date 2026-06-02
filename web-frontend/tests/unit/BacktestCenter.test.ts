import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import BacktestCenter from '@/views/BacktestCenter/index.vue'

const indicatorApiMock = vi.hoisted(() => ({
  getMyIndicators: vi.fn(),
  getSystemIndicators: vi.fn(),
  backtestIndicator: vi.fn()
}))

const analysisApiMock = vi.hoisted(() => ({
  runBacktest: vi.fn()
}))

const stockApiMock = vi.hoisted(() => ({
  searchStocks: vi.fn(),
  getKLineData: vi.fn()
}))

const tradingApiMock = vi.hoisted(() => ({
  createOrder: vi.fn()
}))

const strategyApiMock = vi.hoisted(() => ({
  getStrategies: vi.fn(),
  createStrategy: vi.fn()
}))

const echartsSetOptionMock = vi.hoisted(() => vi.fn())

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

vi.mock('@/services/api', () => ({
  analysisApi: analysisApiMock,
  stockApi: stockApiMock,
  tradingApi: tradingApiMock,
  strategyApi: strategyApiMock,
  indicatorApi: indicatorApiMock
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual<typeof import('element-plus')>('element-plus')
  return {
    ...actual,
    ...elementPlusMock
  }
})

vi.mock('echarts', () => ({
  default: {
    init: vi.fn(() => ({
      setOption: echartsSetOptionMock,
      dispose: vi.fn()
    })),
    graphic: {
      LinearGradient: vi.fn()
    }
  },
  init: vi.fn(() => ({
    setOption: echartsSetOptionMock,
    dispose: vi.fn()
  })),
  graphic: {
    LinearGradient: vi.fn()
  }
}))

describe('BacktestCenter', () => {
  const mountBacktestCenter = () => mount(BacktestCenter, {
    global: {
      stubs: {
        'el-card': { template: '<section><slot name="header" /><slot /></section>' },
        'el-button': {
          props: ['loading'],
          emits: ['click'],
          template: '<button type="button" :data-loading="loading ? `true` : `false`" @click="$emit(`click`)"><slot /></button>'
        },
        'el-form': {
          template: '<form><slot /></form>',
          methods: {
            validate(callback: (valid: boolean) => void) {
              callback(true)
            },
            resetFields() {}
          }
        },
        'el-form-item': { template: '<div><slot /></div>' },
        'el-select': { template: '<div><slot /></div>' },
        'el-segmented': { props: ['modelValue', 'options'], template: '<div>{{ options.map((option) => option.label).join(" ") }}</div>' },
        'el-option': { props: ['label'], template: '<div>{{ label }}</div>' },
        'el-autocomplete': { template: '<div><slot :item="{ symbol: `600519`, name: `贵州茅台` }" /></div>' },
        'el-date-picker': true,
        'el-row': { template: '<div><slot /></div>' },
        'el-col': { template: '<div><slot /></div>' },
        'el-input-number': true,
        'el-divider': { template: '<hr />' },
        'el-radio-group': { template: '<div><slot /></div>' },
        'el-radio-button': { template: '<button type="button"><slot /></button>' },
        'el-table': { template: '<table><slot /></table>' },
        'el-table-column': true,
        'el-tag': { template: '<span><slot /></span>' },
        'el-tabs': { template: '<div><slot /></div>' },
        'el-tab-pane': { template: '<div><slot /></div>' },
        'el-descriptions': { template: '<dl><slot /></dl>' },
        'el-descriptions-item': { template: '<dd><slot /></dd>' },
        'el-empty': { template: '<div />' },
        'el-dialog': { template: '<div><slot /><slot name="footer" /></div>' },
        'el-input': true,
        'el-alert': { template: '<div><slot /></div>' },
        'el-icon': true,
        KLineChart: {
          props: ['data', 'signals', 'height'],
          template: '<div class="kline-chart-stub">{{ data.length }}</div>'
        }
      }
    }
  })

  beforeEach(() => {
    vi.clearAllMocks()
    echartsSetOptionMock.mockClear()
    indicatorApiMock.getMyIndicators.mockResolvedValue([])
    indicatorApiMock.getSystemIndicators.mockResolvedValue([])
    indicatorApiMock.backtestIndicator.mockResolvedValue({
      totalReturn: 0.12,
      annualReturn: 0.1,
      maxDrawdown: -0.04,
      sharpeRatio: 1.2,
      winRate: 0.58,
      profitLossRatio: 1.8,
      totalTrades: 6,
      trades: [],
      equityCurve: [{ date: '2026-05-27', value: 1120000 }],
      monthlyReturns: []
    })
    analysisApiMock.runBacktest.mockResolvedValue({
      finalCapital: 1000000,
      totalReturn: 0,
      annualReturn: 0,
      maxDrawdown: 0,
      sharpeRatio: 0,
      winRate: 0,
      profitLossRatio: 0,
      totalTrades: 0,
      trades: [],
      equityCurve: [],
      monthlyReturns: []
    })
    stockApiMock.getKLineData.mockResolvedValue([
      { date: '2025-06-03', open: 1456.45, close: 1457.44, high: 1467.44, low: 1453.46, volume: 28979, amount: 42235153.76 }
    ])
    strategyApiMock.getStrategies.mockResolvedValue({
      strategies: [],
      total: 0
    })
  })

  it('loads all backtest strategies into a flat selector', async () => {
    indicatorApiMock.getMyIndicators.mockResolvedValueOnce([
      {
        id: 53,
        name: '我的RSI指标',
        codeType: 'indicator',
        strategyType: 'custom',
        category: 'custom'
      }
    ])
    indicatorApiMock.getSystemIndicators.mockResolvedValueOnce([
      {
        id: 88,
        name: '系统布林指标',
        codeType: 'indicator',
        strategyType: 'system',
        category: 'system'
      }
    ])
    strategyApiMock.getStrategies.mockResolvedValueOnce({
      strategies: [
        {
          strategyType: 'adx_trend',
          className: 'ADXTrendStrategy',
          description: 'ADX trend strength strategy.'
        }
      ],
      total: 1
    })

    const wrapper = mountBacktestCenter()

    await vi.waitFor(() => {
      expect(indicatorApiMock.getMyIndicators).toHaveBeenCalled()
      expect(indicatorApiMock.getSystemIndicators).toHaveBeenCalled()
      expect(strategyApiMock.getStrategies).toHaveBeenCalledWith({ source: 'builtin', pageSize: 200 })
      expect(wrapper.text()).toContain('我的RSI指标')
      expect(wrapper.text()).toContain('系统布林指标')
      expect(wrapper.text()).toContain('ADXTrendStrategy')
      expect(wrapper.text()).toContain('GridTradingStrategy')
    })

    expect(wrapper.findComponent({ name: 'ElOptionGroup' }).exists()).toBe(false)
  })

  it('lets users refresh the strategy selector manually', async () => {
    strategyApiMock.getStrategies
      .mockResolvedValueOnce({
        strategies: [],
        total: 0
      })
      .mockResolvedValueOnce({
        strategies: [
          {
            strategyType: 'refreshed_strategy',
            className: 'RefreshedStrategy'
          }
        ],
        total: 1
      })

    const wrapper = mountBacktestCenter()

    await vi.waitFor(() => {
      expect(strategyApiMock.getStrategies).toHaveBeenCalledTimes(1)
    })

    const refreshButton = wrapper.findAll('button').find(button => button.text().includes('刷新策略'))
    expect(refreshButton).toBeTruthy()

    await refreshButton!.trigger('click')

    await vi.waitFor(() => {
      expect(strategyApiMock.getStrategies).toHaveBeenCalledTimes(2)
      expect(wrapper.text()).toContain('RefreshedStrategy')
    })
  })

  it('runs selected custom indicator through indicator backtest API', async () => {
    indicatorApiMock.getMyIndicators.mockResolvedValueOnce([
      {
        id: 53,
        name: '我的RSI指标',
        codeType: 'indicator',
        strategyType: 'custom',
        category: 'custom'
      }
    ])

    const wrapper = mountBacktestCenter()

    await vi.waitFor(() => {
      expect(wrapper.text()).toContain('我的RSI指标')
    })

    const vm = wrapper.vm as any
    vm.backtestForm.strategy = 'indicator:53'
    vm.backtestForm.symbol = '600519'
    vm.backtestForm.klinePeriod = '30min'
    vm.backtestForm.startDate = new Date('2025-05-27T00:00:00')
    vm.backtestForm.endDate = new Date('2026-05-27T00:00:00')

    await vm.handleStartBacktest()

    expect(indicatorApiMock.backtestIndicator).toHaveBeenCalledWith({
      indicatorId: '53',
      symbol: '600519',
      startDate: '2025-05-27',
      endDate: '2026-05-27',
      initialCash: 1000000,
      period: '30min'
    })
    expect(analysisApiMock.runBacktest).not.toHaveBeenCalled()
  })

  it('runs selected builtin strategy with the selected kline period', async () => {
    const wrapper = mountBacktestCenter()

    const vm = wrapper.vm as any
    vm.backtestForm.strategy = 'ma_cross'
    vm.backtestForm.symbol = '600519'
    vm.backtestForm.klinePeriod = '15min'
    vm.backtestForm.startDate = new Date('2025-05-27T00:00:00')
    vm.backtestForm.endDate = new Date('2026-05-27T00:00:00')

    await vm.handleStartBacktest()

    expect(analysisApiMock.runBacktest).toHaveBeenCalledWith(expect.objectContaining({
      strategy: 'ma_cross',
      symbol: '600519',
      startDate: '2025-05-27',
      endDate: '2026-05-27',
      period: '15min'
    }))
    expect(stockApiMock.getKLineData).toHaveBeenCalledWith(expect.objectContaining({
      symbol: '600519',
      timeFrame: '15min'
    }))
  })

  it('normalizes backend trade fields for the trade table', () => {
    const wrapper = mountBacktestCenter()
    const vm = wrapper.vm as any

    const normalized = vm.normalizeBacktestResult({
      trades: [
        {
          symbol: '600519',
          entry_date: '2025-08-28',
          entry_price: 14.82,
          exit_date: '2025-09-12',
          exit_price: 13.99,
          shares: 1000,
          profit: -830,
          cash: 985170
        },
        {
          date: '2025-09-15',
          action: 'buy',
          price: 13.88,
          size: 7200,
          cash: 885234
        }
      ],
      equity_curve: [{ date: '2025-09-15', equity: 990000, cash: 885234 }]
    })

    expect(normalized.trades[0]).toMatchObject({
      date: '2025-09-12',
      type: 'SELL',
      price: 13.99,
      quantity: 1000,
      amount: 13990,
      profit: -830,
      balance: 985170
    })
    expect(normalized.trades[1]).toMatchObject({
      date: '2025-09-15',
      type: 'BUY',
      price: 13.88,
      quantity: 7200,
      amount: 99936,
      commission: 0,
      profit: null,
      balance: 885234
    })
  })

  it('normalizes ratio metrics into display percentages', () => {
    const wrapper = mountBacktestCenter()
    const vm = wrapper.vm as any

    const normalized = vm.normalizeBacktestResult({
      total_return: 0.21213361,
      annual_return: 0.2195,
      max_drawdown: -0.0304,
      win_rate: 0.8333,
      trades: [],
      equity_curve: [{ date: '2026-05-28', equity: 1212133.61 }]
    })

    expect(normalized.totalReturn).toBeCloseTo(21.213361)
    expect(normalized.annualReturn).toBeCloseTo(21.95)
    expect(normalized.maxDrawdown).toBeCloseTo(-3.04)
    expect(normalized.winRate).toBeCloseTo(83.33)
    expect(vm.formatBacktestPercent(normalized.totalReturn)).toBe('+21.21%')
    expect(vm.formatBacktestPercent(normalized.winRate, false)).toBe('83.33%')
  })

  it('renders strategy equity against buy-and-hold benchmark', () => {
    const wrapper = mountBacktestCenter()
    const vm = wrapper.vm as any
    const chartEl = document.createElement('div')

    vm.equityChartRef = chartEl
    vm.backtestKlineData = [
      { date: '2025-08-28', open: 10, close: 10, high: 11, low: 9, volume: 1000, amount: 10000 },
      { date: '2025-09-12', open: 12, close: 12, high: 13, low: 11, volume: 1200, amount: 14400 }
    ]
    vm.backtestResult = vm.normalizeBacktestResult({
      initialCapital: 1000000,
      trades: [
        {
          entry_date: '2025-08-28',
          entry_price: 14.82,
          exit_date: '2025-09-12',
          exit_price: 13.99,
          shares: 1000,
          profit: -830
        }
      ],
      equity_curve: [
        { date: '2025-08-28', equity: 1000000 },
        { date: '2025-09-12', equity: 985170 }
      ]
    })

    vm.renderEquityChart()

    const option = echartsSetOptionMock.mock.calls.at(-1)?.[0]
    expect(option.title.text).toBe('策略 vs 标的')
    expect(option.legend.data).toEqual(['策略收益率', '买入持有收益率', '超额收益率'])
    expect(option.xAxis[1].axisLabel.formatter('2025-09-12')).toBe('09-12')
    expect(option.xAxis[1].axisLabel.formatter('2025-09-12 10:30:00')).toBe('09-12')
    expect(option.yAxis[0].axisLabel.formatter).toBe('{value}%')
    expect(option.yAxis[1].axisLabel.formatter).toBe('{value}%')
    expect(option.series[0].name).toBe('策略收益率')
    expect(option.series[0].data).toEqual([0, -1.48])
    expect(option.series[1].name).toBe('买入持有收益率')
    expect(option.series[1].data).toEqual([0, 20])
    expect(option.series[2].name).toBe('超额收益率')
    expect(option.series[2].type).toBe('bar')
    expect(option.series[2].xAxisIndex).toBe(1)
    expect(option.series[2].yAxisIndex).toBe(1)
    expect(option.series[2].data).toEqual([0, -21.48])
    expect(option.series[0].markArea.data).toEqual([
      [
        { xAxis: '2025-08-28' },
        { xAxis: '2025-09-12' }
      ]
    ])
    expect(option.series[0].markPoint.data).toEqual([
      expect.objectContaining({ name: '买入', value: '买1', coord: ['2025-08-28', 0] }),
      expect.objectContaining({ name: '卖出', value: '卖1', coord: ['2025-09-12', -1.48] })
    ])
    expect(option.series[0].markPoint.label.formatter(option.series[0].markPoint.data[0])).toBe('买1')
    expect(option.series[0].markPoint.label.formatter(option.series[0].markPoint.data[1])).toBe('卖1')
    expect(option.series[0].markLine.data).toEqual([
      expect.objectContaining({ name: '买1', xAxis: '2025-08-28' }),
      expect.objectContaining({ name: '卖1', xAxis: '2025-09-12' })
    ])
  })

  it('places kline chart above strategy comparison chart', async () => {
    const wrapper = mountBacktestCenter()
    const vm = wrapper.vm as any

    vm.backtestForm.symbol = '600519'
    await vm.handleStartBacktest()

    await vi.waitFor(() => {
      expect(wrapper.find('.kline-chart-stub').exists()).toBe(true)
    })

    const html = wrapper.html()
    expect(html.indexOf('K线走势')).toBeLessThan(html.indexOf('策略 vs 标的'))
  })

  it('loads and renders stock klines after a backtest completes', async () => {
    const wrapper = mountBacktestCenter()
    const vm = wrapper.vm as any

    vm.backtestForm.symbol = '600519'
    vm.backtestForm.startDate = new Date('2025-06-01T00:00:00')
    vm.backtestForm.endDate = new Date('2026-06-01T00:00:00')

    await vm.handleStartBacktest()

    await vi.waitFor(() => {
      expect(stockApiMock.getKLineData).toHaveBeenCalledWith({
        symbol: '600519',
        startDate: '2025-06-01',
        endDate: '2026-06-01',
        timeFrame: 'daily',
        limit: 500
      })
    })
    await wrapper.vm.$nextTick()

    expect(stockApiMock.getKLineData).toHaveBeenCalledWith({
      symbol: '600519',
      startDate: '2025-06-01',
      endDate: '2026-06-01',
      timeFrame: 'daily',
      limit: 500
    })
    expect(vm.backtestKlineData).toEqual([
      { date: '2025-06-03', open: 1456.45, close: 1457.44, high: 1467.44, low: 1453.46, volume: 28979, amount: 42235153.76 }
    ])
    expect(wrapper.find('.kline-chart-stub').text()).toBe('1')
  })

  it('passes the selected kline period to the kline API', async () => {
    const wrapper = mountBacktestCenter()
    const vm = wrapper.vm as any

    expect(wrapper.text()).toContain('日线')
    expect(wrapper.text()).toContain('1分钟')

    vm.backtestForm.symbol = '600519'
    vm.backtestForm.klinePeriod = '5min'

    await vm.handleStartBacktest()

    await vi.waitFor(() => {
      expect(stockApiMock.getKLineData).toHaveBeenCalledWith(
        expect.objectContaining({
          symbol: '600519',
          timeFrame: '5min'
        })
      )
    })
  })
})
