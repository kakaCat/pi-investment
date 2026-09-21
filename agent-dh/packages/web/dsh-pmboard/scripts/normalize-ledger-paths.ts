/**
 * 台账产物路径归一脚本（REQ-b63a7d t5）。
 *
 * 背景：`reqboard_task_report` 此前把 files_changed 原样上浮，台账里堆了非工作区相对口径的
 * 产物/文档路径（实测 142 条，四形态）。t2 已从**写入侧**堵住来源，t3/t4 让**读取侧**容忍
 * 存量；本脚本负责把存量数据本身也收敛成统一口径（数据卫生）。
 *
 * ⚠️ 运行时必须停服：JsonLedgerRepository 把整份台账缓存在内存（private ledger），
 * 运行中改文件会在下一次 mutate 时被内存副本覆盖（静默丢失）。故 apply 只能在实例停止的
 * 窗口里做（脚本自身也会检测并拒绝：--apply 前要求文件在最近 N 秒内没有变动）。
 *
 * 用法：
 *   npx tsx scripts/normalize-ledger-paths.ts --file <ledger.json>            # 默认 dry-run
 *   npx tsx scripts/normalize-ledger-paths.ts --file <ledger.json> --apply
 *   npx tsx scripts/normalize-ledger-paths.ts --file <ledger.json> --verify
 */
