/**
 * FR-6 超时归位联调（REQ-260927144541-0481）——任务/链级工具的 timeoutMs 路由到非交互档。
 * serves: FR-6
 *
 * 联调口径（请求样例 -> 期望 -> 实际）：
 *  ① 投递类 reqboard_task_run / reqboard_task_execute → LIMITS.timeoutWriteMs（30_000）；
 *  ② 查询类 reqboard_run_status / reqboard_task_status → LIMITS.timeoutReadMs（15_000）；
 *  ③ 四个工具均不得取 timeoutInteractiveMs（3_600_000）——交互档只服务需人作答的弹框类
 *     （AskConfirm / AcceptSheet）；TaskExecuteTool 是别名，无独立 timeoutMs，随主入口；
 *  ④ 线上投递路径实测：JobsPort 可用时 task_run 认领+投递后立即返回 dispatched
 *     （耗时毫秒级 << 30s），证明写档不会掐断线上链；只有内存/嵌入调用的同步兼容路径可能长跑。
 */
import { describe, expect, it } from 'vitest'
import { defineAdvanceTool, defineTaskExecuteTool, defineRunStatusTool, defineTaskStatusTool } from '../src/tools/index.js'
import { LIMITS } from '../src/domain/limits.js'
import { makeHarness, req, task } from './application/harness.js'

const W = 'session-w-001'

interface ToolShell {
  name: string
  timeoutMs: number
  execute: (a: unknown, e: unknown) => Promise<Record<string, unknown>>
}

function shell(t: unknown): ToolShell {
  return t as unknown as ToolShell
}

/** 线上同款投递端口：start 立即返回 job id（链在后台跑，不由工具调用栈持有）。 */
function jobsPort() {
  return {
    available: () => true,
    start: async () => 'job-integration-1',
    get: async () => null,
  }
}

function seeded() {
  // 任务落**队列**（REQ-260927202051-f6df：v9 台账已无 tasks 通道）
  const h = makeHarness({ tasks: [task({ id: 't-p', status: 'todo', title: '父卡' })] })
  h.repo.ledger.requirements = [req({ status: 'implementing', autoRun: false })]
  return h
}

describe('FR-6 超时归位（任务/链级工具不得挂交互档）', () => {
  it('TC-12a 投递类两个工具都取 timeoutWriteMs，别名与主入口同值', () => {
    const h = seeded()
    const run = shell(defineAdvanceTool(h.deps))
    const exec = shell(defineTaskExecuteTool(h.deps))
    expect(run.timeoutMs).toBe(LIMITS.timeoutWriteMs)
    expect(exec.timeoutMs).toBe(LIMITS.timeoutWriteMs)
    expect(exec.timeoutMs).toBe(run.timeoutMs)
  })

  it('TC-12b 查询类两个工具都取 timeoutReadMs', () => {
    const h = seeded()
    expect(shell(defineRunStatusTool(h.deps)).timeoutMs).toBe(LIMITS.timeoutReadMs)
    expect(shell(defineTaskStatusTool(h.deps)).timeoutMs).toBe(LIMITS.timeoutReadMs)
  })

  it('TC-12c 四个任务/链级工具无一取 timeoutInteractiveMs', () => {
    const h = seeded()
    const all = [
      shell(defineAdvanceTool(h.deps)),
      shell(defineTaskExecuteTool(h.deps)),
      shell(defineRunStatusTool(h.deps)),
      shell(defineTaskStatusTool(h.deps)),
    ]
    expect(all.map((t) => t.name)).toEqual([
      'reqboard_task_run',
      'reqboard_task_execute',
      'reqboard_run_status',
      'reqboard_task_status',
    ])
    expect(all.filter((t) => t.timeoutMs === LIMITS.timeoutInteractiveMs)).toEqual([])
    for (const t of all) expect(t.timeoutMs).toBeLessThan(LIMITS.timeoutInteractiveMs)
  })

  it('TC-12d 线上投递路径：task_run 立即返回 dispatched（耗时可忽略，30s 写档不掐链）', async () => {
    const h = seeded()
    h.deps.jobs = jobsPort() as never
    const started = Date.now()
    const out = await shell(defineAdvanceTool(h.deps)).execute({ task_id: 't-p' }, { agent: { id: W } })
    const elapsed = Date.now() - started
    expect(out.success).toBe(true)
    expect(out.status).toBe('dispatched')
    expect(out.job_id).toBe('job-integration-1')
    expect(typeof out.run_id).toBe('string')
    expect(elapsed).toBeLessThan(LIMITS.timeoutWriteMs)
    expect(h.repo.ledger.requirements[0]!.autoRun).toBe(true)
  })
})
