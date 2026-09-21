/**
 * L1 领域单测 · 子卡状态机与回退转移（REQ-4842fe t2 / FR-5、FR-14）。
 *
 * 口径：子卡收紧四态（不进 integrating/testing/in_review）；done 重开与需求回退上游
 * 都是人工门；legacy 角色行为与改造前逐字一致（存量卡不受影响）。
 */
import { describe, it, expect } from 'vitest'
import {
  TASK_TRANSITIONS,
  SUBTASK_TRANSITIONS,
  PARENT_TRANSITIONS,
  canTaskTransition,
  assertTaskTransition,
  taskTransitionsFor,
  type TaskStatus,
} from '../../src/domain/task/TaskStatus.js'
import {
  canReqTransition,
  assertReqTransition,
  agentNextActions,
} from '../../src/domain/requirement/RequirementStatus.js'

const codeOf = (fn: () => void): string | undefined => {
  try {
    fn()
    return undefined
  } catch (err) {
    return (err as { code?: string }).code
  }
}

describe('子卡四态收紧（FR-5）', () => {
  const ALL: TaskStatus[] = Object.keys(TASK_TRANSITIONS) as TaskStatus[]

  it('子卡合法转移表与 SUBTASK_TRANSITIONS 逐项一致', () => {
    for (const from of ALL) {
      const allowed = new Set(SUBTASK_TRANSITIONS[from])
      for (const to of ALL) {
        expect(canTaskTransition(from, to, 'subtask'), from + ' -> ' + to).toBe(allowed.has(to))
      }
    }
  })

  it('子卡 in_progress → integrating / testing / in_review 一律被拒（无递归语义）', () => {
    for (const to of ['integrating', 'testing', 'in_review'] as TaskStatus[]) {
      expect(codeOf(() => assertTaskTransition('in_progress', to, 'agent', 'subtask')), to).toBe('invalid_transition')
    }
  })

  it('子卡正常路径：todo→in_progress→done 与失败回退 in_progress→todo 均放行', () => {
    expect(() => assertTaskTransition('todo', 'in_progress', 'agent', 'subtask')).not.toThrow()
    expect(() => assertTaskTransition('in_progress', 'done', 'agent', 'subtask')).not.toThrow()
    expect(() => assertTaskTransition('in_progress', 'todo', 'system', 'subtask')).not.toThrow()
  })

  it('角色 → 表分派：legacy 五段表；parent/subtask 各自收紧表', () => {
    expect(taskTransitionsFor('parent')).toBe(PARENT_TRANSITIONS)
    expect(taskTransitionsFor('legacy')).toBe(TASK_TRANSITIONS)
    expect(taskTransitionsFor('subtask')).toBe(SUBTASK_TRANSITIONS)
    expect(PARENT_TRANSITIONS.in_progress).toContain('done')
    expect(PARENT_TRANSITIONS.in_review).toEqual([])
  })
})

describe('done 卡重开与取消：仅人（FR-15）', () => {
  it('done → in_progress：human 放行，agent/system 返回 human_gate', () => {
    expect(canTaskTransition('done', 'in_progress')).toBe(true)
    expect(() => assertTaskTransition('done', 'in_progress', 'human')).not.toThrow()
    expect(codeOf(() => assertTaskTransition('done', 'in_progress', 'agent'))).toBe('human_gate')
    expect(codeOf(() => assertTaskTransition('done', 'in_progress', 'system'))).toBe('human_gate')
  })

  it('done → canceled：human 放行，agent 返回 human_gate', () => {
    expect(() => assertTaskTransition('done', 'canceled', 'human')).not.toThrow()
    expect(codeOf(() => assertTaskTransition('done', 'canceled', 'agent'))).toBe('human_gate')
  })

  it('done → todo 仍非法（重开只到 in_progress，不跳回待办）', () => {
    expect(codeOf(() => assertTaskTransition('done', 'todo', 'human'))).toBe('invalid_transition')
  })
})

describe('需求回退上游（FR-14）', () => {
  it('implementing → design：human 放行，agent/system 返回 human_gate', () => {
    expect(canReqTransition('implementing', 'design')).toBe(true)
    expect(() => assertReqTransition('implementing', 'design', 'human')).not.toThrow()
    expect(codeOf(() => assertReqTransition('implementing', 'design', 'agent'))).toBe('human_gate')
    expect(codeOf(() => assertReqTransition('implementing', 'design', 'system'))).toBe('human_gate')
  })

  it('agentNextActions(implementing) 不变（回退是人工门，不在 agent 可自行推进项里）', () => {
    expect(agentNextActions('implementing')).toEqual(['accepting'])
  })
})

describe('legacy 兼容：存量卡行为与改造前一致', () => {
  it('存量卡仍可走五段状态机', () => {
    expect(() => assertTaskTransition('in_progress', 'integrating', 'agent')).not.toThrow()
    expect(() => assertTaskTransition('integrating', 'testing', 'agent')).not.toThrow()
    expect(() => assertTaskTransition('testing', 'in_review', 'agent')).not.toThrow()
    expect(() => assertTaskTransition('in_review', 'done', 'agent')).not.toThrow()
  })

  it('默认 role 即 legacy（既有三参调用点零改动）', () => {
    expect(canTaskTransition('in_progress', 'integrating')).toBe(true)
    expect(codeOf(() => assertTaskTransition('done', 'todo', 'human'))).toBe('invalid_transition')
  })
})
