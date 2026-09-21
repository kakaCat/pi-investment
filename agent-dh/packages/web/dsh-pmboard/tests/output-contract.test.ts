/**
 * 输出契约回归（REQ-2e9473 补充；2026-09-17 加固）。
 *
 * 背景：DSH 工具 output.schema 是 additionalProperties:false——返回体出现未声明字段会被
 * 绑定层**拒收**（值算出来了、副作用发生了，调用方却只看到一条 invalid output 错误）。
 * 本轮实测已踩三次：accept_sheet 的 archived/status、archive_submit 的 unlisted_files/warning、
 * ask_confirm 的 requirement_id（后者让"用户已确认推进"变成一条错误）。
 *
 * 两道防线：
 *   ① 动态：对关键工具的**成功路径**直调 execute，断言"返回键 ⊆ 声明键"。
 *   ② 静态：扫描 agent-tools.ts 里每个工具工厂体的**所有** `return {...}` 顶层键，
 *      断言全部已声明——穷尽所有分支，不依赖测试是否跑到那条路径。
 * 第 ② 道是根治手段：① 只能覆盖测到的路径，漏掉的分支就是下次的事故。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync, readFileSync, readdirSync, existsSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { JsonLedgerRepository } from '../src/adapters/JsonLedgerRepository.js'
import { FileDocRepository } from '../src/adapters/FileDocRepository.js'
import { SystemClock } from '../src/adapters/SystemClock.js'
import { RandomIdFactory } from '../src/adapters/RandomIdFactory.js'
import { SessionProbeAdapter } from '../src/adapters/SessionProbeAdapter.js'
import { UserQuestionsAdapter } from '../src/adapters/UserQuestionsAdapter.js'
import * as toolModules from '../src/tools/index.js'
import { defineSubmitTool, defineAskConfirmTool } from '../src/tools/index.js'
import type { RequirementRecord } from '../src/shared/protocol.js'

const W = 'session-oc-001'
let root: string
let store: JsonLedgerRepository
beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), 'pmboard-outcontract-'))
  store = new JsonLedgerRepository({ file: join(root, 'dsh-reqboard.json') })
})
afterEach(() => { rmSync(root, { recursive: true, force: true }) })

const REQ = 'REQ-0c0001'
async function seed(status: string, extra: Record<string, unknown> = {}): Promise<void> {
  const r = {
    id: REQ, title: '输出契约', description: '', status, category: 'feature', blocked: false,
    sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' }, statusHistory: [],
    ...extra,
  } as unknown as RequirementRecord
  await store.mutate('seed', (l) => { l.requirements.push(r); return { requirements: [r] } })
}
/** 真适配器构造 UseCaseDeps（t8 起工具壳吃 application 端口，不再吃旧的 ReqboardToolDeps）。 */
const depsWith = (extra: { userQuestions?: unknown } = {}) =>
  ({
    repo: store,
    docs: new FileDocRepository({ workspaceRoot: root }),
    clock: new SystemClock(),
    ids: new RandomIdFactory(),
    session: new SessionProbeAdapter({}),
    questions: new UserQuestionsAdapter(() => extra.userQuestions),
    doneThrottleMs: 0,
  }) as never
const run = (tool: any, args: unknown) => tool.execute(args, { agent: { id: W } })

/** 工具声明的输出字段集合。 */
function declaredKeys(tool: any): Set<string> {
  const props = tool?.output?.schema?.properties ?? tool?.schema?.output?.schema?.properties ?? {}
  return new Set(Object.keys(props))
}
/** 断言返回体的键都被声明（未声明 → DSH 绑定层会拒收）。 */
function assertKeysDeclared(tool: any, value: Record<string, unknown>, label: string): void {
  const declared = declaredKeys(tool)
  for (const k of Object.keys(value)) {
    expect(declared.has(k), label + ' 返回字段未在 output.schema 声明：' + k).toBe(true)
  }
}

// ── 源码扫描工具（静态防线用）───────────────────────────────────────────────

