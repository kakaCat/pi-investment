/**
 * 账本 v4 → v5 迁移测试（REQ-47939a t10）。
 *
 * 基准数据 = `tests/fixtures/ledger-v4-sample.json`（2026-09-17 冻结的真实台账副本，
 * 34 需求 / 97 任务），理由：运行中的台账每推进一个需求就变，晚冻等于没有基准。
 *
 * 本测试守两件事：
 *  ① **无损**：整份真实样本迁移后，差异路径必须全部落在白名单内（白名单外 = 0）；
 *  ② **逐项语义**：C3/C4/C6/C7/C8/C9/C10 各自在合成用例上行为正确（真实样本里多数是空操作，
 *     所以合成用例不可省——否则"空操作通过"会伪装成"逻辑正确"）。
 *
 * CLI 层安全（备份 / 临时文件+rename 原子替换 / 幂等 / 损坏输入不改原文件 / 可回滚）已在
 * 实施时用真实命令逐条实测，证据见 docs/requirements/REQ-47939a/verification.md 的 t10 段。
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { migrate, diffPaths, checkWhitelist } from '../scripts/migrate-ledger.js'

const SAMPLE = new URL('./fixtures/ledger-v4-sample.json', import.meta.url)
const readSample = () => JSON.parse(readFileSync(SAMPLE, 'utf8'))
const NOW = 1_700_000_000_000

describe('迁移：真实样本无损（白名单外差异必须为 0）', () => {
  it('v4 样本 → v7：链式升级（4→5→6→7）、逐段留痕、需求/任务/待归类计数不变', () => {
    const before = readSample()
    const { next } = migrate(before, NOW)
    expect(before.schemaVersion).toBe(4)
    expect(next.schemaVersion).toBe(7)
    expect(next.migrations).toHaveLength(3)
    expect(next.migrations[0]).toMatchObject({ from: 4, to: 5 })
    expect(next.migrations[1]).toMatchObject({ from: 5, to: 6 })
    expect(next.migrations[2]).toMatchObject({ from: 6, to: 7 })
    expect(next.requirements).toHaveLength(before.requirements.length)
    expect(next.tasks).toHaveLength(before.tasks.length)
    expect(next.triages).toHaveLength(before.triages.length)
    // 入参不得被就地修改（纯函数）
    expect(before.schemaVersion).toBe(4)
  })

  it('差异路径全部落在白名单内（白名单外 0 条）', () => {
    const before = readSample()
    const { next } = migrate(before, NOW)
    const paths = diffPaths(before, next)
    const { bad } = checkWhitelist(paths)
    expect(bad, '白名单外差异：\n' + bad.join('\n')).toEqual([])
    expect(paths.length).toBeGreaterThan(0) // 至少 schemaVersion/migrations 必变
  })

  it('幂等：对已是 v7 的台账再迁移，内容不变且 migrations 不再叠加', () => {
    const before = readSample()
    const { next } = migrate(before, NOW)
    expect(next.migrations).toHaveLength(3)
    const { next: again } = migrate(next, NOW + 1)
    expect(again.requirements).toEqual(next.requirements)
    expect(again.tasks).toEqual(next.tasks)
    expect(again.migrations).toHaveLength(3)
  })
})

describe('迁移：逐项语义（合成用例——真实样本多为空操作，空操作不等于逻辑正确）', () => {
  const base = () => ({
    schemaVersion: 4,
    revision: 1,
    requirements: [] as any[],
    tasks: [] as any[],
    triages: [] as any[],
  })
  const req = (over: any = {}) => ({
    id: 'REQ-aaaaaa', title: 't', description: '', category: 'feature', status: 'design',
    blocked: false, comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    statusHistory: [{ status: 'design', at: 1, by: { kind: 'human' } }],
    ...over,
  })

  it('C3：legacy 状态名 reviewing → brainstorming（含时间线事件）', () => {
    const l = base(); l.requirements.push(req({ status: 'reviewing', statusHistory: [{ status: 'reviewing', at: 1, by: { kind: 'human' } }] }))
    const { next, changes } = migrate(l, NOW)
    expect(next.requirements[0].status).toBe('brainstorming')
    expect(next.requirements[0].statusHistory[0].status).toBe('brainstorming')
    expect(changes.C3_legacy_status_renamed?.count).toBe(1)
  })

  it('C4：缺 statusHistory 时按运行时同一 backfill 算法补齐（并标 inferred）', () => {
    const l = base()
    const r = req({ statusHistory: undefined })
    l.requirements.push(r)
    l.tasks.push({ id: 't-1', requirementId: r.id, title: 'x', status: 'todo', dependsOn: [], executions: [], comments: [], version: 1, createdAt: 5, updatedAt: 5, createdBy: { kind: 'human' }, updatedBy: { kind: 'human' } })
    const { next } = migrate(l, NOW)
    expect(Array.isArray(next.requirements[0].statusHistory)).toBe(true)
    expect(next.requirements[0].statusHistory[0]).toMatchObject({ status: 'draft', inferred: true })
    expect(next.tasks[0].statusHistory[0]).toMatchObject({ status: 'todo', inferred: true })
  })

  it('C6：删除零引用预留字段 projectId / parentId', () => {
    const l = base(); l.requirements.push(req({ projectId: 'p1', parentId: 'REQ-bbbbbb' }))
    const { next } = migrate(l, NOW)
    expect('projectId' in next.requirements[0]).toBe(false)
    expect('parentId' in next.requirements[0]).toBe(false)
  })

  it('C7：sheet.items 与 sheetHistory 的 source 都由字符串变判别联合', () => {
    const l = base()
    l.requirements.push(req({
      verification: {
        sheet: { version: 1, items: [
          { id: 'v1-1', source: 't-abc123', criterion: 'c', evidence: [], status: 'passed' },
          { id: 'v1-2', source: 'requirement', criterion: 'c', evidence: [], status: 'pending' },
        ], generatedAt: 1, generatedBy: { kind: 'human' } },
        sheetHistory: [{ version: 0, items: [{ id: 'v0-1', source: 'requirement', criterion: 'c', evidence: [], status: 'passed' }], generatedAt: 0, generatedBy: { kind: 'human' } }],
      },
    }))
    const { next } = migrate(l, NOW)
    const items = next.requirements[0].verification.sheet.items
    expect(items[0].source).toEqual({ kind: 'task', taskId: 't-abc123' })
    expect(items[1].source).toEqual({ kind: 'requirement' })
    expect(next.requirements[0].verification.sheetHistory[0].items[0].source).toEqual({ kind: 'requirement' })
  })

  it('C8/C9：task.scope 补默认；dependsOn 去重、自指与悬空一并剔除', () => {
    const l = base()
    l.tasks.push(
      { id: 't-1', requirementId: 'REQ-aaaaaa', title: 'a', status: 'todo', dependsOn: [], executions: [], comments: [], version: 1, createdAt: 1, updatedAt: 1, createdBy: { kind: 'human' }, updatedBy: { kind: 'human' } },
      { id: 't-2', requirementId: 'REQ-aaaaaa', title: 'b', status: 'todo', dependsOn: ['t-1', 't-1', 't-2', 't-ghost'], executions: [], comments: [], version: 1, createdAt: 1, updatedAt: 1, createdBy: { kind: 'human' }, updatedBy: { kind: 'human' } },
    )
    const { next, changes } = migrate(l, NOW)
    expect(next.tasks[0].scope).toEqual({ apis: [], tables: [], files: [] })
    expect(next.tasks[1].dependsOn).toEqual(['t-1'])
    expect(changes.C8_task_scope_defaulted?.count).toBe(2)
    expect(changes.C9_depends_on_cleaned?.count).toBe(3)
  })

  it('C10：artifacts 按 (kind,path) 去重，保留 confirmedAt 最早的非空者', () => {
    const l = base()
    l.requirements.push(req({
      artifacts: [
        { kind: 'requirement', path: 'docs/requirements/REQ-aaaaaa/requirement.md', registeredAt: 1 },
        { kind: 'requirement', path: 'docs/requirements/REQ-aaaaaa/requirement.md', registeredAt: 2, confirmedAt: 900 },
        { kind: 'requirement', path: 'docs/requirements/REQ-aaaaaa/requirement.md', registeredAt: 3, confirmedAt: 500 },
      ],
    }))
    const { next, changes } = migrate(l, NOW)
    expect(next.requirements[0].artifacts).toHaveLength(1)
    expect(next.requirements[0].artifacts[0].confirmedAt).toBe(500)
    expect(changes.C10_artifact_deduped?.count).toBe(2)
  })
})
