#!/usr/bin/env node
/**
 * 全仓工具输出契约审计（只读）——把 REQ-2e9473 踩了三次的那类 bug 一次扫清。
 *
 * 背景：DSH 工具 output.schema 是 additionalProperties:false。返回体出现未声明字段会被
 * 绑定层**拒收**——值算出来了、副作用发生了，调用方却只看到一条 invalid output 错误。
 * 2026-09-17 在 dsh-pmboard 一处就抓到 6 个工具中招（ask_confirm / move / decompose /
 * task_move / confirm_artifact / verify_submit），且第一个静态扫描器还漏了"条件展开字段"
 * \`...(cond ? { k } : {})\` —— 说明这类缺陷靠人眼和"只测成功路径"都挡不住。
 *
 * 适用范围（重要，别误读成全仓覆盖）：本审计只对 **additionalProperties: false** 的工具有效——
 * 只有严格 schema 才会被绑定层拒收。实测本仓两类形态：
 *   · 严格（inline defineTool + additionalProperties:false）：约 29 个工具，本审计覆盖；
 *   · 开放（BaseTool 三段式，prompt.ts 里 additionalProperties:true）：109 个工具，
 *     多返回字段不会报错（代价是 schema 漂移静默无提示），需要另一套"漂移报告"而非本审计。
 *
 * 用法：node scripts/audit-tool-output-contract.mjs [--json]
 * 退出码：0=未发现可疑项；1=发现可疑项（可用于 CI/门禁）。
 *
 * 口径（与 packages/web/dsh-pmboard/tests/output-contract.test.ts 同源）：
 *   · 只认"响应型"字面量：键集不完全属于 {requirements, tasks}（那是 store.mutate 的变更集）
 *   · 跳过回调实参区（.map/.filter/.forEach/.catch/.then/store.mutate）内的 return
 *   · 计入条件展开 \`...(cond ? { k } : {})\` 里的字段
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'

const ROOTS = ['packages']
const MUTATOR_KEYS = new Set(['requirements', 'tasks'])

function walk(dir) {
  const out = []
  let entries = []
  try { entries = readdirSync(dir, { withFileTypes: true }) } catch { return out }
  for (const e of entries) {
    const p = join(dir, e.name)
    if (e.isDirectory()) {
      if (e.name === 'node_modules' || e.name === 'dist' || e.name === 'lib') continue
      out.push(...walk(p))
    } else if (e.name.endsWith('.ts') && !e.name.endsWith('.d.ts')) out.push(p)
  }
  return out
}

function matchPair(src, start, open, close) {
  let depth = 0, i = start
  while (i < src.length) {
    const c = src[i]
    if (c === '/' && src[i + 1] === '/') { while (i < src.length && src[i] !== '\n') i++; continue }
    if (c === '/' && src[i + 1] === '*') { i += 2; while (i < src.length && !(src[i] === '*' && src[i + 1] === '/')) i++; i += 2; continue }
    if (c === "'" || c === '"' || c === '`') { const q = c; i++; while (i < src.length && src[i] !== q) { if (src[i] === '\\') i++; i++ } i++; continue }
    if (c === open) depth++
    else if (c === close) { depth--; if (depth === 0) return i }
    i++
  }
  return src.length
}

/** 提取对象字面量体（不含花括号）在 depth 0 上的键名（只在键位识别，避开三元 ? x : y）。 */
function topLevelKeys(body) {
  const keys = []
  let depth = 0, expectKey = true, i = 0
  while (i < body.length) {
    const c = body[i]
    if (c === '/' && body[i + 1] === '/') { while (i < body.length && body[i] !== '\n') i++; continue }
    if (c === '/' && body[i + 1] === '*') { i += 2; while (i < body.length && !(body[i] === '*' && body[i + 1] === '/')) i++; i += 2; continue }
    if (c === "'" || c === '"' || c === '`') { const q = c; i++; while (i < body.length && body[i] !== q) { if (body[i] === '\\') i++; i++ } i++; expectKey = false; continue }
    if (c === '{' || c === '(' || c === '[') { depth++; expectKey = false; i++; continue }
    if (c === '}' || c === ')' || c === ']') { depth--; i++; continue }
    if (depth === 0) {
      if (c === ',') { expectKey = true; i++; continue }
      if (expectKey) {
        const m = /^([A-Za-z_$][\w$]*)\s*:/.exec(body.slice(i))
        if (m) { keys.push(m[1]); expectKey = false; i += m[0].length; continue }
        if (body.startsWith('...', i)) {
          let j = i + 3
          while (j < body.length && /\s/.test(body[j])) j++
          if (body[j] === '(') {
            const close = matchPair(body, j, '(', ')')
            const re = /\{([^{}]*)\}/g
            let mm
            while ((mm = re.exec(body.slice(j + 1, close))) !== null) keys.push(...topLevelKeys(mm[1]))
            i = close + 1
          } else i += 3
          expectKey = false; continue
        }
        if (/\s/.test(c)) { i++; continue }
        expectKey = false; i++; continue
      }
    }
    i++
  }
  return keys
}

