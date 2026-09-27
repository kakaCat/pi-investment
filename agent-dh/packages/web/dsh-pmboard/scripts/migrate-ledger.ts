#!/usr/bin/env node
/**
 * 台账迁移脚本（历史链 v4→v5→v6→v7；现行 **v8 → v9**）。
 *
 * ## 历史链（REQ-47939a / REQ-a33899 / REQ-81aabd）
 * v4→v5（C1~C11）、v5→v6、v6→v7（planning → design，含 requirements[].status /
 * statusHistory[].status / artifacts[].stage 三处同改）。本段语义与导出函数 `migrate` 原样保留。
 *
 * ## 现行 v8 → v9（REQ-260927202051-f6df · S-9 / I-8 / D-1~D-9）
 * 任务数据从台账 `tasks[]` 迁到按需求分片的 `docs/requirements/<REQ>/queue.json`，
 * 台账升到 schemaVersion=9 并**移除 tasks**。范式与历史链一致：备份 + 路径白名单 + 原子替换 + 幂等 + 留痕。
 *
 * 运行（**经 tsx**）：
 *   node --import tsx/esm packages/web/dsh-pmboard/scripts/migrate-ledger.ts --file <ledger> --dry-run
 *   node --import tsx/esm packages/web/dsh-pmboard/scripts/migrate-ledger.ts --file <ledger> --apply
 *   node --import tsx/esm packages/web/dsh-pmboard/scripts/migrate-ledger.ts --file <ledger> --verify
 *   node --import tsx/esm packages/web/dsh-pmboard/scripts/migrate-ledger.ts --file <ledger> --rollback
 * 可选：`--root <dir>`（含 docs/requirements 的工作区根，缺省自动上溯探测）、`--json`（只输出机器可读报告）。
 *
 * 为什么必须是 .ts + tsx：C4（statusHistory 必填）的补齐要**复用运行时同一套算法**
 * （shared/protocol.ts 的 backfillRequirementHistory / backfillTaskHistory，内含从历史评论
 * 反推状态转移的 parseTransitionTarget）。纯 .mjs 只能重抄一份 → 第二套时间线语义 → 本仓吃过这个亏。
 *
 * ### v9 的三条硬纪律（做错会毁掉 82 条需求记录）
 * 1. **顺序**：先写全部 queue.json（D-7）再改台账（D-8）。反序会得到"台账已无任务、队列还没生成"
 *    的双向丢失态；按此顺序最坏是"队列已生成但台账仍含 tasks"——可安全重跑（幂等）。
 * 2. **白名单**：台账只允许 `schemaVersion` / `migrations` / `tasks`(删除) 三类路径差异；
 *    出现白名单外差异立即中止、退出码 1、**一个字节都不落盘**。
 * 3. **幂等**：已是 v9 时 `--apply` 无操作（报告 `already_v9`），不重写任何文件。
 *
 * 安全设计（历史链 + v9 共用）：① 迁移前自动备份；② 变更走"临时文件 + fsync + rename"原子替换
 * （复用 `adapters/JsonLedgerRepository.persistAtomic`）；③ 逐**路径**白名单校验，白名单外即中止且不落盘；
 * ④ 幂等（已是现行版本则 --apply 无操作）；⑤ v9 额外为"未被迁入任何队列的任务"写隔离文件（防静默丢失）。
 */
