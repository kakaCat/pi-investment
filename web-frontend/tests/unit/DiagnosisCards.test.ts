/**
 * 测试 DiagnosisCards 组件
 */
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import DiagnosisCards from '@/views/BacktestCenter/DiagnosisCards.vue'

describe('DiagnosisCards', () => {
  const mockProps = {
    metrics: {
      annualReturn: 0.15,
      sharpeRatio: 1.8,
      maxDrawdown: -0.12,
      winRate: 0.65,
      totalTrades: 50
    },
    benchmark: {
      name: '沪深300',
      annualReturn: 0.08,
      sharpeRatio: 1.2,
      maxDrawdown: -0.18
    },
    ratings: {
      overall: 'A' as const,
      return: 'excellent',
      risk: 'low',
      stability: 'excellent'
    }
  }

  describe('Component Rendering', () => {
    it('renders 4 metric cards', () => {
      const wrapper = mount(DiagnosisCards, { props: mockProps })
      const cards = wrapper.findAll('.metric-card')
      expect(cards).toHaveLength(4)
    })

    it('renders annual return card with correct value', () => {
      const wrapper = mount(DiagnosisCards, { props: mockProps })
      expect(wrapper.text()).toContain('年化收益')
      expect(wrapper.text()).toContain('+15.00%')
    })

    it('renders sharpe ratio card with correct value', () => {
      const wrapper = mount(DiagnosisCards, { props: mockProps })
      expect(wrapper.text()).toContain('夏普比率')
      expect(wrapper.text()).toContain('1.80')
    })

    it('renders max drawdown card with correct value', () => {
      const wrapper = mount(DiagnosisCards, { props: mockProps })
      expect(wrapper.text()).toContain('最大回撤')
      expect(wrapper.text()).toContain('-12.00%')
    })

    it('renders rating card with correct grade', () => {
      const wrapper = mount(DiagnosisCards, { props: mockProps })
      expect(wrapper.text()).toContain('综合评级')
      expect(wrapper.text()).toContain('A')
      expect(wrapper.text()).toContain('优秀')
    })

    it('displays benchmark values for all metrics', () => {
      const wrapper = mount(DiagnosisCards, { props: mockProps })
      const benchmarkTexts = wrapper.findAll('.benchmark')
      expect(benchmarkTexts).toHaveLength(3) // 3 metric cards have benchmarks
      expect(wrapper.text()).toContain('基准: +8.00%')
      expect(wrapper.text()).toContain('基准: 1.20')
      expect(wrapper.text()).toContain('基准: -18.00%')
    })
  })

  describe('Format Functions', () => {
    it('formatPercent adds + sign for positive values', () => {
      const wrapper = mount(DiagnosisCards, { props: mockProps })
      const vm = wrapper.vm as any
      expect(vm.formatPercent(0.15)).toBe('+15.00%')
      expect(vm.formatPercent(0.0825)).toBe('+8.25%')
    })

    it('formatPercent keeps - sign for negative values', () => {
      const wrapper = mount(DiagnosisCards, { props: mockProps })
      const vm = wrapper.vm as any
      expect(vm.formatPercent(-0.12)).toBe('-12.00%')
      expect(vm.formatPercent(-0.0567)).toBe('-5.67%')
    })

    it('formatPercent handles zero correctly', () => {
      const wrapper = mount(DiagnosisCards, { props: mockProps })
      const vm = wrapper.vm as any
      expect(vm.formatPercent(0)).toBe('+0.00%')
    })

    it('getSharpeColor returns correct class for excellent sharpe', () => {
      const wrapper = mount(DiagnosisCards, { props: mockProps })
      const vm = wrapper.vm as any
      expect(vm.getSharpeColor(1.8)).toBe('text-excellent')
      expect(vm.getSharpeColor(2.5)).toBe('text-excellent')
    })

    it('getSharpeColor returns correct class for good sharpe', () => {
      const wrapper = mount(DiagnosisCards, { props: mockProps })
      const vm = wrapper.vm as any
      expect(vm.getSharpeColor(1.2)).toBe('text-good')
      expect(vm.getSharpeColor(1.0)).toBe('text-good')
    })

    it('getSharpeColor returns correct class for moderate sharpe', () => {
      const wrapper = mount(DiagnosisCards, { props: mockProps })
      const vm = wrapper.vm as any
      expect(vm.getSharpeColor(0.8)).toBe('text-moderate')
      expect(vm.getSharpeColor(0.5)).toBe('text-moderate')
    })

    it('getSharpeColor returns correct class for poor sharpe', () => {
      const wrapper = mount(DiagnosisCards, { props: mockProps })
      const vm = wrapper.vm as any
      expect(vm.getSharpeColor(0.3)).toBe('text-poor')
      expect(vm.getSharpeColor(-0.5)).toBe('text-poor')
    })

    it('getRatingText maps ratings correctly', () => {
      const wrapper = mount(DiagnosisCards, { props: mockProps })
      const vm = wrapper.vm as any
      expect(vm.getRatingText('A')).toBe('优秀')
      expect(vm.getRatingText('B')).toBe('良好')
      expect(vm.getRatingText('C')).toBe('一般')
      expect(vm.getRatingText('D')).toBe('较差')
    })

    it('getRatingText returns original value for unknown rating', () => {
      const wrapper = mount(DiagnosisCards, { props: mockProps })
      const vm = wrapper.vm as any
      expect(vm.getRatingText('X')).toBe('X')
    })
  })

  describe('Visual Indicators', () => {
    it('shows up icon and green color for positive annual return', () => {
      const wrapper = mount(DiagnosisCards, { props: mockProps })
      const annualReturnCard = wrapper.findAll('.metric-card')[0]
      expect(annualReturnCard.html()).toContain('text-up')
    })

    it('shows down icon and red color for negative annual return', () => {
      const negativeProps = {
        ...mockProps,
        metrics: { ...mockProps.metrics, annualReturn: -0.05 }
      }
      const wrapper = mount(DiagnosisCards, { props: negativeProps })
      const annualReturnCard = wrapper.findAll('.metric-card')[0]
      expect(annualReturnCard.html()).toContain('text-down')
    })

    it('shows warning text when sharpe ratio < 1.0', () => {
      const lowSharpeProps = {
        ...mockProps,
        metrics: { ...mockProps.metrics, sharpeRatio: 0.8 }
      }
      const wrapper = mount(DiagnosisCards, { props: lowSharpeProps })
      expect(wrapper.text()).toContain('⚠️ 不如买指数')
    })

    it('does not show warning text when sharpe ratio >= 1.0', () => {
      const wrapper = mount(DiagnosisCards, { props: mockProps })
      expect(wrapper.text()).not.toContain('⚠️ 不如买指数')
    })

    it('applies correct color class to rating badge', () => {
      const wrapper = mount(DiagnosisCards, { props: mockProps })
      const ratingCard = wrapper.findAll('.metric-card')[3]
      expect(ratingCard.html()).toContain('rating-A')
    })
  })

  describe('Different Rating Scenarios', () => {
    it('renders B rating correctly', () => {
      const bRatingProps = {
        ...mockProps,
        ratings: { ...mockProps.ratings, overall: 'B' as const }
      }
      const wrapper = mount(DiagnosisCards, { props: bRatingProps })
      expect(wrapper.text()).toContain('B')
      expect(wrapper.text()).toContain('良好')
      const ratingCard = wrapper.findAll('.metric-card')[3]
      expect(ratingCard.html()).toContain('rating-B')
    })

    it('renders C rating correctly', () => {
      const cRatingProps = {
        ...mockProps,
        ratings: { ...mockProps.ratings, overall: 'C' as const }
      }
      const wrapper = mount(DiagnosisCards, { props: cRatingProps })
      expect(wrapper.text()).toContain('C')
      expect(wrapper.text()).toContain('一般')
      const ratingCard = wrapper.findAll('.metric-card')[3]
      expect(ratingCard.html()).toContain('rating-C')
    })

    it('renders D rating correctly', () => {
      const dRatingProps = {
        ...mockProps,
        ratings: { ...mockProps.ratings, overall: 'D' as const }
      }
      const wrapper = mount(DiagnosisCards, { props: dRatingProps })
      expect(wrapper.text()).toContain('D')
      expect(wrapper.text()).toContain('较差')
      const ratingCard = wrapper.findAll('.metric-card')[3]
      expect(ratingCard.html()).toContain('rating-D')
    })
  })

  describe('Edge Cases', () => {
    it('handles very small positive values', () => {
      const smallValueProps = {
        ...mockProps,
        metrics: { ...mockProps.metrics, annualReturn: 0.0001 }
      }
      const wrapper = mount(DiagnosisCards, { props: smallValueProps })
      expect(wrapper.text()).toContain('+0.01%')
    })

    it('handles very large negative values', () => {
      const largeNegativeProps = {
        ...mockProps,
        metrics: { ...mockProps.metrics, maxDrawdown: -0.5678 }
      }
      const wrapper = mount(DiagnosisCards, { props: largeNegativeProps })
      expect(wrapper.text()).toContain('-56.78%')
    })

    it('handles sharpe ratio at boundary thresholds', () => {
      const wrapper = mount(DiagnosisCards, { props: mockProps })
      const vm = wrapper.vm as any

      // Boundary at 1.5 (excellent)
      expect(vm.getSharpeColor(1.5)).toBe('text-excellent')
      expect(vm.getSharpeColor(1.49)).toBe('text-good')

      // Boundary at 1.0 (good)
      expect(vm.getSharpeColor(1.0)).toBe('text-good')
      expect(vm.getSharpeColor(0.99)).toBe('text-moderate')

      // Boundary at 0.5 (moderate)
      expect(vm.getSharpeColor(0.5)).toBe('text-moderate')
      expect(vm.getSharpeColor(0.49)).toBe('text-poor')
    })
  })

  describe('Type Safety', () => {
    it('accepts valid props structure', () => {
      const wrapper = mount(DiagnosisCards, { props: mockProps })
      expect(wrapper.exists()).toBe(true)
    })

    it('handles all rating literal types', () => {
      const ratings: Array<'A' | 'B' | 'C' | 'D'> = ['A', 'B', 'C', 'D']
      ratings.forEach(rating => {
        const props = {
          ...mockProps,
          ratings: { ...mockProps.ratings, overall: rating }
        }
        const wrapper = mount(DiagnosisCards, { props })
        expect(wrapper.exists()).toBe(true)
      })
    })
  })
})
