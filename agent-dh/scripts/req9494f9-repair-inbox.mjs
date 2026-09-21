#!/usr/bin/env node
/**
 * REQ-9494f9 一次性数据修复：清掉 session event log 里那条「字符串脏 inbox 消息」。
 *
 * 背景：solve-kit 的 buildNudgeMessage 曾返回纯字符串并直接喂给 agent.followup，
 * 于是 session 的持久化事件 agent/inbox/spliced 里 inserted 落了一个字符串。
 * 后果（已实测）：① 后续催办被 inbox 去重拒绝；② session-controller 的 Host 级
 * control stream 建基线读 message.source.kind 时抛 TypeError——**所有浏览器窗口**控制流失败，
 * 且因为脏数据在持久化 event log 里，**重启不恢复**。
 *
 * 修复形态：向 <session>.v3.jsonl.zstd **追加一帧**（与 dsh-session-persistence-jsonl
 * 同参数：checksumFlag=1、独立可解压帧容器），内容是一条修正用 agent/inbox/spliced，
 * 把 next-turn 里那条坏消息移除（outcome='canceled'）。
 *
 * 安全默认：不带 --apply 只做 dry-run（不写任何字节）。写入前请先备份原文件。
 *
 * 用法：
 *   node scripts/req9494f9-repair-inbox.mjs --file <session.v3.jsonl.zstd>
 *   node scripts/req9494f9-repair-inbox.mjs --file <path> --apply
 */
import { readFileSync, appendFileSync } from 'node:fs'
import { execFileSync } from 'node:child_process'
import { zstdCompressSync, constants } from 'node:zlib'

const argv = process.argv.slice(2)
function argOf(name) {
  const i = argv.indexOf(name)
  return i >= 0 ? argv[i + 1] : undefined
}
const file = argOf('--file')
const apply = argv.includes('--apply')
if (!file) {
  console.error('用法：node scripts/req9494f9-repair-inbox.mjs --file <session.v3.jsonl.zstd> [--apply]')
  process.exit(2)
}

/**
 * 解压「可拼接帧容器」。
 *
 * 为什么不用 node:zlib：实测 createZstdDecompress（流式）只吐出**第一帧**就收工，
 * zstdDecompressSync（one-shot）遇到第二帧报 ZSTD_error_prefix_unknown——两者都吃不下
 * 「多帧拼接」这个本仓 session 日志的落盘形态（见 dsh-session-persistence-jsonl 的
 * concatenated-frame container）。zstd CLI 已验证能完整解码本文件，故此处用它。
 */
function decompressAll(file) {
  return execFileSync('zstd', ['-d', '-c', file], { maxBuffer: 1 << 30 })
}

/** 一条数据是不是合法的 inbox 消息（框架的真实要求：id 为字符串、有 source）。 */
function isBadInboxEntry(v) {
  if (v === null || typeof v !== 'object' || Array.isArray(v)) return true
  if (typeof v.id !== 'string' || v.id.length === 0) return true
  if (v.source === null || typeof v.source !== 'object') return true
  return false
}

/** 重放 agent/inbox/spliced，得到两个 pending 列表的当前值。 */
function foldInbox(lines) {
  const lists = { 'next-turn': [], 'next-step': [] }
  let maxSeq = -1
  let header = null
  for (const line of lines) {
    if (!line.trim()) continue
    let ev
    try { ev = JSON.parse(line) } catch { throw new Error('非法 JSON 行：' + line.slice(0, 120)) }
    if (header === null) { header = ev; continue }   // 首行是 session header（无 seq）
    if (!Number.isSafeInteger(ev.seq)) throw new Error('事件缺 seq：' + line.slice(0, 120))
    maxSeq = Math.max(maxSeq, ev.seq)
    if (ev.type !== 'agent/inbox/spliced') continue
    const d = ev.data || {}
    const list = lists[d.target]
    if (list === undefined) throw new Error('未知 inbox target：' + String(d.target))
    const removed = d.removedCount === undefined ? 0 : d.removedCount
    const inserted = Array.isArray(d.inserted) ? d.inserted : []
    list.splice(d.start, removed, ...inserted)
  }
  return { lists, maxSeq, header }
}

const text = decompressAll(file).toString('utf8')
const lines = text.split('\n').filter(Boolean)
const { lists, maxSeq, header } = foldInbox(lines)

const badByTarget = {}
for (const target of Object.keys(lists)) {
  const bad = []
  lists[target].forEach((v, i) => { if (isBadInboxEntry(v)) bad.push(i) })
  if (bad.length > 0) badByTarget[target] = { count: lists[target].length, badIndices: bad }
}

const summary = {
  file,
  sessionId: header && header.id,
  mode: apply ? 'apply' : 'dry-run',
  lastSeq: maxSeq,
  pending: { 'next-turn': lists['next-turn'].length, 'next-step': lists['next-step'].length },
  bad: badByTarget,
}

if (Object.keys(badByTarget).length === 0) {
  console.log(JSON.stringify({ ...summary, action: '无需修复（未发现非法 inbox 条目）' }, null, 2))
  process.exit(0)
}

if (!apply) {
  console.log(JSON.stringify({ ...summary, action: 'dry-run：未写入。加 --apply 执行修复' }, null, 2))
  process.exit(0)
}

// 逐条追加修正 splice（从后往前删，避免下标位移）。
const appended = []
let seq = maxSeq
for (const target of Object.keys(badByTarget)) {
  const indices = [...badByTarget[target].badIndices].sort((a, b) => b - a)
  for (const index of indices) {
    seq += 1
    const event = {
      type: 'agent/inbox/spliced',
      seq,
      time: Date.now(),
      data: { target, start: index, removedCount: 1, inserted: [], outcome: 'canceled' },
    }
    const line = JSON.stringify(event) + '\n'
    const frame = zstdCompressSync(Buffer.from(line, 'utf8'), {
      params: { [constants.ZSTD_c_checksumFlag]: 1 },
    })
    appendFileSync(file, frame)
    appended.push({ target, start: index, seq })
  }
}

// 回读校验：重新解压并折叠，坏条目必须清零。
const after = foldInbox(decompressAll(file).toString('utf8').split('\n').filter(Boolean))
const residual = {}
for (const target of Object.keys(after.lists)) {
  const bad = []
  after.lists[target].forEach((v, i) => { if (isBadInboxEntry(v)) bad.push(i) })
  if (bad.length > 0) residual[target] = bad
}

console.log(JSON.stringify({ ...summary, appended, verify: { residualBad: residual, lastSeq: after.maxSeq } }, null, 2))
process.exit(Object.keys(residual).length === 0 ? 0 : 1)
