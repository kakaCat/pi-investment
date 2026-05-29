import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn()
}))

vi.mock('@/services/api/client', () => ({
  apiClient: apiClientMock
}))

vi.mock('@/services/api/trading', () => ({
  tradingApi: {
    getPortfolioSummary: vi.fn().mockResolvedValue({
      totalValue: 100000,
      dailyChange: 100
    })
  }
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: vi.fn()
  })
}))

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
    ElMessage: {
      success: vi.fn(),
      warning: vi.fn(),
      error: vi.fn()
    }
  }
})

describe('Dashboard pending tasks', () => {
  it('normalizes paginated signal responses before mapping pending tasks', async () => {
    setActivePinia(createPinia())
    apiClientMock.get.mockImplementation((url: string) => {
      if (url === '/api/signals') {
        return Promise.resolve({
          items: [
            {
              action: 'buy',
              symbol: '600519',
              reason: '突破均线',
              confidence: 0.82,
              signalDate: '2026-05-27'
            }
          ]
        })
      }
      if (url === '/api/portfolio/history') {
        return Promise.resolve({ history: [] })
      }
      return Promise.resolve({})
    })

    const { default: Dashboard } = await import('@/views/Dashboard/index.vue')
    const wrapper = mount(Dashboard, {
      global: {
        stubs: {
          'el-icon': true,
          'el-row': { template: '<div><slot /></div>' },
          'el-col': { template: '<div><slot /></div>' },
          'el-card': { template: '<section><slot name="header" /><slot /></section>' },
          'el-table': { props: ['data'], template: '<div><slot /></div>' },
          'el-table-column': true,
          'el-button': { template: '<button><slot /></button>' },
          'el-timeline': { template: '<div><slot /></div>' },
          'el-timeline-item': { template: '<div><slot /></div>' }
        }
      }
    })

    await vi.waitFor(() => {
      expect((wrapper.vm as any).pendingSignals).toBe(1)
    })
    expect((wrapper.vm as any).pendingTasks[0]).toMatchObject({
      type: '买入申请',
      symbol: '600519',
      description: '突破均线',
      confidence: 82
    })
  })
})
