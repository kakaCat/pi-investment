/**
 * 看板父子卡与自动链控制面（REQ-4842fe t-3be71b）——纯渲染函数单测。
 *
 * 验收口径（任务卡）：父卡展开显示子卡链与进度、徽标随 autoRun 变化（运行中/已暂停/熔断）、
 * 存量卡外观与现状一致。对应 design/observability §2 的看板口径。
 */
import { describe, it, expect } from 'vitest'
import {
  autoBadgeOf,
  isLegacyTask,
  isParentTask,
  progressText,
  renderAutoBadge,
  renderAutoControls,
  renderSubtaskChain,
  subtaskChain,
  subtaskProgress,
} from '../src/client/render/subtask-view.js'

import type { RequirementRecord } from '../src/client/types.js'

type Req = RequirementRecord
type Task = Parameters<typeof renderSubtaskChain>[0][number]

const req = (over: Partial<Req> = {}): Req =>
  ({ id: 'REQ-1', title: 'T', description: '', status: 'implementing', autoRun: true, ...over } as Req)
const task = (over: Record<string, unknown>): Task => ({ status: 'todo', title: 'T', phase: 'implement', ...over } as Task)

describe('自动状态徽标：运行中 / 已暂停 / 熔断 / 手动', () => {
  it('autoRun=true → 运行中', () => {
    expect(autoBadgeOf(req({ autoRun: true })).kind).toBe('running')
  })

  it('autoRun=false + 人工暂停 → 已暂停', () => {
    expect(autoBadgeOf(req({ autoRun: false, advance: { pausedReason: 'manual' } })).kind).toBe('paused')
  })

  it('autoRun=false + 停滞/失败原因 → 熔断', () => {
    expect(autoBadgeOf(req({ autoRun: false, advance: { pausedReason: 'stagnation' } })).kind).toBe('breaker')
    expect(autoBadgeOf(req({ autoRun: false, advance: { pausedReason: 'fail' } })).kind).toBe('breaker')
    expect(autoBadgeOf(req({ autoRun: false, advance: { failureStreak: 3 } })).kind).toBe('breaker')
  })

  it('autoRun 缺省（存量需求）→ 手动，且徽标渲染出 data-auto', () => {
    const r = { } as Req
    expect(autoBadgeOf(r).kind).toBe('manual')
    expect(renderAutoBadge(req({ autoRun: undefined }))).toContain('data-auto="manual"')
    expect(renderAutoBadge(req({ autoRun: true }))).toContain('运行中')
  })
})

describe('子卡链与进度口径', () => {
  const tasks = [
    task({ id: 't-p1', title: '父卡1', status: 'in_progress' }),
    task({ id: 't-s1', title: '研发子卡', parentId: 't-p1', stageKind: 'dev', status: 'done' }),
    task({ id: 't-s2', title: '复核子卡', parentId: 't-p1', stageKind: 'review', status: 'todo', attempt: 1 }),
    task({ id: 't-p2', title: '父卡2', status: 'done' }),
    task({ id: 't-legacy', title: '存量卡', status: 'todo' }),
    task({ id: 't-sx', title: '被取消子卡', parentId: 't-p1', stageKind: 'test', status: 'canceled' }),
  ]

  it('父卡/存量卡判定：有子卡才是父卡，无 parentId 且无子卡是存量卡', () => {
    expect(isParentTask(tasks, tasks[0]!)).toBe(true)
    expect(isParentTask(tasks, tasks[1]!)).toBe(false)
    expect(isLegacyTask(tasks, tasks[4]!)).toBe(true)
    expect(isLegacyTask(tasks, tasks[0]!)).toBe(false)
  })

  it('进度口径：canceled 不计入分母；父卡=有新式子卡的顶层卡（t-p2/t-legacy 无子卡 → 不算父卡）', () => {
    const p = subtaskProgress(tasks)
    expect(p.parentsTotal).toBe(1)      // 只有 t-p1 是父卡
    expect(p.parentsDone).toBe(0)       // t-p1 仍在跑
    expect(p.subtasksTotal).toBe(2)     // t-s1 + t-s2（t-sx 已取消不计）
    expect(p.subtasksDone).toBe(1)
    expect(progressText(p)).toBe('父卡 0/1 · 子卡 1/2')
  })

  it('无子卡的需求退回父卡口径（存量需求显示不变）', () => {
    const only = [task({ id: 't-p', title: '卡', status: 'todo' })]
    expect(progressText(subtaskProgress(only))).toBe('父卡 0/0')
  })

  it('父卡展开显示子卡链：stageKind 中文徽标 + 重跑次数', () => {
    const html = renderSubtaskChain(tasks, tasks[0]!)
    expect(html).toContain('<details')
    expect(html).toContain('open')
    expect(html).toContain('研发')
    expect(html).toContain('复核')
    expect(html).toContain('第 2 次')   // attempt=1 → 第 2 次
    expect(html).toContain('data-action="toggle-subtasks"')
  })

  it('存量卡不出现子卡区（外观与现状一致）', () => {
    expect(renderSubtaskChain(tasks, tasks[4]!)).toBe('')
    expect(subtaskChain(tasks, 't-legacy')).toEqual([])
  })
})

describe('控制面：暂停 / 继续 / 终止', () => {
  it('autoRun 缺省（存量需求）→ 不出现控制面', () => {
    expect(renderAutoControls({ id: 'REQ-1' } as Req)).toBe('')
  })

  it('运行中 → 暂停 + 终止；已暂停 → 继续 + 终止', () => {
    const running = renderAutoControls({ id: 'REQ-1', autoRun: true } as Req)
    expect(running).toContain('data-action="auto-run-pause"')
    expect(running).toContain('data-action="auto-run-stop"')

    const paused = renderAutoControls({ id: 'REQ-1', autoRun: false } as Req)
    expect(paused).toContain('data-action="auto-run-resume"')
    expect(paused).toContain('data-action="auto-run-stop"')
  })
})
