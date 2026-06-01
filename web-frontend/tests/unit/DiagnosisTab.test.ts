import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ElMessage } from 'element-plus'
import DiagnosisTab from '@/views/BacktestCenter/DiagnosisTab.vue'
import * as diagnosisApi from '@/services/api/diagnosis'
import type { DiagnosisResult } from '@/services/api/diagnosis'

vi.mock('@/services/api/diagnosis')
vi.mock('element-plus', () => ({
  ElMessage: {
    warning: vi.fn(),
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn()
  }
}))

// Global stubs for Element Plus components
const globalStubs = {
  'el-button': {
    template: '<button :disabled="disabled" :loading="loading"><slot /></button>',
    props: ['disabled', 'loading', 'type']
  },
  'el-icon': {
    template: '<i><slot /></i>',
    props: ['color']
  },
  'el-empty': {
    template: '<div class="el-empty">{{ description }}<slot /></div>',
    props: ['description']
  },
  'el-skeleton': {
    template: '<div class="el-skeleton"></div>',
    props: ['rows', 'animated']
  },
  'el-card': {
    template: '<div class="el-card"><slot name="header" /><slot /></div>',
    props: ['shadow']
  },
  'el-tag': {
    template: '<span class="el-tag"><slot /></span>',
    props: ['type', 'size']
  },
  'el-divider': {
    template: '<hr class="el-divider" />'
  },
  'el-table': {
    template: '<div class="el-table"><slot /></div>',
    props: ['data', 'stripe']
  },
  'el-table-column': {
    template: '<div class="el-table-column">{{ label }}</div>',
    props: ['prop', 'label', 'width', 'align']
  },
  'DiagnosisCards': {
    template: '<div class="diagnosis-cards"></div>',
    props: ['metrics', 'benchmark', 'ratings']
  },
  'DataAnalysis': { template: '<span>DataAnalysis</span>' },
  'Document': { template: '<span>Document</span>' },
  'CircleCheck': { template: '<span>CircleCheck</span>' },
  'CircleClose': { template: '<span>CircleClose</span>' },
  'Lightbulb': { template: '<span>Lightbulb</span>' }
}

