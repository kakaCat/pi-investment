/**
 * L1 领域单测 · done 凭证门（REQ-47939a t3 / INV-4，REQ-2e9473 t06/W2）。
 * 覆盖四重校验的拒绝码与通过路径；拒绝理由文案与搬迁前一致。
 */
import { describe, it, expect } from 'vitest'
import {
  checkDoneEvidence,
  findRecentAgentDoneTask,
  type DoneEvidenceInput,
} from '../../src/domain/workflow/DoneEvidenceSpec.js'

function input(over: Partial<DoneEvidenceInput> = {}): DoneEvidenceInput {
  return {
    hasReport: true,
    reportFilesChanged: ['src/a.ts'],
    reportCompleted: ['x'],
    hasTraceWork: true,
    fileEvidence: false,
    pagesSrcFiles: [],
    clientBuildExists: false,
    clientBuildMtime: 0,
    newestPagesSrcMtime: 0,
    ...over,
  }
}

describe('checkDoneEvidence：四重校验', () => {
  it('① 无汇报 → REQBOARD_NO_REPORT', () => {
    const v = checkDoneEvidence(input({ hasReport: false }))
    expect(v).toMatchObject({ ok: false, code: 'REQBOARD_NO_REPORT' })
    if (!v.ok) expect(v.reason).toContain('还没有 reqboard_task_report 汇报')
  })

  it('① 汇报证据为空 → REQBOARD_NO_REPORT', () => {
    const v = checkDoneEvidence(input({ reportFilesChanged: [], reportCompleted: [] }))
    expect(v).toMatchObject({ ok: false, code: 'REQBOARD_NO_REPORT' })
    if (!v.ok) expect(v.reason).toContain('汇报证据为空')
  })

  it('② 无工具痕迹且无文件证据 → REQBOARD_NO_EVIDENCE', () => {
    const v = checkDoneEvidence(input({ hasTraceWork: false, fileEvidence: false }))
    expect(v).toMatchObject({ ok: false, code: 'REQBOARD_NO_EVIDENCE' })
    expect(checkDoneEvidence(input({ hasTraceWork: false, fileEvidence: true })).ok).toBe(true)
    expect(checkDoneEvidence(input({ hasTraceWork: true, fileEvidence: false })).ok).toBe(true)
  })

  it('③ 60s 内刚关闭同需求任务 → REQBOARD_BULK_CLOSE', () => {
    const v = checkDoneEvidence(input({ recentDoneTask: { id: 't-abc123', title: '别的任务' } }))
    expect(v).toMatchObject({ ok: false, code: 'REQBOARD_BULK_CLOSE' })
    if (!v.ok) expect(v.reason).toContain('60 秒内刚关闭了任务 t-abc123')
  })

  it('④ 页面插件任务：未构建 → STALE_BUILD；构建陈旧 → STALE_BUILD；新于 src → 通过', () => {
    // 页面插件 src 文件路径（t9 后 host/ 已删除，改用真实存在的路径；本字段只被用于判定"有无页面源码"与取包名）
    const pages = ['packages/pages/dsh-pmboard/src/tools/StatusTool/StatusTool.ts']
    const missing = checkDoneEvidence(input({ pagesSrcFiles: pages, clientBuildExists: false }))
    expect(missing).toMatchObject({ ok: false, code: 'REQBOARD_STALE_BUILD' })
    if (!missing.ok) expect(missing.reason).toContain('未构建')
    const stale = checkDoneEvidence(input({ pagesSrcFiles: pages, clientBuildExists: true, clientBuildMtime: 100, newestPagesSrcMtime: 200 }))
    expect(stale).toMatchObject({ ok: false, code: 'REQBOARD_STALE_BUILD' })
    if (!stale.ok) expect(stale.reason).toContain('构建产物陈旧')
    expect(checkDoneEvidence(input({ pagesSrcFiles: pages, clientBuildExists: true, clientBuildMtime: 200, newestPagesSrcMtime: 100 })).ok).toBe(true)
  })

  it('全部满足 → 放行', () => {
    expect(checkDoneEvidence(input())).toEqual({ ok: true })
  })
})

describe('findRecentAgentDoneTask（节流命中）', () => {
  const tasks = [
    { id: 't-1', title: '同需求', requirementId: 'R', statusHistory: [{ status: 'done', by: { kind: 'agent' }, at: 990 }] },
    { id: 't-2', title: 'task 本身', requirementId: 'R', statusHistory: [{ status: 'done', by: { kind: 'agent' }, at: 995 }] },
    { id: 't-3', title: '人关的', requirementId: 'R', statusHistory: [{ status: 'done', by: { kind: 'human' }, at: 999 }] },
    { id: 't-4', title: '别的需求', requirementId: 'R2', statusHistory: [{ status: 'done', by: { kind: 'agent' }, at: 999 }] },
  ]
  it('只命中同需求、非本任务、agent、窗口内的 done', () => {
    expect(findRecentAgentDoneTask(tasks, 't-2', 'R', 1000, 60_000)).toEqual({ id: 't-1', title: '同需求' })
  })
  it('窗口外 / throttle=0 → 不命中', () => {
    expect(findRecentAgentDoneTask(tasks, 't-2', 'R', 1000, 0)).toBeUndefined()
    expect(findRecentAgentDoneTask([{ id: 't-9', title: 'x', requirementId: 'R', statusHistory: [{ status: 'done', by: { kind: 'agent' }, at: 0 }] }], 't-2', 'R', 1000, 100)).toBeUndefined()
  })
})
