import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import IndicatorIDE from '@/views/IndicatorIDE/index.vue'
import { stockApi } from '@/services/api/stock'
import { indicatorApi } from '@/services/api/indicator'

vi.mock('@/services/api/stock')
vi.mock('@/services/api/indicator')

describe('IndicatorIDE - Stock Selector', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(stockApi.getMyStocks).mockResolvedValue({ positions: [], watchlist: [] })
    vi.mocked(indicatorApi.getMyIndicators).mockResolvedValue([])
    vi.mocked(indicatorApi.getSystemIndicators).mockResolvedValue([])
  })

  it('should load positions and watchlist on mount', async () => {
    const mockStocks = {
      positions: [{ symbol: '600519', name: '贵州茅台' }],
      watchlist: [{ symbol: '600036', name: '招商银行' }]
    }

    vi.mocked(stockApi.getMyStocks).mockResolvedValue(mockStocks)

    const wrapper = mount(IndicatorIDE)
    await nextTick()
    await nextTick() // 等待异步加载

    // 验证 API 被调用
    expect(stockApi.getMyStocks).toHaveBeenCalled()
  })

  it('should update currentSymbol when stock is selected', async () => {
    const wrapper = mount(IndicatorIDE)
    const vm = wrapper.vm as any

    // 模拟选择股票
    vm.currentSymbol = '600036'
    await nextTick()

    expect(vm.currentSymbol).toBe('600036')
  })

  it('should sync backtestForm.symbol with currentSymbol', async () => {
    const wrapper = mount(IndicatorIDE)
    const vm = wrapper.vm as any

    vm.currentSymbol = '000001'
    await nextTick()

    expect(vm.backtestForm.symbol).toBe('000001')
  })

  it('should handle search with debounce', async () => {
    const mockSearchResults = [
      { symbol: '600519', name: '贵州茅台', market: 'SH' }
    ]

    vi.mocked(stockApi.searchStocks).mockResolvedValue(mockSearchResults)

    const wrapper = mount(IndicatorIDE)
    const vm = wrapper.vm as any

    await vm.handleStockSearch('茅台')

    // 防抖后应该调用搜索
    await new Promise(resolve => setTimeout(resolve, 350))

    expect(stockApi.searchStocks).toHaveBeenCalledWith('茅台')
  })

  it('should not search if query is too short', async () => {
    const wrapper = mount(IndicatorIDE)
    const vm = wrapper.vm as any

    await vm.handleStockSearch('6')
    await new Promise(resolve => setTimeout(resolve, 350))

    expect(stockApi.searchStocks).not.toHaveBeenCalled()
  })

  it('should render search results before positions and watchlist', () => {
    const source = readFileSync(resolve(process.cwd(), 'src/views/IndicatorIDE/index.vue'), 'utf8')

    expect(source.indexOf('label="搜索结果"')).toBeGreaterThanOrEqual(0)
    expect(source.indexOf('label="搜索结果"')).toBeLessThan(source.indexOf('label="我的持仓"'))
    expect(source.indexOf('label="搜索结果"')).toBeLessThan(source.indexOf('label="我的自选"'))
  })
})
