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
})
