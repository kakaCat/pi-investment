/**
 * capture-hook.ts 确定性消息 hook 单测。
 * 覆盖判定链：事件类型（仅 user/message；turn/end 清登记）、忽略会话、direct-human
 * source 过滤（plugin kind 跳过 / source 缺失退化放行）、噪声清洗（纯系统块跳过）、
 * 窗口条件（bound / hasPending 跳过，unbound 登记）、登记覆盖、turn/end 清除。
 */
import { describe, it, expect } from 'vitest'
import { emptyLedger, type ReqboardLedger } from '../src/shared/protocol.js'
import { createSessionEventCaptureHook, type CaptureHookDeps } from '../src/adapters/CaptureHook.js'
import { shouldCaptureWindow } from '../src/application/internal/window.js'
import {
  recordToolTrace,
  toolActivitySince,
  TOOL_TRACE_CAP,
  type ToolTraceEntry,
} from '../src/adapters/SessionProbeAdapter.js'

const W = 'session-abc-123'

/** 构造最小 hook 依赖（默认空台账 = unbound 无 pending；setLedger 可换台账快照）。 */
function deps(): {
  deps: CaptureHookDeps
  pending: Map<string, { windowKey: string; text: string; capturedAt: number }>
  logs: string[]
  setLedger: (l: ReqboardLedger) => void
} {
  const pending = new Map<string, { windowKey: string; text: string; capturedAt: number }>()
  let ledger: ReqboardLedger = emptyLedger()
  const logs: string[] = []
  return {
    pending,
    logs,
    setLedger: (l) => { ledger = l },
    deps: {
      snapshot: () => ledger,
      pending,
      now: () => 1000,
      logger: {
        info: (m) => logs.push('info:' + m),
        debug: (m) => logs.push('debug:' + m),
      },
    },
  }
}

/** 构造 user/message 事件。source.kind 缺省 'user'；kind 传 'none' 表示 source 对象缺失。 */
function userMsg(content: unknown, kind?: string): unknown {
  const source =
    kind === 'none' ? undefined : { kind: kind ?? 'user' }
  return { type: 'user/message', data: { content, source } }
}
function turnEnd(): unknown {
  return { type: 'turn/end', data: { turn: 1, reason: 'success' } }
}
function textMsg(text: string, kind?: string): unknown {
  return userMsg([{ type: 'text', text }], kind)
}

describe('工具痕迹跟踪（REQ-2e9473 t05）', () => {
  const handler = (depsObj: ReturnType<typeof deps>) => createSessionEventCaptureHook(depsObj.deps)
  const toolCall = (name: string) => ({ type: 'tool/call', data: { name } })

  it('tool/call 事件按窗口落痕；忽略会话不记', () => {
    const d = deps()
    const toolTrace = new Map<string, ToolTraceEntry[]>()
    d.deps.toolTrace = toolTrace
    const h = handler(d)
    h({ id: W }, toolCall('run_code'))
    h({ id: W }, toolCall('reqboard_task_move'))
    // subagent 会话不记（isIgnoredSession 认 header.origin='subagent' / delegationDepth>0）
    h({ id: 'session-sub-1', header: { origin: 'subagent' } }, toolCall('edit'))
    const act = toolActivitySince(toolTrace, W, 0)
    expect(act.total).toBe(2)
    expect(act.byTool).toEqual({ run_code: 1, reqboard_task_move: 1 })
    expect(act.workLike).toBe(1) // run_code 算干活，reqboard_task_move 不算
    expect(toolTrace.has('session-sub-1')).toBe(false)
  })

  it('toolActivitySince 按时间分段（done 凭证门：since=claimedAt）', () => {
    const trace = new Map<string, ToolTraceEntry[]>()
    recordToolTrace(trace, W, 'bash', 100)
    recordToolTrace(trace, W, 'edit', 200)
    recordToolTrace(trace, W, 'edit', 300)
    expect(toolActivitySince(trace, W, 200).workLike).toBe(2)
    expect(toolActivitySince(trace, W, 400).total).toBe(0)
    // 未知窗口 → 全零，不炸
    expect(toolActivitySince(trace, 'session-nope', 0).total).toBe(0)
  })

  it('环形截断：超过 TOOL_TRACE_CAP 只保留最新', () => {
    const trace = new Map<string, ToolTraceEntry[]>()
    for (let i = 0; i < TOOL_TRACE_CAP + 50; i++) recordToolTrace(trace, W, 'run_code', i)
    expect(trace.get(W)).toHaveLength(TOOL_TRACE_CAP)
    expect(trace.get(W)![0].at).toBe(50) // 最旧的被截掉
  })

  it('turn/end 不清工具痕迹（只清立项捕获登记）', () => {
    const d = deps()
    const toolTrace = new Map<string, ToolTraceEntry[]>()
    d.deps.toolTrace = toolTrace
    const h = handler(d)
    h({ id: W }, toolCall('edit'))
    h({ id: W }, turnEnd())
    expect(toolActivitySince(toolTrace, W, 0).total).toBe(1)
  })
})

