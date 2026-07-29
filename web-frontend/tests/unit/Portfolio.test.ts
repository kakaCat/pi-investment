import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent } from 'vue'

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn()
}))

vi.mock('@/services/api/client', () => ({ apiClient: apiClientMock }))

vi.mock('@/composables/useWebSocket', () => ({
  useMarketWebSocket: () => ({
    subscribe: vi.fn(),
    unsubscribe: vi.fn(),
    on: vi.fn()
  })
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useRoute: () => ({ query: {} })
}))

// AccountSwitcher 打桩：挂载即触发 change，模拟用户选中账户
vi.mock('@/components/AccountSwitcher.vue', () => ({
  default: defineComponent({
    emits: ['change'],
    mounted() {
      this.$emit('change', 'v13_simulation', { account_name: 'v13_simulation' })
    },
    template: '<div class="account-switcher-stub" />'
  })
}))

import PortfolioPage from '@/views/Portfolio/index.vue'

describe('Portfolio 页面多账户', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setActivePinia(createPinia())
    apiClientMock.get.mockImplementation((url: string) => {
      if (url === '/api/portfolio/summary') return Promise.resolve({ totalValue: 1, positions: 0, cash: 0 })
      if (url === '/api/portfolio/positions') return Promise.resolve({ positions: [], count: 0 })
      return Promise.resolve([])
    })
  })

  it('账户切换后按账户加载持仓与汇总', async () => {
    mount(PortfolioPage, {
      global: {
        stubs: {
          'el-table': { props: ['data'], template: '<div><slot /></div>' },
          'el-table-column': true
        }
      }
    })
    await new Promise(r => setTimeout(r, 0))
    const portfolioCalls = apiClientMock.get.mock.calls.filter(c =>
      String(c[0]).startsWith('/api/portfolio/'))
    expect(portfolioCalls.length).toBeGreaterThanOrEqual(2)
    for (const call of portfolioCalls) {
      expect(call[1]).toEqual({ params: { account_name: 'v13_simulation' } })
    }
  })
})
