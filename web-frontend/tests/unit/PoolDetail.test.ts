import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import PoolDetail from '@/views/PoolDetail/index.vue'

const pushMock = vi.hoisted(() => vi.fn())
const poolApiMock = vi.hoisted(() => ({
  getById: vi.fn(),
  refresh: vi.fn(),
  validate: vi.fn(),
  update: vi.fn(),
  delete: vi.fn()
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: pushMock }),
  useRoute: () => ({ params: { id: '4' } })
}))

vi.mock('@/services/api', () => ({
  poolApi: poolApiMock
}))

vi.mock('element-plus', async () => {
  const actual = await vi.importActual<typeof import('element-plus')>('element-plus')
  return {
    ...actual,
    ElMessage: {
      success: vi.fn(),
      error: vi.fn()
    },
    ElMessageBox: {
      confirm: vi.fn(() => Promise.resolve())
    },
    ElLoading: {
      service: vi.fn(() => ({ close: vi.fn() }))
    }
  }
})

describe('PoolDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    poolApiMock.getById.mockResolvedValue({
      id: 4,
      name: 'GridPro_HighVol_Pool',
      pool_type: 'static',
      symbols: ['300750', '688981'],
      members: [
        { symbol: '300750', name: '宁德时代' },
        { symbol: '688981', name: '中芯国际' }
      ],
      last_validation: {
        recommended_pairs: [
          { symbol: '300750', expected_return: 6.51, win_rate: 50, sharpe: 2.38 },
          { symbol: '688981', expected_return: 5.64, win_rate: 53, sharpe: 0.85 }
        ]
      }
    })
  })

  const mountPoolDetail = () => mount(PoolDetail, {
    global: {
      stubs: {
        'el-page-header': { template: '<header><slot name="content" /><slot name="extra" /></header>' },
        'el-button': { template: '<button type="button"><slot /></button>' },
        'el-tag': { template: '<span><slot /></span>' },
        'el-descriptions': { template: '<dl><slot /></dl>' },
        'el-descriptions-item': { props: ['label'], template: '<dd>{{ label }}<slot /></dd>' },
        'el-tabs': { template: '<div><slot /></div>' },
        'el-tab-pane': { template: '<section><slot /></section>' },
        'el-table': { props: ['data'], template: '<table><slot /></table>' },
        'el-table-column': { props: ['label'], template: '<th>{{ label }}</th>' },
        'el-empty': { template: '<div><slot /></div>' },
        'el-card': { template: '<section><slot /></section>' },
        'el-row': { template: '<div><slot /></div>' },
        'el-col': { template: '<div><slot /></div>' },
        'el-progress': true,
        'el-dialog': { template: '<div><slot /><slot name="footer" /></div>' },
        'el-form': { template: '<form><slot /></form>' },
        'el-form-item': { template: '<label><slot /></label>' },
        'el-input': true,
        'el-date-picker': true
      }
    }
  })

  it('shows a stock name column for pool members', async () => {
    const wrapper = mountPoolDetail()

    await vi.waitFor(() => {
      expect(poolApiMock.getById).toHaveBeenCalledWith(4)
    })

    expect(wrapper.text()).toContain('股票名称')
    expect((wrapper.vm as any).memberRows).toEqual([
      { index: 1, symbol: '300750', name: '宁德时代' },
      { index: 2, symbol: '688981', name: '中芯国际' }
    ])
  })

  it('adds stock names to recommended pairs', async () => {
    const wrapper = mountPoolDetail()

    await vi.waitFor(() => {
      expect(poolApiMock.getById).toHaveBeenCalledWith(4)
    })

    expect((wrapper.vm as any).recommendedPairRows).toEqual([
      { symbol: '300750', name: '宁德时代', expected_return: 6.51, win_rate: 50, sharpe: 2.38 },
      { symbol: '688981', name: '中芯国际', expected_return: 5.64, win_rate: 53, sharpe: 0.85 }
    ])
  })
})
