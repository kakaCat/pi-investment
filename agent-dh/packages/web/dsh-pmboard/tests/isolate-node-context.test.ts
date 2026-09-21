/**
 * 节点边界同窗口 surface 整段替换（REQ-422af1 t9）——design/test-cases.md T24-T28。
 *
 * 纪律：只测成功路径等于没测，故五条验收各自的失败路径都真的构造出来；
 * 另含「路线 A 端到端（真实 @deepseek-ai/dsh-session）」与框架不变量证据（拒绝点原文）。
 *
 * @module dsh-pmboard/tests/isolate-node-context
 */
import { describe, it, expect } from 'vitest'
import { Session, SessionId } from '@deepseek-ai/dsh-session'
import { makeHarness, req } from './application/harness.js'
import { resolveStagePrompt, STAGE_CHAIN } from '../src/domain/prompt/index.js'
import { NodeIsolationAdapter } from '../src/adapters/NodeIsolationAdapter.js'
import {
  buildNodeInputPackage,
  isolateNodeContext,
  newWindowInstruction,
  type IsolateNodeContextDeps,
  type IsolationTraceEntry,
  type NodeIsolationPort,
  type SurfaceNode,
} from '../src/application/use-cases/IsolateNodeContext.js'
import { mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createSessionEventCaptureHook, type CaptureHookDeps } from '../src/adapters/CaptureHook.js'
import { IsolationTraceFile } from '../src/adapters/IsolationTraceFile.js'
import {
  ISOLATION_TRACE_FIELDS,
  appendToIsolationTrace,
  isIsolationTraceEntry,
} from '../src/application/internal/isolation-trace.js'
import {
  createNodeSettlementDispatcher,
  type NodeSettlementDispatcher,
  type NodeSettlementDeps,
} from '../src/application/internal/node-settlement.js'
import { nodeIsolationEnabled } from '../src/index.js'
import { emptyLedger, type ReqboardLedger } from '../src/shared/protocol.js'

/** 前序对话里的唯一标记——输入包不得包含它（INV-9）。 */
const OLD_MARKER = '前序对话摘录-应被遗弃-UNIQUE-7f3a'
const REQ_ID = 'REQ-422af1'
const DOC_PATH = 'docs/requirements/REQ-422af1/requirement.md'
const DOC_TEXT = '## 3.6 节点执行模型\n本文档是需求文档投影的唯一来源（DOC-BODY-MARKER）。'
const WINDOW = 'session-w-001'

function requirement() {
  return req({
    id: REQ_ID,
    title: '节点提示词按路径分层注入',
    category: 'feature',
    status: 'implementing',
    sourceSessionId: WINDOW,
    artifacts: [
      {
        stage: 'design', kind: 'plan', path: 'docs/requirements/REQ-422af1/plan.md',
        registeredAt: 10, registeredBy: { kind: 'agent', sessionId: WINDOW },
        confirmedAt: 11, confirmedBy: { kind: 'human' },
      },
      {
        stage: 'implementing', kind: 'task_detail', path: 'docs/requirements/REQ-422af1/tasks/t-1.md',
        registeredAt: 12, registeredBy: { kind: 'agent', sessionId: WINDOW },
      },
    ],
  })
}

/** 台账 + 文档 + 时钟（复用 REQ-47939a 的内存端口夹具）。 */
function baseHarness() {
  const h = makeHarness({ requirements: [requirement()] })
  h.docs.put(DOC_PATH, DOC_TEXT)
  return h
}

class TraceRecorder {
  entries: IsolationTraceEntry[] = []
  record(entry: IsolationTraceEntry): void { this.entries.push(entry) }
}

/** surface 假实现（T24-T28 的失败/成功路径由它驱动）。 */
class FakeIsolation implements NodeIsolationPort {
  reachableFlag = true
  idleFlag = true
  idleThrows = false
  nodes: SurfaceNode[] = [
    { seq: 0, type: 'system/message' },
    { seq: 1, type: 'user/message' },
    { seq: 2, type: 'assistant/message' },
  ]
  before = true
  after = true
  replaces: Array<{ start: number; end: number; text: string; shadowed: readonly number[] }> = []
  calls: string[] = []
  constructor(private readonly seqSource: () => number = () => 100) {}
  reachable(): boolean { return this.reachableFlag }
  idle(): boolean {
    this.calls.push('idle')
    if (this.idleThrows) throw new Error('idle probe exploded')
    return this.idleFlag
  }
  surface(): readonly SurfaceNode[] { this.calls.push('surface'); return this.nodes }
  balancedBefore(seq: number): boolean { this.calls.push('before:' + seq); return this.before }
  balancedAfter(seq: number): boolean { this.calls.push('after:' + seq); return this.after }
  replace(input: { start: number; end: number; text: string; shadowed: readonly number[] }): number {
    this.calls.push('replace')
    this.replaces.push(input)
    return this.seqSource()
  }
}