describe('DiagnosisTab', () => {
  const mockBacktestResult = {
    symbol: '600519.SH',
    startDate: '2023-01-01',
    endDate: '2023-12-31',
    strategyName: '多因子策略'
  }

  const mockDiagnosisResult: DiagnosisResult = {
    metrics: {
      annualReturn: 0.25,
      sharpeRatio: 1.8,
      maxDrawdown: -0.15,
      winRate: 0.65,
      profitFactor: 2.1,
      calmarRatio: 1.67
    },
    benchmark: {
      annualReturn: 0.10,
      sharpeRatio: 1.2,
      maxDrawdown: -0.20
    },
    ratings: {
      overall: 'A',
      return: 'A',
      risk: 'B',
      stability: 'A'
    },
    diagnosis: {
      conclusion: '策略表现优秀，收益稳定，风险可控。',
      strengths: ['收益率显著超越基准', '夏普比率优秀'],
      weaknesses: ['回撤控制有待提升'],
      suggestions: ['优化止损策略', '增加仓位管理']
    },
    reportPath: '/reports/diagnosis_20230101_20231231.html'
  }

  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders toolbar with "运行诊断" button', () => {
    const wrapper = mount(DiagnosisTab, {
      props: { backtestResult: mockBacktestResult },
      global: { stubs: globalStubs }
    })
    expect(wrapper.find('.toolbar').exists()).toBe(true)
    expect(wrapper.text()).toContain('运行诊断')
  })

  it('disables "运行诊断" button when no backtestResult', () => {
    const wrapper = mount(DiagnosisTab, {
      props: { backtestResult: null },
      global: { stubs: globalStubs }
    })
    const button = wrapper.find('.toolbar button')
    expect(button.attributes('disabled')).toBeDefined()
  })

  it('shows empty state when no diagnosis result', () => {
    const wrapper = mount(DiagnosisTab, {
      props: { backtestResult: mockBacktestResult },
      global: { stubs: globalStubs }
    })
    expect(wrapper.find('.empty-state').exists()).toBe(true)
    expect(wrapper.text()).toContain('暂无诊断结果')
  })

  it('calls runDiagnosis API when "运行诊断" button clicked', async () => {
    const mockRunDiagnosis = vi.mocked(diagnosisApi.runDiagnosis)
    mockRunDiagnosis.mockResolvedValue(mockDiagnosisResult)

    const wrapper = mount(DiagnosisTab, {
      props: { backtestResult: mockBacktestResult },
      global: { stubs: globalStubs }
    })

    await wrapper.find('.toolbar button').trigger('click')

    expect(mockRunDiagnosis).toHaveBeenCalledWith({
      symbol: '600519.SH',
      startDate: '2023-01-01',
      endDate: '2023-12-31',
      strategyName: '多因子策略',
      benchmark: '000300.SH'
    })
  })

  it('shows loading state while diagnosis is running', async () => {
    const mockRunDiagnosis = vi.mocked(diagnosisApi.runDiagnosis)
    mockRunDiagnosis.mockImplementation(() => new Promise(() => {})) // Never resolves

    const wrapper = mount(DiagnosisTab, {
      props: { backtestResult: mockBacktestResult },
      global: { stubs: globalStubs }
    })

    await wrapper.find('.toolbar button').trigger('click')
    await wrapper.vm.$nextTick()

    expect(wrapper.find('.loading-state').exists()).toBe(true)
  })

  it('displays diagnosis result after successful API call', async () => {
    const mockRunDiagnosis = vi.mocked(diagnosisApi.runDiagnosis)
    mockRunDiagnosis.mockResolvedValue(mockDiagnosisResult)

    const wrapper = mount(DiagnosisTab, {
      props: { backtestResult: mockBacktestResult },
      global: { stubs: globalStubs }
    })

    await wrapper.find('.toolbar button').trigger('click')
    await flushPromises()

    expect(wrapper.find('.diagnosis-content').exists()).toBe(true)
    expect(wrapper.text()).toContain('诊断结论')
    expect(wrapper.text()).toContain('策略表现优秀，收益稳定，风险可控。')
  })

  it('shows success message after diagnosis completes', async () => {
    const mockRunDiagnosis = vi.mocked(diagnosisApi.runDiagnosis)
    mockRunDiagnosis.mockResolvedValue(mockDiagnosisResult)

    const wrapper = mount(DiagnosisTab, {
      props: { backtestResult: mockBacktestResult },
      global: { stubs: globalStubs }
    })

    await wrapper.find('.toolbar button').trigger('click')
    await flushPromises()

    expect(ElMessage.success).toHaveBeenCalledWith('诊断完成')
  })

  it('shows error message when API call fails', async () => {
    const mockRunDiagnosis = vi.mocked(diagnosisApi.runDiagnosis)
    mockRunDiagnosis.mockRejectedValue(new Error('诊断失败'))

    const wrapper = mount(DiagnosisTab, {
      props: { backtestResult: mockBacktestResult },
      global: { stubs: globalStubs }
    })

    await wrapper.find('.toolbar button').trigger('click')
    await flushPromises()

    expect(ElMessage.error).toHaveBeenCalledWith('诊断失败')
  })

  it('shows "查看报告" button when diagnosis result exists', async () => {
    const mockRunDiagnosis = vi.mocked(diagnosisApi.runDiagnosis)
    mockRunDiagnosis.mockResolvedValue(mockDiagnosisResult)

    const wrapper = mount(DiagnosisTab, {
      props: { backtestResult: mockBacktestResult },
      global: { stubs: globalStubs }
    })

    await wrapper.find('.toolbar button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('查看报告')
  })

  it('shows report path when "查看报告" button clicked', async () => {
    const mockRunDiagnosis = vi.mocked(diagnosisApi.runDiagnosis)
    mockRunDiagnosis.mockResolvedValue(mockDiagnosisResult)

    const wrapper = mount(DiagnosisTab, {
      props: { backtestResult: mockBacktestResult },
      global: { stubs: globalStubs }
    })

    await wrapper.find('.toolbar button').trigger('click')
    await flushPromises()

    const buttons = wrapper.findAll('.toolbar button')
    await buttons[1].trigger('click')

    expect(ElMessage.info).toHaveBeenCalledWith('报告路径: /reports/diagnosis_20230101_20231231.html')
  })

  it('maps rating types correctly', async () => {
    const mockRunDiagnosis = vi.mocked(diagnosisApi.runDiagnosis)
    mockRunDiagnosis.mockResolvedValue(mockDiagnosisResult)

    const wrapper = mount(DiagnosisTab, {
      props: { backtestResult: mockBacktestResult },
      global: { stubs: globalStubs }
    })

    await wrapper.find('.toolbar button').trigger('click')
    await flushPromises()

    // Check if A rating shows as success type
    expect(wrapper.html()).toContain('A 级')
  })

  it('calculates comparison data correctly', async () => {
    const mockRunDiagnosis = vi.mocked(diagnosisApi.runDiagnosis)
    mockRunDiagnosis.mockResolvedValue(mockDiagnosisResult)

    const wrapper = mount(DiagnosisTab, {
      props: { backtestResult: mockBacktestResult },
      global: { stubs: globalStubs }
    })

    await wrapper.find('.toolbar button').trigger('click')
    await flushPromises()

    expect(wrapper.find('.comparison-card').exists()).toBe(true)
    // Check that table column labels are present
    expect(wrapper.text()).toContain('指标')
    expect(wrapper.text()).toContain('策略')
    expect(wrapper.text()).toContain('基准')
    expect(wrapper.text()).toContain('差值')
  })

  it('renders strengths list when available', async () => {
    const mockRunDiagnosis = vi.mocked(diagnosisApi.runDiagnosis)
    mockRunDiagnosis.mockResolvedValue(mockDiagnosisResult)

    const wrapper = mount(DiagnosisTab, {
      props: { backtestResult: mockBacktestResult },
      global: { stubs: globalStubs }
    })

    await wrapper.find('.toolbar button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('优势')
    expect(wrapper.text()).toContain('收益率显著超越基准')
    expect(wrapper.text()).toContain('夏普比率优秀')
  })

  it('renders weaknesses list when available', async () => {
    const mockRunDiagnosis = vi.mocked(diagnosisApi.runDiagnosis)
    mockRunDiagnosis.mockResolvedValue(mockDiagnosisResult)

    const wrapper = mount(DiagnosisTab, {
      props: { backtestResult: mockBacktestResult },
      global: { stubs: globalStubs }
    })

    await wrapper.find('.toolbar button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('劣势')
    expect(wrapper.text()).toContain('回撤控制有待提升')
  })

  it('renders suggestions list when available', async () => {
    const mockRunDiagnosis = vi.mocked(diagnosisApi.runDiagnosis)
    mockRunDiagnosis.mockResolvedValue(mockDiagnosisResult)

    const wrapper = mount(DiagnosisTab, {
      props: { backtestResult: mockBacktestResult },
      global: { stubs: globalStubs }
    })

    await wrapper.find('.toolbar button').trigger('click')
    await flushPromises()

    expect(wrapper.text()).toContain('优化建议')
    expect(wrapper.text()).toContain('优化止损策略')
    expect(wrapper.text()).toContain('增加仓位管理')
  })

  it('does not render strengths section when empty', async () => {
    const resultWithoutStrengths = {
      ...mockDiagnosisResult,
      diagnosis: {
        ...mockDiagnosisResult.diagnosis,
        strengths: []
      }
    }

    const mockRunDiagnosis = vi.mocked(diagnosisApi.runDiagnosis)
    mockRunDiagnosis.mockResolvedValue(resultWithoutStrengths)

    const wrapper = mount(DiagnosisTab, {
      props: { backtestResult: mockBacktestResult },
      global: { stubs: globalStubs }
    })

    await wrapper.find('.toolbar button').trigger('click')
    await flushPromises()

    const sections = wrapper.findAll('.section')
    const strengthSection = sections.find(s => s.text().includes('优势'))
    expect(strengthSection).toBeUndefined()
  })

  it('shows warning when running diagnosis without backtestResult', async () => {
    const wrapper = mount(DiagnosisTab, {
      props: { backtestResult: null },
      global: { stubs: globalStubs }
    })

    // Call the method directly since the button is disabled
    await wrapper.vm.handleRunDiagnosis()

    expect(ElMessage.warning).toHaveBeenCalledWith('请先运行回测')
  })
})
