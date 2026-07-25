import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { apiClient } from '@/services/api/client'
import AccountSwitcher from '@/components/AccountSwitcher.vue'
import SimulationTrading from '@/views/SimulationTrading/index.vue'

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  useRouter: () => ({ back: vi.fn() })
}))

vi.mock('echarts', () => ({
  init: () => ({ setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn() })
}))

// 调度任务 / 股票名称等原始 fetch 一律打桩
global.fetch = vi.fn().mockResolvedValue({
  json: () => Promise.resolve({ success: true, data: [] })
} as any)

vi.stubEnv('VITE_ENABLE_PERFORMANCE_MONITOR', 'false')

/**
 * 与 quantsys-v2 (5001) 实际返回一致的信封。
 * apiClient 响应拦截器会把 { success, data } 解包成内层 data，
 * 调用方拿到的是解包后的载荷 —— 本文件用真实拦截器验证这条链路。
 */
const BACKEND_ACCOUNTS = [
  { account_name: 'v13_simulation', display_name: 'V13 多因子模拟仓', strategy_name: 'v13', status: 'active', cash_available: 110030.89, cash_frozen: 0, position_value: 38990, total_value: 149020.89, cumulative_return: 0.4903, positions_count: 1 },
  { account_name: 'v14_simulation', display_name: 'V14 模拟仓', strategy_name: 'v14', status: 'active', cash_available: 101873.02, cash_frozen: 0, position_value: 45204, total_value: 147077.02, cumulative_return: 0.4708, positions_count: 5 }
]

const BACKEND_ACCOUNT_STATUS = {
  account_name: 'v13_simulation', display_name: 'V13 多因子模拟仓', strategy_name: 'v13',
  cash_available: 110030.89, cash_frozen: 0, position_value: 38990, total_value: 149020.89,
  initial_capital: 99993.81, cumulative_return: 0.4903, last_rebalance_date: '2026-07-17',
  positions_count: 1,
  positions: [{ symbol: '601888', shares_total: 700, shares_available: 700, avg_cost: 52.87, current_price: 55.7, market_value: 38990, profit_total: 33721, profit_total_rate: 0.65, profit_today: 100 }]
}

function envelope(data: any) {
  return { status: 200, data: { success: true, data } }
}

type TransportHandler = (config: any) => { status: number; data: any }

/** 只打桩 HTTP 传输层，保留 apiClient 真实拦截器（解包逻辑） */
function stubTransport(handler: TransportHandler) {
  const instance = (apiClient as any).instance
  const original = instance.defaults.adapter
  instance.defaults.adapter = (config: any) => {
    const { status, data } = handler(config)
    if (status >= 400) {
      return Promise.reject({
        config,
        message: `Request failed with status code ${status}`,
        response: { status, statusText: '', headers: {}, config, data }
      })
    }
    return Promise.resolve({ data, status, statusText: 'OK', headers: {}, config })
  }
  return () => { instance.defaults.adapter = original }
}

function pageTransport(config: any) {
  const url: string = config.url || ''
  if (url === '/api/simulation/accounts') return envelope({ accounts: BACKEND_ACCOUNTS, total: 2 })
  if (url === '/api/simulation/accounts/v13_simulation') return envelope(BACKEND_ACCOUNT_STATUS)
  if (url === '/api/simulation/trades') return envelope([])
  if (url === '/api/simulation/execution-history') return envelope([])
  if (url === '/api/simulation/performance') return envelope({ equity_curve: [], initial_capital: 99993.81, current_value: 149020.89, cumulative_return: 0.4903, max_drawdown: -0.05 })
  if (url === '/api/simulation/strategies/v13') return envelope({ name: 'V13', version: '1.0.0', rebalance_days: 5, max_positions: 8 })
  throw new Error(`unexpected request: ${url}`)
}

const pageStubs = {
  'el-table': { template: '<div class="el-table"><slot /></div>', props: ['data', 'stripe'] },
  'el-table-column': { template: '<div class="el-table-column">{{ label }}</div>', props: ['prop', 'label', 'width', 'align'] }
}

describe('信封解包契约（真实 apiClient 拦截器 + 真实 simulationApi）', () => {
  let restore: () => void

  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    restore?.()
  })

  it('AccountSwitcher 加载账户列表并默认选中首个账户', async () => {
    restore = stubTransport(() => envelope({ accounts: BACKEND_ACCOUNTS, total: 2 }))
    const wrapper = mount(AccountSwitcher)
    await flushPromises()
    await nextTick()

    expect(wrapper.vm.selected).toBe('v13_simulation')
    expect(wrapper.emitted('change')?.[0]).toEqual(['v13_simulation', BACKEND_ACCOUNTS[0]])
    expect(ElMessage.error).not.toHaveBeenCalled()
  })

  it('账户列表接口失败时提示"加载账户列表失败"', async () => {
    restore = stubTransport(() => ({ status: 500, data: { success: false, error: 'db down' } }))
    mount(AccountSwitcher)
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('加载账户列表失败')
  })

  it('SimulationTrading 首载渲染账户资产，不报"加载账户失败"', async () => {
    restore = stubTransport(pageTransport)
    const wrapper = mount(SimulationTrading, { global: { stubs: pageStubs } })
    await flushPromises()
    await nextTick()

    expect(wrapper.vm.selectedAccount).toBe('v13_simulation')
    expect(wrapper.text()).toContain('149,020.89')
    expect(ElMessage.error).not.toHaveBeenCalledWith(expect.stringContaining('加载账户失败'))
  })
})
