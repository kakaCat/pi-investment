/**
 * 子卡派发的 agent 句柄兜底（D14 / REQ-260927123256-196b）单测。
 *
 * 锁三件事：① 调用方带 exec.agent → 原样透传；② 缺 exec 时按父卡所属需求的绑定窗口查在线 agent；
 * ③ 解不到 → 返回 ok:false 与可读原因（不再让引擎抛 "reading 'session'" TypeError）。
 */
import { describe, it, expect } from 'vitest'
import { ensureAgentHandle } from '../src/application/internal/agent-handle.js'
import type { UseCaseDeps } from '../src/application/ports.js'

function depsWith(opts: { boundWindow?: string; online?: boolean; parentExists?: boolean }): UseCaseDeps {
  const tasks = opts.parentExists === false ? [] : [{ id: 't-p', requirementId: 'REQ-x' }]
  const requirements = [{ id: 'REQ-x', sourceSessionId: opts.boundWindow }]
  const agent = { session: {} }
  return {
    repo: { snapshot: () => ({ tasks, requirements, triages: [] }) },
    agents: () => ({ get: (id: string) => (opts.online === true && id === opts.boundWindow ? agent : undefined) }),
  } as unknown as UseCaseDeps
}

describe('ensureAgentHandle（D14）', () => {
  it('调用方带 exec.agent → 原样透传（工具路径）', () => {
    const exec = { agent: { session: {} } }
    const r = ensureAgentHandle(depsWith({ boundWindow: 'w1', online: false }), 't-p', 't-sub', exec)
    expect(r.ok).toBe(true)
    if (r.ok) expect(r.exec).toBe(exec)
  })

  it('缺 exec 但绑定窗口在线 → 兜底解析出 { agent }（看板「继续」/启动恢复）', () => {
    const r = ensureAgentHandle(depsWith({ boundWindow: 'session-a', online: true }), 't-p', 't-sub', undefined)
    expect(r.ok).toBe(true)
    if (r.ok) expect((r.exec as { agent?: unknown }).agent).toBeDefined()
  })

  it('绑定窗口不在线 → ok:false，原因含窗口与恢复命令', () => {
    const r = ensureAgentHandle(depsWith({ boundWindow: 'session-a', online: false }), 't-p', 't-sub', undefined)
    expect(r.ok).toBe(false)
    if (!r.ok) {
      expect(r.reason).toContain('session-a')
      expect(r.reason).toContain('reqboard_task_run')
    }
  })

  it('父卡不存在 → ok:false（窗口未知，仍给可读原因）', () => {
    const r = ensureAgentHandle(depsWith({ parentExists: false, online: true }), 't-nope', 't-sub', undefined)
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.reason).toContain('不在线')
  })
})
