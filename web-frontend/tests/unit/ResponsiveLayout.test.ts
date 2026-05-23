import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

describe('Responsive Layout', () => {
  describe('MainLayout Mobile Responsiveness', () => {
    const mainLayoutPath = resolve(__dirname, '../../src/components/layout/MainLayout.vue')
    const content = readFileSync(mainLayoutPath, 'utf-8')

    it('should have collapsible sidebar state', () => {
      expect(content).toMatch(/const\s+isCollapsed\s*=\s*ref/)
    })

    it('should have mobile breakpoint detection', () => {
      expect(content).toMatch(/const\s+isMobile\s*=\s*ref/)
    })

    it('should have toggle sidebar function', () => {
      expect(content).toMatch(/const\s+toggleSidebar/)
    })

    it('should have hamburger menu button', () => {
      expect(content).toMatch(/@click="toggleSidebar"/)
    })

    it('should have responsive sidebar width', () => {
      expect(content).toMatch(/:width=".*isCollapsed.*"/)
    })

    it('should have media query for mobile', () => {
      expect(content).toMatch(/@media.*max-width.*768px/)
    })
  })

  describe('Dashboard Mobile Responsiveness', () => {
    const dashboardPath = resolve(__dirname, '../../src/views/Dashboard/index.vue')
    const content = readFileSync(dashboardPath, 'utf-8')

    it('should have responsive :xs breakpoint on stat cards', () => {
      // Stat cards should be full width on mobile
      expect(content).toMatch(/:xs="24"/)
    })

    it('should have responsive :sm breakpoint on stat cards', () => {
      expect(content).toMatch(/:sm="12"/)
    })

    it('should have responsive :md breakpoint on stat cards', () => {
      expect(content).toMatch(/:md="6"/)
    })

    it('should have responsive breakpoints on chart column', () => {
      // Chart column should be full width on mobile
      const chartColMatch = content.match(/<el-col[^>]*>[\s\S]*?组合净值走势[\s\S]*?<\/el-col>/m)
      expect(chartColMatch).toBeTruthy()
      if (chartColMatch) {
        expect(chartColMatch[0]).toMatch(/:xs="24"/)
      }
    })

    it('should have media query for mobile table', () => {
      expect(content).toMatch(/@media.*max-width.*768px/)
    })
  })
})
