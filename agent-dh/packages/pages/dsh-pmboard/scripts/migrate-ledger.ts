#!/usr/bin/env node
/**
 * 账本 v4 → v5 → v6 → v7 迁移（REQ-47939a t10 的 v4→v5 语义原样保留；REQ-a33899 t3 追加 v5→v6；
 * REQ-81aabd 追加 v6→v7：状态键 planning → design，含 requirements[].status / statusHistory[].status /
 * artifacts[].stage 三处同改——键改名而不迁移存量，等于把 6 条在制需求钉在不存在的主节点上）。
 *
 * 运行（**经 tsx**，见 design/migration.md §3.1 D-8）：
 *   node --import tsx/esm packages/pages/dsh-pmboard/scripts/migrate-ledger.ts --file <ledger> --dry-run
 *   node --import tsx/esm packages/pages/dsh-pmboard/scripts/migrate-ledger.ts --file <ledger> --apply
 *   node --import tsx/esm packages/pages/dsh-pmboard/scripts/migrate-ledger.ts --file <ledger> --verify
 *
 * 为什么必须是 .ts + tsx：C4（statusHistory 必填）的补齐要**复用运行时同一套算法**
 * （shared/protocol.ts 的 backfillRequirementHistory / backfillTaskHistory，内含从历史评论
 * 反推状态转移的 parseTransitionTarget）。纯 .mjs 只能重抄一份 → 第二套时间线语义 → 本仓吃过这个亏。
 *
 * 安全设计：① 迁移前自动备份；② 变更走"临时文件 + rename"原子替换；③ 逐**路径**白名单校验，
 * 出现白名单外的差异即中止且不落盘；④ 幂等（已是现行版本则 --apply 无操作）。
 */
import { copyFileSync, existsSync, readFileSync, renameSync, writeFileSync, unlinkSync } from 'node:fs'
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
const USAGE = `用法：--file <ledger> [--dry-run|--apply|--verify]（默认 --dry-run）`

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

function main(): void {
  const argv = process.argv.slice(2)
  const fileArg = argv.indexOf('--file')
  const file = fileArg >= 0 ? argv[fileArg + 1] : undefined
  const mode = argv.includes('--apply') ? 'apply' : (argv.includes('--verify') ? 'verify' : 'dry-run')
  if (file === undefined || file.length === 0) { console.error('❌ 必须指定 --file <ledger>\n' + USAGE); process.exit(2) }
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
if (invokedDirectly) main()