/** 找到 src 中下标 start 处 '{' 的配对 '}'（跳过字符串/模板/注释）。 */
function matchBrace(src: string, start: number): number {
  let depth = 0
  let i = start
  while (i < src.length) {
    const c = src[i]!
    if (c === '/' && src[i + 1] === '/') { while (i < src.length && src[i] !== '\n') i++; continue }
    if (c === '/' && src[i + 1] === '*') { i += 2; while (i < src.length && !(src[i] === '*' && src[i + 1] === '/')) i++; i += 2; continue }
    if (c === "'" || c === '"' || c === '`') {
      const q = c; i++
      while (i < src.length && src[i] !== q) { if (src[i] === '\\') i++; i++ }
      i++
      continue
    }
    if (c === '{') depth++
    else if (c === '}') { depth--; if (depth === 0) return i }
    i++
  }
  return src.length
}

/**
 * 提取对象字面量体（不含花括号）在 depth 0 上的键名。
 *
 * 只在「键位」识别键：开头、或顶层 `,` 之后。为什么不能只认 `ident:`——三元表达式
 * `kind: cond ? kindRaw : ''` 里的 `kindRaw :` 会被误当成键（实测踩到，见 defineConfirmArtifactTool）。
 */
function topLevelKeys(body: string): string[] {
  const keys: string[] = []
  let depth = 0
  let expectKey = true
  let i = 0
  while (i < body.length) {
    const c = body[i]!
    if (c === '/' && body[i + 1] === '/') { while (i < body.length && body[i] !== '\n') i++; continue }
    if (c === '/' && body[i + 1] === '*') { i += 2; while (i < body.length && !(body[i] === '*' && body[i + 1] === '/')) i++; i += 2; continue }
    if (c === "'" || c === '"' || c === '`') {
      const q = c; i++
      while (i < body.length && body[i] !== q) { if (body[i] === '\\') i++; i++ }
      i++
      expectKey = false
      continue
    }
    if (c === '{' || c === '(' || c === '[') { depth++; expectKey = false; i++; continue }
    if (c === '}' || c === ')' || c === ']') { depth--; i++; continue }
    if (depth === 0) {
      if (c === ',') { expectKey = true; i++; continue }
      if (expectKey) {
        const m = /^([A-Za-z_$][\w$]*)\s*:/.exec(body.slice(i))
        if (m !== null) { keys.push(m[1]!); expectKey = false; i += m[0].length; continue }
        if (body.startsWith('...', i)) {
          // 条件字段：...(cond ? { a, b } : {}) —— 展开表达式里的对象字面量键也是响应字段。
          // 不处理它会漏掉"只在某条路径上返回的键"（2026-09-17 实测：task_move 的
          // task_card / blockers / warning 正是这样漏过静态扫描，上线后绑定层拒收回执）。
          let j = i + 3
          while (j < body.length && /\s/.test(body[j]!)) j++
          if (body[j] === '(') {
            const close = matchPair(body, j, '(', ')')
            const re = /\{([^{}]*)\}/g
            let mm: RegExpExecArray | null
            while ((mm = re.exec(body.slice(j + 1, close))) !== null) keys.push(...topLevelKeys(mm[1]!))
            i = close + 1
          } else {
            i += 3
          }
          expectKey = false
          continue
        }
        if (/\s/.test(c)) { i++; continue }
        expectKey = false; i++; continue
      }
    }
    i++
  }
  return keys
}

/** 台账变更集（store.mutate 回调返回体）只由这两种键组成——据此与工具响应区分。 */
const MUTATOR_KEYS = new Set(['requirements', 'tasks'])
const isResponseLiteral = (keys: string[]): boolean =>
  keys.length > 0 && !keys.every(k => MUTATOR_KEYS.has(k))