// ---------------------------------------------------------------------------
// T24 输入包内容：路由结果 + 文档/台账投影；不含前序对话摘录
// ---------------------------------------------------------------------------

describe('T24 节点输入包内容（INV-9）', () => {
  it('纯函数：= 路由结果 + 需求文档投影 + 台账投影（五字段齐备）', () => {
    const r = requirement()
    const pkg = buildNodeInputPackage({
      stage: 'implementing', category: 'feature',
      requirement: r, requirementDoc: DOC_TEXT, requirementDocPath: DOC_PATH,
    })
    const route = resolveStagePrompt({ stage: 'implementing', category: 'feature' })
    expect(pkg.text).toContain(route.text)          // 路由结果
    expect(pkg.text).toContain(DOC_TEXT)            // 文档投影
    expect(pkg.text).toContain(REQ_ID)              // 台账投影
    for (const field of ['## 当前节点', '## 上游结论', '## 未决问题', '## 下一步', '## 证据指针']) {
      expect(pkg.text, '缺字段 ' + field).toContain(field)
    }
    expect(pkg.text).toContain(STAGE_CHAIN.implementing.label)                 // 下一步（链声明）
    expect(pkg.text).toContain('docs/requirements/REQ-422af1/plan.md')         // 上游结论（已确认）
    expect(pkg.text).toContain('docs/requirements/REQ-422af1/tasks/t-1.md')    // 未决问题（未确认）
    expect(pkg.resolved.routeKey).toBe('implementing/light/feature')
  })

  it('端到端文本不含任何前序对话摘录', async () => {
    const h = baseHarness()
    const iso = new FakeIsolation()
    const result = await isolateNodeContext(
      { repo: h.repo, docs: h.docs, clock: h.clock, isolation: iso },
      { windowKey: WINDOW, stage: 'implementing', category: 'feature', persistArtifacts: () => 1 },
    )
    expect(result.packageText).not.toContain(OLD_MARKER)
    expect(result.packageText).not.toContain('user:')
    expect(result.packageText).not.toContain('assistant:')
    // 替换进会话的正文就是输入包本身（同源）
    expect(iso.replaces[0]!.text).toBe(result.packageText)
  })
})

// ---------------------------------------------------------------------------
// T25 边界不平衡（tool 调用无结果）→ 替换不发生 + 结构化错误
// ---------------------------------------------------------------------------

describe('T25 边界不平衡拒执行', () => {
  it('终点后切不平衡 → 不替换 + 结构化错误 + 留痕', async () => {
    const h = baseHarness()
    const trace = new TraceRecorder()
    const iso = new FakeIsolation()
    iso.after = false
    const result = await isolateNodeContext(
      { repo: h.repo, docs: h.docs, clock: h.clock, isolation: iso, trace },
      { windowKey: WINDOW, stage: 'implementing', category: 'feature', persistArtifacts: () => 1 },
    )
    expect(result.replaced).toBe(false)
    expect(result.status).toBe('rejected')
    expect(result.code).toBe('boundary_unbalanced')
    expect(result.message).toContain('不平衡')
    expect(iso.replaces.length).toBe(0)                  // 替换不发生
    expect(iso.calls).not.toContain('replace')
    expect(trace.entries).toHaveLength(1)                // 留痕
    expect(trace.entries[0]!.code).toBe('boundary_unbalanced')
    expect(trace.entries[0]!.range).toEqual({ start: 1, end: 2 })
    expect(result.packageText.length).toBeGreaterThan(0) // 输入包仍返回（兜底路径可用）
  })

  it('起点前切不平衡 → 同样拒绝（两侧任一不平衡即拒）', async () => {
    const h = baseHarness()
    const iso = new FakeIsolation()
    iso.before = false
    const result = await isolateNodeContext(
      { repo: h.repo, docs: h.docs, clock: h.clock, isolation: iso },
      { windowKey: WINDOW, stage: 'implementing', category: 'feature', persistArtifacts: () => 1 },
    )
    expect(result.status).toBe('rejected')
    expect(result.code).toBe('boundary_unbalanced')
    expect(iso.replaces.length).toBe(0)
  })
})

// ---------------------------------------------------------------------------
// T26 agent 忙碌 → 不替换、留痕、无未捕获异常
// ---------------------------------------------------------------------------

