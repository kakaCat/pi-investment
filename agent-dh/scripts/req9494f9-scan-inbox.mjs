#!/usr/bin/env node
/**
 * REQ-9494f9 全量 inbox 投影体检（AC-4 / AC-6 的**正确**判据）。
 *
 * 为什么要另写一个扫描器，而不是 `zstd -d | grep 'inserted":\["'`：
 *   session event log 是**追加式**帧容器——修复帧（outbox 里的 cancel splice）只把坏条目从
 *   **折叠投影**里取消，绝不会抹掉历史字节。因此 raw grep 会永远命中那条早已被取消的旧帧
 *   （本实例：seq=1471 的原始脏 splice）。plan.md §5 写的「全量扫描 hits=0」在这个修复方式下
 *   **不可能成立**，除非改写历史/裁剪日志——而那被需求边界明确禁止。
 *   运行时真正读的是折叠投影（session-controller 建基线就是重放 agent/inbox/spliced），
 *   所以正确的判据是：**折叠后投影里不得再有字符串条目**。
 *
 * 用法：node scripts/req9494f9-scan-inbox.mjs [--sessions <dir>] [--verbose]
 * 退出码：0=投影干净；1=仍有非法条目；2=用法/IO 错误。
 */
import { execFileSync } from 'node:child_process'
import { readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'

const argv = process.argv.slice(2)
const argOf = (n) => { const i = argv.indexOf(n); return i >= 0 ? argv[i + 1] : undefined }
const verbose = argv.includes('--verbose')
const sessionsDir = argOf('--sessions') ?? join(process.cwd(), '.dsh-data/sessions')

/** 广度优先找出所有 session.v3.jsonl.zstd */
function findLogs(dir) {
  const out = []
  const walk = (d) => {
    let entries
    try { entries = readdirSync(d, { withFileTypes: true }) } catch { return }
    for (const e of entries) {
      const p = join(d, e.name)
      if (e.isDirectory()) walk(p)
      else if (e.isFile() && e.name === 'session.v3.jsonl.zstd') out.push(p)
    }
  }
  walk(dir)
  return out.sort()
}

function fold(file) {
  const text = execFileSync('zstd', ['-d', '-c', file], { maxBuffer: 1 << 30 }).toString('utf8')
  const lists = { 'next-turn': [], 'next-step': [] }
  let header = null
  let maxSeq = -1
  let rawStringFrames = 0
  for (const line of text.split('\n')) {
    if (!line.trim()) continue
    const ev = JSON.parse(line)
    if (header === null) { header = ev; continue }
    if (Number.isSafeInteger(ev.seq)) maxSeq = Math.max(maxSeq, ev.seq)
    if (ev.type !== 'agent/inbox/spliced') continue
    const d = ev.data || {}
    if (Array.isArray(d.inserted) && d.inserted.some((x) => typeof x === 'string')) rawStringFrames += 1
    const list = lists[d.target]
    if (list === undefined) continue
    const removed = d.removedCount === undefined ? 0 : d.removedCount
    list.splice(d.start, removed, ...(Array.isArray(d.inserted) ? d.inserted : []))
  }
  let foldedStrings = 0
  for (const t of Object.keys(lists)) for (const v of lists[t]) if (typeof v === 'string') foldedStrings += 1
  return { id: header && header.id, maxSeq, foldedStrings, rawStringFrames }
}

const logs = findLogs(sessionsDir)
const bad = []
let rawResidual = 0
for (const f of logs) {
  let r
  try { r = fold(f) } catch (e) { bad.push({ file: f, error: String(e && e.message ? e.message : e) }); continue }
  if (r.rawStringFrames > 0) rawResidual += r.rawStringFrames
  if (r.foldedStrings > 0) bad.push({ file: f, sessionId: r.id, maxSeq: r.maxSeq, foldedStrings: r.foldedStrings })
  if (verbose) console.log(`scanned: ${r.id ?? f} foldedStrings=${r.foldedStrings} rawStringFrames=${r.rawStringFrames}`)
}

const summary = {
  sessionsDir,
  scanned: logs.length,
  sessionsWithFoldedStringEntries: bad.filter((b) => b.foldedStrings).length,
  bad: bad.filter((b) => b.foldedStrings),
  readErrors: bad.filter((b) => b.error),
  note: 'rawStringFramesStillOnDisk 是**追加式日志的历史字节**（修复帧只取消投影，不抹字节），不是运行时故障；判据看 sessionsWithFoldedStringEntries。',
  rawStringFramesStillOnDisk: rawResidual,
}
console.log(JSON.stringify(summary, null, 2))
process.exit(summary.sessionsWithFoldedStringEntries === 0 && summary.readErrors.length === 0 ? 0 : 1)