/** 找 start 处开括号的配对闭括号（跳过字符串/模板/注释）。 */
function matchPair(src: string, start: number, open: string, close: string): number {
  let depth = 0
  let i = start
  while (i < src.length) {
    const c = src[i]!
    if (c === '/' && src[i + 1] === '/') { while (i < src.length && src[i] !== '\n') i++; continue }
    if (c === '/' && src[i + 1] === '*') { i += 2; while (i < src.length && !(src[i] === '*' && src[i + 1] === '/')) i++; i += 2; continue }
    if (c === "'" || c === '"' || c === '`') {
      const q = c; i++
      while (i < src.length && src[i] !== q) { if (src[i] === '\\') i++; i++ }
      i++
      continue
    }
    if (c === open) depth++
    else if (c === close) { depth--; if (depth === 0) return i }
    i++
  }
  return src.length
}

/**
 * 回调实参区（`.map(...)` / `.filter(...)` / `.forEach(...)` / `.catch(...)` /
 * `.then(...)` / `store.mutate(...)`）——其内部的 `return {...}` 不是工具响应
 * （如 archive_submit 里 `.map(u => { return { path, section, summary } })`）。
 */
function callbackSpans(src: string): [number, number][] {
  const spans: [number, number][] = []
  const re = /(?:\.map|\.filter|\.forEach|\.catch|\.then|\.mutate)\s*\(/g
  let m: RegExpExecArray | null
  while ((m = re.exec(src)) !== null) {
    const open = m.index + m[0].length - 1
    spans.push([open, matchPair(src, open, '(', ')')])
  }
  return spans
}

/**
 * 源码片段里所有**响应型** `return {...}` 的顶层键。
 *
 * 判定口径：**不是台账变更集的对象字面量就是工具响应**。为什么用这条：`store.mutate(...)`
 * 的回调也 return 对象（`{ requirements: [...] }` / `{ requirements, tasks }`），它们不是
 * 工具返回体，且其键集恒 ⊆ {requirements, tasks}；据此排除。反向口径（"含 success 才算响应"）
 * 已验证不成立——`reqboard_status` 的响应不带 success。
 */
function returnKeys(src: string): string[] {
  const keys: string[] = []
  const excluded = callbackSpans(src)
  const inCallback = (at: number) => excluded.some(([s, e]) => at > s && at < e)
  let i = 0
  while (i < src.length) {
    const c = src[i]!
    if (c === '/' && src[i + 1] === '/') { while (i < src.length && src[i] !== '\n') i++; continue }
    if (c === '/' && src[i + 1] === '*') { i += 2; while (i < src.length && !(src[i] === '*' && src[i + 1] === '/')) i++; i += 2; continue }
    if (c === "'" || c === '"' || c === '`') {
      const q = c; i++
      while (i < src.length && src[i] !== q) { if (src[i] === '\\') i++; i++ }
      i++
      continue
    }
    const prev = src[i - 1] ?? ''
    if (src.startsWith('return', i) && !/[A-Za-z0-9_$]/.test(prev) && !inCallback(i)) {
      let j = i + 6
      while (j < src.length && /\s/.test(src[j]!)) j++
      if (src[j] === '{') {
        const end = matchBrace(src, j)
        const lit = topLevelKeys(src.slice(j + 1, end))
        if (isResponseLiteral(lit)) keys.push(...lit) // 排除 store.mutate 回调的变更集
        i = end + 1
        continue
      }
    }
    i++
  }
  return keys
}

describe('输出契约：返回字段 ⊆ output.schema 声明', () => {
  it('archive_submit（含 unlisted_files 警告路径）', async () => {
    await seed('archived')
    const reqDir = join(root, 'docs/requirements', REQ)
    mkdirSync(reqDir, { recursive: true })
    writeFileSync(join(reqDir, 'requirement.md'), 'x')
    // REQ-2d1c74 FR-5：archive 清单内文档须真实落盘
    writeFileSync(join(reqDir, 'plan.md'), 'x')
    writeFileSync(join(reqDir, 'verification.md'), 'x')
    writeFileSync(join(reqDir, 'prototype.html'), 'x') // 未列入清单 → warning 路径
    const tool = defineSubmitTool(depsWith())
    let out: any
    try {
      out = await run(tool, {
        kind: 'archive',
        dir: 'docs/requirements/' + REQ,
        docs: [
          { kind: 'requirement', path: 'docs/requirements/' + REQ + '/requirement.md' },
          { kind: 'plan', path: 'docs/requirements/' + REQ + '/plan.md' },
          { kind: 'verification', path: 'docs/requirements/' + REQ + '/verification.md' },
        ],
        merged_into: ['docs/architecture/workflow-stages.md'],
        index_entry: '输出契约测试',
        manual_updates: [{ path: 'docs/architecture/workflow-stages.md', section: 'x', summary: 'y' }],
      })
    } catch (err) {
      rmSync(reqDir, { recursive: true, force: true })
      throw err
    }
    assertKeysDeclared(tool, out, 'archive_submit')
    rmSync(reqDir, { recursive: true, force: true })
  })

  it('verify_submit（含 sheet 摘要路径）', async () => {
    await seed('implementing')
    const tool = defineSubmitTool(depsWith())
    const out = await run(tool, { kind: 'verification', summary: '交付', evidence: ['npx vitest run 全绿'] })
    assertKeysDeclared(tool, out, 'verify_submit')
  })

  it('ask_confirm 成功路径（肯定项 → 落章 + 推进）', async () => {
    await seed('brainstorming', {
      artifacts: [{ kind: 'requirement', path: 'docs/requirements/' + REQ + '/requirement.md' }],
    })
    const uq = { ask: async () => ({ answers: [{ id: 'confirm', selected: ['好'] }] }) }
    const tool = defineAskConfirmTool(depsWith({ userQuestions: uq }))
    const out = await run(tool, { target: 'artifact', kind: 'requirement', question: '确认？', options: ['好', '不'] })
    assertKeysDeclared(tool, out, 'ask_confirm(success)')
    expect((out as any).confirmed).toBe(true)
    expect((out as any).advanced).toBe(true)
  })

  it('ask_confirm 非肯定项（不推进）', async () => {
    await seed('brainstorming', {
      artifacts: [{ kind: 'requirement', path: 'docs/requirements/' + REQ + '/requirement.md' }],
    })
    const uq = { ask: async () => ({ answers: [{ id: 'confirm', selected: ['不'] }] }) }
    const tool = defineAskConfirmTool(depsWith({ userQuestions: uq }))
    const out = await run(tool, { target: 'artifact', kind: 'requirement', question: '确认？', options: ['好', '不'] })
    assertKeysDeclared(tool, out, 'ask_confirm(declined)')
    expect((out as any).confirmed).toBe(false)
  })

  it('ask_confirm 弹框不可用（fallback=board）', async () => {
    await seed('brainstorming')
    const tool = defineAskConfirmTool(depsWith())
    const out = await run(tool, { target: 'artifact', kind: 'requirement', question: '确认？' })
    assertKeysDeclared(tool, out, 'ask_confirm(fallback)')
    expect((out as any).fallback).toBe('board')
  })
})

/** 递归列出目录下全部 .ts（扫描器覆盖全部工具文件，而非只读一个文件）。 */
function listTs(dir: string): string[] {
  if (!existsSync(dir)) return []
  const out: string[] = []
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, e.name)
    if (e.isDirectory()) out.push(...listTs(p))
    else if (e.name.endsWith('.ts')) out.push(p)
  }
  return out
}

