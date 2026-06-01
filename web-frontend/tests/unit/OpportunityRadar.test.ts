import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import OpportunityRadar from '@/views/OpportunityRadar/index.vue'

const analysisApiMock = vi.hoisted(() => ({
  getOpportunities: vi.fn(),
  scanOpportunities: vi.fn()
}))

const strategyApiMock = vi.hoisted(() => ({
  getStrategies: vi.fn()
}))

const tradingApiMock = vi.hoisted(() => ({
  createOrder: vi.fn()
}))

const pollingMock = vi.hoisted(() => vi.fn())

vi.mock('@/services/api/analysis', () => ({
  analysisApi: analysisApiMock
}))

vi.mock('@/services/api/strategy', () => ({
  strategyApi: strategyApiMock
}))

vi.mock('@/services/api/trading', () => ({
  tradingApi: tradingApiMock
}))

vi.mock('@/composables/usePolling', () => ({
  usePolling: pollingMock
}))

describe('OpportunityRadar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    analysisApiMock.getOpportunities.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      pageSize: 10,
      totalPages: 0
    })
    analysisApiMock.scanOpportunities.mockResolvedValue({
      success: true,
      scanMode: 'score',
      opportunities: [],
      total: 0,
      scanned: 0
    })
    strategyApiMock.getStrategies.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      pageSize: 200,
      totalPages: 0
    })
  })

  const mountRadar = () => mount(OpportunityRadar, {
    global: {
      stubs: {
        'el-card': { template: '<section><slot name="header" /><slot /></section>' },
        'el-button': { template: '<button type="button" @click="$emit(`click`)"><slot /></button>' },
        'el-row': { template: '<div><slot /></div>' },
        'el-col': { template: '<div><slot /></div>' },
        'el-form-item': { props: ['label'], template: '<label>{{ label }}<slot /></label>' },
        'el-select': { template: '<select><slot /></select>' },
        'el-option': { props: ['label'], template: '<option>{{ label }}</option>' },
        'el-checkbox': { template: '<label><input type="checkbox" /><slot /></label>' },
        'el-slider': true,
        'el-tag': { template: '<span><slot /></span>' },
        'el-rate': true,
        'el-progress': true,
        'el-empty': true,
        'el-dialog': { template: '<div><slot /><slot name="footer" /></div>' },
        'el-input': true,
        'el-input-number': true,
        'el-radio-group': { template: '<div><slot /></div>' },
        'el-radio': { template: '<label><slot /></label>' },
        'el-icon': true
      }
    }
  })

  it('loads opportunities once on mount without starting polling', async () => {
    mountRadar()

    await vi.waitFor(() => {
      expect(strategyApiMock.getStrategies).toHaveBeenCalledWith({ page: 1, pageSize: 200 })
      expect(analysisApiMock.getOpportunities).toHaveBeenCalledTimes(1)
    })

    expect(pollingMock).not.toHaveBeenCalled()
  })

  it('shows strategy names together with ids in the scan selector', async () => {
    strategyApiMock.getStrategies.mockResolvedValueOnce({
      items: [
        {
          id: '193',
          name: '趋势突破策略'
        },
        {
          id: '199',
          name: null,
          description: 'v11：趋势突破策略，趋势过滤 + 冷却期'
        },
        {
          id: '200',
          name: null,
          description: '',
          code: '# v12: 均线回归策略\nsignal = true'
        }
      ],
      total: 3,
      page: 1,
      pageSize: 200,
      totalPages: 1
    })

    const wrapper = mountRadar()

    await vi.waitFor(() => {
      expect(wrapper.text()).toContain('趋势突破策略 #193')
      expect(wrapper.text()).toContain('v11：趋势突破策略，趋势过滤 + 冷却期 #199')
      expect(wrapper.text()).toContain('v12: 均线回归策略 #200')
    })
  })
})