describe('T26 活动轮次（agent 忙碌）拒执行', () => {
  it('忙碌 → skipped/agent_busy，不替换，无异常，留痕一条', async () => {
    const h = baseHarness()
    const trace = new TraceRecorder()
    const iso = new FakeIsolation()
    iso.idleFlag = false
    const result = await isolateNodeContext(
      { repo: h.repo, docs: h.docs, clock: h.clock, isolation: iso, trace },
      { windowKey: WINDOW, stage: 'implementing', category: 'feature', persistArtifacts: () => 1 },
    )
    expect(result.replaced).toBe(false)
    expect(result.status).toBe('skipped')
    expect(result.code).toBe('agent_busy')
    expect(iso.replaces.length).toBe(0)
    expect(trace.entries).toHaveLength(1)
    expect(trace.entries[0]!.status).toBe('skipped')
  })

  it('idle 探测抛错 → 视为不空闲（保守），仍无未捕获异常', async () => {
    const h = baseHarness()
    const iso = new FakeIsolation()
    iso.idleThrows = true
    const result = await isolateNodeContext(
      { repo: h.repo, docs: h.docs, clock: h.clock, isolation: iso },
      { windowKey: WINDOW, stage: 'implementing', category: 'feature', persistArtifacts: () => 1 },
    )
    expect(result.status).toBe('skipped')
    expect(result.replaced).toBe(false)
    expect(iso.replaces.length).toBe(0)
  })

  it('surface 读不到事件（腐坏）→ 结构化返回，不冒泡', async () => {
    const h = baseHarness()
    const iso = new FakeIsolation()
    iso.surface = () => { throw new Error('corrupt surface') }
    const result = await isolateNodeContext(
      { repo: h.repo, docs: h.docs, clock: h.clock, isolation: iso },
      { windowKey: WINDOW, stage: 'implementing', category: 'feature', persistArtifacts: () => 1 },
    )
    expect(result.replaced).toBe(false)
    expect(result.code).toBe('isolation_internal_error')
    expect(result.message).toContain('corrupt surface')
  })
})

// ---------------------------------------------------------------------------
// T27 先落盘后遗弃：产物写入事件 seq < 替换事件 seq
// ---------------------------------------------------------------------------

describe('T27 先落盘后遗弃', () => {
  it('落盘先于替换；artifactSeq < replacementSeq', async () => {
    const h = baseHarness()
    const order: string[] = []
    let clock = 0
    const next = () => { clock += 1; return clock }
    const iso = new FakeIsolation(() => { order.push('replace'); return next() })
    const result = await isolateNodeContext(
      { repo: h.repo, docs: h.docs, clock: h.clock, isolation: iso },
      {
        windowKey: WINDOW, stage: 'implementing', category: 'feature',
        persistArtifacts: () => { order.push('persist'); return next() },
      },
    )
    expect(result.status).toBe('replaced')
    expect(result.replaced).toBe(true)
    expect(order).toEqual(['persist', 'replace'])          // 顺序断言
    expect(result.artifactSeq).toBe(1)
    expect(result.replacementSeq).toBe(2)
    expect(result.artifactSeq! < result.replacementSeq!).toBe(true)
    expect(result.code).toBeUndefined()                    // 无不一致标记
  })

  it('产物落盘失败 → 遗弃不发生（先落盘不可满足就不遗弃）', async () => {
    const h = baseHarness()
    const iso = new FakeIsolation()
    const result = await isolateNodeContext(
      { repo: h.repo, docs: h.docs, clock: h.clock, isolation: iso },
      {
        windowKey: WINDOW, stage: 'implementing', category: 'feature',
        persistArtifacts: () => { throw new Error('disk full') },
      },
    )
    expect(result.status).toBe('skipped')
    expect(result.code).toBe('artifact_persist_failed')
    expect(iso.replaces.length).toBe(0)
  })

  it('落盘 seq 非法 → 不遗弃', async () => {
    const h = baseHarness()
    const iso = new FakeIsolation()
    const result = await isolateNodeContext(
      { repo: h.repo, docs: h.docs, clock: h.clock, isolation: iso },
      { windowKey: WINDOW, stage: 'implementing', category: 'feature', persistArtifacts: () => Number.NaN },
    )
    expect(result.status).toBe('skipped')
    expect(result.code).toBe('artifact_seq_invalid')
    expect(iso.replaces.length).toBe(0)
  })

  it('替换 seq 早于落盘 seq → 结果显式标 replace_before_persist（不静默）', async () => {
    const h = baseHarness()
    const iso = new FakeIsolation(() => 1)   // 替换 seq = 1
    const result = await isolateNodeContext(
      { repo: h.repo, docs: h.docs, clock: h.clock, isolation: iso },
      { windowKey: WINDOW, stage: 'implementing', category: 'feature', persistArtifacts: () => 5 },
    )
    expect(result.status).toBe('replaced')
    expect(result.code).toBe('replace_before_persist')
  })
})