/**
 * 工具工厂 → 其响应体所在源文件（t8 起工具壳只委托用例，响应字面量在 application 用例里）。
 * 新增工具必须在此补映射，否则该工具的契约检查会因缺映射而红。
 */
const RESPONSE_SOURCES: Record<string, string[]> = {
  Create: ['application/use-cases/CreateRequirement.ts'],
  Status: ['application/query/QueryState.ts'],
  Move: ['application/use-cases/MoveRequirement.ts'],
  Decompose: ['application/use-cases/Decompose.ts'],
  TaskMove: ['application/use-cases/MoveTask.ts'],
  TaskReport: ['application/use-cases/ReportTask.ts'],
  Submit: [
    'application/use-cases/SubmitArtifact.ts',
    'application/use-cases/SubmitVerification.ts',
    'application/use-cases/SubmitArchive.ts',
  ],
  AskConfirm: ['application/use-cases/AskConfirm.ts', 'application/use-cases/ConfirmArtifact.ts'],
  AcceptSheet: ['application/use-cases/AcceptSheet.ts'],
  // REQ-e3b6a0 t8：立项三问 pm 专有弹框（响应体在抓化用例里）
  Capture: ['application/use-cases/CaptureRequirement.ts'],
  // REQ-4842fe t10：事件链对外入口（响应体在工具文件内组装，同 TaskExecute 口径）
  Advance: ['tools/AdvanceTool/AdvanceTool.ts'],
  // REQ-f0579a t4：任务执行/状态两工具暂无独立用例层（响应体在工具文件内），映射指向自身——
  // 后续若抽出用例（t8 收敛方向），把此处改成 application/use-cases/* 路径即可。
  TaskExecute: ['tools/TaskExecuteTool/TaskExecuteTool.ts'],
  TaskStatus: ['tools/TaskStatusTool/TaskStatusTool.ts'],
}

