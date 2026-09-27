/*
 * reqboard_run_status 工具壳回归（serves: 修复「getRequirement is not a function」）。
 *
 * 根因：RunStatusTool.execute 曾把 QueryRunStatus 用例当 (deps, id, exec) 调用，
 * 而用例契约是单个 QueryParams 对象 → 运行期 getRequirement 为 undefined 直接抛错。
 * 本测试锁：① 有 checkpoint + 宿主 JobsPort → 返回 runId/stepIndex/jobStatus；
 * ② 无 JobsPort → 不抛错、如实 not_found；③ 无 checkpoint → 不出现 run_id 键；④ 需求缺失 → 响亮报错。
 */
import { describe, it, expect } from 'vitest'
import { defineRunStatusTool } from '../src/tools/RunStatusTool/RunStatusTool.js'
import type { UseCaseDeps } from '../src/application/ports.js'

function depsOf(requirements: unknown[], tasks: unknown[] = [], jobs?: unknown): UseCaseDeps {
  const ledger = { schemaVersion: 1, revision: 0, requirements, tasks, triages: [] }
  return {
    repo: { snapshot: () => ledger },
    session: { windowKey: () => 'session-w-001' },
    // v9（REQ-260927202051-f6df）：任务改从队列取；工具在「有 checkpoint」的路径上
    // 必须拿到 TaskStore，否则按端口缺省语义**显式失败**（这正是它该有的行为）。
    // 本夹具只验证工具壳的形状，故用一个最小只读桩。
    taskStore: {
      listByRequirement: async () => tasks,
      listAll: async () => tasks,
      get: async (id: string) => tasks.find((t) => (t as { id?: string }).id === id),
    },
    ...(jobs !== undefined ? { jobs } : {}),
  } as unknown as UseCaseDeps
}

function execute(deps: UseCaseDeps, args: Record<string, unknown>): Promise<Record<string, unknown>> {
  const tool = defineRunStatusTool(deps) as unknown as {
    execute: (a: unknown, e: unknown) => Promise<Record<string, unknown>>
  }
  return tool.execute(args, {})
}

/**
 * 闸门：**返回值必须能通过工具自己声明的输出 schema**。
 *
 * 为什么需要它（2026-09-27 实测事故）：`reqboard_run_status` 在无 active run 时
 * `snapshot.runId` 发的是 `null`，而 schema 把它声明为 `type: 'string'` ⇒ 值级类型校验失败，
 * 把「当前没有链在跑」这个**正常事实**转译成硬错误 `value.snapshot.runId must be a string`。
 * 单测之所以没拦住：它只断言 `execute()` 的返回值，**从不拿返回值去过自己的输出 schema**。
 * 本函数补上这道闸门——凡在 schema 里声明为 string/number/boolean 的键，一旦出现就必须是该类型，
 * 不允许 null/undefined 混进来（本仓 DSL 表达不了 `string | null`）。
 */
function assertConformsToSchema(schema: any, value: any, path = '$'): void {
  if (schema?.type !== 'object' || schema.properties === undefined) return
  const obj = (value ?? {}) as Record<string, unknown>
  for (const [key, spec] of Object.entries<any>(schema.properties)) {
    if (!(key in obj)) continue // 键整体省略是合法的（这正是降级路径的正确形状）
    const v = obj[key]
    const declared = spec?.type
    if (declared === 'string' || declared === 'number' || declared === 'boolean') {
      expect(typeof v, `${path}.${key} 在 schema 里声明为 ${declared}，实际值 ${JSON.stringify(v)}`).toBe(declared)
    } else if (declared === 'array') {
      expect(Array.isArray(v), `${path}.${key} 应声明为 array，实际 ${JSON.stringify(v)}`).toBe(true)
    } else if (declared === 'object') {
      assertConformsToSchema(spec, v, `${path}.${key}`)
    }
  }
}

const runningJobs = {
  start: async (): Promise<string> => 'job-1',
  get: async (): Promise<{ id: string; status: string }> => ({ id: 'run-1', status: 'running' }),
  available: (): boolean => true,
}