// ---------------------------------------------------------------------------
// T28 触达失败 → 「请开新窗口 + 输入包文本」而非静默跳过
// ---------------------------------------------------------------------------

describe('T28 触达能力探测失败 → D-12 降级', () => {
  it('未注入端口 → fallback，返回开新窗口指引 + 完整输入包', async () => {
    const h = baseHarness()
    const trace = new TraceRecorder()
    const result = await isolateNodeContext(
      { repo: h.repo, docs: h.docs, clock: h.clock, trace },
      { windowKey: WINDOW, stage: 'implementing', category: 'feature', persistArtifacts: () => 1 },
    )
    expect(result.replaced).toBe(false)
    expect(result.status).toBe('fallback')
    expect(result.code).toBe('isolation_unreachable')
    expect(result.fallbackInstruction).toContain('新窗口')
    expect(result.fallbackInstruction).toContain('# 节点输入包')     // 输入包文本随降级一起给出
    expect(result.fallbackInstruction).toContain(DOC_TEXT)
    expect(result.packageText.length).toBeGreaterThan(0)
    expect(trace.entries).toHaveLength(1)
    expect(trace.entries[0]!.status).toBe('fallback')
  })

  it('reachable()=false → 同样 fallback（不静默跳过、不替换）', async () => {
    const h = baseHarness()
    const iso = new FakeIsolation()
    iso.reachableFlag = false
    const result = await isolateNodeContext(
      { repo: h.repo, docs: h.docs, clock: h.clock, isolation: iso },
      { windowKey: WINDOW, stage: 'implementing', category: 'feature', persistArtifacts: () => 1 },
    )
    expect(result.status).toBe('fallback')
    expect(result.replaced).toBe(false)
    expect(iso.replaces.length).toBe(0)
    expect(result.fallbackInstruction).toBe(newWindowInstruction(result.packageText))
  })
})

// ---------------------------------------------------------------------------
// 路线 A 端到端：真实 Session（证明 surface 原语可行 + 拒绝点原文）
// ---------------------------------------------------------------------------

function sysMsg(text: string) {
  return { id: 'sys-1', role: 'system', content: [{ type: 'text', text }], source: { kind: 'plugin', plugin: 'dsh-pmboard' } }
}
function userMsg(text: string) {
  return { id: 'u-1', role: 'user', content: [{ type: 'text', text }], source: { kind: 'user' } }
}
function assistantToolCall() {
  return {
    id: 'a-1', role: 'assistant',
    content: [{ type: 'text', text: '调用工具' }, { type: 'tool-call', id: 'c1', name: 'foo', arguments: '{}' }],
    source: { kind: 'model', provider: 'p', model: 'm' },
  }
}
function toolResult() {
  return {
    id: 'r-1', role: 'user',
    content: [{ type: 'tool-result', toolCallId: 'c1', content: [{ type: 'text', text: 'ok' }] }],
    source: { kind: 'tool', callId: 'c1' },
  }
}

/** 真实会话：system + 旧用户消息（含唯一标记） + assistant(tool-call) + tool/result（配对平衡）。 */
function realSession() {
  const s = Session.create(SessionId(WINDOW))
  const sys = s.append('system/message', { turn: 1, step: 1, message: sysMsg('SYS PROMPT') } as any, { surfaceOp: 'append' })
  const u1 = s.append('user/message', userMsg('旧上下文：' + OLD_MARKER) as any, { surfaceOp: 'append' })
  const a1 = s.append('assistant/message', { turn: 1, step: 1, message: assistantToolCall(), stream: [] } as any, { surfaceOp: 'append' })
  const tr = s.append('tool/result', { turn: 1, step: 1, message: toolResult() } as any, { surfaceOp: 'append' })
  return { s, sys, u1, a1, tr }
}