import { copyFileSync, readFileSync, statSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { normalizeArtifactPath } from '../src/domain/artifact/ArtifactPath.js'

interface Change { where: string; from: string; to: string; action: 'normalized' | 'dropped' | 'deduped' }

const args = process.argv.slice(2)
const fileArg = args.indexOf('--file')
const file = fileArg >= 0 ? args[fileArg + 1] : ''
const apply = args.includes('--apply')
const verifyOnly = args.includes('--verify')
if (!file) {
  console.error('用法：npx tsx scripts/normalize-ledger-paths.ts --file <ledger.json> [--apply|--verify]')
  process.exit(2)
}

// 工作区根 = 台账文件的**祖父目录**（<workspace>/.dsh-data/dsh-reqboard.json）。
// 不能用 process.cwd()：脚本在包目录下跑，会把 packages/pages/dsh-pmboard 当工作区根，
// 从而把 <workspace>/packages/... 错剥成 src/...（首次 dry-run 实测踩到）。
// 可用 --root 显式覆盖。
const rootArg = args.indexOf('--root')
const workspaceRoot = rootArg >= 0 ? resolve(args[rootArg + 1]!) : resolve(dirname(resolve(file)), '..')
const ledger = JSON.parse(readFileSync(file, 'utf8')) as {
  requirements?: Array<Record<string, any>>
}

/** 单条路径归一：返回 [新值 | undefined(丢弃), 动作]。 */
function norm(raw: unknown): [string | undefined, Change['action'] | 'keep'] {
  if (typeof raw !== 'string' || raw.length === 0) return [undefined, 'keep']
  const r = normalizeArtifactPath(raw, workspaceRoot)
  if (r.form === 'pseudo' || r.path.length === 0) return [undefined, 'dropped']
  if (r.form === 'outside' && r.path.startsWith('/')) return [undefined, 'dropped']
  if (r.path !== raw) return [r.path, 'normalized']
  return [raw, 'keep']
}

const changes: Change[] = []
let scanned = 0

/** --verify：仅扫描会被文件接口判 403 的写法。 */
function forbidden(raw: unknown): boolean {
  if (typeof raw !== 'string' || raw.length === 0) return false
  if (raw.includes(String.fromCharCode(92)) || raw.split('/').some(s => s === '..')) return true
  return raw.startsWith('/') && normalizeArtifactPath(raw, workspaceRoot).form !== 'workspace'
}

if (verifyOnly) {
  const bad: string[] = []
  for (const req of ledger.requirements ?? []) {
    const scan = (v: unknown, where: string): void => { if (forbidden(v)) bad.push(where + ' -> ' + String(v)) }
    for (const a of (req.artifacts ?? []) as Array<Record<string, any>>) scan(a.path, req.id + '.artifacts(' + String(a.kind) + ')')
    for (const d of ((req.archive?.docs ?? []) as Array<Record<string, any>>)) scan(d.path, req.id + '.archive.docs')
    for (const m of ((req.archive?.mergedInto ?? []) as unknown[])) scan(m, req.id + '.archive.mergedInto')
    scan(req.plan?.path, req.id + '.plan.path')
    for (const [k, v] of Object.entries((req.docLinks ?? {}) as Record<string, unknown>)) {
      if (typeof v === 'string') scan(v, req.id + '.docLinks.' + k)
      if (Array.isArray(v)) for (const e of v as Array<Record<string, any>>) scan(e.path, req.id + '.docLinks.' + k + '[].path')
    }
  }
  console.log(bad.length === 0
    ? 'verify: OK —— 台账内不存在会被判 403 的路径写法'
    : 'verify: FAIL —— ' + bad.length + ' 条：\n' + bad.join('\n'))
  process.exit(bad.length === 0 ? 0 : 1)
}

for (const req of ledger.requirements ?? []) {
  const id = String(req.id ?? '?')
  const artifacts = (req.artifacts ?? []) as Array<Record<string, any>>
  const kept: Array<Record<string, any>> = []
  const seen = new Set<string>()
  for (const a of artifacts) {
    scanned += 1
    const [next, action] = norm(a.path)
    if (next === undefined) {
      changes.push({ where: id + '.artifacts(' + String(a.kind) + ')', from: String(a.path), to: '', action: 'dropped' })
      continue
    }
    if (action === 'normalized') {
      changes.push({ where: id + '.artifacts(' + String(a.kind) + ')', from: String(a.path), to: next, action })
      a.path = next
    }
    const key = String(a.kind) + '|' + String(a.path)
    if (seen.has(key)) {
      changes.push({ where: id + '.artifacts(' + String(a.kind) + ')', from: String(a.path), to: '(dedupe)', action: 'deduped' })
      continue
    }
    seen.add(key)
    kept.push(a)
  }
  if (kept.length !== artifacts.length) req.artifacts = kept
  for (const d of ((req.archive?.docs ?? []) as Array<Record<string, any>>)) {
    scanned += 1
    const [next] = norm(d.path)
    if (next === undefined) changes.push({ where: id + '.archive.docs', from: String(d.path), to: '', action: 'dropped' })
    else if (next !== d.path) { changes.push({ where: id + '.archive.docs', from: String(d.path), to: next, action: 'normalized' }); d.path = next }
  }
  const merged = (req.archive?.mergedInto ?? []) as unknown[]
  if (merged.length > 0) {
    const nextMerged: unknown[] = []
    for (const m of merged) {
      scanned += 1
      const [next] = norm(m)
      if (next === undefined) { changes.push({ where: id + '.archive.mergedInto', from: String(m), to: '', action: 'dropped' }); continue }
      if (next !== m) changes.push({ where: id + '.archive.mergedInto', from: String(m), to: next, action: 'normalized' })
      nextMerged.push(next)
    }
    if (req.archive !== undefined) req.archive.mergedInto = nextMerged
  }
  if (req.plan?.path !== undefined) {
    scanned += 1
    const [next] = norm(req.plan.path)
    if (next !== undefined && next !== req.plan.path) {
      changes.push({ where: id + '.plan.path', from: String(req.plan.path), to: next, action: 'normalized' })
      req.plan.path = next
    }
  }
}

const byAction = { normalized: 0, dropped: 0, deduped: 0 } as Record<Change['action'], number>
for (const c of changes) byAction[c.action] += 1

console.log('工作区根：' + workspaceRoot)
console.log('扫描路径：' + scanned)
console.log('需变更：' + changes.length + '（normalized=' + byAction.normalized + ', dropped=' + byAction.dropped + ', deduped=' + byAction.deduped + '）')
for (const c of changes.slice(0, 40)) console.log('  [' + c.action + '] ' + c.where + ': ' + c.from + ' -> ' + c.to)
if (changes.length > 40) console.log('  …（其余 ' + (changes.length - 40) + ' 条略）')

if (!apply) {
  console.log('dry-run：未写盘。加 --apply 落盘（须在实例停服的窗口内执行）。')
  process.exit(0)
}

// 一致性护栏：运行中的实例会缓存台账，改盘会被覆盖 → 文件刚被写过就拒绝 apply
const ageSec = (Date.now() - statSync(file).mtimeMs) / 1000
if (ageSec < 120) {
  console.error('拒绝 apply：台账文件 ' + ageSec.toFixed(1) + 's 前刚被写过——实例可能仍在运行（其内存副本会覆盖本次改动）。先在停服窗口执行。')
  process.exit(3)
}
const backup = file + '.bak-normalize-' + Date.now()
copyFileSync(file, backup)
writeFileSync(file, JSON.stringify(ledger, null, 2))
console.log('已写盘；备份：' + backup)
