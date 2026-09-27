/**
 * 汇报路径归一（D15 / REQ-260927123256-196b）单测。
 *
 * 锁：子代理写相对 git 根的 `agent-dh/…` 前缀时，凭证门仍能解析到工作区根下的真实文件；
 * 路径不存在时**照旧返回 undefined**（不猜、不放宽）。
 */
import { describe, it, expect } from 'vitest'
import { reportPathCandidates, reportFileMtime } from '../src/application/internal/report-path.js'
import type { UseCaseDeps } from '../src/application/ports.js'

const ROOT = '/work/agent-dh'

/** 只实现 workspaceRoot/stat 的极简 docs 假件：只认 `packages/x.ts`。 */
function depsWith(files: Record<string, number>): UseCaseDeps {
  return {
    docs: {
      workspaceRoot: () => ROOT,
      stat: (p: string) => (p in files ? { mtimeMs: files[p]!, size: 1 } : undefined),
    },
  } as unknown as UseCaseDeps
}

describe('reportPathCandidates（D15）', () => {
  it('原样优先；命中工作区根 basename 前缀时追加去前缀候选', () => {
    expect(reportPathCandidates('agent-dh/packages/x.ts', ROOT)).toEqual(['agent-dh/packages/x.ts', 'packages/x.ts'])
  })
  it('无前缀 / 空串：只给原样（空串给空数组）', () => {
    expect(reportPathCandidates('packages/x.ts', ROOT)).toEqual(['packages/x.ts'])
    expect(reportPathCandidates('   ', ROOT)).toEqual([])
  })
  it('./ 前缀被归一后再判前缀；非 basename 开头不追加', () => {
    expect(reportPathCandidates('./agent-dh/packages/x.ts', ROOT)).toEqual(['./agent-dh/packages/x.ts', 'packages/x.ts'])
    expect(reportPathCandidates('docs/x.md', ROOT)).toEqual(['docs/x.md'])
  })
})

describe('reportFileMtime（D15）', () => {
  it('agent-dh/ 前缀路径 → 归一到 packages/x.ts 后取到 mtime', () => {
    expect(reportFileMtime(depsWith({ 'packages/x.ts': 123 }), 'agent-dh/packages/x.ts')).toBe(123)
  })
  it('原样存在时优先原样', () => {
    expect(reportFileMtime(depsWith({ 'packages/x.ts': 111, 'agent-dh/packages/x.ts': 222 }), 'agent-dh/packages/x.ts')).toBe(222)
  })
  it('两个候选都不存在 → undefined（不放宽）', () => {
    expect(reportFileMtime(depsWith({}), 'agent-dh/nope.ts')).toBeUndefined()
    expect(reportFileMtime(depsWith({}), '')).toBeUndefined()
  })
  it('workspaceRoot() 抛错也能降级（只按原样解析）', () => {
    const deps = { docs: { workspaceRoot: () => { throw new Error('x') }, stat: (p: string) => (p === 'packages/x.ts' ? { mtimeMs: 9, size: 1 } : undefined) } } as unknown as UseCaseDeps
    expect(reportFileMtime(deps, 'packages/x.ts')).toBe(9)
  })
})