describe('路线 A 端到端（真实 @deepseek-ai/dsh-session）', () => {
  it('框架不变量证据：user/message 遮蔽 surface 节点 0 被硬拒（错误原文）', () => {
    const { s, sys, tr } = realSession()
    const all = [...s.surface.nodes]
    expect(() => s.append('user/message', userMsg('PKG') as any, {
      surfaceOp: { op: 'replace', startSeq: sys.seq, endSeq: tr.seq },
      sourceEventSeqs: all,
    })).toThrow(/node 0 holds the system prompt and may be rewritten only by a system\/message over exactly that node/)
  })

  it('合法区间（首个非 system 节点 → 末尾）真实替换成功：surface=[系统段, 输入包]', async () => {
    const h = baseHarness()
    const { s, u1, tr } = realSession()
    const trace = new TraceRecorder()
    const iso = new NodeIsolationAdapter(s, { idle: () => true })
    const deps: IsolateNodeContextDeps = { repo: h.repo, docs: h.docs, clock: h.clock, isolation: iso, trace }

    // 边界检查：配对平衡（assistant tool-call 与 tool/result 都在被替换区间内）
    expect(iso.balancedBefore(u1.seq)).toBe(true)
    expect(iso.balancedAfter(tr.seq)).toBe(true)

    const result = await isolateNodeContext(deps, {
      windowKey: WINDOW, stage: 'implementing', category: 'feature', persistArtifacts: () => 3,
    })

    expect(result.status).toBe('replaced')
    expect(result.range).toEqual({ start: u1.seq, end: tr.seq })
    expect(result.replacementSeq! > result.artifactSeq!).toBe(true)
    expect([...s.surface.nodes]).toEqual([0, result.replacementSeq])
    const derived = s.deriveMessages()
    expect(derived).toHaveLength(2)
    expect(derived[0]!.role).toBe('system')
    expect(JSON.stringify(derived[1]!.content)).toContain('# 节点输入包')
    // 旧上下文真的被遗弃：派生消息里再也看不到它的标记
    expect(JSON.stringify(derived)).not.toContain(OLD_MARKER)
    expect(JSON.stringify(derived)).toContain('routeKey=implementing/light/feature')
    expect(trace.entries[0]!.status).toBe('replaced')
    // 事件日志仍保留旧事件（可回放/可审计）
    expect(s.snapshotEvents().some(e => e.type === 'user/message')).toBe(true)
  })

  it('真实未配对 tool 调用 → 边界检查判定不平衡，用例拒绝替换', async () => {
    const h = baseHarness()
    const s = Session.create(SessionId(WINDOW))
    s.append('system/message', { turn: 1, step: 1, message: sysMsg('SYS') } as any, { surfaceOp: 'append' })
    const u = s.append('user/message', userMsg('旧上下文 ' + OLD_MARKER) as any, { surfaceOp: 'append' })
    const a = s.append('assistant/message', { turn: 1, step: 1, message: assistantToolCall(), stream: [] } as any, { surfaceOp: 'append' })
    const iso = new NodeIsolationAdapter(s, { idle: () => true })
    expect(iso.balancedAfter(a.seq)).toBe(false)      // 有 tool-call 无 result

    const result = await isolateNodeContext(
      { repo: h.repo, docs: h.docs, clock: h.clock, isolation: iso },
      { windowKey: WINDOW, stage: 'implementing', category: 'feature', persistArtifacts: () => 1 },
    )
    expect(result.status).toBe('rejected')
    expect(result.code).toBe('boundary_unbalanced')
    expect([...s.surface.nodes]).toEqual([0, u.seq, a.seq])   // 替换不发生
  })

  it('无历史节点（只有系统段）→ 不替换，skipped 留痕', async () => {
    const h = baseHarness()
    const s = Session.create(SessionId(WINDOW))
    s.append('system/message', { turn: 1, step: 1, message: sysMsg('SYS') } as any, { surfaceOp: 'append' })
    const iso = new NodeIsolationAdapter(s, { idle: () => true })
    const result = await isolateNodeContext(
      { repo: h.repo, docs: h.docs, clock: h.clock, isolation: iso },
      { windowKey: WINDOW, stage: 'design', category: 'feature', persistArtifacts: () => 1 },
    )
    expect(result.status).toBe('skipped')
    expect(result.code).toBe('no_replaceable_range')
    expect([...s.surface.nodes]).toEqual([0])
  })
})

// ---------------------------------------------------------------------------
// REQ-422af1 t10：节点结算点接入隔离（开关 NODE_ISOLATION 默认关 / D-17 异步边界）
// ---------------------------------------------------------------------------

/** 默认异步边界跑到底：多轮宏任务 + 微任务排空（setImmediate 默认调度用）。 */
async function settleAsync(): Promise<void> {
  for (let i = 0; i < 5; i += 1) {
    await new Promise<void>((resolve) => { setImmediate(resolve) })
  }
}

/** 绑定本窗口、处于 implementing 的台账（hook 的 snapshot 与 dispatcher 的 repo 共用一份语义）。 */
function boundLedger(): ReqboardLedger {
  return { ...emptyLedger(), requirements: [requirement()] }
}

function userEvent(text: string): unknown {
  return { type: 'user/message', data: { content: [{ type: 'text', text }], source: { kind: 'user' } } }
}
function turnEndEvent(): unknown {
  return { type: 'turn/end', data: { turn: 1, reason: 'success' } }
}

