import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import PoolDetail from '@/views/PoolDetail/index.vue'

const pushMock = vi.hoisted(() => vi.fn())
const poolApiMock = vi.hoisted(() => ({
  getById: vi.fn(),
  refresh: vi.fn(),
  validate: vi.fn(),
  update: vi.fn(),
  delete: vi.fn(),
  syncStockNames: vi.fn(),
  scanSignals: vi.fn()
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
      },
      last_signal_scan: {
        buy_signals: [],
        sell_signals: [],
        hold_signals: [],
        errors: [],
        scanned_at: '2026-06-05T09:30:00',
        summary: { buy: 0, sell: 0, hold: 2, error: 0 }
      }
    })
  })

  const mountPoolDetail = () => mount(PoolDetail, {
    global: {
      stubs: {
        'el-page-header': { template: '<header><slot name="content" /><slot name="extra" /></header>' },
        'el-button': { props: ['loading'], emits: ['click'], template: '<button type="button" :data-loading="loading ? `true` : `false`" @click="$emit(`click`)"><slot /></button>' },
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
      { index: 1, symbol: '300750', name: '宁德时代', description: undefined, buy_point: undefined, sell_point: undefined, tags: [] },
      { index: 2, symbol: '688981', name: '中芯国际', description: undefined, buy_point: undefined, sell_point: undefined, tags: [] }
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

  it('syncs stock names and reloads pool detail', async () => {
    poolApiMock.syncStockNames.mockResolvedValue({ success: true })
    const wrapper = mountPoolDetail()

    await vi.waitFor(() => {
      expect(poolApiMock.getById).toHaveBeenCalledWith(4)
    })

    const syncButton = wrapper.findAll('button').find(button => button.text().includes('同步股票名称'))
    expect(syncButton).toBeTruthy()
    await syncButton!.trigger('click')

    await vi.waitFor(() => {
      expect(poolApiMock.syncStockNames).toHaveBeenCalledWith(4)
      expect(poolApiMock.getById).toHaveBeenCalledTimes(2)
    })
  })

  it('updates buy and sell signal data after a rescan', async () => {
    poolApiMock.scanSignals.mockResolvedValue({
      buy_signals: [
        {
          symbol: '300750',
          current_price: 180,
          trade_params: { stop_loss: 174.6, take_profit: 194.4, suggested_position: 0.2 },
          reasons: ['RSI超卖反弹'],
          trade_date: '2026-06-06'
        }
      ],
      sell_signals: [],
      hold_signals: [],
      errors: [],
      scanned_at: '2026-06-06T10:00:00',
      summary: { buy: 1, sell: 0, hold: 0, error: 0 }
    })
    const wrapper = mountPoolDetail()

    await vi.waitFor(() => {
      expect(poolApiMock.getById).toHaveBeenCalledWith(4)
    })

    expect((wrapper.vm as any).buySignalRows).toEqual([])

    await (wrapper.vm as any).handleScanSignals()

    await vi.waitFor(() => {
      expect(poolApiMock.scanSignals).toHaveBeenCalledWith(4, { strategy_id: 272 })
      expect((wrapper.vm as any).buySignalRows).toEqual([
        {
          symbol: '300750',
          name: '宁德时代',
          current_price: 180,
          trade_params: { stop_loss: 174.6, take_profit: 194.4, suggested_position: 0.2 },
          reasons: ['RSI超卖反弹'],
          trade_date: '2026-06-06'
        }
      ])
    })
  })
})
