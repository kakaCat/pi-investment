/**
 * 子卡派发的 agent 句柄兜底（D14 / REQ-260927123256-196b）单测。
 *
 * 锁三件事：① 调用方带 exec.agent → 原样透传；② 缺 exec 时按父卡所属需求的绑定窗口查在线 agent；
 * ③ 解不到 → 返回 ok:false 与可读原因（不再让引擎抛 "reading 'session'" TypeError）。
 *
 * **调用方适配（2026-09-27，REQ-260927202051-f6df 读方改造 D）**：`ensureAgentHandle` 新增第 5 参
 * `tasks`（任务改从队列取，`LedgerView.tasks` 随台账 v9 移除）。本文件原按 4 参调用，第 5 参缺失
 * ⇒ `tasks.find` 抛 `Cannot read properties of undefined (reading 'find')`（3 条用例红）。
 * 生产调用点 `ExecuteTask.ts:171` 已传 `queueTasks`，本处仅补齐测试夹具。
 */
import { describe, it, expect } from 'vitest'
import { ensureAgentHandle } from '../src/application/internal/agent-handle.js'
import type { UseCaseDeps } from '../src/application/ports.js'
import type { TaskRecord } from '../src/shared/protocol.js'

interface Fixture {
  deps: UseCaseDeps
  /** 队列任务（v9：任务不再存台账，改由调用方显式传入）。 */
  tasks: readonly TaskRecord[]
}

function fixture(opts: { boundWindow?: string; online?: boolean; parentExists?: boolean }): Fixture {
  const tasks = (opts.parentExists === false
    ? []
    : [{ id: 't-p', requirementId: 'REQ-x' }]) as unknown as readonly TaskRecord[]
  const requirements = [{ id: 'REQ-x', sourceSessionId: opts.boundWindow }]
  const agent = { session: {} }
  const deps = {
    repo: { snapshot: () => ({ tasks, requirements, triages: [] }) },
    agents: () => ({ get: (id: string) => (opts.online === true && id === opts.boundWindow ? agent : undefined) }),
  } as unknown as UseCaseDeps
  return { deps, tasks }
}

describe('ensureAgentHandle（D14）', () => {
  it('调用方带 exec.agent → 原样透传（工具路径）', () => {
    const exec = { agent: { session: {} } }
    const { deps, tasks } = fixture({ boundWindow: 'w1', online: false })
    const r = ensureAgentHandle(deps, 't-p', 't-sub', exec, tasks)
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.exec).toBe(exec)
  })

  it('缺 exec 但绑定窗口在线 → 兜底解析出 { agent }（看板「继续」/启动恢复）', () => {
    const { deps, tasks } = fixture({ boundWindow: 'session-a', online: true })
    const r = ensureAgentHandle(deps, 't-p', 't-sub', undefined, tasks)
    expect(r.ok).toBe(true)
    if (r.ok) expect((r.exec as { agent?: unknown }).agent).toBeDefined()
  })

  it('绑定窗口不在线 → ok:false，原因含窗口与恢复命令', () => {
    const { deps, tasks } = fixture({ boundWindow: 'session-a', online: false })
    const r = ensureAgentHandle(deps, 't-p', 't-sub', undefined, tasks)
    expect(r.ok).toBe(false)
    if (!r.ok) {
      expect(r.reason).toContain('session-a')
      expect(r.reason).toContain('reqboard_task_run')
    }
  })

  it('父卡不存在 → ok:false（窗口未知，仍给可读原因）', () => {
    const { deps, tasks } = fixture({ parentExists: false, online: true })
    const r = ensureAgentHandle(deps, 't-nope', 't-sub', undefined, tasks)
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.reason).toContain('不在线')
  })
})
