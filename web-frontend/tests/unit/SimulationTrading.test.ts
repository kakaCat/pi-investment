import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import SimulationTrading from '@/views/SimulationTrading/index.vue'

const simulationApiMock = vi.hoisted(() => ({
  listAccounts: vi.fn(),
  getAccount: vi.fn(),
  getTrades: vi.fn(),
  getPerformance: vi.fn(),
  getExecutionHistory: vi.fn(),
  getStrategyInfo: vi.fn(),
  runStrategy: vi.fn(),
  trade: vi.fn(),
  createAccount: vi.fn()
}))

vi.mock('@/services/api/simulation', () => ({ simulationApi: simulationApiMock }))

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ back: vi.fn() })
}))

vi.mock('echarts', () => ({
  init: () => ({ setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn() })
}))

// 调度任务等原始 fetch 一律打桩
global.fetch = vi.fn().mockResolvedValue({
  json: () => Promise.resolve({ success: true, data: [] })
} as any)

// Element Plus 重组件打桩（仓库测试惯例）
const globalStubs = {
  'el-table': { template: '<div class="el-table"><slot /></div>', props: ['data', 'stripe'] },
  'el-table-column': { template: '<div class="el-table-column">{{ label }}</div>', props: ['prop', 'label', 'width', 'align'] }
}

function mountPage() {
  return mount(SimulationTrading, { global: { stubs: globalStubs } })
}

const ACCOUNT_STATUS = {
  account_name: 'v13_simulation', display_name: 'V13 多因子模拟仓', strategy_name: 'v13',
  cash_available: 110030.89, cash_frozen: 0, position_value: 38255, total_value: 148285.89,
  initial_capital: 99993.81, cumulative_return: 0.483, last_rebalance_date: '2026-07-13',
  positions_count: 1,
  positions: [{ symbol: '601888', shares_total: 700, shares_available: 700, avg_cost: 52.87, current_price: 54.65, market_value: 38255, profit_total: 1246, profit_total_rate: 0.0337, profit_today: 100 }]
}

// apiClient 拦截器已解包信封，mock 直接返回内层载荷
const ACCOUNT_LIST = { accounts: [
  { account_name: 'v13_simulation', display_name: 'V13', strategy_name: 'v13', status: 'active', cash_available: 0, cash_frozen: 0, position_value: 0, total_value: 148285, cumulative_return: 0.48, positions_count: 1 },
  { account_name: 'v14_simulation', display_name: 'V14', strategy_name: 'v14', status: 'active', cash_available: 0, cash_frozen: 0, position_value: 0, total_value: 144859, cumulative_return: 0.45, positions_count: 5 }
], total: 2 }

describe('SimulationTrading 统一账户页', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    simulationApiMock.listAccounts.mockResolvedValue(ACCOUNT_LIST)
    simulationApiMock.getAccount.mockResolvedValue(ACCOUNT_STATUS)
    simulationApiMock.getTrades.mockResolvedValue([])
    simulationApiMock.getPerformance.mockResolvedValue({ equity_curve: [], initial_capital: 100000, current_value: 148285, cumulative_return: 48.3, max_drawdown: -5 })
    simulationApiMock.getExecutionHistory.mockResolvedValue([])
    simulationApiMock.getStrategyInfo.mockResolvedValue({ name: 'V13', version: '1.0.0', rebalance_days: 5, max_positions: 8 })
  })

  it('首载后所有数据请求携带默认账户 account_name', async () => {
    mountPage()
    await nextTick(); await nextTick(); await nextTick(); await nextTick()
    expect(simulationApiMock.getAccount).toHaveBeenCalledWith('v13_simulation')
    expect(simulationApiMock.getTrades).toHaveBeenCalledWith('v13_simulation', 50)
    expect(simulationApiMock.getPerformance).toHaveBeenCalledWith('v13_simulation')
  })

  it('切换账户后所有数据请求携带新 account_name', async () => {
    const wrapper = mountPage()
    await nextTick(); await nextTick(); await nextTick(); await nextTick()
    await wrapper.vm.onAccountChange('v14_simulation', { account_name: 'v14_simulation', strategy_name: 'v14' })
    await nextTick(); await nextTick()
    expect(simulationApiMock.getAccount).toHaveBeenCalledWith('v14_simulation')
    expect(simulationApiMock.getTrades).toHaveBeenCalledWith('v14_simulation', 50)
    expect(simulationApiMock.getPerformance).toHaveBeenCalledWith('v14_simulation')
    expect(simulationApiMock.getStrategyInfo).toHaveBeenCalledWith('v14')
  })

  it('执行策略时携带 account_name', async () => {
    simulationApiMock.runStrategy.mockResolvedValue({ action: 'skip', message: 'no rebalance' })
    const wrapper = mountPage()
    await nextTick(); await nextTick(); await nextTick(); await nextTick()
    await wrapper.vm.runStrategy()
    expect(simulationApiMock.runStrategy).toHaveBeenCalledWith('v13', 'v13_simulation')
  })

  it('账户无绑定策略时 hasStrategy 为 false', async () => {
    const wrapper = mountPage()
    await nextTick(); await nextTick(); await nextTick(); await nextTick()
    await wrapper.vm.onAccountChange('manual_test', { account_name: 'manual_test', strategy_name: null })
    await nextTick()
    expect(wrapper.vm.hasStrategy).toBe(false)
  })
})