function callbackSpans(src) {
  const spans = []
  const re = /(?:\.map|\.filter|\.forEach|\.catch|\.then|store\.mutate)\s*\(/g
  let m
  while ((m = re.exec(src)) !== null) {
    const open = m.index + m[0].length - 1
    spans.push([open, matchPair(src, open, '(', ')')])
  }
  return spans
}

function responseKeys(region) {
  const keys = [], spans = callbackSpans(region)
  const inCb = (at) => spans.some(([s, e]) => at > s && at < e)
  let i = 0
  while (i < region.length) {
    const prev = region[i - 1] ?? ''
    if (region.startsWith('return', i) && !/[A-Za-z0-9_$]/.test(prev) && !inCb(i)) {
      let j = i + 6
      while (j < region.length && /\s/.test(region[j])) j++
      if (region[j] === '{') {
        const end = matchPair(region, j, '{', '}')
        const lit = topLevelKeys(region.slice(j + 1, end))
        if (lit.length > 0 && !lit.every((k) => MUTATOR_KEYS.has(k))) keys.push(...lit)
        i = end + 1; continue
      }
    }
    i++
  }
  return keys
}

/** 取 output.schema.properties 的键集（工具注册对象内的第一处）。 */
function declaredKeys(region) {
  const oi = region.indexOf('output:')
  if (oi < 0) return null
  const pi = region.indexOf('properties:', oi)
  if (pi < 0) return null
  const brace = region.indexOf('{', pi)
  const end = matchPair(region, brace, '{', '}')
  return new Set(topLevelKeys(region.slice(brace + 1, end)))
}

const files = ROOTS.flatMap((r) => walk(r))
const findings = []
const scanned = []
let toolCount = 0

for (const f of files) {
  let src
  try { src = readFileSync(f, 'utf8') } catch { continue }
  if (!src.includes('defineTool(')) continue
  const idx = []
  const re = /defineTool\s*\(/g
  let m
  while ((m = re.exec(src)) !== null) idx.push(m.index)
  for (let k = 0; k < idx.length; k++) {
    const region = src.slice(idx[k], k + 1 < idx.length ? idx[k + 1] : src.length)
    const nameM = /name:\s*'([a-z0-9_]+)'/.exec(region)
    if (!nameM) continue
    toolCount++
    scanned.push({ file: f, tool: nameM[1] })
    const declared = declaredKeys(region)
    if (declared === null) continue // 非标准结构（如委托给 BaseTool），跳过
    const missing = [...new Set(responseKeys(region))].filter((x) => !declared.has(x))
    if (missing.length > 0) findings.push({ file: f, tool: nameM[1], missing })
  }
}

if (process.argv.includes('--list')) {
  // 自证覆盖：列出每个被扫描到的工具（防止"扫了 0 个也算通过"）
  for (const t of scanned) console.log(t.file + ' :: ' + t.tool)
  console.log('--- 共 ' + scanned.length + ' 个工具')
  process.exit(0)
}

if (process.argv.includes('--json')) {
  console.log(JSON.stringify({ toolCount, findings }, null, 2))
} else {
  console.log('扫描工具数：' + toolCount + '（' + files.length + ' 个源文件）')
  if (findings.length === 0) console.log('✅ 未发现"返回键未在 output.schema 声明"的可疑项')
  else {
    console.log('❌ 发现 ' + findings.length + ' 个可疑工具：')
    for (const x of findings) console.log('  - ' + x.file + ' :: ' + x.tool + ' → ' + x.missing.join(', '))
  }
}
process.exit(findings.length === 0 ? 0 : 1)
