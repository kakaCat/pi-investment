import { describe, it, expect, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import SignalCard from '@/components/trading/SignalCard.vue'
import type { TradingSignal } from '@/types/models'

// Mock Element Plus components
const mockElCard = {
  name: 'ElCard',
  template: '<div class="el-card"><slot name="header"></slot><slot></slot><slot name="footer"></slot></div>'
}

const mockElTag = {
  name: 'ElTag',
  template: '<span class="el-tag"><slot></slot></span>',
  props: ['type', 'size']
}

const mockElProgress = {
  name: 'ElProgress',
  template: '<div class="el-progress"></div>',
  props: ['percentage', 'color', 'strokeWidth']
}

const mockElButton = {
  name: 'ElButton',
  template: '<button class="el-button"><slot></slot></button>',
  props: ['type', 'icon']
}

const mockElCollapse = {
  name: 'ElCollapse',
  template: '<div class="el-collapse"><slot></slot></div>'
}

const mockElCollapseItem = {
  name: 'ElCollapseItem',
  template: '<div class="el-collapse-item"><slot></slot></div>',
  props: ['title', 'name']
}

describe('SignalCard.vue', () => {
  let mockSignal: TradingSignal

  beforeEach(() => {
    mockSignal = {
      id: '1',
      type: 'buy',
      symbol: '600000',
      symbolName: '浦发银行',
      price: 10.5,
      confidence: 0.85,
      operator: 'agent',
      status: 'pending',
      createdAt: '2024-01-01T12:00:00Z',
      reasons: ['技术指标看涨', '资金流入明显'],
      analysis: {
        technical: {
          rsi: 65.5,
          macd: {
            value: 0.15,
            signal: 0.12,
            histogram: 0.03
          },
          ma: {
            ma5: 10.2,
            ma10: 10.0,
            ma20: 9.8,
            ma60: 9.5
          }
        },
        fundamental: {
          pe: 8.5,
          roe: 0.12,
          grossMargin: 0.35
        },
        sentiment: {
          fundFlow: 50000000,
          dragonTiger: true
        }
      }
    } as TradingSignal
  })

  const createWrapper = (signal: TradingSignal) => {
    return mount(SignalCard, {
      props: { signal },
      global: {
        components: {
          ElCard: mockElCard,
          ElTag: mockElTag,
          ElProgress: mockElProgress,
          ElButton: mockElButton,
          ElCollapse: mockElCollapse,
          ElCollapseItem: mockElCollapseItem
        }
      }
    })
  }

  describe('Rendering', () => {
    it('should render signal card', () => {
      const wrapper = createWrapper(mockSignal)
      expect(wrapper.find('.signal-card').exists()).toBe(true)
    })

    it('should display buy signal correctly', () => {
      const wrapper = createWrapper(mockSignal)
      expect(wrapper.text()).toContain('买入')
      expect(wrapper.find('.signal-buy').exists()).toBe(true)
    })

    it('should display sell signal correctly', () => {
      const sellSignal = { ...mockSignal, type: 'sell' }
      const wrapper = createWrapper(sellSignal)
      expect(wrapper.text()).toContain('卖出')
      expect(wrapper.find('.signal-sell').exists()).toBe(true)
    })

    it('should display symbol and name', () => {
      const wrapper = createWrapper(mockSignal)
      expect(wrapper.text()).toContain('600000')
      expect(wrapper.text()).toContain('浦发银行')
    })

    it('should display price', () => {
      const wrapper = createWrapper(mockSignal)
      expect(wrapper.text()).toContain('10.50')
    })

    it('should display operator', () => {
      const wrapper = createWrapper(mockSignal)
      expect(wrapper.text()).toContain('Agent')
    })

    it('should display manual operator', () => {
      const manualSignal = { ...mockSignal, operator: 'manual' }
      const wrapper = createWrapper(manualSignal)
      expect(wrapper.text()).toContain('手动')
    })
  })

  describe('Status Display', () => {
    it('should display pending status', () => {
      const wrapper = createWrapper(mockSignal)
      expect(wrapper.text()).toContain('待处理')
    })

    it('should display approved status', () => {
      const approvedSignal = { ...mockSignal, status: 'approved' }
      const wrapper = createWrapper(approvedSignal)
      expect(wrapper.text()).toContain('已批准')
    })

    it('should display rejected status', () => {
      const rejectedSignal = { ...mockSignal, status: 'rejected' }
      const wrapper = createWrapper(rejectedSignal)
      expect(wrapper.text()).toContain('已拒绝')
    })

    it('should display executed status', () => {
      const executedSignal = { ...mockSignal, status: 'executed' }
      const wrapper = createWrapper(executedSignal)
      expect(wrapper.text()).toContain('已执行')
    })
  })

  describe('Reasons Section', () => {
    it('should display reasons when available', () => {
      const wrapper = createWrapper(mockSignal)
      expect(wrapper.text()).toContain('信号原因')
      expect(wrapper.text()).toContain('技术指标看涨')
      expect(wrapper.text()).toContain('资金流入明显')
    })

    it('should not display reasons section when empty', () => {
      const signalWithoutReasons = { ...mockSignal, reasons: [] }
      const wrapper = createWrapper(signalWithoutReasons)
      expect(wrapper.text()).not.toContain('信号原因')
    })
  })

  describe('Analysis Section', () => {
    it('should display technical analysis', () => {
      const wrapper = createWrapper(mockSignal)
      expect(wrapper.text()).toContain('技术指标')
      expect(wrapper.text()).toContain('RSI')
      expect(wrapper.text()).toContain('65.50')
      expect(wrapper.text()).toContain('MACD')
      expect(wrapper.text()).toContain('0.15')
    })

    it('should display fundamental analysis', () => {
      const wrapper = createWrapper(mockSignal)
      expect(wrapper.text()).toContain('基本面')
      expect(wrapper.text()).toContain('PE')
      expect(wrapper.text()).toContain('8.50')
      expect(wrapper.text()).toContain('ROE')
      expect(wrapper.text()).toContain('12.00%')
    })

    it('should display sentiment analysis', () => {
      const wrapper = createWrapper(mockSignal)
      expect(wrapper.text()).toContain('市场情绪')
      expect(wrapper.text()).toContain('资金流向')
      expect(wrapper.text()).toContain('5000.00万')
      expect(wrapper.text()).toContain('龙虎榜')
      expect(wrapper.text()).toContain('是')
    })

    it('should not display analysis section when not available', () => {
      const signalWithoutAnalysis = { ...mockSignal, analysis: undefined }
      const wrapper = createWrapper(signalWithoutAnalysis)
      expect(wrapper.find('.analysis-section').exists()).toBe(false)
    })
  })

  describe('PnL Section', () => {
    it('should display positive PnL', () => {
      const signalWithPnL = {
        ...mockSignal,
        pnl: {
          unrealizedPnL: 500,
          unrealizedPnLPercent: 0.05
        }
      }
      const wrapper = createWrapper(signalWithPnL)
      expect(wrapper.text()).toContain('未实现盈亏')
      expect(wrapper.text()).toContain('500.00')
      expect(wrapper.text()).toContain('+5.00%')
    })

    it('should display negative PnL', () => {
      const signalWithPnL = {
        ...mockSignal,
        pnl: {
          unrealizedPnL: -300,
          unrealizedPnLPercent: -0.03
        }
      }
      const wrapper = createWrapper(signalWithPnL)
      expect(wrapper.text()).toContain('-300.00')
      expect(wrapper.text()).toContain('-3.00%')
    })

    it('should not display PnL section when not available', () => {
      const wrapper = createWrapper(mockSignal)
      expect(wrapper.find('.pnl-section').exists()).toBe(false)
    })
  })

  describe('Action Buttons', () => {
    it('should show approve, reject, and verify buttons for pending status', () => {
      const wrapper = createWrapper(mockSignal)
      const buttons = wrapper.findAll('.el-button')
      expect(buttons).toHaveLength(3)
      expect(wrapper.text()).toContain('批准')
      expect(wrapper.text()).toContain('拒绝')
      expect(wrapper.text()).toContain('验证')
    })

    it('should show view detail button for approved status', () => {
      const approvedSignal = { ...mockSignal, status: 'approved' }
      const wrapper = createWrapper(approvedSignal)
      expect(wrapper.text()).toContain('查看详情')
    })

    it('should show view detail button for executed status', () => {
      const executedSignal = { ...mockSignal, status: 'executed' }
      const wrapper = createWrapper(executedSignal)
      expect(wrapper.text()).toContain('查看详情')
    })

    it('should not show action buttons for rejected status', () => {
      const rejectedSignal = { ...mockSignal, status: 'rejected' }
      const wrapper = createWrapper(rejectedSignal)
      const buttons = wrapper.findAll('.el-button')
      expect(buttons).toHaveLength(0)
    })
  })

  describe('Events', () => {
    it('should emit approve event when approve button clicked', async () => {
      const wrapper = createWrapper(mockSignal)
      const buttons = wrapper.findAll('.el-button')
      await buttons[0].trigger('click')

      expect(wrapper.emitted('approve')).toBeTruthy()
      expect(wrapper.emitted('approve')?.[0]).toEqual([mockSignal])
    })

    it('should emit reject event when reject button clicked', async () => {
      const wrapper = createWrapper(mockSignal)
      const buttons = wrapper.findAll('.el-button')
      await buttons[1].trigger('click')

      expect(wrapper.emitted('reject')).toBeTruthy()
      expect(wrapper.emitted('reject')?.[0]).toEqual([mockSignal])
    })

    it('should emit verify event when verify button clicked', async () => {
      const wrapper = createWrapper(mockSignal)
      const buttons = wrapper.findAll('.el-button')
      await buttons[2].trigger('click')

      expect(wrapper.emitted('verify')).toBeTruthy()
      expect(wrapper.emitted('verify')?.[0]).toEqual([mockSignal])
    })

    it('should emit view-detail event when view detail button clicked', async () => {
      const approvedSignal = { ...mockSignal, status: 'approved' }
      const wrapper = createWrapper(approvedSignal)
      const button = wrapper.find('.el-button')
      await button.trigger('click')

      expect(wrapper.emitted('view-detail')).toBeTruthy()
      expect(wrapper.emitted('view-detail')?.[0]).toEqual([approvedSignal])
    })
  })

  describe('CSS Classes', () => {
    it('should apply correct class for buy signal', () => {
      const wrapper = createWrapper(mockSignal)
      expect(wrapper.find('.signal-buy').exists()).toBe(true)
    })

    it('should apply correct class for sell signal', () => {
      const sellSignal = { ...mockSignal, type: 'sell' }
      const wrapper = createWrapper(sellSignal)
      expect(wrapper.find('.signal-sell').exists()).toBe(true)
    })

    it('should apply status class', () => {
      const wrapper = createWrapper(mockSignal)
      expect(wrapper.find('.status-pending').exists()).toBe(true)
    })
  })

  describe('Helper Functions', () => {
    it('should get correct status type', () => {
      const wrapper = createWrapper(mockSignal)
      const vm = wrapper.vm as any

      expect(vm.getStatusType('pending')).toBe('warning')
      expect(vm.getStatusType('approved')).toBe('success')
      expect(vm.getStatusType('rejected')).toBe('danger')
      expect(vm.getStatusType('executed')).toBe('info')
      expect(vm.getStatusType('unknown')).toBe('info')
    })

    it('should get correct status text', () => {
      const wrapper = createWrapper(mockSignal)
      const vm = wrapper.vm as any

      expect(vm.getStatusText('pending')).toBe('待处理')
      expect(vm.getStatusText('approved')).toBe('已批准')
      expect(vm.getStatusText('rejected')).toBe('已拒绝')
      expect(vm.getStatusText('executed')).toBe('已执行')
      expect(vm.getStatusText('unknown')).toBe('unknown')
    })

    it('should get correct confidence color', () => {
      const wrapper = createWrapper(mockSignal)
      const vm = wrapper.vm as any

      expect(vm.getConfidenceColor(0.9)).toBe('#52c41a')
      expect(vm.getConfidenceColor(0.7)).toBe('#faad14')
      expect(vm.getConfidenceColor(0.5)).toBe('#f5222d')
    })
  })
})
