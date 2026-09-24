/**
 * 事件型 worktree 提示词单测（REQ-260923222557-d3b0 t2 · serves FR-2, FR-3）。
 *
 * 断言：变量替换无残骸、两份事件文本各含所需命令、implementing 路由档含创建命令（FR-1）。
 */
import { describe, it, expect } from 'vitest'
import { renderWorktreePrompt, WORKTREE_EVENT_TEMPLATES } from '../src/domain/prompt/worktree-events.js'
import { resolveStagePrompt } from '../src/domain/prompt/index.js'

describe('renderWorktreePrompt 变量替换', () => {
  it('task_done：{id}/{task_id}/{task_title} 全部替换、无花括号残骸', () => {
    const text = renderWorktreePrompt('task_done', { requirementId: 'REQ-260923222557-d3b0', taskId: 't-abc123', taskTitle: '修面板文案' })
    expect(text).toContain('REQ-260923222557-d3b0')
    expect(text).toContain('t-abc123')
    expect(text).toContain('修面板文案')
    expect(text).not.toMatch(/\{(id|task_id|task_title)\}/)
    expect(text).toContain('git commit -m')
  })

  it('archived：含合并与清理命令、无花括号残骸', () => {
    const text = renderWorktreePrompt('archived', { requirementId: 'REQ-x' })
    expect(text).toContain('git merge --no-ff feature/REQ-x')
    expect(text).toContain('git worktree remove .worktrees/REQ-x/')
    expect(text).toContain('git branch -d feature/REQ-x')
    expect(text).not.toMatch(/\{(id|task_id|task_title)\}/)
  })

  it('缺失变量置空串（不留 {} 残骸）', () => {
    const text = renderWorktreePrompt('task_done', { requirementId: 'REQ-y' })
    expect(text).not.toMatch(/\{(id|task_id|task_title)\}/)
    expect(text).toContain('REQ-y')
  })

  it('两份模板齐备且各自含「不强制」口径（边界：不强制 agent 执行）', () => {
    expect(Object.keys(WORKTREE_EVENT_TEMPLATES).sort()).toEqual(['archived', 'task_done'])
    expect(WORKTREE_EVENT_TEMPLATES.task_done).toContain('不强制执行')
    expect(WORKTREE_EVENT_TEMPLATES.archived).toContain('不强制执行')
  })
})

describe('implementing 路由档（FR-1）', () => {
  it('resolveStagePrompt(implementing/light) 含 worktree 创建命令与目录/分支约定', () => {
    const r = resolveStagePrompt({ stage: 'implementing', difficulty: 'light' })
    expect(r.text).toContain('git worktree add .worktrees/REQ-')
    expect(r.text).toContain('feature/REQ-')
    expect(r.text).toContain('git worktree remove')
    expect(r.text).toContain('不强制')
  })
})