interface T10Wiring {
  hook: (session: unknown, event: unknown) => void
  dispatcher: NodeSettlementDispatcher
  trace: TraceRecorder
  warns: string[]
  prompts: string[]
}

/** 组装与 index.ts 同形状的接线：CaptureHook → onNodeSettled → 隔离分发器。 */
function wireT10(over: {
  enabled: boolean
  isolationFor?: NodeSettlementDeps['isolationFor']
  persistArtifacts?: NodeSettlementDeps['persistArtifacts']
  schedule?: NodeSettlementDeps['schedule']
  run?: NodeSettlementDeps['run']
  warn?: (message: string) => void
}): T10Wiring {
  const h = baseHarness()
  const trace = new TraceRecorder()
  const warns: string[] = []
  const prompts: string[] = []
  const ledger = boundLedger()
  const dispatcher = createNodeSettlementDispatcher({
    enabled: over.enabled,
    repo: h.repo,
    docs: h.docs,
    clock: h.clock,
    trace,
    warn: over.warn ?? ((m) => { warns.push(m) }),
    ...(over.isolationFor === undefined ? {} : { isolationFor: over.isolationFor }),
    ...(over.persistArtifacts === undefined ? {} : { persistArtifacts: over.persistArtifacts }),
    ...(over.schedule === undefined ? {} : { schedule: over.schedule }),
    ...(over.run === undefined ? {} : { run: over.run }),
  })
  const deps: CaptureHookDeps = {
    snapshot: () => ledger,
    pending: new Map(),
    now: () => 1000,
    onStagePrompt: (_k, prompt) => { prompts.push(prompt) },
    onNodeSettled: (settle, session) => { dispatcher.onSettle(settle, session) },
    logger: { info: () => {}, debug: () => {} },
  }
  return { hook: createSessionEventCaptureHook(deps), dispatcher, trace, warns, prompts }
}

describe('t10 §1 开关 NODE_ISOLATION（默认关）', () => {
  it('缺省 → false；显式配置优先于环境变量；环境变量 on 才开', () => {
    expect(nodeIsolationEnabled(undefined, {})).toBe(false)
    expect(nodeIsolationEnabled({}, {})).toBe(false)
    expect(nodeIsolationEnabled({}, { NODE_ISOLATION: 'off' })).toBe(false)
    expect(nodeIsolationEnabled({}, { NODE_ISOLATION: '0' })).toBe(false)
    expect(nodeIsolationEnabled({}, { NODE_ISOLATION: 'true' })).toBe(true)
    expect(nodeIsolationEnabled({}, { NODE_ISOLATION: '1' })).toBe(true)
    expect(nodeIsolationEnabled({}, { NODE_ISOLATION: 'ON' })).toBe(true)
    expect(nodeIsolationEnabled({ nodeIsolation: false }, { NODE_ISOLATION: '1' })).toBe(false)
    expect(nodeIsolationEnabled({ nodeIsolation: true }, {})).toBe(true)
  })
})

describe('t10 §2 关（默认）：隔离代码路径执行 0 次，既有行为不变', () => {
  it('一次真实节点结算（user/message + turn/end）→ 四项计数全 0、端口一次未建、无告警；阶段注入照旧', async () => {
    let isolationForCalls = 0
    const fake = new FakeIsolation()
    const w = wireT10({
      enabled: false,
      isolationFor: () => { isolationForCalls += 1; return fake },
      persistArtifacts: () => 1,
    })
    w.hook({ id: WINDOW }, userEvent('继续推进'))
    w.hook({ id: WINDOW }, turnEndEvent())
    await settleAsync()
    expect(w.dispatcher.stats()).toEqual({ scheduled: 0, executed: 0, replaced: 0, failed: 0 })
    expect(isolationForCalls).toBe(0)      // 隔离端口一次都没构造
    expect(fake.calls).toEqual([])         // 隔离端口一次都没被碰
    expect(w.trace.entries).toEqual([])    // 无留痕
    expect(w.warns).toEqual([])            // 无告警（不是"失败后才不报"）
    expect(w.prompts).toHaveLength(1)      // 既有行为不变：状态转移阶段提示词注入照旧
    expect(w.prompts[0]).toContain('下一步：accepting')
  })

  it('关：即使注入的隔离端口会抛（框架拒绝），也一次都不会被碰——流水线照常推进且无异常', async () => {
    const exploding = new FakeIsolation()
    exploding.replace = () => { throw new Error('session append cannot reenter while another append is being published') }
    let calls = 0
    const w = wireT10({
      enabled: false,
      isolationFor: () => { calls += 1; return exploding },
      persistArtifacts: () => 1,
    })
    expect(() => {
      w.hook({ id: WINDOW }, userEvent('继续推进'))
      w.hook({ id: WINDOW }, turnEndEvent())
    }).not.toThrow()
    await settleAsync()
    expect(calls).toBe(0)
    expect(w.dispatcher.stats().executed).toBe(0)
    expect(w.prompts).toHaveLength(1)      // 流水线状态仍推进
  })
})

