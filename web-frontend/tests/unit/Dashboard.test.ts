import { describe, it, expect } from 'vitest'
import * as fs from 'fs'
import * as path from 'path'

describe('Dashboard', () => {
  it('should have chart component instead of placeholder text', () => {
    const dashboardPath = path.resolve(process.cwd(), 'src/views/Dashboard/index.vue')
    const content = fs.readFileSync(dashboardPath, 'utf-8')

    // Should not have hardcoded placeholder text
    expect(content).not.toContain('图表加载中...')
    expect(content).not.toContain('placeholder-chart')

    // Should have actual chart implementation (using ECharts or similar)
    // Check for chart-related code
    const hasChartRef = content.includes('ref') && (
      content.includes('chart') ||
      content.includes('Chart')
    )

    expect(hasChartRef).toBe(true)
  })

  it('should initialize chart in onMounted lifecycle', () => {
    const dashboardPath = path.resolve(process.cwd(), 'src/views/Dashboard/index.vue')
    const content = fs.readFileSync(dashboardPath, 'utf-8')

    // Should use onMounted to initialize chart
    expect(content).toContain('onMounted')
  })
})
