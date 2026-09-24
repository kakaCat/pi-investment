/**
 * 并发上限与冲突两级防线测试（REQ-4842fe t9）——对应 design/test-cases.md §6。
 *
 * 口径：同需求 in_progress 父卡 ≤3；互无依赖父卡并行且 rollup 正常；子卡依赖不跨父卡；
 * 拆分期改动面重叠即拒；运行期 mtime 跨卡覆盖判失败。
 */
import { describe, it, expect } from 'vitest'
import { readdirSync, readFileSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { executeMoveTask } from '../src/application/use-cases/MoveTask.js'
import { advanceRequirement } from '../src/application/use-cases/AdvanceChain.js'
import { executeSubtask } from '../src/application/use-cases/ExecuteTask.js'
import { findWorkSurfaceConflicts, declaredFiles } from '../src/application/internal/conflict-check.js'
import { detectCrossCardOverwrite } from '../src/application/internal/cross-card.js'
import { checkSubtaskInvariants } from '../src/shared/protocol.js'
import { LIMITS } from '../src/domain/limits.js'
import type { WorkflowRunner, WorkflowRunOutcome } from '../src/application/ports.js'
import { makeHarness, task, req } from './application/harness.js'

const FILE = 'src/domain/x.ts'
const exec = { agent: { id: 'session-w-001' } }

class OkRunner implements WorkflowRunner {
  async start(_i: unknown): Promise<WorkflowRunOutcome> {
    return { ok: true, value: { ok: true, output: JSON.stringify({ filesChanged: [FILE], completed: ['done'] }) } }
  }
}

describe('父卡并发上限（6.1）', () => {
  it('第 4 张父卡开工被拒（REQBOARD_PARENT_LIMIT）', async () => {
    const h = makeHarness()
    h.repo.ledger.requirements = [req({ id: 'REQ-000001', status: 'implementing', category: 'feature', autoRun: true })]
    h.repo.ledger.tasks = [
      task({ id: 't-p1', requirementId: 'REQ-000001', status: 'in_progress', title: 'p1' }),
      task({ id: 't-p2', requirementId: 'REQ-000001', status: 'in_progress', title: 'p2' }),
      task({ id: 't-p3', requirementId: 'REQ-000001', status: 'in_progress', title: 'p3' }),
      task({ id: 't-p4', requirementId: 'REQ-000001', status: 'todo', title: 'p4' }),
    ]
    let code: string | undefined
    try { await executeMoveTask(h.deps, { task_id: 't-p4', to: 'in_progress' }, exec) } catch (err) { code = (err as { code?: string }).code }
    expect(code).toBe('REQBOARD_PARENT_LIMIT')
    expect(h.repo.ledger.tasks.find(t => t.id === 't-p4')!.status).toBe('todo')
    expect(LIMITS.advanceMaxParallelParents).toBe(3)
  })
})

describe('父卡层并行（6.2）', () => {
  it('两张互不依赖父卡的子卡链同时推进，都完成后 rollup 进 accepting', async () => {
    const h = makeHarness()
    h.docs.put(FILE, 'x')
    h.repo.ledger.requirements = [req({ id: 'REQ-000001', status: 'implementing', category: 'doc', autoRun: true })]
    h.repo.ledger.tasks = [
      task({ id: 't-a', requirementId: 'REQ-000001', status: 'todo', title: 'A' }),
      task({ id: 't-b', requirementId: 'REQ-000001', status: 'todo', title: 'B' }),
    ]
    h.deps.workflow = new OkRunner()
    const out = await advanceRequirement(h.deps, 'REQ-000001')
    expect(out.stopped).toBe('rollup')
    expect(h.repo.ledger.tasks.find(t => t.id === 't-a')!.status).toBe('done')
    expect(h.repo.ledger.tasks.find(t => t.id === 't-b')!.status).toBe('done')
    expect(h.repo.ledger.requirements[0]!.status).toBe('accepting')
  })
})

describe('子卡依赖不跨父卡（6.3 / INV-4）', () => {
  it('子卡依赖另一父卡的子卡 → INV-4', () => {
    const parentA = task({ id: 't-a', requirementId: 'REQ-000001', title: 'A' })
    const parentB = task({ id: 't-b', requirementId: 'REQ-000001', title: 'B' })
    const sa = task({ id: 't-a1', requirementId: 'REQ-000001', parentId: 't-a', stageKind: 'dev' as never })
    const sb = task({ id: 't-b1', requirementId: 'REQ-000001', parentId: 't-b', stageKind: 'dev' as never, dependsOn: ['t-a1'] })
    const v = checkSubtaskInvariants([parentA, parentB, sa, sb], 'REQ-000001')
    expect(v.map(x => x.inv)).toContain('INV-4')
  })
})

describe('拆分期冲突拦截（6.4）', () => {
  it('抽取 implementation 声明的文件路径', () => {
    expect(declaredFiles('改 packages/pages/dsh-pmboard/src/a.ts 与 src/domain/x.ts')).toContain('packages/pages/dsh-pmboard/src/a.ts')
    expect(declaredFiles('无路径')).toEqual([])
  })

  it('互无依赖且改动面重叠 → 冲突；有依赖（串行）→ 不冲突', () => {
    const a = { key: 't1', implementation: '改 packages/x/src/a.ts', dependsOn: [] }
    const b = { key: 't2', implementation: '改 packages/x/src/a.ts', dependsOn: [] }
    expect(findWorkSurfaceConflicts([a, b])).toEqual([{ file: 'packages/x/src/a.ts', keys: ['t1', 't2'] }])
    const bDep = { key: 't2', implementation: '改 packages/x/src/a.ts', dependsOn: ['t1'] }
    expect(findWorkSurfaceConflicts([a, bDep])).toEqual([])
    const c = { key: 't3', implementation: '改 packages/x/src/c.ts', dependsOn: [] }
    expect(findWorkSurfaceConflicts([a, c])).toEqual([])
  })
})

describe('运行期跨卡覆盖兜底（6.5）', () => {
  it('detectCrossCardOverwrite：mtime 落在另一在跑父卡窗口内 → 报冲突', () => {
    const tasks = [
      { id: 't-a', status: 'in_progress' },
      { id: 't-a1', parentId: 't-a', status: 'in_progress', executions: [{ startedAt: 100, outcome: 'running' }] },
      { id: 't-b', status: 'in_progress' },
    ]
    const hit = detectCrossCardOverwrite(tasks, 't-b', ['src/domain/x.ts'], () => 150, 200)
    expect(hit?.otherParentId).toBe('t-a')
    expect(detectCrossCardOverwrite(tasks, 't-b', ['src/domain/x.ts'], () => 50, 200)).toBeUndefined()
  })

  it('子卡产出文件落在另一在跑父卡窗口 → 子卡判失败（REQBOARD_CROSS_CARD）', async () => {
    const h = makeHarness()
    h.docs.put(FILE, 'x')
    h.repo.ledger.requirements = [req({ id: 'REQ-000001', status: 'implementing', category: 'feature', autoRun: true })]
    h.repo.ledger.tasks = [
      task({ id: 't-a', requirementId: 'REQ-000001', status: 'in_progress', title: 'A', claimedAt: h.clock.t }),
      task({ id: 't-a1', requirementId: 'REQ-000001', status: 'in_progress', parentId: 't-a', stageKind: 'dev' as never, executions: [{ id: 'e1', trigger: 'auto', startedAt: h.clock.t, outcome: 'running' }] } as never),
      task({ id: 't-b', requirementId: 'REQ-000001', status: 'in_progress', title: 'B', claimedAt: h.clock.t }),
      task({ id: 't-b1', requirementId: 'REQ-000001', status: 'todo', parentId: 't-b', stageKind: 'dev' as never }),
    ]
    h.deps.workflow = new OkRunner()
    const r = await executeSubtask(h.deps, { subtaskId: 't-b1', windowKey: 'session-w-001' })
    expect(r.ok).toBe(false)
    expect(r.code).toBe('REQBOARD_CROSS_CARD')
  })
})

// ---------------------------------------------------------------------------
// TC-8 超时契约（REQ-260923222557-d3b0 FR-5）
// ---------------------------------------------------------------------------

function walkTs(dir: string, acc: string[] = []): string[] {
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name)
    if (e.isDirectory()) walkTs(p, acc)
    else if (e.name.endsWith('.ts')) acc.push(p)
  }
  return acc
}

describe('TC-8 超时契约：人机回路不再 10 分钟超时（FR-5）', () => {
  it('交互确认与验收单超时均为 1 小时，且全 src 无旧 600s/900s 硬编码残留', () => {
    expect(LIMITS.timeoutInteractiveMs).toBe(3_600_000)
    expect(LIMITS.timeoutSheetMs).toBe(3_600_000)
    const files = walkTs(fileURLToPath(new URL('../src', import.meta.url)))
    // 扫描器自检：目录失效/被裁剪时不能静默假绿
    expect(files.length).toBeGreaterThan(50)
    // \b 保证 3_600_000 不算残留（下划线是词字符，_600_000 前无词边界）
    const offenders = files.filter(f => /\b(600_000|900_000)\b/.test(readFileSync(f, 'utf8')))
    expect(offenders).toEqual([])
  })
})
