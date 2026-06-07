import { describe, expect, it } from 'vitest'
import * as fs from 'fs'
import * as path from 'path'

describe('StockDetail prototype style parity', () => {
  it('uses the v2 prototype shell and professional chart chrome', () => {
    const stockDetailPath = path.resolve(process.cwd(), 'src/views/StockDetail/index.vue')
    const content = fs.readFileSync(stockDetailPath, 'utf-8')

    expect(content).toContain('class="text-sm text-slate-400 mb-4"')
    expect(content).toContain('class="bg-white rounded-xl p-5 shadow-sm border border-slate-200 mb-4"')
    expect(content).toContain('class="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden"')
    expect(content).toContain('class="bg-slate-900 px-4 py-2 flex items-center justify-between border-b border-slate-700"')
    expect(content).toContain('class="bg-slate-900 px-4 py-2 flex items-center gap-6 text-xs border-b border-slate-700 stock-price-bar"')
    expect(content).toContain('class="w-12 bg-[#1e222d] border-r border-[#2a2e39] flex flex-col items-center py-3 gap-3 stock-chart-tools"')
    expect(content).toContain('class="professional-chart-area"')
    expect(content).toContain('latestKlineTurnoverLabel')
    expect(content).toContain('latestKlineTurnoverValue')
    expect(content).toContain('TIMEFRAME')
    expect(content).toContain('INDICATOR')
    expect(content).toContain('修复数据')
    expect(content).toContain('handleRepairData')
    expect(content).toContain('repairLoading')
    expect(content).not.toContain('<el-card class="stock-header')
    expect(content).not.toContain('<el-card class="stock-tabs')
  })
})