describe('reqboard_run_status 工具壳', () => {
  it('有 checkpoint + JobsPort：返回 runId/stepIndex/当前子卡与 running', async () => {
    const req = { id: 'REQ-x', status: 'implementing', advance: { runId: 'run-1', stepIndex: 3, currentSubtaskId: 't-a' } }
    const task = { id: 't-a', requirementId: 'REQ-x', status: 'todo', dependsOn: [] }
    const out = await execute(depsOf([req], [task], runningJobs), { requirement_id: 'REQ-x' })
    expect(out.success).toBe(true)
    expect(out.run_id).toBe('run-1')
    const snap = out.snapshot as Record<string, unknown>
    expect(snap.runId).toBe('run-1')
    expect(snap.stepIndex).toBe(3)
    expect(snap.currentSubtaskId).toBe('t-a')
    expect(snap.jobStatus).toBe('running')
    expect(snap.autoRun).toBe(true)
  })

  it('无 JobsPort：不抛错，jobStatus 如实 not_found（不伪装成运行中）', async () => {
    const req = { id: 'REQ-x', status: 'implementing', advance: { runId: 'run-1', stepIndex: 1 } }
    const out = await execute(depsOf([req]), { requirement_id: 'REQ-x' })
    expect(out.success).toBe(true)
    expect(out.run_id).toBe('run-1')
    const snap = out.snapshot as Record<string, unknown>
    expect(snap.jobStatus).toBe('not_found')
    expect(snap.autoRun).toBe(false)
  })

  it('无 checkpoint（advance 缺省）：runId 键**整体省略**（不是 null），且返回体不出现 run_id 键', async () => {
    const req = { id: 'REQ-y', status: 'implementing' }
    const out = await execute(depsOf([req]), { requirement_id: 'REQ-y' })
    expect(out.success).toBe(true)
    expect('run_id' in out).toBe(false)
    const snap = out.snapshot as Record<string, unknown>
    // 旧断言是 `toBeNull()` —— 那正是事故根源：null 与 schema 的 `type: 'string'` 冲突，
    // 工具输出校验会把它转成硬错误 value.snapshot.runId must be a string。
    // 正确形状是**键不存在**（本仓 DSL 表达不了 `string | null`）。
    expect('runId' in snap).toBe(false)
    // 真实降级形状（QueryRunStatus.ts:71-77）：无 checkpoint 时给出
    // {stepIndex:0, nextReady, jobStatus:'not_found', autoRun:false}，**不含 status/reason**。
    // （prompt 与 schema 此前声称会返回 `status:'terminated'`/`reason` —— 那是从未被产出的形状，
    //   已一并改正；这又是一处"声明与实现不符"。）
    expect(snap.jobStatus).toBe('not_found')
    expect(snap.autoRun).toBe(false)
    expect(snap.stepIndex).toBe(0)
    // 降级路径也必须能过自己的 schema（本次事故的直接回归）
    assertConformsToSchema(
      (defineRunStatusTool(depsOf([])) as any).output.schema,
      out,
    )
  })

  it('有 active run 的返回体同样必须过自己的 schema（防止修复把正常路径一起改坏）', async () => {
    const req = { id: 'REQ-x', status: 'implementing', advance: { runId: 'run-1', stepIndex: 3, currentSubtaskId: 't-a' } }
    const task = { id: 't-a', requirementId: 'REQ-x', status: 'todo', dependsOn: [] }
    const out = await execute(depsOf([req], [task], runningJobs), { requirement_id: 'REQ-x' })
    assertConformsToSchema((defineRunStatusTool(depsOf([])) as any).output.schema, out)
  })

  it('闸门本身不是恒真：把 runId 塞成 null 必须被它拦下（故障注入）', () => {
    const schema = (defineRunStatusTool(depsOf([])) as any).output.schema
    expect(() => assertConformsToSchema(schema, { success: true, snapshot: { runId: null } })).toThrow()
    // 对照组：键省略时放行（这才是修复后的正确形状）
    expect(() => assertConformsToSchema(schema, { success: true, snapshot: { status: 'terminated' } })).not.toThrow()
  })

  it('需求不存在：getRequirement 抛错被工具传播（不静默成功）', async () => {
    await expect(execute(depsOf([]), { requirement_id: 'REQ-none' })).rejects.toThrow(/需求不存在/)
  })
})
