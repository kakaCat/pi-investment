/**
 * task_run / task_execute 契约（REQ-260927144541-0481 FR-1/FR-2）。
 * serves: FR-1, FR-2
 *
 * 口径：① 参数与副作用显式（task_id 与 requirement_id 两种调用同形，且调用即写 autoRun）；
 * ② 返回体与 output.schema 逐键对齐（additionalProperties:false 下未声明键会被绑定层拒收）；
 * ③ 别名是真委托（同一实现，不再各跑一套）。
 */
import { describe, expect, it } from 'vitest'
import { makeHarness, req, task } from './application/harness.js'
import { defineAdvanceTool, defineTaskExecuteTool } from '../src/tools/index.js'

const W = 'session-w-001'
const run = (t: unknown, args: unknown): Promise<Record<string, unknown>> =>
  (t as { execute: (a: unknown, e: unknown) => Promise<Record<string, unknown>> }).execute(args, { agent: { id: W } })

/** 可用的后台任务端口（缺省 = 投递式路径不可用，回执会变成 dispatched:false）。 */
function jobsPort() {
  return {
    available: () => true,
    start: async () => 'job-1',
    get: async () => null,
  }
}

function seed() {
  // 任务落**队列**（REQ-260927202051-f6df：v9 台账已无 tasks 通道）
  const h = makeHarness({ tasks: [task({ id: 't-p', status: 'todo', title: '父卡' })] })
  h.repo.ledger.requirements = [req({ status: 'implementing', autoRun: false })]
  return h
}

describe('reqboard_task_run（FR-1/FR-2）', () => {
  it('TC-1 传 task_id：dispatched + job_id/run_id 齐全，且 autoRun 副作用已落台账', async () => {
    const h = seed()
    h.deps.jobs = jobsPort() as never
    const out = await run(defineAdvanceTool(h.deps), { task_id: 't-p' })
    expect(out.success).toBe(true)
    expect(out.status).toBe('dispatched')
    expect(typeof out.job_id).toBe('string')
    expect(typeof out.run_id).toBe('string')
    expect(h.repo.ledger.requirements[0]!.autoRun).toBe(true)
  })

  it('TC-1b 传 requirement_id：与传 task_id 同形（键集合一致）', async () => {
    const a = seed()
    a.deps.jobs = jobsPort() as never
    const outA = await run(defineAdvanceTool(a.deps), { task_id: 't-p' })

    const b = seed()
    b.deps.jobs = jobsPort() as never
    const outB = await run(defineAdvanceTool(b.deps), { requirement_id: 'REQ-000001' })

    expect(Object.keys(outB).sort()).toEqual(Object.keys(outA).sort())
    expect(outB.requirement_id).toBe('REQ-000001')
    expect(b.repo.ledger.requirements[0]!.autoRun).toBe(true)
  })

  it('TC-2 不传任何 id 且未绑定 → REQBOARD_NO_BOUND_REQ（不静默当成功）', async () => {
    const h = makeHarness()
    const out = await run(defineAdvanceTool(h.deps), {})
    expect(out.success).toBe(false)
    expect(out.code).toBe('REQBOARD_NO_BOUND_REQ')
  })

  it('TC-2b 跨窗口需求 → REQBOARD_NOT_BOUND_TO_WINDOW', async () => {
    const h = makeHarness()
    h.repo.ledger.requirements = [req({ status: 'implementing', sourceSessionId: 'session-other' })]
    const out = await run(defineAdvanceTool(h.deps), { requirement_id: 'REQ-000001' })
    expect(out.success).toBe(false)
    expect(out.code).toBe('REQBOARD_NOT_BOUND_TO_WINDOW')
  })

  it('FR-2 声明 ⊇ 返回：实跑一遍，返回键全部已在 output.schema 声明', async () => {
    const h = seed()
    h.deps.jobs = jobsPort() as never
    const tool = defineAdvanceTool(h.deps) as unknown as { output?: { schema?: { properties?: Record<string, unknown> } } }
    const declared = new Set(Object.keys(tool.output?.schema?.properties ?? {}))
    const out = await run(tool, { task_id: 't-p' })
    expect(Object.keys(out).filter((k) => !declared.has(k))).toEqual([])
    // 已不再返回的键不得留在声明里（否则描述与行为继续脱节）
    expect(declared.has('subtask_executed')).toBe(false)
    expect(declared.has('blocked')).toBe(false)
    expect(declared.has('stopped')).toBe(false)
  })

  it('FR-2b 已有 run 在跑（locked）→ 结构化错误 + 回执是 lossless JSON（不吐 undefined）', async () => {
    const h = seed()
    h.deps.jobs = jobsPort() as never
    // 锁新鲜 = 该需求已有 run。旧实现走成功回执并带 job_id/run_id=undefined，
    // 绑定层（dsh-tools snapshotJsonValue）把它转成无信息的
    // "tool \"reqboard_task_run\" returned invalid output: value is not lossless JSON"。
    const locked = req({ status: 'implementing', autoRun: true })
    locked.advance = { lockAt: h.clock.t, runId: 'run-inflight' }
    h.repo.ledger.requirements = [locked]

    const out = await run(defineAdvanceTool(h.deps), { task_id: 't-p' })
    expect(out.success).toBe(false)
    expect(out.status).toBe('error')
    expect(out.code).toBe('REQBOARD_ADVANCE_LOCKED')
    expect(typeof out.error).toBe('string')
    expect(String(out.error)).toContain('run-inflight')
    // 关键回归：绑定层要求 lossless JSON——含 undefined 的对象 JSON 往返后不再相等。
    expect(JSON.parse(JSON.stringify(out))).toEqual(out)
  })
})

describe('reqboard_task_execute（FR-1：兼容别名是真委托）', () => {
  it('TC-3 返回体与 task_run 同形，且同样写 autoRun', async () => {
    const h = seed()
    h.deps.jobs = jobsPort() as never
    const out = await run(defineTaskExecuteTool(h.deps), { task_id: 't-p' })
    expect(out.success).toBe(true)
    expect(out.status).toBe('dispatched')
    expect(out.job_id).toBe('job-1')
    expect(typeof out.run_id).toBe('string')
    expect(h.repo.ledger.requirements[0]!.autoRun).toBe(true)
  })
})