import { copyFileSync, existsSync, readFileSync, readdirSync, renameSync, statSync, unlinkSync, writeFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { basename, dirname, join, resolve } from 'node:path'
import { persistAtomic } from '../src/adapters/JsonLedgerRepository.js'
import { QUEUE_VERSION, type QueueEdge, type QueueFile, type QueueLayer, type ValidationResult } from '../src/domain/queue/QueueTypes.js'
// 拓扑与校验**唯一实现**（t2/t3）。迁移脚本一律 import，绝不重抄一份——
// 重复实现 = 第二套拓扑/校验语义，本仓吃过这个亏（design/interfaces.md I-3/I-4）。
import { computeEdges, computeLayers, computeReady } from '../src/domain/queue/topology.js'
import { validateQueueFile } from '../src/domain/queue/validateQueue.js'
// t10 收口：这三个函数已从运行时契约（shared/protocol.ts）搬到**迁移专属模块**
// src/domain/legacy/LegacyStatus.ts——脚本行为与输出零变化，仅 import 换位置。
import {
  backfillRequirementHistory,
  backfillTaskHistory,
  migrateArtifactStageNames,
  migrateRequirementStatusNames,
} from '../src/domain/legacy/LegacyStatus.js'

const V5 = 5
/** v6（REQ-a33899：token 字段为纯附加，v5→v6 只 bump 版本 + 留痕，不伪造历史快照）。 */
const V6 = 6
/** 现行契约版本（REQ-81aabd：设计节点英文键 planning → design，v6→v7 改状态键与产物 stage）。 */
const V7 = 7
const USAGE = `用法：--file <ledger> [--dry-run|--apply|--verify|--rollback] [--root <工作区根>] [--json] [--force]（默认 --dry-run）
  注：--apply/--rollback 会先探测 <ledgerDir>/state/server.pid，服务在跑时拒绝（防内存态覆盖）；--force 跳过该探测。`

interface Change { count: number; detail: string[] }

/** v4 → v5 变换。纯函数：不改入参（内部 structuredClone）。 */
export function migrate(ledger: any, now: number): { next: any; changes: Record<string, Change> } {
  const next = structuredClone(ledger)
  const changes: Record<string, Change> = {}
  const bump = (k: string, detail?: string) => {
    const c = (changes[k] ??= { count: 0, detail: [] })
    c.count += 1
    if (detail !== undefined && c.detail.length < 5) c.detail.push(detail)
  }
  const reqs: any[] = next.requirements ?? []
  const tasks: any[] = next.tasks ?? []

  // C3 legacy 状态名归一（reviewing → brainstorming；planning → design，含时间线事件）
  for (const r of reqs) if (migrateRequirementStatusNames(r)) bump('C3_legacy_status_renamed', r.id)
  // C11 产物 stage 字段同键归一（planning → design，与 C3 同一张别名表，避免两套改名名单）
  for (const r of reqs) if (migrateArtifactStageNames(r)) bump('C11_artifact_stage_renamed', r.id)
  // C4 statusHistory 必填（复用运行时 backfill）
  for (const r of reqs) { const h = backfillRequirementHistory(r); if (h !== undefined) { r.statusHistory = h; bump('C4_status_history_backfilled', r.id) } }
  for (const t of tasks) { const h = backfillTaskHistory(t); if (h !== undefined) { t.statusHistory = h; bump('C4_status_history_backfilled', t.id) } }
  // C5 category 必填
  for (const r of reqs) if (r.category === undefined || r.category === null) { r.category = 'feature'; bump('C5_category_defaulted', r.id) }
  // C6 删零引用预留字段
  for (const r of reqs) {
    for (const k of ['projectId', 'parentId']) if (k in r) { delete r[k]; bump('C6_reserved_field_dropped', r.id + '.' + k) }
  }
  // C7 sheet.items[].source → 判别联合（在册 + 历史两处）
  const unionize = (items: any[], where: string) => {
    for (const it of items ?? []) {
      if (typeof it.source !== 'string') continue
      const from = it.source
      it.source = from === 'requirement' ? { kind: 'requirement' } : { kind: 'task', taskId: from }
      bump('C7_sheet_source_unioned', where + ':' + from)
    }
  }
  for (const r of reqs) {
    const v = r.verification
    if (v === undefined || v === null) continue
    if (v.sheet !== undefined) unionize(v.sheet.items, r.id + '.sheet')
    for (const s of v.sheetHistory ?? []) unionize(s.items, r.id + '.sheetHistory')
  }
  // C8 task.scope 补默认
  for (const t of tasks) if (t.scope === undefined || t.scope === null) { t.scope = { apis: [], tables: [], files: [] }; bump('C8_task_scope_defaulted', t.id) }
  // C9 dependsOn 去重 + 自指 + 剔除悬空
  const ids = new Set(tasks.map(t => t.id))
  for (const t of tasks) {
    const arr: unknown[] = Array.isArray(t.dependsOn) ? t.dependsOn : []
    const seen = new Set<string>(); const out: string[] = []
    for (const d of arr) {
      if (typeof d !== 'string' || d === t.id || !ids.has(d) || seen.has(d)) { bump('C9_depends_on_cleaned', t.id + '<-' + String(d)); continue }
      seen.add(d); out.push(d)
    }
    if (out.length !== arr.length) t.dependsOn = out
  }
  // C10 artifacts 去重（同 kind+path 只留一条，保留 confirmedAt 最早的非空者）
  for (const r of reqs) {
    if (!Array.isArray(r.artifacts)) continue
    const byKey = new Map<string, any>(); const out: any[] = []
    for (const a of r.artifacts) {
      const key = String(a?.kind) + '\u0000' + String(a?.path)
      const prev = byKey.get(key)
      if (prev === undefined) { byKey.set(key, a); out.push(a); continue }
      bump('C10_artifact_deduped', r.id + ':' + key.split('\u0000')[0])
      const p = prev.confirmedAt; const c = a.confirmedAt
      if ((p === undefined && c !== undefined) || (p !== undefined && c !== undefined && c < p)) {
        out[out.indexOf(prev)] = a; byKey.set(key, a)
      }
    }
    if (out.length !== r.artifacts.length) r.artifacts = out
  }
  // C1 + C2 版本与迁移留痕（链式 v4 → v5 → v6 → v7，逐段留痕；已是 v7 则零改动 = 幂等）
  const from = typeof next.schemaVersion === 'number' ? next.schemaVersion : 4
  next.migrations = [...(next.migrations ?? [])]
  if (from <= V5 - 1) next.migrations.push({ from: 4, to: 5, at: now, by: 'migrate-ledger.ts' })
  if (from <= V5) next.migrations.push({ from: 5, to: 6, at: now, by: 'migrate-ledger.ts' })
  if (from <= V6) next.migrations.push({ from: 6, to: 7, at: now, by: 'migrate-ledger.ts' })
  next.schemaVersion = V7
  return { next, changes }
}

/** 递归收集两对象差异的**路径**（数组按下标；长度不同只报 .length）。 */
export function diffPaths(a: any, b: any, path = '', out: string[] = []): string[] {
  if (a === b) return out
  const isObj = (x: any) => x !== null && typeof x === 'object'
  if (!isObj(a) || !isObj(b) || Array.isArray(a) !== Array.isArray(b)) { out.push(path === '' ? '$' : path); return out }
  if (Array.isArray(a)) {
    if (a.length !== b.length) { out.push((path === '' ? '$' : path) + '.length'); return out }
    for (let i = 0; i < a.length; i++) diffPaths(a[i], b[i], path + '[' + i + ']', out)
    return out
  }
  for (const k of new Set([...Object.keys(a), ...Object.keys(b)])) diffPaths(a[k], b[k], path === '' ? k : path + '.' + k, out)
  return out
}

/** 白名单：允许出现的差异路径（design/migration.md §4）。 */
export const WHITELIST: { re: RegExp; why: string }[] = [
  { re: /^(schemaVersion|migrations)(\.|$)/, why: 'C1/C2' },
  { re: /^revision$|^updatedAt$/, why: 'revision/updatedAt 由写入方 bump，允许变化' },
  { re: /^requirements\[\d+\]\.(status|statusHistory|category|projectId|parentId|artifacts)(\.|\[|$)/, why: 'C3/C4/C5/C6/C10/C11' },
  { re: /^requirements\[\d+\]\.verification\.(sheet|sheetHistory)\[?\d*\]?\.?items\[\d+\]\.source$/, why: 'C7' },
  { re: /^requirements\[\d+\]\.verification\.sheet\.items$/, why: 'C7（长度不变，逐项比较）' },
  { re: /^requirements\[\d+\]\.verification\.sheetHistory\[\d+\]\.items\[\d+\]\.source$/, why: 'C7' },
  { re: /^tasks\[\d+\]\.(statusHistory|scope|dependsOn)(\.|\[|$)/, why: 'C4/C8/C9' },
]

export function checkWhitelist(paths: string[]): { ok: string[]; bad: string[] } {
  const ok: string[] = []; const bad: string[] = []
  for (const p of paths) (WHITELIST.some(w => w.re.test(p)) ? ok : bad).push(p)
  return { ok, bad }
}

// ===========================================================================
// v8 → v9：任务分片迁移（REQ-260927202051-f6df · S-9 / I-8 / D-1~D-9）
// ===========================================================================

/** 源台账契约版本（v8：`tasks[]` 仍在台账内）。 */
export const LEDGER_V8 = 8
/** 目标台账契约版本（v9：`tasks` 移除，任务改存各需求 `queue.json`）。 */
export const LEDGER_V9 = 9

/**
 * v8→v9 允许出现的差异路径白名单（design/migration.md §4 / interfaces.md I-8）。
 *
 * 只有三类：版本 bump / 迁移留痕 / `tasks` 字段移除。任何第四类差异都说明变换动了不该动的东西
 * （需求记录、triage、revision…）——82 条需求记录就靠这道闸门保住：白名单外差异 → 退出码 1、不落盘。
 */
export const V9_WHITELIST: { re: RegExp; why: string }[] = [
  { re: /^schemaVersion$/, why: 'V9-1 版本 bump 8→9' },
  { re: /^migrations(\.|\[|$)/, why: 'V9-2 迁移留痕追加 {8,9}' },
  { re: /^tasks(\.|\[|$)/, why: 'V9-3 tasks 字段移除（任务改存 queue.json）' },
]

export function checkV9Whitelist(paths: string[]): { ok: string[]; bad: string[] } {
  const ok: string[] = []; const bad: string[] = []
  for (const p of paths) (V9_WHITELIST.some(w => w.re.test(p)) ? ok : bad).push(p)
  return { ok, bad }
}

// ---------------------------------------------------------------------------
// 拓扑 / 校验：直接用 t2/t3 的唯一实现（见文件头 import）
// ---------------------------------------------------------------------------

/** Kahn 入度分层；有环抛 Error（message 含 CIRCULAR）。空输入返回 `[]`（不抛错）。同层保持输入序。 */
export function computeLayersLocal(tasks: readonly any[]): QueueLayer[] {
  const ids = tasks.map((t) => t.id)
  const idSet = new Set(ids)
  const indeg = new Map<string, number>(ids.map((id) => [id, 0]))
  const dependents = new Map<string, string[]>(ids.map((id) => [id, []]))
  for (const t of tasks) {
    for (const d of depsOf(t)) {
      if (!idSet.has(d)) continue
      indeg.set(t.id, (indeg.get(t.id) ?? 0) + 1)
      dependents.get(d)!.push(t.id)
    }
  }
  const layers: QueueLayer[] = []
  let current = ids.filter((id) => (indeg.get(id) ?? 0) === 0)
  let processed = 0
  let layer = 0
  while (current.length > 0) {
    layers.push({ layer, tasks: [...current] })
    const next: string[] = []
    for (const id of current) {
      processed += 1
      for (const nx of dependents.get(id) ?? []) {
        const v = (indeg.get(nx) ?? 0) - 1
        indeg.set(nx, v)
        if (v === 0) next.push(nx)
      }
    }
    current = next
    layer += 1
  }
  if (processed !== ids.length) {
    const cyclic = ids.filter((id) => (indeg.get(id) ?? 0) > 0)
    throw new Error('CIRCULAR_DEPENDENCY: 检出环依赖（涉及 ' + cyclic.length + ' 个任务：' + cyclic.slice(0, 8).join(',') + '）')
  }
  return layers
}

/** ready = 自身 `todo` 且依赖全部 `done`（V-5 的唯一推导口径）。 */
export function computeReadyLocal(tasks: readonly any[]): string[] {
  const byId = new Map(tasks.map((t) => [t.id, t]))
  return tasks.filter((t) => t.status === 'todo' && depsOf(t).every((d) => byId.get(d)?.status === 'done')).map((t) => t.id)
}

/** V-1~V-6 校验；**永不抛错**（失败只填 issues）。 */
export function validateQueueFileLocal(file: any): ValidationResult {
  const issues: { rule: any; message: string; path?: string }[] = []
  const push = (rule: any, message: string, path?: string) => { issues.push(path === undefined ? { rule, message } : { rule, message, path }) }
  try {
    // V-1 必填字段完整性
    if (typeof file?.version !== 'number') push('V-1', 'version 缺失或非 number', 'version')
    if (typeof file?.requirement_id !== 'string' || file.requirement_id.length === 0) push('V-1', 'requirement_id 缺失或非 string', 'requirement_id')
    if (typeof file?.schemaVersion !== 'number') push('V-1', 'schemaVersion 缺失或非 number', 'schemaVersion')
    if (typeof file?.generated_at !== 'string') push('V-1', 'generated_at 缺失或非 string', 'generated_at')
    if (file?.updated_at !== undefined && typeof file.updated_at !== 'string') push('V-1', 'updated_at 非 string', 'updated_at')
    for (const k of ['tasks', 'edges', 'layers', 'ready']) if (!Array.isArray(file?.[k])) push('V-1', k + ' 缺失或非数组', k)
    if (!Array.isArray(file?.tasks) || !Array.isArray(file?.edges) || !Array.isArray(file?.layers) || !Array.isArray(file?.ready)) {
      return { passed: false, issues } // 结构已坏，后续规则无意义（且不得抛错）
    }
    const tasks: any[] = file.tasks
    const ids = new Set<string>()
    const byId = new Map<string, any>()
    tasks.forEach((t, i) => {
      const id = t?.id
      if (typeof id !== 'string' || id.length === 0) { push('V-2', 'tasks[' + i + '].id 缺失或非 string', 'tasks[' + i + '].id'); return }
      if (ids.has(id)) push('V-2', '任务 id 重复：' + id, 'tasks[' + i + '].id')
      ids.add(id)
      byId.set(id, t)
    })
    tasks.forEach((t, i) => {
      if (t?.requirementId !== file.requirement_id) push('V-3', 'task.requirementId≠queue.requirement_id（跨需求串档）：' + String(t?.requirementId), 'tasks[' + i + '].requirementId')
      depsOf(t).forEach((d, j) => { if (!ids.has(d)) push('V-3', 'dependsOn 引用不存在的任务：' + d, 'tasks[' + i + '].dependsOn[' + j + ']') })
    })
    file.edges.forEach((e: any, i: number) => { if (!ids.has(e?.from) || !ids.has(e?.to)) push('V-3', 'edge 引用不存在的任务', 'edges[' + i + ']') })
    file.layers.forEach((l: any, i: number) => { for (const id of l?.tasks ?? []) if (!ids.has(id)) push('V-3', 'layers 引用不存在的任务：' + id, 'layers[' + i + ']') })
    file.ready.forEach((id: string, i: number) => { if (!ids.has(id)) push('V-3', 'ready 引用不存在的任务：' + id, 'ready[' + i + ']') })
    // V-4 层级一致性
    tasks.forEach((t, i) => {
      if (typeof t?.layer !== 'number' || t.layer < 0) { push('V-4', 'layer 缺失或为负', 'tasks[' + i + '].layer'); return }
      if (t.layer === 0 && depsOf(t).length > 0) push('V-4', 'layer=0 的任务不得有依赖', 'tasks[' + i + '].layer')
      for (const d of depsOf(t)) {
        const dep = byId.get(d)
        if (dep !== undefined && typeof dep.layer === 'number' && t.layer <= dep.layer) push('V-4', 'layer(' + t.layer + ') 不大于依赖 ' + d + '.layer(' + dep.layer + ')', 'tasks[' + i + '].layer')
      }
    })
    // V-5 ready 双向一致性
    const readySet = new Set<string>(file.ready.filter((x: unknown): x is string => typeof x === 'string'))
    for (const t of tasks) {
      const depsDone = depsOf(t).every((d) => byId.get(d)?.status === 'done')
      if (readySet.has(t.id) && !depsDone) push('V-5', '假就绪：依赖未全 done 却进 ready：' + t.id, 'ready')
      if (t?.status === 'todo' && !readySet.has(t.id) && depsDone) push('V-5', '漏就绪：依赖已全 done 却不在 ready：' + t.id, 'ready')
    }
    // V-6 无环性
    try { computeLayersLocal(tasks) } catch (e) { push('V-6', (e as Error).message) }
  } catch (e) {
    push('V-1', '校验过程内部异常（已降级为 issue，不抛错）：' + (e as Error).message)
  }
  return { passed: issues.length === 0, issues }
}

/** 迁移默认依赖的拓扑/校验实现（接线 t2/t3 后改这里即可全量切换）。 */
export const v9Defaults = {
  computeLayers: computeLayersLocal,
  computeEdges: computeEdgesLocal,
  computeReady: computeReadyLocal,
  validate: validateQueueFileLocal as (file: any) => ValidationResult,
}

// ---------------------------------------------------------------------------
// 纯变换
// ---------------------------------------------------------------------------

export interface V9Orphan {
  taskId: string
  requirementId?: string
  reason: 'missing-requirement-id' | 'unknown-requirement'
}

export interface V9QueueOutput {
  requirementId: string
  file: QueueFile
  path: string
  /** 序列化后的文件内容（与落盘字节一致，便于契约比对与 sha256） */
  json: string
}

export interface V9Skipped {
  requirementId: string
  reason: string
  taskIds: string[]
}

export interface V9Report {
  sourceVersion: number
  totalTasks: number
  migratedTasks: number
  groupedTasks: number
  requirementsWithTasks: number
  orphanTasks: V9Orphan[]
  skipped: V9Skipped[]
  whitelist: { ok: string[]; bad: string[] }
  alreadyV9: boolean
}

/** 迁移执行顺序打点（D-1~D-9），供"先写队列、后改台账"的机器可核验断言。 */
export interface V9OrderEvent {
  seq: number
  phase: string
  detail: string
}

export interface V9Options {
  /** 需求目录解析（返回绝对或工作区相对路径；queue.json 落在其中） */
  requirementDirOf: (requirementId: string) => string
  /** 目录存在性探测（缺省 fs.existsSync；单测可注入，保持变换无 I/O） */
  dirExists?: (dir: string) => boolean
  generatedAt?: string
  computeLayers?: (tasks: readonly any[]) => QueueLayer[]
  computeEdges?: (tasks: readonly any[]) => QueueEdge[]
  computeReady?: (tasks: readonly any[]) => string[]
  validate?: (file: any) => ValidationResult
}

export interface V9Result {
  /** 变换后的台账（v9：无 tasks） */
  ledger: any
  queues: V9QueueOutput[]
  changes: Record<string, Change>
  report: V9Report
  /** 未被任何队列接收的任务（orphan / 缺目录 / 环 / 校验失败）——防静默丢失，落隔离文件 */
  unmigrated: { reason: string; requirementId?: string; tasks: any[] }[]
  events: V9OrderEvent[]
}

/**
 * v8 → v9 变换（**纯函数**：内部 structuredClone，不改入参；唯一"副作用"是注入的 dirExists 探测）。
 *
 * 逐字段无损的做法是**整对象展开**：`{ ...structuredClone(task), layer }`——不按文档表格重列字段，
 * 从结构上让"少迁一个字段"不可能发生（TaskRecord 37 字段 + layer = QueueTask 38 字段；
 * 权威真身是 `src/shared/protocol.ts:1150-1216`，不是文档表格）。
 *
 * 已是 v9 时早返回（`alreadyV9: true`，台账零改动、不追加迁移留痕）——变换自身幂等。
 */
export function migrateV8toV9(ledger: any, now: number, opts: V9Options): V9Result {
  const events: V9OrderEvent[] = []
  let seq = 0
  const ev = (phase: string, detail: string) => { events.push({ seq: ++seq, phase, detail }) }

  const changes: Record<string, Change> = {}
  const bump = (k: string, detail?: string) => {
    const c = (changes[k] ??= { count: 0, detail: [] })
    c.count += 1
    if (detail !== undefined && c.detail.length < 5) c.detail.push(detail)
  }

  const dirExists = opts.dirExists ?? existsSync
  const computeLayers = opts.computeLayers ?? v9Defaults.computeLayers
  const computeEdges = opts.computeEdges ?? v9Defaults.computeEdges
  const computeReady = opts.computeReady ?? v9Defaults.computeReady
  const validate = opts.validate ?? v9Defaults.validate
  const generatedAt = opts.generatedAt ?? new Date(now).toISOString()

  // D-1 读台账
  const sourceVersion = typeof ledger?.schemaVersion === 'number' ? ledger.schemaVersion : LEDGER_V8
  const reqs: any[] = Array.isArray(ledger?.requirements) ? ledger.requirements : []
  const rawTasks: any[] = Array.isArray(ledger?.tasks) ? ledger.tasks : []
  const reqIds = new Set(reqs.map((r) => r.id))

  if (sourceVersion >= LEDGER_V9) {
    return {
      ledger: structuredClone(ledger),
      queues: [],
      changes: {},
      report: {
        sourceVersion, totalTasks: rawTasks.length, migratedTasks: 0, groupedTasks: 0,
        requirementsWithTasks: 0, orphanTasks: [], skipped: [], whitelist: { ok: [], bad: [] }, alreadyV9: true,
      },
      unmigrated: [],
      events: [{ seq: 1, phase: 'D-1', detail: '已是 v9（schemaVersion=' + sourceVersion + '）：无操作' }],
    }
  }

  ev('D-1', '解析台账：requirements=' + reqs.length + ' tasks=' + rawTasks.length + ' triages=' + (Array.isArray(ledger?.triages) ? ledger.triages.length : 0))

  // D-3 分组 / orphan（宁可不迁也不串档）
  const groups = new Map<string, any[]>()
  const orphans: V9Orphan[] = []
  const unmigrated: V9Result['unmigrated'] = []
  const orphanTasks: any[] = []
  for (const t of rawTasks) {
    const rid = typeof t?.requirementId === 'string' ? t.requirementId : ''
    if (rid.length === 0) { orphans.push({ taskId: String(t?.id), reason: 'missing-requirement-id' }); orphanTasks.push(t); continue }
    if (!reqIds.has(rid)) { orphans.push({ taskId: String(t?.id), requirementId: rid, reason: 'unknown-requirement' }); orphanTasks.push(t); continue }
    const arr = groups.get(rid) ?? []
    arr.push(t)
    groups.set(rid, arr)
  }
  if (orphanTasks.length > 0) {
    unmigrated.push({ reason: 'orphan（无 requirementId 或指向不存在需求）', tasks: orphanTasks })
    bump('V9_orphan_tasks', String(orphanTasks.length))
  }
  ev('D-3', '分组：有任务需求 ' + groups.size + ' 个；orphan ' + orphans.length + ' 条（不迁移、不串档）')

  // D-4 构造 QueueFile（含 layer）；D-5 拓扑；D-6 校验
  const queues: V9QueueOutput[] = []
  const skipped: V9Skipped[] = []
  for (const [rid, ts] of groups) {
    const taskIds = ts.map((t) => String(t.id))
    let dir = ''
    try { dir = opts.requirementDirOf(rid) } catch (e) {
      skipped.push({ requirementId: rid, reason: 'requirementDirOf 抛错：' + (e as Error).message, taskIds })
      unmigrated.push({ reason: 'requirementDirOf 抛错', requirementId: rid, tasks: ts })
      bump('V9_skipped_requirement', rid)
      continue
    }
    if (dir.length === 0 || !dirExists(dir)) {
      skipped.push({ requirementId: rid, reason: '需求目录不存在（不隐式建目录，任务隔离保留）：' + dir, taskIds })
      unmigrated.push({ reason: 'missing-requirement-dir', requirementId: rid, tasks: ts })
      bump('V9_skipped_missing_dir', rid)
      continue
    }
    // 拓扑分层（环 → 该需求中止，不写半成品）
    let layers: QueueLayer[]
    try {
      layers = computeLayers(ts)
    } catch (e) {
      skipped.push({ requirementId: rid, reason: 'CIRCULAR：' + (e as Error).message, taskIds })
      unmigrated.push({ reason: 'circular-dependency', requirementId: rid, tasks: ts })
      bump('V9_skipped_circular', rid)
      continue
    }
    const layerOf = new Map<string, number>()
    for (const l of layers) for (const id of l.tasks) layerOf.set(id, l.layer)
    const queueTasks = ts.map((t) => ({ ...structuredClone(t), layer: layerOf.get(t.id) ?? 0 }))
    const file: QueueFile = {
      version: QUEUE_VERSION,
      requirement_id: rid,
      schemaVersion: LEDGER_V9,
      generated_at: generatedAt,
      tasks: queueTasks as any,
      edges: computeEdges(queueTasks),
      layers: computeLayers(queueTasks),
      ready: computeReady(queueTasks),
    }
    const v = validate(file)
    if (!v.passed) {
      const msg = v.issues.slice(0, 5).map((i) => i.rule + '@' + (i.path ?? '') + ':' + i.message).join(' | ')
      skipped.push({ requirementId: rid, reason: 'QUEUE_VALIDATION_FAILED（' + v.issues.length + ' 项）：' + msg, taskIds })
      unmigrated.push({ reason: 'queue-validation-failed', requirementId: rid, tasks: ts })
      bump('V9_skipped_validation', rid)
      continue
    }
    const json = JSON.stringify(file, null, 2)
    queues.push({ requirementId: rid, file, path: join(dir, 'queue.json'), json })
    bump('V9_tasks_sharded', rid + ':' + queueTasks.length)
  }
  ev('D-4', '构造 QueueFile：' + queues.length + ' 份（schemaVersion=9，QueueTask=TaskRecord+layer）')
  ev('D-5', '拓扑分层 + 求 ready：成功 ' + queues.length + ' 个；环/缺目录/校验失败跳过 ' + skipped.length + ' 个需求')
  ev('D-6', '校验 V-1~V-6：通过 ' + queues.length + ' 份')

  // D-8（纯变换部分）台账变换：删 tasks / schemaVersion=9 / migrations 追加留痕
  const next = structuredClone(ledger)
  delete next.tasks
  next.schemaVersion = LEDGER_V9
  next.migrations = [...(Array.isArray(next.migrations) ? next.migrations : []), { from: LEDGER_V8, to: LEDGER_V9, at: now, by: 'migrate-ledger.ts' }]
  bump('V9_schema_version_bumped')
  bump('V9_migration_marked', '{from:8,to:9}')
  if (rawTasks.length > 0) bump('V9_ledger_tasks_removed', String(rawTasks.length))

  const paths = diffPaths(ledger, next)
  const { ok, bad } = checkV9Whitelist(paths)

  const migrated = queues.reduce((s, q) => s + q.file.tasks.length, 0)
  const report: V9Report = {
    sourceVersion,
    totalTasks: rawTasks.length,
    migratedTasks: migrated,
    groupedTasks: [...groups.values()].reduce((s, a) => s + a.length, 0),
    requirementsWithTasks: groups.size,
    orphanTasks: orphans,
    skipped,
    whitelist: { ok, bad },
    alreadyV9: false,
  }

  return { ledger: next, queues, changes, report, unmigrated, events }
}

// ---------------------------------------------------------------------------
// CLI 编排：路径解析 / 备份 / manifest / 四态
// ---------------------------------------------------------------------------

function sha256(contents: string): string {
  return createHash('sha256').update(contents, 'utf8').digest('hex')
}

/** 解析工作区根（含 `docs/requirements/` 的目录）：显式 --root 优先，否则从台账路径/ cwd 上溯探测。 */
export function resolveWorkspaceRoot(ledgerFile: string, rootArg?: string): string {
  if (rootArg !== undefined && rootArg.length > 0) return resolve(rootArg)
  const probe = (start: string): string | undefined => {
    let dir = resolve(start)
    for (let i = 0; i < 6; i++) {
      if (existsSync(join(dir, 'docs', 'requirements'))) return dir
      const up = dirname(dir)
      if (up === dir) break
      dir = up
    }
    return undefined
  }
  return probe(dirname(ledgerFile)) ?? probe(process.cwd())
    ?? (() => { throw new Error('无法定位工作区根（含 docs/requirements/ 的目录）；请用 --root <dir> 显式指定') })()
}

function listSiblings(file: string, suffixPrefix: string): string[] {
  const abs = resolve(file)
  const dir = dirname(abs)
  const base = basename(abs)
  if (!existsSync(dir)) return []
  return readdirSync(dir)
    .filter((n) => n.startsWith(base + suffixPrefix))
    .map((n) => join(dir, n))
    .sort((a, b) => {
      const ta = Number((a.split(suffixPrefix).pop() ?? '').replace(/[^0-9].*$/, ''))
      const tb = Number((b.split(suffixPrefix).pop() ?? '').replace(/[^0-9].*$/, ''))
      if (Number.isFinite(ta) && Number.isFinite(tb) && ta !== tb) return tb - ta
      try { return statSync(b).mtimeMs - statSync(a).mtimeMs } catch { return 0 }
    })
}

const listBackups = (file: string): string[] => listSiblings(file, '.backup-')
const listManifests = (file: string): string[] => listSiblings(file, '.migrate-manifest-')

/**
 * 服务运行探测（design/migration.md「兼容性处理」：迁移**必须在服务停止状态下执行**）。
 *
 * 为什么必须拦：DSH 进程把台账**整份**读进内存，写路径按内存快照原子替换文件。
 * 服务运行期间迁移，下一次任何需求写入都会用 v8 内存态覆盖 v9 台账 —— `tasks` 复活、
 * queue.json 变成无人引用的孤儿分片，且**不报任何错**。
 *
 * 判据：`<ledgerDir>/state/server.pid` 存在且该 PID 存活（活实例实测：pid 文件 + :13080 LISTEN 同一 PID）。
 */
export function defaultServiceRunningCheck(ledgerFile: string): boolean {
  const pidFile = join(dirname(resolve(ledgerFile)), 'state', 'server.pid')
  if (!existsSync(pidFile)) return false
  const pid = Number(readFileSync(pidFile, 'utf8').trim())
  if (!Number.isInteger(pid) || pid <= 0) return false
  try { process.kill(pid, 0); return true } catch { return false }
}

export type V9Mode = 'dry-run' | 'apply' | 'verify' | 'rollback'

export interface V9RunOutcome {
  code: number
  mode: V9Mode
  report: V9Report | undefined
  events: V9OrderEvent[]
  lines: string[]
  queuePaths: string[]
  backupPath?: string
  manifestPath?: string
  unmigratedPath?: string
  /** 顺序契约的机器可核验点：D-9 落盘台账前，全部 queue.json 是否已在磁盘上 */
  queueFilesWrittenBeforeLedger: boolean
}

export interface RunV9Options {
  file: string
  ledger: any
  mode: 'dry-run' | 'apply' | 'verify'
  requirementDirOf: (requirementId: string) => string
  now: number
  dirExists?: (dir: string) => boolean
  persist?: (path: string, contents: string) => Promise<void>
  transform?: (ledger: any, now: number, opts: V9Options) => V9Result
  /** 服务运行探测（缺省 defaultServiceRunningCheck）；仅 --apply 生效 */
  isServiceRunning?: (ledgerFile: string) => boolean
  /** true = 明知服务在跑仍执行（仅用于可控的紧急场景） */
  force?: boolean
}

/**
 * 执行 v8→v9 迁移（三态）。**顺序契约**：白名单检查 → D-2 备份 → D-7 写全部队列 → D-8 台账变换就绪
 * → D-9 原子替换台账；白名单外差异或校验失败时**一个字节都不写**。
 */
export async function runV9(opts: RunV9Options): Promise<V9RunOutcome> {
  const { file, ledger, now } = opts
  const mode = opts.mode
  const persist = opts.persist ?? persistAtomic
  const transform = opts.transform ?? migrateV8toV9
  const lines: string[] = []
  const log = (s: string) => lines.push(s)

  // 幂等硬闸门：已是 v9 → 零写操作（不备份、不重写台账、不重写队列文件，mtime 全不变）
  if (mode !== 'verify' && typeof ledger?.schemaVersion === 'number' && ledger.schemaVersion >= LEDGER_V9) {
    const line = 'already_v9：台账已是 schemaVersion=' + ledger.schemaVersion + '，--' + mode + ' 无操作（未重写任何文件，mtime 不变）'
    return {
      code: 0, mode, report: undefined,
      events: [{ seq: 1, phase: 'already_v9', detail: line }],
      lines: ['✅ ' + line], queuePaths: [], queueFilesWrittenBeforeLedger: false,
    }
  }

  // 前置纪律：服务在跑时禁止写（内存态 v8 会在下一次写入时覆盖 v9 台账，且不报错）
  if (mode === 'apply' && opts.force !== true) {
    const running = (opts.isServiceRunning ?? defaultServiceRunningCheck)(file)
    if (running) {
      const line = '❌ 检测到服务正在运行（<ledgerDir>/state/server.pid 存活）——拒绝执行 --apply。'
        + '请先停机（agent-dh/scripts/stop.sh），否则 DSH 内存中的 v8 快照会在下次写入时覆盖本次迁移成果（tasks 复活、queue.json 变孤儿）。'
        + '确认可控时用 --force 强制。'
      return { code: 1, mode, report: undefined, events: [{ seq: 1, phase: 'ABORT', detail: 'service-running' }], lines: [line], queuePaths: [], queueFilesWrittenBeforeLedger: false }
    }
  }

  const result = transform(ledger, now, {
    requirementDirOf: opts.requirementDirOf,
    dirExists: opts.dirExists,
  })
  // 白名单以"输入 vs 结果"重算为权威（不信任 transform 自报）
  const paths = diffPaths(ledger, result.ledger)
  const { ok, bad } = checkV9Whitelist(paths)
  result.report.whitelist = { ok, bad }

  if (mode === 'verify') return verifyV9(opts, result)

  log('── v8 → v9 迁移报告（' + mode + '）──')
  log('台账：' + file)
  log('源 schemaVersion：' + result.report.sourceVersion + '  需求 ' + (ledger.requirements?.length ?? 0) + ' 条  任务 ' + result.report.totalTasks + ' 条')
  log('分组：' + result.report.requirementsWithTasks + ' 个需求有任务；orphan ' + result.report.orphanTasks.length + ' 条（不迁移）')
  log('队列文件：' + result.queues.length + ' 个' + (mode === 'dry-run' ? '（计划）' : ''))
  for (const s of result.report.skipped) log('⚠️ 跳过需求 ' + s.requirementId + '：' + s.reason)
  log('白名单：' + ok.length + ' 条命中 / 白名单外 ' + bad.length + ' 条')

  const events: V9OrderEvent[] = []
  const push = (phase: string, detail: string) => { events.push({ seq: events.length + 1, phase, detail }) }

  if (bad.length > 0) {
    log('❌ 出现白名单外差异，**未落盘**（一个字节都没写）：')
    for (const p of bad.slice(0, 20)) log('  - ' + p)
    events.push({ seq: 1, phase: 'ABORT', detail: '白名单外差异 ' + bad.length + ' 条 → 退出码 1' })
    return { code: 1, mode, report: result.report, events, lines, queuePaths: [], queueFilesWrittenBeforeLedger: false }
  }

  if (mode === 'dry-run') {
    push('D-1', '解析台账：requirements=' + (ledger.requirements?.length ?? 0) + ' tasks=' + result.report.totalTasks)
    push('D-3', '分组：有任务需求 ' + result.report.requirementsWithTasks + ' 个；orphan ' + result.report.orphanTasks.length + ' 条（不迁移）')
    push('D-4', '构造 QueueFile：' + result.queues.length + ' 份')
    push('D-5', '拓扑分层 + 求 ready')
    push('D-6', '校验 V-1~V-6：通过 ' + result.queues.length + ' 份；跳过 ' + result.report.skipped.length + ' 个需求')
    for (const q of result.queues) log('  · ' + q.requirementId + ' → ' + q.path + '（' + q.file.tasks.length + ' 任务，ready=' + q.file.ready.length + '）')
    log('执行顺序（计划）：D-7 先写 ' + result.queues.length + ' 份 queue.json → D-8 台账变换 → D-9 原子替换台账')
    log('✅ dry-run 完成：未落盘（台账 md5/mtime 不变，未生成任何 queue.json）')
    return { code: 0, mode, report: result.report, events, lines, queuePaths: result.queues.map((q) => q.path), queueFilesWrittenBeforeLedger: false }
  }

  // ---- apply ----
  const backupPath = resolve(file) + '.backup-' + now
  const rawBefore = readFileSync(file, 'utf8')
  const preSha = sha256(rawBefore)
  // 保留源台账的序列化形态（实测活台账是单行 compact：7.89MB；强行 pretty 会整文件重排 + 体积近翻倍）
  const compact = !rawBefore.includes('\n')
  push('D-1', '解析台账：requirements=' + (ledger.requirements?.length ?? 0) + ' tasks=' + result.report.totalTasks + '（源格式=' + (compact ? 'compact' : 'pretty') + '）')
  // D-2 备份（先于任何写）
  copyFileSync(file, backupPath)
  push('D-2', '备份台账 → ' + backupPath)
  push('D-3', '分组：有任务需求 ' + result.report.requirementsWithTasks + ' 个；orphan ' + result.report.orphanTasks.length + ' 条（不迁移）')
  push('D-4', '构造 QueueFile：' + result.queues.length + ' 份')
  push('D-5', '拓扑分层 + 求 ready')
  push('D-6', '校验 V-1~V-6：通过 ' + result.queues.length + ' 份；跳过 ' + result.report.skipped.length + ' 个需求')

  // D-7 写队列（**先**）
  const queueHashes: { path: string; sha256: string }[] = []
  for (const q of result.queues) {
    await persist(q.path, q.json)
    const sha = sha256(q.json)
    queueHashes.push({ path: q.path, sha256: sha })
    push('D-7', '写队列 ' + q.path + '（' + q.file.tasks.length + ' 任务, sha256=' + sha.slice(0, 12) + '…）')
  }
  push('D-7', '全部 ' + result.queues.length + '/' + result.queues.length + ' 份 queue.json 已落盘')

  // 未被任何队列接收的任务 → 隔离保留（v9 移除 tasks 后防静默丢失）
  let unmigratedPath: string | undefined
  const unmigratedCount = result.unmigrated.reduce((s, u) => s + u.tasks.length, 0)
  if (unmigratedCount > 0) {
    unmigratedPath = resolve(file) + '.unmigrated-' + now + '.json'
    await persist(unmigratedPath, JSON.stringify({
      schemaVersion: LEDGER_V8, at: now, by: 'migrate-ledger.ts',
      note: '未被任何 queue.json 接收的任务（orphan / 缺目录 / 环 / 校验失败）。v9 台账不再持有 tasks，故隔离保留以防静默丢失；请人工裁决后再删除本文件。',
      groups: result.unmigrated,
    }, null, 2))
    push('D-7', '隔离保留 ' + unmigratedCount + ' 条未迁移任务 → ' + unmigratedPath)
  }

  // 清单（回滚归属凭据）：写于 D-9 之前，故台账替换后仍可凭它精确清理本次生成的队列
  const manifestPath = resolve(file) + '.migrate-manifest-' + now + '.json'
  await persist(manifestPath, JSON.stringify({
    at: now, by: 'migrate-ledger.ts', from: LEDGER_V8, to: LEDGER_V9,
    ledger: resolve(file), backup: backupPath, unmigrated: unmigratedPath,
    ledgerPreSha256: preSha, queues: queueHashes,
  }, null, 2))
  push('D-7', '写迁移清单 → ' + manifestPath)

  // D-8 台账变换就绪（此时队列必须已全部落盘——顺序契约的机器可核验点）
  const allQueuesOnDisk = result.queues.every((q) => existsSync(q.path))
  push('D-8', '台账变换就绪（删 tasks / schemaVersion=9 / migrations+={8,9}）；此时 ' + result.queues.length + ' 份 queue.json 均已落盘=' + allQueuesOnDisk)
  if (!allQueuesOnDisk) {
    log('❌ 顺序契约失败：D-7 声称已写队列，但磁盘上仍有缺失——**未改台账**（台账保持 v8，可安全重跑）')
    return { code: 1, mode, report: result.report, events, lines, queuePaths: result.queues.map((q) => q.path), backupPath, manifestPath, unmigratedPath, queueFilesWrittenBeforeLedger: false }
  }

  // D-9 原子替换台账（**后**）
  const ledgerText = compact ? JSON.stringify(result.ledger) : JSON.stringify(result.ledger, null, 2)
  await persist(file, ledgerText)
  push('D-9', '原子替换台账 ' + file + '（保留源格式=' + (compact ? 'compact' : 'pretty') + '）')

  log('执行顺序打点：' + events.map((e) => e.seq + ':' + e.phase).join(' → '))
  log('台账写前 sha256=' + preSha.slice(0, 12) + '…  写后 sha256=' + sha256(readFileSync(file, 'utf8')).slice(0, 12) + '…')
  log('✅ 已迁移并原子替换：' + file)
  log('   备份：' + backupPath)
  log('   清单：' + manifestPath)
  if (unmigratedPath !== undefined) log('   ⚠️ 未迁移任务隔离：' + unmigratedPath)
  const migs = Array.isArray(result.ledger.migrations) ? result.ledger.migrations : []
  log('   台账：schemaVersion=' + result.ledger.schemaVersion + '，tasks=' + ('tasks' in result.ledger ? '仍在（异常！）' : '已移除') + '，migrations 末条=' + JSON.stringify(migs[migs.length - 1]))
  log('   队列：' + result.queues.length + ' 份，共 ' + result.report.migratedTasks + ' 任务；跳过需求 ' + result.report.skipped.length + ' 个')
  log('   回滚：--rollback（从最近备份还原台账并清理本次生成的 queue.json）')

  return { code: 0, mode, report: result.report, events, lines, queuePaths: result.queues.map((q) => q.path), backupPath, manifestPath, unmigratedPath, queueFilesWrittenBeforeLedger: allQueuesOnDisk }
}

/** --verify：v9 结构检查 + 从最近备份**重放变换**与磁盘逐份比对（归一 generated_at/updated_at 与 migrations[].at）。 */
async function verifyV9(opts: RunV9Options, result: V9Result): Promise<V9RunOutcome> {
  const { file, ledger } = opts
  const lines: string[] = []
  const log = (s: string) => lines.push(s)
  const problems: string[] = []
  const events: V9OrderEvent[] = []
  let seq = 0
  const ev = (phase: string, detail: string) => { events.push({ seq: ++seq, phase, detail }) }

  log('── v8 → v9 迁移校验（--verify）──')
  log('台账：' + file)
  ev('D-1', '读台账')

  if (ledger.schemaVersion !== LEDGER_V9) problems.push('schemaVersion=' + ledger.schemaVersion + '（应为 ' + LEDGER_V9 + '，说明尚未迁移）')
  if ('tasks' in ledger) problems.push('台账仍含 tasks 键（v9 必须移除）')
  const migs = Array.isArray(ledger.migrations) ? ledger.migrations : []
  const last = migs[migs.length - 1]
  if (!last || last.from !== LEDGER_V8 || last.to !== LEDGER_V9) problems.push('migrations 末条不是 {from:8,to:9}：' + JSON.stringify(last))
  ev('V-1', 'v9 结构检查：schemaVersion/tasks/migrations 三项')

  // 独立校验磁盘上的每份 queue.json（不依赖备份）
  let checked = 0
  for (const r of Array.isArray(ledger.requirements) ? ledger.requirements : []) {
    const dir = opts.requirementDirOf(r.id)
    const p = join(dir, 'queue.json')
    if (!existsSync(p)) continue
    checked += 1
    let parsed: any
    try { parsed = JSON.parse(readFileSync(p, 'utf8')) } catch (e) { problems.push('队列 JSON 解析失败：' + p + '（' + (e as Error).message + '）'); continue }
    if (parsed.requirement_id !== r.id) problems.push('queue.requirement_id(' + parsed.requirement_id + ') ≠ 目录需求(' + r.id + ')：' + p)
    if (basename(dir) !== r.id) problems.push('队列所在目录名(' + basename(dir) + ') ≠ requirement_id(' + r.id + ')')
    const v = v9Defaults.validate(parsed)
    if (!v.passed) problems.push('队列未过 V-1~V-6：' + p + ' → ' + v.issues.slice(0, 3).map((i) => i.rule + ':' + i.message).join(' | '))
    try {
      const residue = readdirSync(dir).filter((n) => /^\..*\.tmp$/.test(n))
      if (residue.length > 0) problems.push('临时文件残留：' + join(dir, residue[0]))
    } catch { /* 目录不可读已由上面的 existsSync 覆盖 */ }
  }
  log('磁盘队列校验：扫描到 ' + checked + ' 份 queue.json（V-1~V-6 + requirement_id 归属 + 无 .tmp 残留）')
  ev('V-2', '磁盘 queue.json 校验 ' + checked + ' 份')

  // 从最近备份重放变换，与磁盘逐份比对
  const backups = listBackups(file)
  if (backups.length === 0) {
    log('⚠️ 未找到备份（<ledger>.backup-*），跳过"从备份重放比对"；本项为 warning，不影响退出码')
  } else {
    const backup = backups[0]!
    const raw = JSON.parse(readFileSync(backup, 'utf8'))
    const replay = (opts.transform ?? migrateV8toV9)(raw, 0, { requirementDirOf: opts.requirementDirOf, dirExists: opts.dirExists })
    const normQueue = (f: any) => { const c = structuredClone(f); delete c.generated_at; delete c.updated_at; return JSON.stringify(c, null, 2) }
    let diffs = 0
    for (const q of replay.queues) {
      if (!existsSync(q.path)) { problems.push('缺队列文件（备份中该需求有任务）：' + q.path); continue }
      const onDisk = JSON.parse(readFileSync(q.path, 'utf8'))
      if (normQueue(onDisk) !== normQueue(q.file)) { diffs += 1; problems.push('队列与备份重放不一致（若为迁移后运行期改动可复核后忽略）：' + q.path) }
    }
    const normLedger = (l: any) => { const c = structuredClone(l); if (Array.isArray(c.migrations)) for (const m of c.migrations) delete m.at; return JSON.stringify(c, null, 2) }
    if (normLedger(replay.ledger) !== normLedger(ledger)) problems.push('台账与备份重放不一致（除 migrations[].at 外）')
    log('备份重放比对：' + backup + ' → ' + replay.queues.length + ' 份队列，差异 ' + diffs + ' 份')
    ev('V-3', '从备份重放比对 ' + replay.queues.length + ' 份队列 + 台账')
  }

  const unmigratedSidecars = listSiblings(file, '.unmigrated-')
  if (unmigratedSidecars.length > 0) log('⚠️ 存在未迁移任务隔离文件（需人工裁决）：' + unmigratedSidecars.join(', '))

  if (problems.length > 0) {
    log('❌ 校验未通过（' + problems.length + ' 项）：')
    for (const p of problems.slice(0, 30)) log('  - ' + p)
    return { code: 1, mode: 'verify', report: result.report, events, lines, queuePaths: [], queueFilesWrittenBeforeLedger: false }
  }
  log('✅ 校验通过：台账为 v9（无 tasks、migrations 末条 {8,9}），磁盘队列数与备份重放一致，退出码 0')
  return { code: 0, mode: 'verify', report: result.report, events, lines, queuePaths: [], queueFilesWrittenBeforeLedger: false }
}

export interface RollbackOutcome {
  code: number
  lines: string[]
  backupPath?: string
  restored: boolean
  removed: string[]
  kept: string[]
}

/**
 * --rollback：从最近 `<ledger>.backup-*` 还原台账，并按迁移清单清理**本次生成**的 queue.json。
 * 归属判定用清单里的 sha256：内容已被迁移后写路径改过的文件**保留不删**（避免抹掉新数据），只在报告里点名。
 */
export async function rollbackV9(opts: { file: string; now: number; persist?: (p: string, c: string) => Promise<void>; isServiceRunning?: (ledgerFile: string) => boolean; force?: boolean }): Promise<RollbackOutcome> {
  const file = resolve(opts.file)
  const persist = opts.persist ?? persistAtomic
  const lines: string[] = []
  const removed: string[] = []
  const kept: string[] = []

  // 与 --apply 同一条前置纪律：服务在跑时回滚同样会被内存态覆盖
  if (opts.force !== true && (opts.isServiceRunning ?? defaultServiceRunningCheck)(file)) {
    lines.push('❌ 检测到服务正在运行（<ledgerDir>/state/server.pid 存活）——拒绝执行 --rollback。请先停机，确认可控时用 --force。')
    return { code: 1, lines, restored: false, removed, kept }
  }

  const backups = listBackups(file)
  if (backups.length === 0) {
    lines.push('❌ 未找到备份（' + file + '.backup-*），无法回滚')
    return { code: 1, lines, restored: false, removed, kept }
  }
  const backup = backups[0]!
  lines.push('── v8 → v9 回滚（--rollback）──')
  lines.push('台账：' + file)
  lines.push('备份：' + backup)

  let raw: any
  let backupText: string
  try { backupText = readFileSync(backup, 'utf8'); raw = JSON.parse(backupText) } catch (e) {
    lines.push('❌ 备份不是合法 JSON，拒绝回滚：' + (e as Error).message)
    return { code: 1, lines, backupPath: backup, restored: false, removed, kept }
  }
  if (!Array.isArray(raw.tasks) || typeof raw.schemaVersion !== 'number' || raw.schemaVersion >= LEDGER_V9) {
    lines.push('❌ 备份不是"迁移前 v8"状态（schemaVersion=' + raw.schemaVersion + '，tasks=' + (Array.isArray(raw.tasks) ? raw.tasks.length : 'N/A') + '），拒绝回滚')
    return { code: 1, lines, backupPath: backup, restored: false, removed, kept }
  }

  // 迁移清单 → 精确清理本次生成的队列
  const manifests = listManifests(file).filter((m) => {
    try { return JSON.parse(readFileSync(m, 'utf8')).backup === backup } catch { return false }
  })
  const manifest = manifests[0]
  if (manifest === undefined) {
    lines.push('⚠️ 未找到与本次备份匹配的迁移清单（<ledger>.migrate-manifest-*）——跳过 queue.json 清理，仅还原台账')
  } else {
    const meta = JSON.parse(readFileSync(manifest, 'utf8'))
    for (const q of Array.isArray(meta.queues) ? meta.queues : []) {
      if (!existsSync(q.path)) continue
      const cur = sha256(readFileSync(q.path, 'utf8'))
      if (cur === q.sha256) { unlinkSync(q.path); removed.push(q.path) }
      else { kept.push(q.path + '（迁移后被改动，保留）') }
    }
    for (const extra of [meta.unmigrated]) {
      if (typeof extra === 'string' && existsSync(extra)) { unlinkSync(extra); removed.push(extra) }
    }
    unlinkSync(manifest)
    removed.push(manifest)
    lines.push('清理清单：' + manifest)
  }

  // R-1 还原台账（**逐字节**还原备份原文，不做任何重排——回滚必须是格式无损的）
  await persist(file, backupText)
  const after = JSON.parse(readFileSync(file, 'utf8'))
  const okRestore = after.schemaVersion === LEDGER_V8 && Array.isArray(after.tasks)
  const byteExact = readFileSync(file, 'utf8') === backupText
  lines.push('✅ 台账已还原：schemaVersion=' + after.schemaVersion + '，tasks=' + (Array.isArray(after.tasks) ? after.tasks.length : 'N/A') + ' 条，逐字节等于备份=' + byteExact)
  lines.push('   删除本次生成的队列文件 ' + removed.length + ' 个；保留 ' + kept.length + ' 个')
  for (const k of kept) lines.push('   ⚠️ 保留 ' + k)
  lines.push(okRestore ? '✅ 回滚完成（--verify 应报 schemaVersion=8 未迁移）' : '❌ 还原后台账结构异常，请人工检查')
  return { code: okRestore ? 0 : 1, lines, backupPath: backup, restored: okRestore, removed, kept }
}

function readLedger(file: string): any {
  if (!existsSync(file)) { console.error('❌ 台账不存在：' + file); process.exit(2) }
  const raw = readFileSync(file, 'utf8')
  try { return JSON.parse(raw) } catch (e) { console.error('❌ 台账不是合法 JSON：' + (e as Error).message); process.exit(2) }
}

function counts(ledger: any): string {
  const reqs = ledger.requirements ?? []; const tasks = ledger.tasks ?? []
  return 'schemaVersion=' + ledger.schemaVersion + ' revision=' + ledger.revision
    + ' requirements=' + reqs.length + ' tasks=' + tasks.length + ' triages=' + (ledger.triages ?? []).length
}

/**
 * 历史链 v4→v7 的 CLI 分支（原样保留）。v8 台账不再走这里；`schemaVersion < 8` 时回落到此。
 */
function legacyV7Main(file: string, mode: 'dry-run' | 'apply' | 'verify'): void {
  const ledger = readLedger(file)

  if (mode === 'verify') {
    const reqs: any[] = ledger.requirements ?? []; const tasks: any[] = ledger.tasks ?? []
    const problems: string[] = []
    if (ledger.schemaVersion !== V7) problems.push('schemaVersion=' + ledger.schemaVersion + '（应为 ' + V7 + '）')
    if (reqs.some((r: any) => !Array.isArray(r.statusHistory) || r.statusHistory.length === 0)) problems.push('存在缺少 statusHistory 的需求')
    if (reqs.some((r: any) => 'projectId' in r || 'parentId' in r)) problems.push('仍有 projectId/parentId 未删')
    if (reqs.some((r: any) => r.category === undefined || r.category === null)) problems.push('存在缺少 category 的需求')
    const badSrc = reqs.some((r: any) => [...(r.verification?.sheet?.items ?? []), ...((r.verification?.sheetHistory ?? []).flatMap((s: any) => s.items ?? []))].some((i: any) => typeof i.source === 'string'))
    if (badSrc) problems.push('仍有字符串型 sheet.items[].source')
    if (tasks.some((t: any) => t.scope === undefined)) problems.push('存在缺少 scope 的任务')
    if (reqs.some((r: any) => r.status === 'planning' || (r.statusHistory ?? []).some((e: any) => e.status === 'planning'))) problems.push('仍有 planning 状态名未归一为 design')
    if (reqs.some((r: any) => (r.artifacts ?? []).some((a: any) => a.stage === 'planning'))) problems.push('仍有 artifacts[].stage=planning 未归一为 design')
    console.log('── --verify ──\n' + counts(ledger))
    if (problems.length > 0) { console.error('❌ 未达 v5：\n  - ' + problems.join('\n  - ')); process.exit(1) }
    console.log('✅ 已是 v7 且结构自洽（需求/任务计数见上）')
    return
  }

  if (ledger.schemaVersion === V7) {
    console.log('── 无需迁移 ──\n' + counts(ledger) + '\n✅ 已是 v7，--apply 幂等无操作')
    return
  }

  const now = Date.now()
  const before = structuredClone(ledger)
  const { next, changes } = migrate(ledger, now)
  const paths = diffPaths(before, next)
  const { ok, bad } = checkWhitelist(paths)

  console.log('── 迁移报告（' + mode + '）──')
  console.log('before: ' + counts(before))
  console.log('after : ' + counts(next))
  console.log('差异路径 ' + paths.length + ' 条；白名单内 ' + ok.length + ' 条，**白名单外 ' + bad.length + ' 条**')
  console.log('逐项变更计数：')
  const keys = Object.keys(changes)
  if (keys.length === 0) console.log('  （无实际数据变更——本台账已满足所有 v5 结构要求）')
  for (const k of keys) console.log('  ' + k + ': ' + changes[k]!.count + (changes[k]!.detail.length > 0 ? '  例：' + changes[k]!.detail.join(' | ') : ''))
  if (bad.length > 0) {
    console.error('❌ 出现白名单外差异，**未落盘**：\n  - ' + bad.slice(0, 20).join('\n  - '))
    process.exit(1)
  }
  if (mode === 'dry-run') { console.log('✅ 白名单外差异 0 条 —— 可执行 --apply'); return }

  // --apply：备份 → 原子替换 → 复核
  const bak = file + '.bak-req47939a-' + Math.floor(now / 1000)
  copyFileSync(file, bak)
  const tmp = file + '.tmp-req47939a-' + process.pid
  try {
    writeFileSync(tmp, JSON.stringify(next, null, 2), 'utf8')
    renameSync(tmp, file)
  } catch (e) {
    try { unlinkSync(tmp) } catch { /* 清理失败不掩盖主错误 */ }
    console.error('❌ 写入失败（原文件未被替换）：' + (e as Error).message + '\n备份仍在：' + bak)
    process.exit(1)
  }
  const after = readLedger(file)
  console.log('✅ 已迁移并原子替换：' + file)
  console.log('   备份：' + bak)
  console.log('   after: ' + counts(after))
  console.log('   回滚：mv "' + bak + '" "' + file + '" 后重启（v5 读路径可读 v4，反之不行，故回滚须连文件一起回）')
}

const invokedDirectly = process.argv[1] !== undefined && /migrate-ledger\.(ts|mjs|js)$/.test(process.argv[1])

interface EmitPayload {
  code: number
  lines: string[]
  events: V9OrderEvent[]
  report?: V9Report
  backupPath?: string
  manifestPath?: string
  unmigratedPath?: string
  queuePaths?: string[]
  queueFilesWrittenBeforeLedger?: boolean
}

function emit(payload: EmitPayload, asJson: boolean, mode: string): void {
  if (asJson) {
    process.stdout.write(JSON.stringify({
      mode, code: payload.code, report: payload.report ?? null, events: payload.events,
      lines: payload.lines, backupPath: payload.backupPath ?? null, manifestPath: payload.manifestPath ?? null,
      unmigratedPath: payload.unmigratedPath ?? null, queuePaths: payload.queuePaths ?? [],
      queueFilesWrittenBeforeLedger: payload.queueFilesWrittenBeforeLedger ?? false,
    }, null, 2) + '\n')
    return
  }
  for (const l of payload.lines) console.log(l)
}

/**
 * 顶层 CLI：四态分发。
 * - `--rollback` 任意版本通用；`>= v9` 走 already_v9 / verify；`== v8` 走 v8→v9；`< v8` 回落历史链 v4→v7。
 * - 退出码：0 成功 / 1 白名单外差异或校验失败 / 2 参数错误。
 */
async function main(): Promise<void> {
  const argv = process.argv.slice(2)
  const valueOf = (flag: string): string | undefined => { const i = argv.indexOf(flag); return i >= 0 ? argv[i + 1] : undefined }
  const file = valueOf('--file')
  const rootArg = valueOf('--root')
  const asJson = argv.includes('--json')
  const force = argv.includes('--force')
  const mode: V9Mode = argv.includes('--rollback') ? 'rollback'
    : argv.includes('--apply') ? 'apply'
      : argv.includes('--verify') ? 'verify'
        : 'dry-run'

  if (file === undefined || file.length === 0) { console.error('❌ 必须指定 --file <ledger>\n' + USAGE); process.exitCode = 2; return }

  if (mode === 'rollback') {
    const o = await rollbackV9({ file, now: Date.now(), force })
    emit({ code: o.code, lines: o.lines, events: [], backupPath: o.backupPath }, asJson, 'rollback')
    process.exitCode = o.code
    return
  }

  const ledger = readLedger(file)
  const requirementDirOf = (root: string) => (rid: string) => join(root, 'docs', 'requirements', rid)

  if (ledger.schemaVersion >= LEDGER_V9) {
    if (mode === 'verify') {
      let root: string
      try { root = resolveWorkspaceRoot(file, rootArg) } catch (e) { console.error('❌ ' + (e as Error).message); process.exitCode = 2; return }
      const o = await runV9({ file, ledger, mode: 'verify', requirementDirOf: requirementDirOf(root), now: Date.now() })
      emit(o, asJson, 'verify')
      process.exitCode = o.code
      return
    }
    const line = 'already_v9：台账已是 schemaVersion=' + ledger.schemaVersion + '，--' + mode + ' 无操作（未重写任何文件，mtime 不变）'
    emit({ code: 0, lines: ['✅ ' + line], events: [] }, asJson, mode)
    process.exitCode = 0
    return
  }

  if (ledger.schemaVersion === LEDGER_V8) {
    let root: string
    try { root = resolveWorkspaceRoot(file, rootArg) } catch (e) { console.error('❌ ' + (e as Error).message); process.exitCode = 2; return }
    const o = await runV9({ file, ledger, mode, requirementDirOf: requirementDirOf(root), now: Date.now(), force })
    emit(o, asJson, mode)
    process.exitCode = o.code
    return
  }

  // schemaVersion < 8：历史链 v4→v7（原样保留）
  legacyV7Main(file, mode)
}

if (invokedDirectly) {
  main().catch((e: unknown) => {
    console.error('❌ 迁移脚本异常：' + ((e as Error)?.stack ?? String(e)))
    process.exitCode = 1
  })
}
