import { describe, it, expect } from 'vitest'
import * as fs from 'fs'
import * as path from 'path'

describe('Router', () => {
  it('should not use deprecated next() callback in beforeEach guard', () => {
    const routerPath = path.resolve(process.cwd(), 'src/router/index.ts')
    const content = fs.readFileSync(routerPath, 'utf-8')

    // The deprecated pattern is: beforeEach((to, from, next) => { ... next() })
    // The new pattern is: beforeEach((to, from) => { ... }) without next parameter

    // Should not have three parameters with 'next' in beforeEach
    const deprecatedPattern = /beforeEach\s*\(\s*\(\s*\w+\s*,\s*\w+\s*,\s*next\s*\)/
    expect(content).not.toMatch(deprecatedPattern)

    // Should have the new two-parameter pattern
    const newPattern = /beforeEach\s*\(\s*\(\s*\w+\s*,\s*\w+\s*\)\s*=>/
    expect(content).toMatch(newPattern)
  })

  it('/v14-trading 重定向到统一页并预选 v14_simulation', () => {
    const routerPath = path.resolve(process.cwd(), 'src/router/index.ts')
    const content = fs.readFileSync(routerPath, 'utf-8')

    // v14 路由必须是重定向（不再有独立组件页）
    expect(content).toMatch(
      /path:\s*'\/v14-trading'[\s\S]{0,200}redirect:[\s\S]{0,200}v14_simulation/)
    expect(content).not.toMatch(/import\([^)]*V14Trading\/index\.vue[^)]*\)/)
  })

  it('/simulation-trading 标题为模拟交易', () => {
    const routerPath = path.resolve(process.cwd(), 'src/router/index.ts')
    const content = fs.readFileSync(routerPath, 'utf-8')

    expect(content).toMatch(
      /path:\s*'\/simulation-trading'[\s\S]{0,300}title:\s*'模拟交易'/)
  })
})
