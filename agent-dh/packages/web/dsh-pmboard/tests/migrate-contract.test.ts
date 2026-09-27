/**
 * v8 → v9 迁移契约测试（REQ-260927202051-f6df · t15 · TC-7.1~7.5）
 *
 * 目标：**零字段丢失**。断言分两层：
 *
 * ① **结构层（合成穷举）**：造一张携全部 37 个 `TaskRecord` 字段的任务卡跑变换，断言迁移后键集
 *    恰为 37 + `layer` = 38；并把 18 个可选字段**逐一**点名（尤其 `executorHint / cardDoc /
 *    requirementRefs / skipIntegration / blockedReason / claimedBy / claimedAt` —— 原文档漏列、
 *    最易被静默漏迁）。
 *
 * ② **真实台账层（数据驱动）**：直接读活台账（只读！绝不写），现算源侧分组/状态分布/依赖条数，
 *    与迁移结果逐一比对。**不硬编码任何计数**（本仓 2026-09-27 实测：文档写的 587 条已过期，
 *    实际 612 条 —— 冻结数字是定时炸弹，拆分一次需求就红）。
 *
 * 权威字段真身：`src/shared/protocol.ts:1150-1216`（不是任何文档表格）。
 */
import { describe, expect, it } from 'vitest'
import { existsSync, readFileSync, readdirSync } from 'node:fs'
import { basename, dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { LEDGER_V8, LEDGER_V9, migrateV8toV9 } from '../scripts/migrate-ledger.js'

const PKG_ROOT = dirname(dirname(fileURLToPath(import.meta.url)))

/** TaskRecord 的 19 个必填字段（protocol.ts:1150-1216）。 */
const REQUIRED_FIELDS = [
  'id', 'requirementId', 'title', 'description', 'phase', 'side', 'dependsOn', 'scope',
  'acceptance', 'context', 'status', 'blocked', 'executions', 'comments', 'version',
  'createdAt', 'updatedAt', 'createdBy', 'updatedBy',
] as const

/** TaskRecord 的 18 个可选字段（protocol.ts:1150-1216）。 */
const OPTIONAL_FIELDS = [
  'implementation', 'dependsSummary', 'parentId', 'stageKind', 'stages', 'attempt',
  'revisions', 'lastRun', 'lastReport', 'teamTaskId', 'executorHint', 'cardDoc',
  'requirementRefs', 'skipIntegration', 'blockedReason', 'claimedBy', 'claimedAt', 'statusHistory',
] as const

/** 原设计文档漏列、最易静默漏迁的 7 个字段（Lead 校准点名）。 */
const PREVIOUSLY_MISSING = ['executorHint', 'cardDoc', 'requirementRefs', 'skipIntegration', 'blockedReason', 'claimedBy', 'claimedAt'] as const

const TASK_FIELDS = [...REQUIRED_FIELDS, ...OPTIONAL_FIELDS]

/** 转换函数：去 layer 后取键（排序，便于集合比较）。 */
const keysWithoutLayer = (task: any): string[] => Object.keys(task).filter((k) => k !== 'layer').sort()

/** 携全部 37 字段的任务卡（合成穷举：任何字段漏迁都会改变键集）。 */
function fullTask(id = 't-full01', requirementId = 'REQ-full'): any {
  return {
    // 19 必填
    id, requirementId, title: '全字段卡', description: '穷举 37 字段',
    phase: 'implement', side: 'fullstack', dependsOn: [],
    scope: { apis: ['/x'], tables: ['t'], files: ['f.ts'] },
    acceptance: '命令退出码 0', context: '背景',
    status: 'in_progress', blocked: false, executions: [{ at: 5, by: { kind: 'agent' }, note: 'run' }],
    comments: [{ at: 6, by: { kind: 'human' }, text: 'hi' }], version: 3,
    createdAt: 100, updatedAt: 200, createdBy: { kind: 'agent' }, updatedBy: { kind: 'agent' },
    // 18 可选
    implementation: '改 A/B', dependsSummary: '上游产出',
    parentId: 't-parent', stageKind: 'dev', stages: ['dev', 'test'], attempt: 2,
    revisions: [{ at: 7, by: { kind: 'agent' }, kind: 'update', reason: 'r', changes: ['c'] }],
    lastRun: { at: 8, ok: true, stopReason: 'completed', valueNonEmpty: true },
    lastReport: { at: 9, summary: 's', completed: ['a'], filesChanged: ['f.ts'] },
    teamTaskId: 'team-1', executorHint: 'subagent', cardDoc: 'docs/x.md',
    requirementRefs: ['FR-1', 'FR-2'], skipIntegration: true, blockedReason: '等上游',
    claimedBy: 'w-1', claimedAt: 10, statusHistory: [{ to: 'todo', at: 1, by: { kind: 'agent' } }],
  }
}

const ledgerOf = (tasks: any[], requirementIds: string[]): any => ({
  schemaVersion: LEDGER_V8, revision: 7, triages: [],
  requirements: requirementIds.map((id) => ({ id, title: id, status: 'implementing', category: 'feature', version: 1 })),
  tasks,
})

// ---------------------------------------------------------------------------
// TC-7.1 / TC-7.2：结构层穷举
// ---------------------------------------------------------------------------

describe('TC-7.1/7.2 零字段丢失（合成穷举 37 字段）', () => {
  const opts = { requirementDirOf: (rid: string) => join('/tmp/fake-root', 'docs', 'requirements', rid), dirExists: () => true }

  it('迁移后键集恰为 37 + layer（差集仅 {layer}）', () => {
    const src = fullTask()
    expect(Object.keys(src).sort()).toEqual([...TASK_FIELDS].sort())
    const r = migrateV8toV9(ledgerOf([src], ['REQ-full']), 0, opts)
    const got = r.queues[0]!.file.tasks[0] as any
    expect(Object.keys(got).sort()).toEqual([...TASK_FIELDS, 'layer'].sort())
    expect(keysWithoutLayer(got)).toEqual(Object.keys(src).sort())
    expect(got.layer).toBe(0)
  })

  it('逐字段深比对：去 layer 后与源任务 deepEqual（含嵌套结构）', () => {
    const src = fullTask()
    const r = migrateV8toV9(ledgerOf([src], ['REQ-full']), 0, opts)
    const got: any = { ...r.queues[0]!.file.tasks[0] }
    delete got.layer
    expect(got).toEqual(src)
    // 嵌套对象不得被"投影/裁剪"
    expect(got.scope).toEqual({ apis: ['/x'], tables: ['t'], files: ['f.ts'] })
    expect(got.lastRun).toEqual({ at: 8, ok: true, stopReason: 'completed', valueNonEmpty: true })
    expect(got.revisions[0].changes).toEqual(['c'])
  })

  it('18 个可选字段逐一被覆盖（不做逐字段抽查，而是断言字段名集合被完整覆盖）', () => {
    const src = fullTask()
    const r = migrateV8toV9(ledgerOf([src], ['REQ-full']), 0, opts)
    const got = r.queues[0]!.file.tasks[0] as any
    const migratedKeys = new Set(Object.keys(got))
    for (const f of OPTIONAL_FIELDS) {
      expect(migratedKeys.has(f), `可选字段未迁移：${f}`).toBe(true)
      expect(got[f], `可选字段值不等：${f}`).toEqual((src as any)[f])
    }
    // 原文档漏列的 7 个必须逐一点名
    for (const f of PREVIOUSLY_MISSING) {
      expect(migratedKeys.has(f), `原文档漏列字段未迁移：${f}`).toBe(true)
    }
    expect(OPTIONAL_FIELDS).toHaveLength(18)
    expect(PREVIOUSLY_MISSING).toHaveLength(7)
  })

  it('字段缺失也不得凭空补齐（源没有的键，迁移后也不得出现；唯一新增是 layer）', () => {
    const bare: any = {
      id: 't-bare', requirementId: 'REQ-bare', title: 't', description: 'd', phase: 'doc', side: 'doc',
      dependsOn: [], scope: { apis: [], tables: [], files: [] }, acceptance: 'a', context: 'c',
      status: 'todo', blocked: false, executions: [], comments: [], version: 1,
      createdAt: 1, updatedAt: 1, createdBy: { kind: 'agent' }, updatedBy: { kind: 'agent' },
    }
    const r = migrateV8toV9(ledgerOf([bare], ['REQ-bare']), 0, opts)
    const got = r.queues[0]!.file.tasks[0] as any
    expect(Object.keys(got).sort()).toEqual([...Object.keys(bare), 'layer'].sort())
  })
})

// ---------------------------------------------------------------------------
// 真实台账：数据驱动（不硬编码计数）
// ---------------------------------------------------------------------------

/** 从包目录上溯找活台账（只读）。 */
function findLiveLedger(): string | undefined {
  let dir = PKG_ROOT
  for (let i = 0; i < 6; i++) {
    const p = join(dir, '.dsh-data', 'dsh-reqboard.json')
    if (existsSync(p)) return p
    const up = dirname(dir)
    if (up === dir) break
    dir = up
  }
  return undefined
}

/** 若活台账已是 v9（迁移已投产），退回最近一份 v8 备份作为源。 */
function sourceLedger(): { path: string; ledger: any; note: string } | undefined {
  const live = findLiveLedger()
  if (live === undefined) return undefined
  const parsed = JSON.parse(readFileSync(live, 'utf8'))
  if (parsed.schemaVersion === LEDGER_V8) return { path: live, ledger: parsed, note: '活台账（v8）' }
  const dir = dirname(live)
  const base = basename(live)
  const backups = readdirSync(dir).filter((n) => n.startsWith(base + '.backup-')).sort().reverse()
  for (const b of backups) {
    const p = join(dir, b)
    try {
      const l = JSON.parse(readFileSync(p, 'utf8'))
      if (l.schemaVersion === LEDGER_V8 && Array.isArray(l.tasks)) return { path: p, ledger: l, note: 'v8 备份（活台账已迁移）' }
    } catch { /* 跳过坏备份 */ }
  }
  return undefined
}

describe('TC-7.1/7.3/7.4/7.5 真实台账数据驱动比对（零字段丢失）', () => {
  const found = sourceLedger()

  it.runIf(found !== undefined)('源侧现算 → 目标侧逐一相等（计数/分组/状态分布/依赖/归属）', () => {
    const { path, ledger, note } = found!
    const sourceTasks: any[] = ledger.tasks
    const reqIds = new Set((ledger.requirements ?? []).map((r: any) => r.id))
    const dataPoint = note + ' ' + path + '（revision=' + ledger.revision + '，' + sourceTasks.length + ' 条任务）'

    // dirExists 恒真 → 不因缺目录丢组（缺目录是文件系统事实，另由行为测试覆盖）
    const r = migrateV8toV9(ledger, 0, {
      requirementDirOf: (rid: string) => join('/tmp/fake-root', 'docs', 'requirements', rid),
      dirExists: () => true,
    })

    // 白名单：真实数据变换不得触碰 tasks/schemaVersion/migrations 之外的任何路径
    expect(r.report.whitelist.bad, '白名单外差异（真实台账变换）').toEqual([])

    // 守恒：迁移 + 未迁移（orphan 等）= 源总数
    const unmigratedTotal = r.unmigrated.reduce((s, u) => s + u.tasks.length, 0)
    expect(r.report.migratedTasks + unmigratedTotal, '任务守恒（' + dataPoint + '）').toBe(sourceTasks.length)

    // Lead D9 验收⑥：未迁移只允许是**真 orphan**（requirementId 缺失 / 指向不存在需求）；
    // "需求存在但目录缺失"必须建目录迁入（本用例 dirExists 恒真，故 createdDirs 为空）。
    const expectedOrphans = sourceTasks.filter((t) => typeof t.requirementId !== 'string' || !reqIds.has(t.requirementId)).length
    expect(unmigratedTotal, '未迁移任务数必须等于真 orphan 数（设计定义之外的丢失不得当合规）').toBe(expectedOrphans)
    expect(r.report.createdDirs).toEqual([])

    // ── TC-7.1：逐条（按 id 配对，不按下标）去 layer 后 deepEqual
    const gotById = new Map<string, any>()
    for (const q of r.queues) for (const t of q.file.tasks as any[]) gotById.set(t.id, t)
    let compared = 0
    for (const src of sourceTasks) {
      const got = gotById.get(src.id)
      if (got === undefined) continue // orphan（无归属需求）不迁移，已在守恒式里计入
      const stripped: any = { ...got }
      delete stripped.layer
      expect(stripped, '字段深比对失败：' + src.id).toEqual(src)
      compared += 1
    }
    expect(compared).toBe(r.report.migratedTasks)
    expect(compared).toBeGreaterThan(0)

    // 键集相等（数据驱动：源有什么键，目标就有什么键 + layer）
    for (const q of r.queues) {
      for (const t of q.file.tasks as any[]) {
        const src = sourceTasks.find((x) => x.id === t.id)!
        expect(Object.keys(t).filter((k) => k !== 'layer').sort(), '键集不等：' + t.id).toEqual(Object.keys(src).sort())
      }
    }

    // ── TC-7.3：全部 dependsOn 在目标队列内可解析，且条数守恒（现算，不硬编码 465）
    const sourceDepEntries = sourceTasks.reduce((s, t) => s + (Array.isArray(t.dependsOn) ? t.dependsOn.length : 0), 0)
    const targetDepEntries = r.queues.reduce((s, q) => s + q.file.tasks.reduce((a, t: any) => a + (t.dependsOn?.length ?? 0), 0), 0)
    expect(targetDepEntries, 'dependsOn 条数守恒（' + dataPoint + '）').toBe(sourceDepEntries)
    for (const q of r.queues) {
      const ids = new Set(q.file.tasks.map((t: any) => t.id))
      for (const t of q.file.tasks as any[]) {
        for (const d of t.dependsOn ?? []) {
          expect(ids.has(d), `依赖断链：${t.id} → ${d}（${q.requirementId}）`).toBe(true)
        }
      }
      expect(q.file.edges.length, '边数应等于可解析依赖数').toBe(q.file.tasks.reduce((a, t: any) => a + (t.dependsOn?.length ?? 0), 0))
    }

    // 源侧依赖若跨需求/悬空，必须已由 V-3 拦下（即该需求不落盘）——真实数据现算
    const allIds = new Set(sourceTasks.map((t) => t.id))
    const dangling = sourceTasks.flatMap((t) => (t.dependsOn ?? []).filter((d: string) => !allIds.has(d)))
    if (dangling.length > 0) console.warn('源台账存在悬空依赖 ' + dangling.length + ' 条（' + dataPoint + '）')

    // ── TC-7.4：状态分布迁移前后逐一相等（分布由源现算，不写死 556/7/24）
    const dist = (tasks: any[]) => {
      const m: Record<string, number> = {}
      for (const t of tasks) m[t.status] = (m[t.status] ?? 0) + 1
      return m
    }
    const sourceDist = dist(sourceTasks)
    const targetDist = dist(r.queues.flatMap((q) => q.file.tasks as any[]))
    const sourceMigratedDist = dist(sourceTasks.filter((t) => gotById.has(t.id)))
    expect(targetDist, '状态分布不一致（' + dataPoint + '）').toEqual(sourceMigratedDist)
    expect(Object.keys(sourceDist).sort()).toEqual(Object.keys(sourceMigratedDist).sort())

    // ── 分组守恒：源侧按 requirementId 计数 → 各 queue.json 条数逐一相等
    const sourceCounts = new Map<string, number>()
    for (const t of sourceTasks) if (reqIds.has(t.requirementId)) sourceCounts.set(t.requirementId, (sourceCounts.get(t.requirementId) ?? 0) + 1)
    const queueById = new Map(r.queues.map((q) => [q.requirementId, q]))
    expect(queueById.size, '有任务的需求数应等于源侧现算').toBe(sourceCounts.size)
    for (const [rid, n] of sourceCounts) {
      const q = queueById.get(rid)
      expect(q, '缺队列：' + rid).toBeDefined()
      expect(q!.file.tasks.length, '分组条数不等：' + rid).toBe(n)
    }

    // ── TC-7.5：每份 queue.json 的 requirement_id 与目录/分组一致（无任务落错需求）
    for (const q of r.queues) {
      expect(q.file.requirement_id).toBe(q.requirementId)
      expect(basename(dirname(q.path))).toBe(q.file.requirement_id)
      expect(q.file.schemaVersion).toBe(LEDGER_V9)
      expect(q.file.version).toBe(1)
      for (const t of q.file.tasks as any[]) expect(t.requirementId).toBe(q.file.requirement_id)
    }

    console.log('[TC-7.x] ' + dataPoint + ' → 队列 ' + r.queues.length + ' 份 / 迁移 ' + r.report.migratedTasks
      + ' 任务 / 未迁移 ' + unmigratedTotal + ' 条 / dependsOn ' + targetDepEntries + ' 条 / 状态 ' + JSON.stringify(targetDist)
      + ' / 跳过需求 ' + r.report.skipped.length + ' 个')
  })

  it('报告真实台账定位结果（不可用时应显式说明，而非静默通过）', () => {
    if (found === undefined) {
      console.warn('[TC-7.x] 未定位到 v8 活台账或备份 —— 真实台账层比对已跳过（合成穷举层仍生效）')
    }
    expect(true).toBe(true)
  })
})