describe('输出契约·静态扫描：每个工具的全部 return 分支键都必须已声明', () => {
  const ROOT = fileURLToPath(new URL('../src', import.meta.url))
  const toolFiles = listTs(join(ROOT, 'tools'))
  // 工具工厂：export function define<Name>Tool(deps: UseCaseDeps)
  const re = /export function define(\w+)Tool\(deps: UseCaseDeps\)/g
  const sites: { name: string; file: string; at: number }[] = []
  for (const f of toolFiles) {
    const text = readFileSync(f, 'utf8')
    let mm: RegExpExecArray | null
    while ((mm = re.exec(text)) !== null) sites.push({ name: mm[1]!, file: f, at: mm.index })
  }

  it('扫描器覆盖全部工具文件，且至少发现 9 个工具工厂（少一个即红——防退化为只覆盖部分）', () => {
    // 遍历 src/tools/**/*.ts：覆盖下限 9；t9 删除 host/agent-tools.ts 后本扫描不受影响
    expect(toolFiles.length).toBeGreaterThanOrEqual(9)
    expect(sites.length).toBeGreaterThanOrEqual(9)
    // 工厂名唯一（同名的第二个工具会静默覆盖第一个）
    expect(new Set(sites.map(s => s.name)).size).toBe(sites.length)
  })

  for (const site of sites) {
    it('define' + site.name + 'Tool：所有 return 分支键均已声明', () => {
      const srcs = RESPONSE_SOURCES[site.name]
      expect(srcs, 'define' + site.name + 'Tool 缺少响应源映射（新增工具必须补 RESPONSE_SOURCES）').toBeDefined()
      const keys: string[] = [...returnKeys(readFileSync(site.file, 'utf8'))]
      for (const rel of srcs ?? []) keys.push(...returnKeys(readFileSync(join(ROOT, rel), 'utf8')))
      // 扫描器可信度：每个工具体至少应抓到一个键
      expect(keys.length, 'define' + site.name + 'Tool 未扫到任何 return 键，扫描器可能失效').toBeGreaterThan(0)
      const factory = (toolModules as unknown as Record<string, (d: unknown) => any>)['define' + site.name + 'Tool']
      expect(typeof factory, 'define' + site.name + 'Tool 未导出').toBe('function')
      const declared = declaredKeys(factory({} as never))
      const missing = [...new Set(keys)].filter(k => !declared.has(k))
      expect(missing, 'define' + site.name + 'Tool 的 return 含未声明字段：' + missing.join(', ')).toEqual([])
    })
  }
})