describe('t10 §3 开：一次节点结算 → 1 次执行 + 留痕完整（routeKey + 被替换区间）', () => {
  it('真实 Session 端到端：替换真的发生、旧上下文真的被遗弃、留痕字段完整', async () => {
    const { s, u1, tr } = realSession()
    const w = wireT10({
      enabled: true,
      isolationFor: () => new NodeIsolationAdapter(s, { idle: () => true }),
      persistArtifacts: () => 1,
    })
    w.hook({ id: WINDOW }, userEvent('继续推进'))
    expect(w.dispatcher.stats().executed).toBe(0)   // 派发内未执行（D-17）
    expect(w.trace.entries).toHaveLength(0)
    w.hook({ id: WINDOW }, turnEndEvent())
    expect(w.dispatcher.stats().executed).toBe(0)   // turn/end 派发内仍未执行
    await settleAsync()
    expect(w.dispatcher.stats()).toEqual({ scheduled: 1, executed: 1, replaced: 1, failed: 0 })
    expect(w.trace.entries).toHaveLength(1)
    const entry = w.trace.entries[0]!
    expect(entry.status).toBe('replaced')
    expect(entry.routeKey).toBe('implementing/light/feature')
    expect(entry.range).toEqual({ start: u1.seq, end: tr.seq })
    expect(entry.replacementSeq).toBeGreaterThan(entry.artifactSeq!)
    expect(entry.packageChars).toBeGreaterThan(0)
    expect([...s.surface.nodes]).toEqual([0, entry.replacementSeq])
    const derived = JSON.stringify(s.deriveMessages())
    expect(derived).not.toContain(OLD_MARKER)        // 旧上下文真被遗弃
    expect(derived).toContain('routeKey=implementing/light/feature')
    expect(w.prompts).toHaveLength(1)                // 既有注入行为未受影响
  })

  it('异步边界：onSettle 返回前隔离动作不执行（只交给边界），边界运行后才执行', async () => {
    const queued: Array<() => void> = []
    const fake = new FakeIsolation()
    const w = wireT10({
      enabled: true,
      isolationFor: () => fake,
      persistArtifacts: () => 1,
      schedule: (task) => { queued.push(task) },
    })
    w.hook({ id: WINDOW }, userEvent('继续推进'))
    w.hook({ id: WINDOW }, turnEndEvent())
    expect(queued).toHaveLength(1)      // 交给边界，而非同步执行
    expect(w.dispatcher.stats()).toEqual({ scheduled: 1, executed: 0, replaced: 0, failed: 0 })
    expect(fake.calls).toEqual([])
    expect(w.trace.entries).toEqual([])
    queued[0]!()                        // 边界运行
    await settleAsync()
    expect(w.dispatcher.stats()).toEqual({ scheduled: 1, executed: 1, replaced: 1, failed: 0 })
    expect(fake.calls).toContain('replace')
    expect(w.trace.entries).toHaveLength(1)
  })

  it('同一节点只结算一次：连续 3 个回合只遗弃一次上下文', async () => {
    const fake = new FakeIsolation()
    const w = wireT10({ enabled: true, isolationFor: () => fake, persistArtifacts: () => 1 })
    for (let i = 0; i < 3; i += 1) {
      w.hook({ id: WINDOW }, userEvent('继续推进'))
      w.hook({ id: WINDOW }, turnEndEvent())
      await settleAsync()
    }
    expect(w.dispatcher.stats()).toEqual({ scheduled: 1, executed: 1, replaced: 1, failed: 0 })
    expect(fake.replaces).toHaveLength(1)
  })
})

