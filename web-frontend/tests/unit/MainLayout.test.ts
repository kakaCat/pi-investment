import { describe, it, expect } from 'vitest'
import * as fs from 'fs'
import * as path from 'path'
import { fileURLToPath } from 'url'

describe('MainLayout', () => {
  it('should use the prototype Q logo in the sidebar header', () => {
    const mainLayoutPath = path.resolve(process.cwd(), 'src/components/layout/MainLayout.vue')
    const content = fs.readFileSync(mainLayoutPath, 'utf-8')

    expect(content).toContain('<div class="logo-mark">Q</div>')
    expect(content).toContain('<span class="logo-text">QuantSys Pro</span>')
    expect(content).toContain('background: #3b82f6')
  })

  it('should use Aim icon instead of non-existent Radar icon', () => {
    const mainLayoutPath = path.resolve(process.cwd(), 'src/components/layout/MainLayout.vue')
    const content = fs.readFileSync(mainLayoutPath, 'utf-8')

    // Should not use Radar icon
    expect(content).not.toContain('<Radar')
    expect(content).not.toContain('<Radar />')

    // Should use Aim icon for opportunity-radar menu item
    expect(content).toContain('<Aim')
    expect(content).toContain('opportunity-radar')
  })

  it('should match the v2 prototype sidebar menu groups and items', () => {
    const mainLayoutPath = path.resolve(process.cwd(), 'src/components/layout/MainLayout.vue')
    const content = fs.readFileSync(mainLayoutPath, 'utf-8')

    const expectedGroups = ['总览', '研究分析', '交易风控', '策略运营', '系统运维']
    const expectedItems = [
      '仪表盘',
      '指标IDE',
      '图表研究',
      '机会雷达',
      '回测与快速交易',
      '持仓管理',
      '交易记录',
      '订单管理',
      '风控检查',
      '执行记录',
      '策略运营中心',
      '量化链路',
      '策略配置',
      'ML 引擎',
      '定时任务',
      '数据更新',
      '日报'
    ]

    const groups = Array.from(content.matchAll(/<div class="menu-group-title">([^<]+)<\/div>/g)).map(
      (match) => match[1]
    )
    const items = Array.from(content.matchAll(/<el-menu-item[\s\S]*?<span>([^<]+)<\/span>[\s\S]*?<\/el-menu-item>/g))
      .map((match) => match[1])
      .filter((label) => !expectedGroups.includes(label))

    expect(groups).toEqual(expectedGroups)
    expect(items).toEqual(expectedItems)
    expect(content).not.toContain('<el-sub-menu')
  })

  it('should style the flat v2 sidebar groups and active item', () => {
    const mainLayoutPath = path.resolve(process.cwd(), 'src/components/layout/MainLayout.vue')
    const content = fs.readFileSync(mainLayoutPath, 'utf-8')

    expect(content).toContain('.menu-group-title')
    expect(content).toContain('color: #94a3b8')
    expect(content).toContain('background: #1e293b')
    expect(content).toContain('background: #334155')
    expect(content).toContain('border-left: 3px solid #3b82f6')
  })
})
