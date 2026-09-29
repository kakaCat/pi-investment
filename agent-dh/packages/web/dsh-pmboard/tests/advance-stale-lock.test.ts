/**
 * advance 残留锁回收回归（2026-09-28 实机死锁）。
 *
 * 缺陷：`driveChain` 正常收尾会清 `advance.lockAt/runId`，但**进程被杀/重启时 finally 不执行**，
 * `advance.runId` 永久留下；而投递前置检查只看「runId 是否存在」就判「已有 run 在跑」，
 * 于是该需求此后**再也无法投递**（线上实测：quick_restart 后 REQ-260928222643-4d34 恒返回
 * REQBOARD_ADVANCE_LOCKED，启动恢复扫描 scanAndResume 也被同一判断挡下）。
 *
 * 本文件锁定两条：① 过期残留被回收且链能继续（根因修复）；② 新鲜锁仍挡并发（没被放水）。
 */
import { describe, it, expect } from 'vitest'
import { advanceRequirement } from '../src/application/use-cases/AdvanceChain.js'
import { LIMITS } from '../src/domain/limits.js'
import type { WorkflowRunner, WorkflowRunOutcome } from '../src/application/ports.js'
import { makeHarness, task, req } from './application/harness.js'

const FILE = 'src/domain/x.ts'

const runner: WorkflowRunner = {
  async start(): Promise<WorkflowRunOutcome> {
    return { ok: true, value: { ok: true, output: JSON.stringify({ filesChanged: [FILE], completed: ['完成'], evidence: ['绿'] }) } }
  },
}

function harnessWith(advance: { lockAt?: number; runId?: string }) {
  const h = makeHarness()
  h.docs.put(FILE, 'x')
  const r = req({ id: 'REQ-000001', status: 'implementing', category: 'feature', autoRun: true })
  r.advance = { ...advance } as never
  h.repo.ledger.requirements = [r]
  h.seedTasks('REQ-000001', [task({ id: 't-p', requirementId: 'REQ-000001', status: 'todo', title: '父卡' })])
  h.deps.workflow = runner
  return h
}

describe('advance 残留锁回收（进程被杀后 runId 不再死锁）', () => {
  it('lockAt 已过期 + runId 残留 → 回收并继续推进（不再 locked）', async () => {
    const h = makeHarness()
    const staleAt = h.clock.t - LIMITS.advanceLockStaleMs - 1
    const hh = harnessWith({ lockAt: staleAt, runId: 'run-dead-1' })
    const out = await advanceRequirement(hh.deps, 'REQ-000001')
    expect(out.stopped).toBe('rollup')
    expect(out.steps.length).toBeGreaterThan(0)
    const after = hh.repo.ledger.requirements.find((r) => r.id === 'REQ-000001')!
    expect(after.advance?.runId).toBeUndefined()
    expect(after.status).toBe('accepting')
  })

  it('lockAt 新鲜 → 仍按「有 run 在跑」挡下（不放行并发）', async () => {
    const hh = harnessWith({ lockAt: 1_000_000, runId: 'run-live-1' })
    const out = await advanceRequirement(hh.deps, 'REQ-000001')
    expect(out.stopped).toBe('locked')
    expect(out.dispatched).toBe(false)
    expect(hh.repo.ledger.requirements[0]!.advance?.runId).toBe('run-live-1')
    expect(hh.repo.ledger.requirements[0]!.status).toBe('implementing')
  })
})