describe('shouldCaptureWindow', () => {
  it('unbound 且无 pending → true；bound / hasPending → false', () => {
    expect(shouldCaptureWindow(emptyLedger(), W)).toBe(true)
    const bound: ReqboardLedger = { ...emptyLedger(), requirements: [{ id: 'REQ-1', sourceSessionId: W, status: 'implementing' } as never] }
    expect(shouldCaptureWindow(bound, W)).toBe(false)
    const pending: ReqboardLedger = { ...emptyLedger(), triages: [{ id: 'tri-1', sessionId: W, status: 'pending' } as never] }
    expect(shouldCaptureWindow(pending, W)).toBe(false)
  })
})

describe('createSessionEventCaptureHook', () => {
  it('用户消息到达 unbound 窗口 → 登记待捕获（原文入档）', () => {
    const d = deps()
    const h = createSessionEventCaptureHook(d.deps)
    h({ id: W }, textMsg('帮我写一个日报自动化工具'))
    const entry = d.pending.get(W)
    expect(entry).toBeTruthy()
    expect(entry?.text).toContain('日报自动化')
    expect(entry?.windowKey).toBe(W)
  })
  it('非 user/message 事件不触发（turn/start / assistant 消息等）', () => {
    const d = deps()
    const h = createSessionEventCaptureHook(d.deps)
    h({ id: W }, { type: 'turn/start', data: { turn: 1 } })
    h({ id: W }, { type: 'assistant/message' })
    expect(d.pending.size).toBe(0)
  })
  it('direct-human source 过滤：plugin（agent.inject 注入）kind 跳过', () => {
    const d = deps()
    const h = createSessionEventCaptureHook(d.deps)
    h({ id: W }, textMsg('注意：workspace 文件变更 /Users/x/src/a.ts', 'plugin'))
    expect(d.pending.size).toBe(0)
    expect(d.logs.some(l => l.includes('non-direct-human'))).toBe(true)
  })
  it('source 缺失（未知注入形状）→ 文本清洗兜底放行', () => {
    const d = deps()
    const h = createSessionEventCaptureHook(d.deps)
    h({ id: W }, textMsg('帮我看看这个池子该不该新建', 'none'))
    expect(d.pending.size).toBe(1)
  })
  it('噪声消息（纯系统块）跳过：checkpoint / runtime context', () => {
    const d = deps()
    const h = createSessionEventCaptureHook(d.deps)
    const noise =
      '<system-reminder>Current runtime context...</system-reminder>\n' +
      '<system-reminder>Current DSH file policy: read-only...</system-reminder>\n' +
      'This is an automatically generated checkpoint condensing an earlier span...'
    h({ id: W }, textMsg(noise))
    expect(d.pending.size).toBe(0)
    expect(d.logs.some(l => l.includes('noise-only'))).toBe(true)
  })
  it('忽略会话：subagent / child / session-reqboard-* / parentSession 派生', () => {
    const d = deps()
    const h = createSessionEventCaptureHook(d.deps)
    h({ id: 'subagent-xyz' }, textMsg('帮我写个工具'))
    h({ id: 'session-reqboard-abc' }, textMsg('帮我写个工具'))
    h({ id: W, header: { parentSession: 'session-root' } }, textMsg('帮我写个工具'))
    expect(d.pending.size).toBe(0)
  })
  it('窗口已 bound（直挂 implementing req）→ 不登记', () => {
    const d = deps()
    d.setLedger({ ...emptyLedger(), requirements: [{ id: 'REQ-1', sourceSessionId: W, status: 'implementing' } as never] })
    const h = createSessionEventCaptureHook(d.deps)
    h({ id: W }, textMsg('帮我写个工具'))
    expect(d.pending.size).toBe(0)
    expect(d.logs.some(l => l.includes('bound or has pending'))).toBe(true)
  })
  it('窗口已有 pending 建议卡 → 不登记（不重复 nag）', () => {
    const d = deps()
    d.setLedger({ ...emptyLedger(), triages: [{ id: 'tri-1', sessionId: W, status: 'pending' } as never] })
    const h = createSessionEventCaptureHook(d.deps)
    h({ id: W }, textMsg('帮我写个工具'))
    expect(d.pending.size).toBe(0)
  })
  it('同窗口新消息覆盖旧条目（只跟踪最新）', () => {
    const d = deps()
    const h = createSessionEventCaptureHook(d.deps)
    h({ id: W }, textMsg('第一条消息'))
    h({ id: W }, textMsg('第二条更新的消息'))
    expect(d.pending.size).toBe(1)
    expect(d.pending.get(W)?.text).toContain('第二条')
    expect(d.logs.some(l => l.includes('覆盖旧条目'))).toBe(true)
  })
  it('turn/end 清除待捕获（该回合 LLM 已消费立项评估机会）', () => {
    const d = deps()
    const h = createSessionEventCaptureHook(d.deps)
    h({ id: W }, textMsg('帮我写个工具'))
    expect(d.pending.size).toBe(1)
    h({ id: W }, turnEnd())
    expect(d.pending.size).toBe(0)
  })
  it('session 缺 id / 事件缺 type → 静默忽略', () => {
    const d = deps()
    const h = createSessionEventCaptureHook(d.deps)
    h({}, textMsg('帮我写个工具'))
    h({ id: W }, {})
    expect(d.pending.size).toBe(0)
  })
})
describe('R1 接手推进信号（onBoundWindowActivity）', () => {
  it('bound 窗口收到直接人类消息 → 触发回调一次（带 windowKey 与消息文本）', () => {
    const d = deps()
    const calls: Array<[string, string]> = []
    const h = createSessionEventCaptureHook({ ...d.deps, onBoundWindowActivity: (k, t) => calls.push([k, t]) })
    d.setLedger({ ...emptyLedger(), requirements: [{ id: 'REQ-1', sourceSessionId: W, status: 'draft' } as never] })
    h({ id: W }, textMsg('继续推进这个需求'))
    expect(calls).toHaveLength(1)
    expect(calls[0][0]).toBe(W)
    expect(calls[0][1]).toContain('继续推进')
    // bound 窗口不再登记待捕获（不重复 nag 立项）
    expect(d.pending.size).toBe(0)
  })

  it('unbound 窗口不触发接手推进（仍走立项捕获）', () => {
    const d = deps()
    const calls: string[] = []
    const h = createSessionEventCaptureHook({ ...d.deps, onBoundWindowActivity: (k) => calls.push(k) })
    h({ id: W }, textMsg('帮我做个日报工具'))
    expect(calls).toHaveLength(0)
    expect(d.pending.size).toBe(1)
  })

  it('非直接人类消息（plugin 注入）不触发接手推进', () => {
    const d = deps()
    const calls: string[] = []
    const h = createSessionEventCaptureHook({ ...d.deps, onBoundWindowActivity: (k) => calls.push(k) })
    d.setLedger({ ...emptyLedger(), requirements: [{ id: 'REQ-1', sourceSessionId: W, status: 'draft' } as never] })
    h({ id: W }, textMsg('workspace 文件变更', 'plugin'))
    expect(calls).toHaveLength(0)
  })

  it('未注入回调 → 不抛错（可选依赖）', () => {
    const d = deps()
    const h = createSessionEventCaptureHook(d.deps)
    d.setLedger({ ...emptyLedger(), requirements: [{ id: 'REQ-1', sourceSessionId: W, status: 'draft' } as never] })
    expect(() => h({ id: W }, textMsg('继续'))).not.toThrow()
  })
})


