import { describe, expect, it } from 'vitest'
import type { HeatmapResponse } from '@/types'
import { buildHeatmapOption, changeColor } from '@/views/StockHeatmap/chart-options'

function fixture(): HeatmapResponse {
  return {
    date: '2026-07-24', window: 5, actualEndDate: '2026-07-31',
    partial: false, scopeDegraded: false, excludedCount: 0,
    industries: [{
      name: '半导体', changePct: 4.2, agentStance: 'bullish',
      stocks: [
        { symbol: '688981', name: '中芯国际', changePct: 8.2, marketCap: 4.5e11, inScope: true,
          signals: [{ type: 'buy', date: '2026-07-23', strategy: 'v13' }] },
        { symbol: '300999', name: '池外股', changePct: 1.1, marketCap: 2e10, inScope: false },
      ],
    }],
  }
}

describe('changeColor', () => {
  it('红涨绿跌', () => {
    const up = changeColor(5)
    const down = changeColor(-5)
    expect(up).not.toBe(down)
    // 涨为红色系（R 通道高），跌为绿色系（G 通道高）
    expect(up).toMatch(/192|#c0|rgb\(19/)
    expect(down).toMatch(/39, 174|#27|rgb\(39/)
  })

  it('池外股票低饱和灰化', () => {
    expect(changeColor(5, false)).not.toBe(changeColor(5, true))
  })
})

describe('buildHeatmapOption', () => {
  it('行业→个股两级 treemap 数据', () => {
    const option = buildHeatmapOption({ data: fixture(), overlays: { signals: true, pool: true, industry: true } })
    const series = (option.series as any[])[0]
    expect(series.type).toBe('treemap')
    const industryNode = series.data[0]
    expect(industryNode.name).toContain('半导体')
    expect(industryNode.children).toHaveLength(2)
    const stock = industryNode.children[0]
    expect(stock.name).toContain('中芯国际')
    expect(stock.value).toBe(4.5e11)
  })

  it('信号叠加开启时 in_scope 股票 label 带角标，关闭时不带', () => {
    const on = buildHeatmapOption({ data: fixture(), overlays: { signals: true, pool: true, industry: true } })
    const off = buildHeatmapOption({ data: fixture(), overlays: { signals: false, pool: false, industry: false } })
    const stockOn = (on.series as any[])[0].data[0].children[0]
    const stockOff = (off.series as any[])[0].data[0].children[0]
    expect(stockOn.name).toContain('▲')
    expect(stockOff.name).not.toContain('▲')
  })

  it('行业 stance 叠加开启时 bullish 行业节点带金色边框', () => {
    const option = buildHeatmapOption({ data: fixture(), overlays: { signals: false, pool: false, industry: true } })
    const industryNode = (option.series as any[])[0].data[0]
    expect(industryNode.itemStyle.borderColor).toBe('#d4a017')
  })

  it('空数据返回空 series', () => {
    const empty = { ...fixture(), industries: [] }
    const option = buildHeatmapOption({ data: empty, overlays: { signals: true, pool: true, industry: true } })
    expect((option.series as any[])[0].data).toHaveLength(0)
  })

  it('支持行业下钻：zoomToNode + 面包屑 + roam 缩放', () => {
    const option = buildHeatmapOption({ data: fixture(), overlays: { signals: true, pool: true, industry: true } })
    const series = (option.series as any[])[0]
    // 点击行业节点可下钻放大（700+ 方块时小方块看不清的必需交互）
    expect(series.nodeClick).toBe('zoomToNode')
    // 面包屑可返回上一级
    expect(series.breadcrumb.show).toBe(true)
    // 允许拖拽/滚轮缩放平移
    expect(series.roam).toBe(true)
  })
})
