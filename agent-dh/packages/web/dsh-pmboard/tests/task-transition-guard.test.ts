/**
 * 任务级收敛点单测（REQ-260927100007-b8ba t1 / FR-8）。
 *
 * 契约：任务状态只能经 transitionTask 改变；**非法/越权转移抛错且不改动任何字段**
 * （禁止半迁移态）。四条写入路径（ExecuteTask / AdvanceChain / failure-handling / HTTP 路由）
 * 全部改经此收敛点后，这里锁死「拒绝 = 零副作用」。
 */
import { describe, it, expect } from 'vitest'
import { transitionTask } from '../src/application/internal/task-transition.js'
import { task } from './application/harness.js'
import type { TaskRecord } from '../src/shared/protocol.js'

/** 捕获抛错并返回 code（无 code 时返回 message）。 */
function codeOf(fn: () => void): string {
  try {
    fn()
    throw new Error('应当抛错但没有')
  } catch (err) {
    const e = err as { code?: string; message?: string }
    return e.code ?? String(e.message)
  }
}

describe('transitionTask（唯一任务状态收敛点）', () => {
  it('合法转移：状态/版本/时间/操作者更新，且追加状态事件', () => {
    const before = task()
    const t = structuredClone(before)
    transitionTask(t, 'in_progress', { at: 5, actor: { kind: 'agent', sessionId: 's' }, reason: '开工' })
    expect(t.status).toBe('in_progress')
    expect(t.version).toBe(before.version + 1)
    expect(t.updatedAt).toBe(5)
    expect(t.updatedBy).toEqual({ kind: 'agent', sessionId: 's' })
    expect(t.statusHistory?.at(-1)).toMatchObject({ status: 'in_progress', at: 5 })
  })

  it('非法转移（todo→done）：抛 invalid_transition 且 task 字段全部不变（零副作用）', () => {
    const t = task()
    const snap: TaskRecord = structuredClone(t)
    expect(codeOf(() => transitionTask(t, 'done', { at: 9, actor: { kind: 'agent' } }))).toBe('invalid_transition')
    expect(t).toEqual(snap)
  })

  it('人工闸门（todo→canceled，agent）：抛 human_gate 且零副作用；human 放行', () => {
    const t = task()
    const snap: TaskRecord = structuredClone(t)
    expect(codeOf(() => transitionTask(t, 'canceled', { at: 9, actor: { kind: 'agent' } }))).toBe('human_gate')
    expect(t).toEqual(snap)
    transitionTask(t, 'canceled', { at: 9, actor: { kind: 'human' } })
    expect(t.status).toBe('canceled')
  })

  it('system 白名单：父卡收尾 in_progress→done 放行；in_review→done 抛 system_gate 且不变', () => {
    const p = task({ status: 'in_progress' })
    transitionTask(p, 'done', { at: 1, actor: { kind: 'system' }, role: 'parent' })
    expect(p.status).toBe('done')

    const r = task({ status: 'in_review' })
    const snap: TaskRecord = structuredClone(r)
    expect(codeOf(() => transitionTask(r, 'done', { at: 1, actor: { kind: 'system' } }))).toBe('system_gate')
    expect(r).toEqual(snap)
  })

  it('逃生舱 allowIllegalTransition：仅迁移/回填可用，放行且不动其它字段语义', () => {
    const t = task()
    transitionTask(t, 'done', { at: 3, actor: { kind: 'agent' }, allowIllegalTransition: true })
    expect(t.status).toBe('done')
    expect(t.updatedAt).toBe(3)
  })
})