describe('REQ-31e11f t5：onStagePrompt 阶段提示词注入', () => {
  it('bound 窗口收到消息 → 触发 onStagePrompt（带当前阶段提示词）', async () => {
    const d = deps()
    const prompts: string[] = []
    const h = createSessionEventCaptureHook({
      ...d.deps,
      onStagePrompt: (_key, prompt) => prompts.push(prompt),
    })
    d.setLedger({
      ...emptyLedger(),
      requirements: [{ id: 'REQ-1', sourceSessionId: W, status: 'implementing', category: 'feature' } as never],
    })
    h({ id: W }, textMsg('继续推进'))
    expect(prompts).toHaveLength(1)
    // 断言与唯一取词入口同源（旧的 STAGE_PROMPTS 常量表/旧分片名已下线）：
    // 注入的就是 resolveStagePrompt 按当前阶段+类型+需求实质算出来的那段文本。
    const { resolveStagePrompt } = await import('../src/domain/prompt/index.js')
    const expected = resolveStagePrompt({
      stage: 'implementing', category: 'feature', requirement: { title: undefined, description: undefined },
    })
    expect(prompts[0]).toContain(expected.text)
    expect(expected.text.length).toBeGreaterThan(0)
  })

  it('分类跳过的阶段不触发 onStagePrompt', async () => {
    const d = deps()
    const prompts: string[] = []
    const h = createSessionEventCaptureHook({
      ...d.deps,
      onStagePrompt: (_key, prompt) => prompts.push(prompt),
    })
    // bug 分类：无 brainstorming 阶段
    d.setLedger({
      ...emptyLedger(),
      requirements: [{ id: 'REQ-1', sourceSessionId: W, status: 'draft', category: 'bug' } as never],
    })
    h({ id: W }, textMsg('开始'))
    // draft 阶段无对应提示词（STAGE_PROMPTS 无 draft 键）→ 不触发
    expect(prompts).toHaveLength(0)
  })

  it('未注入 onStagePrompt 回调 → 不抛错（可选依赖）', async () => {
    const d = deps()
    const h = createSessionEventCaptureHook(d.deps)
    d.setLedger({
      ...emptyLedger(),
      requirements: [{ id: 'REQ-1', sourceSessionId: W, status: 'implementing', category: 'feature' } as never],
    })
    expect(() => h({ id: W }, textMsg('继续'))).not.toThrow()
  })
})

