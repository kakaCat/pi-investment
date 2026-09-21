/**
 * L1 领域单测 · 任务状态机（REQ-47939a t2 / INV-1）。
 * 表驱动口径同 requirement-status.test.ts：遍历 TASK_TRANSITIONS 逐项断言 + 人工闸门。
 */
import { describe, it, expect } from 'vitest'
import {
  TASK_TRANSITIONS,
  HUMAN_ONLY_TASK_TRANSITIONS,
  SYSTEM_TASK_TRANSITIONS,
  canTaskTransition,
  assertTaskTransition,
  type TaskStatus,
} from '../../src/domain/task/TaskStatus.js'
import * as protocol from '../../src/shared/protocol.js'

const ALL: TaskStatus[] = Object.keys(TASK_TRANSITIONS) as TaskStatus[]

describe('INV-1 任务状态机：表驱动逐项一致', () => {
  it('canTaskTransition 对全表每个 (from,to) 组合与 TASK_TRANSITIONS 一致', () => {
    for (const from of ALL) {
      const allowed = new Set(TASK_TRANSITIONS[from])
      for (const to of ALL) {
        expect(canTaskTransition(from, to), from + ' -> ' + to).toBe(allowed.has(to))
      }
    }
  })

  it('assertTaskTransition：非法转移抛 invalid_transition', () => {
    try {
      assertTaskTransition('todo', 'done', 'agent')
      throw new Error('应当抛错')
    } catch (err) {
      expect((err as { code?: string }).code).toBe('invalid_transition')
    }
  })

  it('人工闸门（取消/复活）：agent 一律 human_gate、human 放行', () => {
    for (const key of HUMAN_ONLY_TASK_TRANSITIONS) {
      const [from, to] = key.split('>') as [TaskStatus, TaskStatus]
      expect(canTaskTransition(from, to), key).toBe(true)
      try {
        assertTaskTransition(from, to, 'agent')
        throw new Error('应当抛 human_gate: ' + key)
      } catch (err) {
        expect((err as { code?: string }).code, key).toBe('human_gate')
      }
      expect(() => assertTaskTransition(from, to, 'human'), key).not.toThrow()
    }
  })

  it('system 白名单：in_progress>todo 可，todo>integrating 不可', () => {
    for (const key of SYSTEM_TASK_TRANSITIONS) {
      const [from, to] = key.split('>') as [TaskStatus, TaskStatus]
      expect(() => assertTaskTransition(from, to, 'system'), key).not.toThrow()
    }
    expect(() => assertTaskTransition('todo', 'canceled', 'system')).toThrow()
  })
})

describe('t2 再导出：shared/protocol 与 domain 同源', () => {
  it('任务状态机常量经 protocol 再导出后引用同一实现', () => {
    expect(protocol.TASK_TRANSITIONS).toBe(TASK_TRANSITIONS)
    expect(protocol.HUMAN_ONLY_TASK_TRANSITIONS).toBe(HUMAN_ONLY_TASK_TRANSITIONS)
    expect(protocol.canTaskTransition('todo', 'in_progress')).toBe(true)
  })
})
