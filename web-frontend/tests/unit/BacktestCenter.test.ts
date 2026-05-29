import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import BacktestCenter from '@/views/BacktestCenter/index.vue'

const indicatorApiMock = vi.hoisted(() => ({
  getMyIndicators: vi.fn(),
  backtestIndicator: vi.fn()
}))

const analysisApiMock = vi.hoisted(() => ({
  runBacktest: vi.fn()
}))

const stockApiMock = vi.hoisted(() => ({
  searchStocks: vi.fn()
}))

const tradingApiMock = vi.hoisted(() => ({
  createOrder: vi.fn()
}))

const strategyApiMock = vi.hoisted(() => ({
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
        'el-button': { template: '<button type="button"><slot /></button>' },
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
        'el-option': { props: ['label'], template: '<div>{{ label }}</div>' },
        'el-option-group': { props: ['label'], template: '<div><span>{{ label }}</span><slot /></div>' },
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
        'el-icon': true
      }
    }
  })

  beforeEach(() => {
    vi.clearAllMocks()
    echartsSetOptionMock.mockClear()
    indicatorApiMock.getMyIndicators.mockResolvedValue([])
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
  })

  it('loads my indicators into the strategy selector', async () => {
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
      expect(indicatorApiMock.getMyIndicators).toHaveBeenCalled()
      expect(wrapper.text()).toContain('我的RSI指标')
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
    vm.backtestForm.startDate = new Date('2025-05-27T00:00:00')
    vm.backtestForm.endDate = new Date('2026-05-27T00:00:00')

    await vm.handleStartBacktest()

    expect(indicatorApiMock.backtestIndicator).toHaveBeenCalledWith({
      indicatorId: '53',
      symbol: '600519',
      startDate: '2025-05-27',
      endDate: '2026-05-27',
      initialCash: 1000000
    })
    expect(analysisApiMock.runBacktest).not.toHaveBeenCalled()
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

  it('adds buy and sell markers to the equity chart', () => {
    const wrapper = mountBacktestCenter()
    const vm = wrapper.vm as any
    const chartEl = document.createElement('div')

    vm.equityChartRef = chartEl
    vm.backtestResult = vm.normalizeBacktestResult({
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
    expect(option.title.text).toBe('资产权益曲线')
    expect(option.series[0].name).toBe('资产权益')
    expect(option.series[0].markPoint.data).toEqual([
      expect.objectContaining({ name: '买入', coord: ['2025-08-28', 1000000] }),
      expect.objectContaining({ name: '卖出', coord: ['2025-09-12', 985170] })
    ])
  })
})
