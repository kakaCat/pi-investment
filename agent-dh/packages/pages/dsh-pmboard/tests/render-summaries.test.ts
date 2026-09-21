/**
 * render-summaries 人话摘要单测（REQ-c48f99 t4 / FR-5）。
 * 锁定：13 个摘要函数对正常/错误/畸形输入不 throw、输出单行、首行非 {。
 */
import { describe, it, expect } from 'vitest'
import {
  taskMoveSummary, submitSummary, statusSummary, captureSummary, createSummary,
  askConfirmSummary, decomposeSummary, moveSummary, taskReportSummary,
  acceptSheetSummary, taskStatusSummary, taskRunSummary, taskExecuteSummary,
} from '../src/tools/render-summaries.js'
import { renderSmart } from '../src/tools/shared.js'

const ALL: Array<[string, (v: unknown) => string, unknown, string[]]> = [
  ['taskMove', taskMoveSummary, { success: true, task_id: 't-x', from: 'todo', to: 'in_progress' }, ['t-x', '开工', '退回 → 开工']],
  ['submit', submitSummary, { success: true, requirement_id: 'REQ-x', status: 'accepting', artifact: { kind: 'verification' } }, ['REQ-x', '验收材料', 'accepting']],
  ['status-bound', statusSummary, { bound: true, open_count: 2, open_requirements: [{ id: 'REQ-x', status: 'implementing' }] }, ['2 个进行中', 'REQ-x']],
  ['status-unbound', statusSummary, { bound: false }, ['未绑定']],
  ['capture', captureSummary, { success: true, requirement_id: 'REQ-x', answers: { title: '需求A', category: 'feature', difficulty: 'standard' } }, ['REQ-x', '需求A', 'feature/standard']],
  ['create', createSummary, { requirement_id: 'REQ-x', title: '标题', status: 'draft' }, ['REQ-x', '标题', 'draft']],
  ['askConfirm-ok', askConfirmSummary, { confirmed: true, advanced: true, from: 'design', to: 'decomposing' }, ['已确认', 'design → decomposing']],
  ['askConfirm-no', askConfirmSummary, { confirmed: false, user_choice: '需要修改' }, ['未确认', '需要修改']],
  ['decompose', decomposeSummary, { success: true, created: [{}, {}, {}], requirement_status: 'implementing' }, ['3 个任务', 'implementing']],
  ['move', moveSummary, { success: true, requirement_id: 'REQ-x', from: 'design', to: 'decomposing' }, ['REQ-x', 'design → decomposing']],
  ['taskReport', taskReportSummary, { success: true, task_id: 't-x', report_index: 2 }, ['t-x', '第 2 段']],
  ['acceptSheet', acceptSheetSummary, { recorded: 5, passed: 3, pending: 2 }, ['3/5', '剩余 2']],
  ['acceptSheet-archived', acceptSheetSummary, { archived: true }, ['已归档']],
  ['taskStatus', taskStatusSummary, { task_id: 't-x', status: 'in_progress', progress: 60 }, ['t-x', 'in_progress', '60%']],
  ['taskRun', taskRunSummary, { success: true, task_id: 't-x', subtask_executed: { id: 't-y' }, parent_status: 'in_progress' }, ['t-x', 't-y']],
]

describe('render-summaries · 正常档', () => {
  for (const [name, fn, value, frags] of ALL) {
    it(name, () => {
      const line = fn(value)
      for (const f of frags) expect(line, name + ' 缺 ' + f).toContain(f)
      expect(line.includes('\n')).toBe(false)
    })
  }
})

describe('render-summaries · 错误与畸形档（不 throw、单行）', () => {
  const fns = [taskMoveSummary, submitSummary, statusSummary, captureSummary, createSummary,
    askConfirmSummary, decomposeSummary, moveSummary, taskReportSummary,
    acceptSheetSummary, taskStatusSummary, taskRunSummary]
  it('字符串错误值 → ❌ 前缀', () => {
    for (const fn of fns) {
      const line = fn('REQBOARD_BAD_STATUS: 状态不允许')
      expect(line.startsWith('❌')).toBe(true)
      expect(line).toContain('REQBOARD_BAD_STATUS')
    }
  })
  it('undefined/null/数组/数字 不 throw', () => {
    for (const fn of fns) {
      for (const bad of [undefined, null, [1, 2], 42, {}]) {
        const line = fn(bad)
        expect(typeof line).toBe('string')
        expect(line.includes('\n')).toBe(false)
      }
    }
  })
  it('success=false 对象 → ❌ 前缀', () => {
    expect(taskMoveSummary({ success: false, note: '状态机拒绝' })).toContain('❌')
    expect(submitSummary({ success: false, note: '缺文档' })).toContain('❌')
    expect(decomposeSummary({ success: false, note: '条款未覆盖' })).toContain('❌')
  })
})

describe('renderSmart 接线（FR-5 端到端形态）', () => {
  it('reqboard_status 形态：首行中文摘要 + 空行 + JSON', () => {
    const value = { bound: true, open_count: 1, open_requirements: [{ id: 'REQ-x', status: 'implementing' }] }
    const text = renderSmart(statusSummary)(undefined, value)[0].text
    const head = text.split('\n')[0]
    expect(head.startsWith('📊')).toBe(true)
    expect(head.startsWith('{')).toBe(false)
    expect(text).toContain('\n\n')
    expect(text).toContain('"open_count": 1')
  })
  it('taskExecuteSummary 是 taskRunSummary 别名', () => {
    expect(taskExecuteSummary).toBe(taskRunSummary)
  })
})
