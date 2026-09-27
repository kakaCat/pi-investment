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
    ...(jobs !== undefined ? { jobs } : {}),
  } as unknown as UseCaseDeps
}

function execute(deps: UseCaseDeps, args: Record<string, unknown>): Promise<Record<string, unknown>> {
  const tool = defineRunStatusTool(deps) as unknown as {
    execute: (a: unknown, e: unknown) => Promise<Record<string, unknown>>
  }
  return tool.execute(args, {})
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

  it('无 checkpoint（advance 缺省）：runId=null，且返回体不出现 run_id 键', async () => {
    const req = { id: 'REQ-y', status: 'implementing' }
    const out = await execute(depsOf([req]), { requirement_id: 'REQ-y' })
    expect(out.success).toBe(true)
    expect('run_id' in out).toBe(false)
    expect((out.snapshot as Record<string, unknown>).runId).toBeNull()
  })

  it('需求不存在：getRequirement 抛错被工具传播（不静默成功）', async () => {
    await expect(execute(depsOf([]), { requirement_id: 'REQ-none' })).rejects.toThrow(/需求不存在/)
  })
})