describe('里程碑超时提醒（REQ-2e9473 t09）', () => {
  it('产物登记 >30min 未确认 → 注入提醒，含 reqboard_ask_confirm 调用指引', () => {
    const injected: string[] = []
    const d = deps()
    const testNow = 2000000000000 // 固定时间避免 deps.now() 为 1000 导致负数
    d.deps.now = () => testNow
    d.deps.onStagePrompt = (_w, text) => { injected.push(text) }
    const h = createSessionEventCaptureHook(d.deps)
    d.setLedger({
      ...emptyLedger(),
      requirements: [{
        id: 'REQ-abc',
        title: 'test',
        description: '',
        sourceSessionId: W,
        status: 'brainstorming',
        category: 'feature',
        blocked: false,
        comments: [],
        version: 1,
        createdAt: 1,
        updatedAt: testNow,
        createdBy: { kind: 'human' },
        updatedBy: { kind: 'human' },
        statusHistory: [],
        artifacts: [{ stage: 'brainstorming', kind: 'requirement', path: 'r.md', registeredAt: testNow - 31 * 60 * 1000 }],
      } as never],
    })
    h({ id: W }, textMsg('继续'))
    expect(injected.some(t => t.includes('里程碑提醒'))).toBe(true)
    expect(injected.some(t => t.includes('reqboard_ask_confirm'))).toBe(true)
    expect(injected.some(t => t.includes('kind=requirement'))).toBe(true)
  })

  it('每产物只提醒一次：第二条消息不重复注入', () => {
    const injected: string[] = []
    const d = deps()
    const testNow = 2000000000000
    d.deps.now = () => testNow
    d.deps.onStagePrompt = (_w, text) => { injected.push(text) }
    const h = createSessionEventCaptureHook(d.deps)
    d.setLedger({
      ...emptyLedger(),
      requirements: [{
        id: 'REQ-abc', title: 'test', description: '', sourceSessionId: W, status: 'brainstorming', category: 'feature',
        blocked: false, comments: [], version: 1, createdAt: 1, updatedAt: testNow,
        createdBy: { kind: 'human' }, updatedBy: { kind: 'human' }, statusHistory: [],
        artifacts: [{ stage: 'brainstorming', kind: 'requirement', path: 'r.md', registeredAt: testNow - 31 * 60 * 1000 }],
      } as never],
    })
    h({ id: W }, textMsg('继续'))
    const count1 = injected.filter(t => t.includes('里程碑提醒')).length
    h({ id: W }, textMsg('再来'))
    const count2 = injected.filter(t => t.includes('里程碑提醒')).length
    expect(count1).toBe(1)
    expect(count2).toBe(1)
  })

  it('产物已确认 → 不提醒', () => {
    const injected: string[] = []
    const d = deps()
    const testNow = 2000000000000
    d.deps.now = () => testNow
    d.deps.onStagePrompt = (_w, text) => { injected.push(text) }
    const h = createSessionEventCaptureHook(d.deps)
    d.setLedger({
      ...emptyLedger(),
      requirements: [{
        id: 'REQ-abc', title: 'test', description: '', sourceSessionId: W, status: 'brainstorming', category: 'feature',
        blocked: false, comments: [], version: 1, createdAt: 1, updatedAt: testNow,
        createdBy: { kind: 'human' }, updatedBy: { kind: 'human' }, statusHistory: [],
        artifacts: [{
          stage: 'brainstorming', kind: 'requirement', path: 'r.md',
          registeredAt: testNow - 31 * 60 * 1000, confirmedAt: testNow,
        }],
      } as never],
    })
    h({ id: W }, textMsg('继续'))
    expect(injected.some(t => t.includes('里程碑提醒'))).toBe(false)
  })

  it('产物新鲜（<30min）→ 不提醒', () => {
    const injected: string[] = []
    const d = deps()
    const testNow = 2000000000000
    d.deps.now = () => testNow
    d.deps.onStagePrompt = (_w, text) => { injected.push(text) }
    const h = createSessionEventCaptureHook(d.deps)
    d.setLedger({
      ...emptyLedger(),
      requirements: [{
        id: 'REQ-abc', title: 'test', description: '', sourceSessionId: W, status: 'brainstorming', category: 'feature',
        blocked: false, comments: [], version: 1, createdAt: 1, updatedAt: testNow,
        createdBy: { kind: 'human' }, updatedBy: { kind: 'human' }, statusHistory: [],
        artifacts: [{ stage: 'brainstorming', kind: 'requirement', path: 'r.md', registeredAt: testNow - 10 * 60 * 1000 }],
      } as never],
    })
    h({ id: W }, textMsg('继续'))
    expect(injected.some(t => t.includes('里程碑提醒'))).toBe(false)
  })
})