describe('t10 §4 失败只告警不中断流水线（两种模式）', () => {
  it('开：框架拒绝 surface 替换 → 不抛、只告警、留痕 rejected、流水线仍推进', async () => {
    const fake = new FakeIsolation()
    fake.replace = () => { throw new Error('session append cannot reenter while another append is being published') }
    const w = wireT10({ enabled: true, isolationFor: () => fake, persistArtifacts: () => 1 })
    expect(() => {
      w.hook({ id: WINDOW }, userEvent('继续推进'))
      w.hook({ id: WINDOW }, turnEndEvent())
    }).not.toThrow()
    await settleAsync()
    expect(w.dispatcher.stats()).toEqual({ scheduled: 1, executed: 1, replaced: 0, failed: 0 })
    expect(w.trace.entries).toHaveLength(1)
    expect(w.trace.entries[0]!.status).toBe('rejected')
    expect(w.trace.entries[0]!.code).toBe('framework_rejected')
    expect(w.warns).toHaveLength(1)
    expect(w.warns[0]).toContain('节点隔离未替换')
    expect(w.prompts).toHaveLength(1)     // 流水线状态仍推进
  })

  it('开：用例自身抛错 → failed 计数 + 告警，绝不冒泡到结算点', async () => {
    const w = wireT10({
      enabled: true,
      isolationFor: () => new FakeIsolation(),
      persistArtifacts: () => 1,
      run: async () => { throw new Error('use case exploded') },
    })
    expect(() => {
      w.hook({ id: WINDOW }, userEvent('继续推进'))
      w.hook({ id: WINDOW }, turnEndEvent())
    }).not.toThrow()
    await settleAsync()
    expect(w.dispatcher.stats()).toEqual({ scheduled: 1, executed: 1, replaced: 0, failed: 1 })
    expect(w.warns).toHaveLength(1)
    expect(w.warns[0]).toContain('节点隔离执行异常')
    expect(w.prompts).toHaveLength(1)
  })

  it('开：告警通道自身抛错也不冒泡（无未捕获异常/未处理 rejection）', async () => {
    const w = wireT10({
      enabled: true,
      isolationFor: () => new FakeIsolation(),
      persistArtifacts: () => 1,
      run: async () => { throw new Error('boom') },
      warn: () => { throw new Error('logger down') },
    })
    w.hook({ id: WINDOW }, userEvent('继续推进'))
    w.hook({ id: WINDOW }, turnEndEvent())
    await settleAsync()
    expect(w.dispatcher.stats().failed).toBe(1)
    expect(w.prompts).toHaveLength(1)
  })
})

describe('t10 §5 隔离留痕（ring buffer + 原子写，只告警不抛）', () => {
  const traceEntry = (over: Partial<IsolationTraceEntry> = {}): IsolationTraceEntry => ({
    at: 1,
    windowKey: WINDOW,
    stage: 'implementing',
    status: 'replaced',
    reason: '已整段替换 surface[1, 2] 为节点输入包',
    routeKey: 'implementing/light/feature',
    packageChars: 10,
    range: { start: 1, end: 2 },
    ...over,
  })

  it('必需字段单点固定；replaced 记录必须带被替换区间（否则不可信）', () => {
    expect([...ISOLATION_TRACE_FIELDS]).toEqual([
      'at', 'windowKey', 'stage', 'status', 'reason', 'routeKey', 'packageChars',
    ])
    expect(isIsolationTraceEntry(traceEntry())).toBe(true)
    expect(isIsolationTraceEntry(traceEntry({ status: 'replaced', range: undefined }))).toBe(false)
    expect(isIsolationTraceEntry(traceEntry({ status: 'skipped', range: undefined }))).toBe(true)
    expect(isIsolationTraceEntry({ ...traceEntry(), routeKey: undefined })).toBe(false)
  })

  it('ring buffer 有界：写入 N+5 只保留最近 N；cap 非法 → 响亮抛错', () => {
    let all: IsolationTraceEntry[] = []
    for (let i = 0; i < 10; i += 1) all = appendToIsolationTrace(all, traceEntry({ at: i }), 5)
    expect(all).toHaveLength(5)
    expect(all[0]!.at).toBe(5)
    expect(() => appendToIsolationTrace([], traceEntry(), 0)).toThrow(/cap/)
  })

  it('文件适配器：写入后可读回（字段一致）；写入失败只走 onError、绝不抛', async () => {
    const dir = mkdtempSync(join(tmpdir(), 'dsh-isotrace-'))
    const file = join(dir, 'state/node-isolation-log.json')
    const errors: unknown[] = []
    const log = new IsolationTraceFile(file, (e) => errors.push(e))
    log.record(traceEntry({ at: 7 }))
    await log.flush()
    const onDisk = JSON.parse(readFileSync(file, 'utf8')) as IsolationTraceEntry[]
    expect(onDisk).toHaveLength(1)
    expect(onDisk[0]!.routeKey).toBe('implementing/light/feature')
    expect(onDisk[0]!.range).toEqual({ start: 1, end: 2 })
    expect(await log.readAll()).toHaveLength(1)
    // 目标路径是目录 → 写失败：只告警，不抛（留痕是旁路，不是流水线的一部分）
    const bad = new IsolationTraceFile(dir, (e) => errors.push(e))
    bad.record(traceEntry())
    await expect(bad.flush()).resolves.toBeUndefined()
    expect(errors.length).toBeGreaterThan(0)
    rmSync(dir, { recursive: true, force: true })
  })
})
