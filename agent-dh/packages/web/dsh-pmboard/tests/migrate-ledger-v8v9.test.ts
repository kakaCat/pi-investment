/**
 * v8 → v9 迁移行为测试（REQ-260927202051-f6df · t13/t14 · TC-6.x）
 *
 * 纪律（本需求唯一会动全局共享数据的一步）：
 * - 全部用例只在 `os.tmpdir()` 的临时工作区上跑，**绝不触碰活台账** `.dsh-data/dsh-reqboard.json`；
 *   需要"真实台账规模"的契约比对见 migrate-contract.test.ts（只读活台账/或读其冻结副本）。
 * - 三条硬顺序/安全纪律各有独立用例：① D-7 先于 D-8（打点 + 磁盘事实）② 白名单外差异 → 退出码 1 且零落盘
 *   ③ 第二次 --apply 报 already_v9 且所有文件 mtime 不变。
 *
 * 覆盖：TC-6.1/6.2（dry-run 不落盘 + 报告）、6.3/6.4（apply 写队列 + 改台账）、6.5（幂等）、
 * 6.7（白名单中止）、6.8（回滚）、6.9（orphan 不迁移不串档）、6.10（环依赖中止、其余照常）。
 */
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { spawnSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, statSync, writeFileSync, readdirSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import {
  LEDGER_V8,
  LEDGER_V9,
  defaultServiceRunningCheck,
  migrateV8toV9,
  rollbackV9,
  runV9,
  v9Defaults,
} from '../scripts/migrate-ledger.js'
import { computeLayers as canonicalComputeLayers, computeEdges as canonicalComputeEdges, computeReady as canonicalComputeReady } from '../src/domain/queue/topology.js'
import { validateQueueFile as canonicalValidateQueueFile } from '../src/domain/queue/validateQueue.js'

const PKG_ROOT = dirname(dirname(fileURLToPath(import.meta.url)))
const NOW = 1_760_000_000_000
const sha256 = (s: string) => createHash('sha256').update(s, 'utf8').digest('hex')
const mtime = (p: string) => statSync(p).mtimeMs

// ---------------------------------------------------------------------------
// fixtures
// ---------------------------------------------------------------------------

function mkTask(over: Record<string, unknown> = {}): any {
  return {
    id: 't-aaaaaa',
    requirementId: 'REQ-aaaaaa',
    title: 'T',
    description: 'D',
    phase: 'implement',
    side: 'backend',
    scope: { apis: [], tables: [], files: [] },
    /** V-1 任务级必填（19 字段）之一——canonical validateQueueFile 会点名校验 */
    dependsOn: [],
    acceptance: 'A',
    context: 'C',
    status: 'todo',
    blocked: false,
    executions: [],
    comments: [],
    version: 1,
    createdAt: 1,
    updatedAt: 1,
    createdBy: { kind: 'agent' },
    updatedBy: { kind: 'agent' },
    ...over,
  }
}

function mkReq(id: string, over: Record<string, unknown> = {}): any {
  return {
    id, title: 'R', status: 'implementing', category: 'feature', version: 1,
    createdAt: 1, updatedAt: 1, createdBy: { kind: 'agent' }, updatedBy: { kind: 'agent' },
    comments: [], ...over,
  }
}

function mkLedger(tasks: any[], reqs: any[] = [mkReq('REQ-aaaaaa')]): any {
  return { schemaVersion: LEDGER_V8, revision: 42, requirements: reqs, tasks, triages: [] }
}

/** 两任务最小台账：t-1（todo，无依赖）+ t-2（done，依赖 t-1）。 */
function tinyLedger(): any {
  return mkLedger([
    mkTask({ id: 't-1', title: '卡一' }),
    mkTask({ id: 't-2', dependsOn: ['t-1'], status: 'done' }),
  ])
}

let tmp: string
beforeEach(() => { tmp = mkdtempSync(join(tmpdir(), 'mig-v9-')) })
afterEach(() => { rmSync(tmp, { recursive: true, force: true }) })

/** 建临时工作区：含 .dsh-data/dsh-reqboard.json 与 docs/requirements/<REQ>/ 目录。 */
function setupWorkspace(ledger: any, reqDirs: string[]): { file: string; root: string } {
  const root = join(tmp, 'ws')
  mkdirSync(join(root, 'docs', 'requirements'), { recursive: true })
  for (const r of reqDirs) mkdirSync(join(root, 'docs', 'requirements', r), { recursive: true })
  mkdirSync(join(root, '.dsh-data'), { recursive: true })
  const file = join(root, '.dsh-data', 'dsh-reqboard.json')
  writeFileSync(file, JSON.stringify(ledger, null, 2))
  return { file, root }
}

const requirementDirOf = (root: string) => (rid: string) => join(root, 'docs', 'requirements', rid)

// ---------------------------------------------------------------------------
// 纯变换
// ---------------------------------------------------------------------------

describe('v8→v9 纯变换（migrateV8toV9）', () => {
  it('分层/边/ready：线性链 + 菱形（layer 由拓扑算，ready 只含可执行者）', () => {
    const tasks = [
      mkTask({ id: 't-1' }),
      mkTask({ id: 't-2', dependsOn: ['t-1'] }),
      mkTask({ id: 't-3', dependsOn: ['t-1'], status: 'todo' }),
      mkTask({ id: 't-4', dependsOn: ['t-2', 't-3'] }),
    ]
    const r = migrateV8toV9(mkLedger(tasks), NOW, { requirementDirOf: requirementDirOf(join(tmp, 'ws')), dirExists: () => true })
    expect(r.report.skipped).toEqual([])
    expect(r.queues).toHaveLength(1)
    const q = r.queues[0]!.file
    expect(q.layers).toEqual([{ layer: 0, tasks: ['t-1'] }, { layer: 1, tasks: ['t-2', 't-3'] }, { layer: 2, tasks: ['t-4'] }])
    expect(q.edges).toEqual([
      { from: 't-1', to: 't-2' }, { from: 't-1', to: 't-3' },
      { from: 't-2', to: 't-4' }, { from: 't-3', to: 't-4' },
    ])
    expect(q.ready).toEqual(['t-1'])
    expect(q.tasks.map((t) => t.layer)).toEqual([0, 1, 1, 2])
  })

  it('ready 解锁：依赖已 done 的 todo 进入 ready（TC-1.6 同口径）', () => {
    const tasks = [
      mkTask({ id: 't-1', status: 'done' }),
      mkTask({ id: 't-2', dependsOn: ['t-1'], status: 'todo' }),
    ]
    const r = migrateV8toV9(mkLedger(tasks), NOW, { requirementDirOf: requirementDirOf(join(tmp, 'ws')), dirExists: () => true })
    expect(r.queues[0]!.file.ready).toEqual(['t-2'])
  })

  it('零字段丢失：整对象展开（去 layer 后与源任务 deepEqual）', () => {
    const src = mkTask({ id: 't-rich', lastRun: { at: 9, ok: true, stopReason: 'completed', valueNonEmpty: true }, parentId: 't-parent', stageKind: 'dev' })
    const r = migrateV8toV9(mkLedger([src]), NOW, { requirementDirOf: requirementDirOf(join(tmp, 'ws')), dirExists: () => true })
    const got: any = { ...r.queues[0]!.file.tasks[0] }
    delete got.layer
    expect(got).toEqual(src)
  })

  it('纯函数：不改入参；已是 v9 时早返回 alreadyV9 且不追加 migrations', () => {
    const before = mkLedger([mkTask({ id: 't-1' })])
    const snapshot = JSON.stringify(before)
    migrateV8toV9(before, NOW, { requirementDirOf: requirementDirOf(join(tmp, 'ws')), dirExists: () => true })
    expect(JSON.stringify(before)).toBe(snapshot)

    const v9 = { ...before, schemaVersion: LEDGER_V9, tasks: undefined }
    delete (v9 as any).tasks
    const r = migrateV8toV9(v9, NOW, { requirementDirOf: requirementDirOf(join(tmp, 'ws')), dirExists: () => true })
    expect(r.report.alreadyV9).toBe(true)
    expect(r.queues).toEqual([])
    expect(r.ledger.migrations).toBeUndefined()
  })

  it('空白清单：orphan（无 requirementId / 指向不存在需求）不迁移、不串档（TC-6.9）', () => {
    const tasks = [
      mkTask({ id: 't-ok', requirementId: 'REQ-aaaaaa' }),
      mkTask({ id: 't-noreq', requirementId: undefined }),
      mkTask({ id: 't-ghost', requirementId: 'REQ-zzzzzz' }),
    ]
    const r = migrateV8toV9(mkLedger(tasks), NOW, { requirementDirOf: requirementDirOf(join(tmp, 'ws')), dirExists: () => true })
    expect(r.report.orphanTasks).toEqual([
      { taskId: 't-noreq', reason: 'missing-requirement-id' },
      { taskId: 't-ghost', requirementId: 'REQ-zzzzzz', reason: 'unknown-requirement' },
    ])
    expect(r.queues).toHaveLength(1)
    expect(r.queues[0]!.file.tasks.map((t) => t.id)).toEqual(['t-ok'])
    // orphan 全文隔离保留（v9 台账已无 tasks，不隔离就等于静默丢失）
    const isolated = r.unmigrated.flatMap((u) => u.tasks.map((t: any) => t.id))
    expect(isolated.sort()).toEqual(['t-ghost', 't-noreq'])
  })

  it('环依赖：该需求中止不落盘，其余需求照常（TC-6.10）', () => {
    const tasks = [
      mkTask({ id: 't-c1', requirementId: 'REQ-cycle', dependsOn: ['t-c2'] }),
      mkTask({ id: 't-c2', requirementId: 'REQ-cycle', dependsOn: ['t-c1'] }),
      mkTask({ id: 't-ok', requirementId: 'REQ-ok' }),
    ]
    const r = migrateV8toV9(mkLedger(tasks, [mkReq('REQ-cycle'), mkReq('REQ-ok')]), NOW, { requirementDirOf: requirementDirOf(join(tmp, 'ws')), dirExists: () => true })
    expect(r.queues.map((q) => q.requirementId)).toEqual(['REQ-ok'])
    expect(r.report.skipped).toHaveLength(1)
    expect(r.report.skipped[0]!.requirementId).toBe('REQ-cycle')
    expect(r.report.skipped[0]!.reason).toContain('CIRCULAR')
    expect(r.unmigrated.some((u) => u.reason === 'circular-dependency' && u.tasks.length === 2)).toBe(true)
  })

  it('缺需求目录但需求记录存在：**建目录迁入**（Lead D10 裁决 b），不再隔离', () => {
    const tasks = [mkTask({ id: 't-w', requirementId: 'REQ-nodir' })]
    const r = migrateV8toV9(mkLedger(tasks, [mkReq('REQ-nodir')]), NOW, { requirementDirOf: requirementDirOf(join(tmp, 'ws')), dirExists: () => false })
    expect(r.queues).toHaveLength(1)
    expect(r.queues[0]!.createDir).toBe(true)
    expect(r.report.createdDirs).toEqual([
      { requirementId: 'REQ-nodir', dir: join(tmp, 'ws', 'docs', 'requirements', 'REQ-nodir'), taskCount: 1 },
    ])
    expect(r.report.skipped).toEqual([])
    // Lead D9 验收⑥：未迁移必须为 0（设计定义之外的丢失不得当合规）
    expect(r.unmigrated).toEqual([])
  })

  it('真 orphan 永不建目录：requirementId 不存在 → 隔离，且 createdDirs 为空', () => {
    const tasks = [mkTask({ id: 't-ghost', requirementId: 'REQ-zzzzzz' })]
    const r = migrateV8toV9(mkLedger(tasks), NOW, { requirementDirOf: requirementDirOf(join(tmp, 'ws')), dirExists: () => false })
    expect(r.queues).toEqual([])
    expect(r.report.createdDirs).toEqual([])
    expect(r.report.orphanTasks).toEqual([{ taskId: 't-ghost', requirementId: 'REQ-zzzzzz', reason: 'unknown-requirement' }])
    expect(r.unmigrated.flatMap((u) => u.tasks.map((t: any) => t.id))).toEqual(['t-ghost'])
  })

  it('拓扑/校验用 t2/t3 的唯一实现（不留第二套语义）', () => {
    expect(v9Defaults.computeLayers).toBe(canonicalComputeLayers)
    expect(v9Defaults.computeEdges).toBe(canonicalComputeEdges)
    expect(v9Defaults.computeReady).toBe(canonicalComputeReady)
    expect(v9Defaults.validate).toBe(canonicalValidateQueueFile)
  })

  it('canonical 拓扑：空输入不抛错；有环 message 含 CIRCULAR', () => {
    expect(canonicalComputeLayers([])).toEqual([])
    expect(canonicalComputeReady([])).toEqual([])
    expect(() => canonicalComputeLayers([
      mkTask({ id: 'a', dependsOn: ['b'] }), mkTask({ id: 'b', dependsOn: ['a'] }),
    ])).toThrow(/CIRCULAR/)
  })

  it('环依赖需求即使目录缺失也不得留下待建目录（createDirRollback：不为失败需求建空目录）', () => {
    const tasks = [
      mkTask({ id: 't-c1', requirementId: 'REQ-cycle', dependsOn: ['t-c2'] }),
      mkTask({ id: 't-c2', requirementId: 'REQ-cycle', dependsOn: ['t-c1'] }),
    ]
    const r = migrateV8toV9(mkLedger(tasks, [mkReq('REQ-cycle')]), NOW, { requirementDirOf: requirementDirOf(join(tmp, 'ws')), dirExists: () => false })
    expect(r.report.createdDirs).toEqual([])
    expect(r.report.skipped).toHaveLength(1)
  })
})

// ---------------------------------------------------------------------------
// CLI 三态 + 幂等 + 回滚（在临时副本上；不碰活台账）
// ---------------------------------------------------------------------------

describe('v8→v9 CLI：dry-run / apply / verify / rollback', () => {
  it('TC-6.1/6.2 dry-run：台账 md5/mtime 不变，且未生成任何 queue.json', async () => {
    const { file, root } = setupWorkspace(tinyLedger(), ['REQ-aaaaaa'])
    const before = readFileSync(file, 'utf8')
    const o = await runV9({ file, mode: 'dry-run', ledger: JSON.parse(before), requirementDirOf: requirementDirOf(root), now: NOW })
    expect(o.code).toBe(0)
    expect(o.queuePaths).toHaveLength(1)
    expect(readFileSync(file, 'utf8')).toBe(before)
    expect(sha256(readFileSync(file, 'utf8'))).toBe(sha256(before))
    expect(existsSync(join(root, 'docs', 'requirements', 'REQ-aaaaaa', 'queue.json'))).toBe(false)
    // 报告含 总数 / 分组 / orphan / 白名单
    expect(o.report!.totalTasks).toBe(2)
    expect(o.report!.requirementsWithTasks).toBe(1)
    expect(o.report!.orphanTasks).toEqual([])
    expect(o.report!.whitelist.ok.length).toBeGreaterThan(0)
    expect(o.lines.join('\n')).toContain('未落盘')
  })

  it('TC-6.3/6.4 apply：先写全部 queue.json（D-7）再改台账（D-8/D-9）；台账 v9、无 tasks、migrations 末条 {8,9}', async () => {
    const { file, root } = setupWorkspace(tinyLedger(), ['REQ-aaaaaa'])
    const o = await runV9({ file, mode: 'apply', ledger: JSON.parse(readFileSync(file, 'utf8')), requirementDirOf: requirementDirOf(root), now: NOW })
    expect(o.code).toBe(0)
    const after = JSON.parse(readFileSync(file, 'utf8'))
    expect(after.schemaVersion).toBe(LEDGER_V9)
    expect('tasks' in after).toBe(false)
    const last = after.migrations[after.migrations.length - 1]
    expect(last).toMatchObject({ from: LEDGER_V8, to: LEDGER_V9 })
    expect(last.by).toBe('migrate-ledger.ts')
    // 队列文件
    const qp = join(root, 'docs', 'requirements', 'REQ-aaaaaa', 'queue.json')
    expect(existsSync(qp)).toBe(true)
    const q = JSON.parse(readFileSync(qp, 'utf8'))
    expect(q.requirement_id).toBe('REQ-aaaaaa')
    expect(q.schemaVersion).toBe(LEDGER_V9)
    expect(q.tasks).toHaveLength(2)
    expect(q.ready).toEqual(['t-1']) // t-1 todo 无依赖 → 可执行；t-2 依赖未 done 且自身 done → 不入 ready
    // 备份 + 清单
    expect(existsSync(o.backupPath!)).toBe(true)
    expect(existsSync(o.manifestPath!)).toBe(true)
    // 顺序打点：全部 D-7 在 D-8 之前，D-8 在 D-9 之前
    const phases = o.events.map((e) => e.phase)
    const lastD7 = phases.lastIndexOf('D-7')
    const d8 = phases.indexOf('D-8')
    const d9 = phases.indexOf('D-9')
    expect(lastD7).toBeGreaterThan(-1)
    expect(d8).toBeGreaterThan(lastD7)
    expect(d9).toBeGreaterThan(d8)
    expect(o.queueFilesWrittenBeforeLedger).toBe(true)
  })

  it('TC-6.5 幂等：第二次 apply 报 already_v9，台账与队列 mtime 全不变', async () => {
    const { file, root } = setupWorkspace(tinyLedger(), ['REQ-aaaaaa'])
    await runV9({ file, mode: 'apply', ledger: JSON.parse(readFileSync(file, 'utf8')), requirementDirOf: requirementDirOf(root), now: NOW })
    const qp = join(root, 'docs', 'requirements', 'REQ-aaaaaa', 'queue.json')
    const snap = { ledger: mtime(file), queue: mtime(qp) }
    const o2 = await runV9({ file, mode: 'apply', ledger: JSON.parse(readFileSync(file, 'utf8')), requirementDirOf: requirementDirOf(root), now: NOW + 60_000 })
    expect(o2.code).toBe(0)
    expect(o2.lines.join('\n')).toContain('already_v9')
    expect(o2.events[0]!.phase).toBe('already_v9')
    expect(mtime(file)).toBe(snap.ledger)
    expect(mtime(qp)).toBe(snap.queue)
    // 不叠加 migration 留痕
    const after = JSON.parse(readFileSync(file, 'utf8'))
    expect(after.migrations).toHaveLength(1)
  })

  it('TC-6.6 verify：迁移后退出码 0；未迁移（v8）退出码 1', async () => {
    const { file, root } = setupWorkspace(tinyLedger(), ['REQ-aaaaaa'])
    const v8 = await runV9({ file, mode: 'verify', ledger: JSON.parse(readFileSync(file, 'utf8')), requirementDirOf: requirementDirOf(root), now: NOW })
    expect(v8.code).toBe(1)
    expect(v8.lines.join('\n')).toContain('尚未迁移')

    await runV9({ file, mode: 'apply', ledger: JSON.parse(readFileSync(file, 'utf8')), requirementDirOf: requirementDirOf(root), now: NOW })
    const v9 = await runV9({ file, mode: 'verify', ledger: JSON.parse(readFileSync(file, 'utf8')), requirementDirOf: requirementDirOf(root), now: NOW })
    expect(v9.code).toBe(0)
    expect(v9.lines.join('\n')).toContain('校验通过')
  })

  it('TC-6.7 白名单拦截：注入白名单外字段改动 → 退出码 1 且零落盘（无备份、无队列、台账 md5 不变）', async () => {
    const { file, root } = setupWorkspace(tinyLedger(), ['REQ-aaaaaa'])
    const before = readFileSync(file, 'utf8')
    const rogue = (ledger: any, now: number, o: any) => {
      const r = migrateV8toV9(ledger, now, o)
      r.ledger.requirements[0].title = '被篡改' // 白名单外
      return r
    }
    const o = await runV9({ file, mode: 'apply', ledger: JSON.parse(before), requirementDirOf: requirementDirOf(root), now: NOW, transform: rogue })
    expect(o.code).toBe(1)
    expect(o.report!.whitelist.bad.length).toBeGreaterThan(0)
    expect(o.events.some((e) => e.phase === 'ABORT')).toBe(true)
    expect(readFileSync(file, 'utf8')).toBe(before)
    expect(existsSync(join(root, 'docs', 'requirements', 'REQ-aaaaaa', 'queue.json'))).toBe(false)
    expect(existsSync(file + '.backup-' + NOW)).toBe(false)
    expect(readdirSync(join(root, '.dsh-data'))).toEqual(['dsh-reqboard.json'])
  })

  it('TC-6.8 rollback：还原 v8（含 tasks）并清理本次生成的 queue.json', async () => {
    const { file, root } = setupWorkspace(tinyLedger(), ['REQ-aaaaaa'])
    const before = readFileSync(file, 'utf8')
    await runV9({ file, mode: 'apply', ledger: JSON.parse(readFileSync(file, 'utf8')), requirementDirOf: requirementDirOf(root), now: NOW })
    const qp = join(root, 'docs', 'requirements', 'REQ-aaaaaa', 'queue.json')
    expect(existsSync(qp)).toBe(true)

    const o = await rollbackV9({ file, now: NOW + 1 })
    expect(o.code).toBe(0)
    expect(o.restored).toBe(true)
    const back = JSON.parse(readFileSync(file, 'utf8'))
    expect(back.schemaVersion).toBe(LEDGER_V8)
    expect(Array.isArray(back.tasks)).toBe(true)
    expect(back.tasks).toHaveLength(2)
    // 回滚必须格式无损：逐字节等于迁移前原文
    expect(readFileSync(file, 'utf8')).toBe(before)
    expect(existsSync(qp)).toBe(false)
    expect(o.removed).toContain(qp)
  })

  it('格式保真：compact（单行）源台账 apply 后仍单行，rollback 逐字节还原', async () => {
    const { file, root } = setupWorkspace(tinyLedger(), ['REQ-aaaaaa'])
    const compact = JSON.stringify(tinyLedger()) // 活台账实测就是 compact（7.89MB 单行）
    writeFileSync(file, compact)
    expect(compact.includes('\n')).toBe(false)

    await runV9({ file, mode: 'apply', ledger: JSON.parse(compact), requirementDirOf: requirementDirOf(root), now: NOW })
    const after = readFileSync(file, 'utf8')
    expect(after.includes('\n'), 'apply 不得把 compact 台账重排成 pretty（会整文件 diff + 体积近翻倍）').toBe(false)
    expect(JSON.parse(after).schemaVersion).toBe(LEDGER_V9)

    const o = await rollbackV9({ file, now: NOW + 1 })
    expect(o.code).toBe(0)
    expect(readFileSync(file, 'utf8')).toBe(compact)
  })

  it('目录缺失（需求记录存在）：apply 建目录并迁入，rollback 删掉本次新建的目录', async () => {
    const { file, root } = setupWorkspace(tinyLedger(), []) // 不预建任何需求目录
    const dir = join(root, 'docs', 'requirements', 'REQ-aaaaaa')
    expect(existsSync(dir)).toBe(false)

    const o = await runV9({ file, mode: 'apply', ledger: JSON.parse(readFileSync(file, 'utf8')), requirementDirOf: requirementDirOf(root), now: NOW })
    expect(o.code).toBe(0)
    expect(existsSync(join(dir, 'queue.json'))).toBe(true)
    expect(o.report!.createdDirs).toEqual([{ requirementId: 'REQ-aaaaaa', dir, taskCount: 2 }])
    expect(o.report!.skipped).toEqual([])
    // manifest 留痕（回滚依据）
    const manifest = JSON.parse(readFileSync(o.manifestPath!, 'utf8'))
    expect(manifest.createdDirs).toEqual([dir])

    const rb = await rollbackV9({ file, now: NOW + 1 })
    expect(rb.code).toBe(0)
    expect(rb.removedDirs).toContain(dir)
    expect(existsSync(dir)).toBe(false)
    expect(JSON.parse(readFileSync(file, 'utf8')).schemaVersion).toBe(LEDGER_V8)
  })

  it('rollback 边界：无备份时拒绝且不写台账', async () => {
    const { file } = setupWorkspace(tinyLedger(), ['REQ-aaaaaa'])
    const before = readFileSync(file, 'utf8')
    const o = await rollbackV9({ file, now: NOW })
    expect(o.code).toBe(1)
    expect(o.restored).toBe(false)
    expect(readFileSync(file, 'utf8')).toBe(before)
  })
})

// ---------------------------------------------------------------------------
// 前置纪律：服务必须在停机状态（否则内存态 v8 会在下次写入时覆盖 v9 成果）
// ---------------------------------------------------------------------------

describe('服务运行守卫（design/migration.md 兼容性处理）', () => {
  it('服务在跑：--apply 拒绝（exit 1、零落盘），--force 放行；--rollback 同样拒绝', async () => {
    const { file, root } = setupWorkspace(tinyLedger(), ['REQ-aaaaaa'])
    const before = readFileSync(file, 'utf8')
    const running = () => true

    const denied = await runV9({ file, mode: 'apply', ledger: JSON.parse(before), requirementDirOf: requirementDirOf(root), now: NOW, isServiceRunning: running })
    expect(denied.code).toBe(1)
    expect(denied.lines.join('\n')).toContain('服务正在运行')
    expect(denied.events[0]!.phase).toBe('ABORT')
    expect(readFileSync(file, 'utf8')).toBe(before)
    expect(existsSync(join(root, 'docs', 'requirements', 'REQ-aaaaaa', 'queue.json'))).toBe(false)

    const forced = await runV9({ file, mode: 'apply', ledger: JSON.parse(before), requirementDirOf: requirementDirOf(root), now: NOW, isServiceRunning: running, force: true })
    expect(forced.code).toBe(0)
    expect(JSON.parse(readFileSync(file, 'utf8')).schemaVersion).toBe(LEDGER_V9)

    const rb = await rollbackV9({ file, now: NOW + 1, isServiceRunning: running })
    expect(rb.code).toBe(1)
    expect(rb.restored).toBe(false)
    expect(JSON.parse(readFileSync(file, 'utf8')).schemaVersion).toBe(LEDGER_V9)
  })

  it('defaultServiceRunningCheck：state/server.pid 指向存活 PID → true；陈旧/不存在 → false', () => {
    const { file, root } = setupWorkspace(tinyLedger(), ['REQ-aaaaaa'])
    const stateDir = join(root, '.dsh-data', 'state')
    mkdirSync(stateDir, { recursive: true })
    const pidFile = join(stateDir, 'server.pid')
    writeFileSync(pidFile, String(process.pid)) // 本进程一定存活
    expect(defaultServiceRunningCheck(file)).toBe(true)
    writeFileSync(pidFile, '999999999') // 不存在的 PID（陈旧 pidfile）
    expect(defaultServiceRunningCheck(file)).toBe(false)
    rmSync(pidFile)
    expect(defaultServiceRunningCheck(file)).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// 真实 CLI 进程（证明 main() 接线可用，而不只是核心函数）
// ---------------------------------------------------------------------------

describe('v8→v9 真实 CLI 进程', () => {
  const run = (args: string[]) => spawnSync('node', ['--import', 'tsx/esm', join(PKG_ROOT, 'scripts', 'migrate-ledger.ts'), ...args], { cwd: PKG_ROOT, encoding: 'utf8' })

  it('--dry-run --json / --apply / --verify / 幂等 / --rollback 全链路', () => {
    const { file, root } = setupWorkspace(mkLedger([mkTask({ id: 't-1' })]), ['REQ-aaaaaa'])
    const before = readFileSync(file, 'utf8')

    const dry = run(['--file', file, '--root', root, '--dry-run', '--json'])
    expect(dry.status).toBe(0)
    const dryJson = JSON.parse(dry.stdout)
    expect(dryJson.mode).toBe('dry-run')
    expect(dryJson.report.totalTasks).toBe(1)
    expect(readFileSync(file, 'utf8')).toBe(before)

    const apply = run(['--file', file, '--root', root, '--apply', '--json'])
    expect(apply.status).toBe(0)
    const applyJson = JSON.parse(apply.stdout)
    expect(applyJson.report.migratedTasks).toBe(1)
    expect(JSON.parse(readFileSync(file, 'utf8')).schemaVersion).toBe(LEDGER_V9)

    const ledgerM = mtime(file)
    const again = run(['--file', file, '--root', root, '--apply', '--json'])
    expect(again.status).toBe(0)
    expect(JSON.parse(again.stdout).lines.join('\n')).toContain('already_v9')
    expect(mtime(file)).toBe(ledgerM)

    const verify = run(['--file', file, '--root', root, '--verify', '--json'])
    expect(verify.status).toBe(0)
    expect(JSON.parse(verify.stdout).code).toBe(0)

    const rb = run(['--file', file, '--root', root, '--rollback', '--json'])
    expect(rb.status).toBe(0)
    expect(JSON.parse(readFileSync(file, 'utf8')).schemaVersion).toBe(LEDGER_V8)
  })

  it('参数缺失 → 退出码 2', () => {
    const r = run(['--dry-run'])
    expect(r.status).toBe(2)
  })
})
