import { describe, it, expect } from 'vitest'
import { readFileSync } from 'fs'
import { resolve } from 'path'

describe('Dashboard Button Click Handlers', () => {
  const dashboardPath = resolve(__dirname, '../../src/views/Dashboard/index.vue')
  const content = readFileSync(dashboardPath, 'utf-8')

  it('should have @click handler on "查看全部" button', () => {
    // The "View All" button should have a click handler
    expect(content).toMatch(/<el-button[^>]*>查看全部<\/el-button>/)
    expect(content).toMatch(/@click="[^"]*"[^>]*>查看全部/)
  })

  it('should have @click handler on "批准" button', () => {
    // The "Approve" button should have a click handler with row parameter
    expect(content).toMatch(/@click="[^"]*\(row\)[^"]*"[^>]*>批准/)
  })

  it('should have @click handler on "拒绝" button', () => {
    // The "Reject" button should have a click handler with row parameter
    expect(content).toMatch(/@click="[^"]*\(row\)[^"]*"[^>]*>拒绝/)
  })

  it('should have @click handler on "查看" button', () => {
    // The "View" button should have a click handler with row parameter
    expect(content).toMatch(/@click="[^"]*\(row\)[^"]*"[^>]*>查看/)
  })

  it('should define handleViewAll function in script', () => {
    expect(content).toMatch(/const handleViewAll/)
  })

  it('should define handleApprove function in script', () => {
    expect(content).toMatch(/const handleApprove/)
  })

  it('should define handleReject function in script', () => {
    expect(content).toMatch(/const handleReject/)
  })

  it('should define handleView function in script', () => {
    expect(content).toMatch(/const handleView/)
  })
})
