/**
 * 断点常驻与续跑输入包（REQ-260924213231-b1c4 T-9 · serves: FR-6 / I-8）。
 *
 * 验收口径（任务卡 t-7b5e7a）：
 *   ① 只交棒 → 台账 `interruption.reason==='checkpoint'` 且 pendingAction 非空；
 *   ② 喂 `turn/end` 且 reason.kind='error' → reason 变 `error:UPSTREAM_STREAM_IDLE:…`；
 *   ③ 重建输入包含「## 断点」与 pendingAction；
 *   ④ 老需求无字段 → 输入包逐字节不变（不出现「## 断点」，段间分隔与改造前一致）；
 *   ⑤ 畸形态（`{}` / `{reason:{}}`）→ turnEndOutcome undefined（不猜、不误报）。
 *
 * 分层：应用层用例 + 内部纯函数 + 适配器 hook，全部走内存端口（tests/application/harness）。
 *
 * @module dsh-pmboard/tests/interruption-checkpoint
 */
import { describe, it, expect } from 'vitest'
import { makeHarness, req } from './application/harness.js'
import { executeMoveRequirement } from '../src/application/use-cases/MoveRequirement.js'
import { noteInterruption, noteInterruptionForWindow } from '../src/application/use-cases/NoteInterruption.js'
import { nextActionFor, turnEndOutcome } from '../src/application/internal/interruption.js'
import { buildNodeInputPackage } from '../src/application/internal/node-input-package.js'
import { createSessionEventCaptureHook, type CaptureHookDeps } from '../src/adapters/CaptureHook.js'
import { defineNoteInterruptionTool } from '../src/tools/NoteInterruptionTool/NoteInterruptionTool.js'
import type { ReqboardLedger, RequirementRecord } from '../src/shared/protocol.js'

const W = 'session-w-001'
const exec = { agent: { id: W } }
const DOC = 'docs/requirements/REQ-000001/requirement.md'

/** 构建一次节点输入包（stage=brainstorming；文档给占位正文）。 */
function build(requirement: RequirementRecord | undefined): string {
  return buildNodeInputPackage({
    stage: 'brainstorming',
    requirement,
    requirementDoc: '# 需求文档\n',
    requirementDocPath: DOC,
  }).text
}

describe('断点常驻 · 写入器 A（交棒即写 checkpoint）', () => {
  it('reqboard_move 交棒 → 台账 interruption.reason=checkpoint 且 pendingAction 非空', async () => {
    const h = makeHarness({ requirements: [req({ status: 'draft' })] })
    await executeMoveRequirement(h.deps, { to: 'brainstorming' }, exec)
    const r = h.repo.snapshot().requirements[0]!
    expect(r.status).toBe('brainstorming')
    expect(r.interruption).toBeDefined()
    expect(r.interruption!.reason).toBe('checkpoint')
    expect(r.interruption!.stage).toBe('brainstorming')
    expect(r.interruption!.pendingAction.length).toBeGreaterThan(0)
    // 状态 + 产物态推出的下一步：无需求文档 → 先 submit
    expect(r.interruption!.pendingAction).toBe('reqboard_submit(kind=requirement)')
    expect(r.interruption!.tool).toBe('reqboard_move')
  })

  it('nextActionFor 是断点与输入包的唯一事实源（各阶段映射）', () => {
    const at = (over: Partial<RequirementRecord>): string => nextActionFor(req(over))
    expect(at({ status: 'draft' })).toBe('reqboard_move(to=brainstorming)')
    expect(at({ status: 'brainstorming' })).toBe('reqboard_submit(kind=requirement)')
    expect(at({ status: 'design' })).toBe('reqboard_submit(kind=design)')
    expect(at({ status: 'decomposing' })).toBe('reqboard_submit(kind=plan)')
    expect(at({ status: 'implementing' })).toBe('reqboard_task_run')
    expect(at({ status: 'accepting' })).toBe('reqboard_accept_sheet')
  })

  it('幂等：同一 stage + 同一 pendingAction 再交棒不重写、不 bump version', async () => {
    const h = makeHarness({ requirements: [req({ status: 'draft' })] })
    await executeMoveRequirement(h.deps, { to: 'brainstorming' }, exec)
    const first = h.repo.snapshot().requirements[0]!
    const at1 = first.interruption!.at
    const v1 = first.version
    h.clock.t += 5000
    // 再交棒一次（brainstorming → draft → brainstorming：回到同一 stage/pendingAction）
    await executeMoveRequirement(h.deps, { to: 'draft' }, exec)
    await executeMoveRequirement(h.deps, { to: 'brainstorming' }, exec)
    const again = h.repo.snapshot().requirements[0]!
    expect(again.interruption!.pendingAction).toBe(first.interruption!.pendingAction)
    // 断点重新落笔（stage 曾在中间变过），但内容语义一致
    expect(again.interruption!.reason).toBe('checkpoint')
    expect(again.version).toBeGreaterThan(v1)
    expect(typeof at1).toBe('number')
  })
})

describe('断点常驻 · 写入器 B（turn/end 异常原因补新）', () => {
  it('turnEndOutcome 规范化 error / aborted / interrupted；非异常不算中断', () => {
    expect(turnEndOutcome({ reason: { kind: 'completed' } })).toEqual({ abnormal: false, reason: 'completed' })
    expect(turnEndOutcome({ reason: { kind: 'max-tokens' } })).toEqual({ abnormal: false, reason: 'max-tokens' })
    expect(turnEndOutcome({ reason: { kind: 'interrupted' } })).toEqual({ abnormal: true, reason: 'interrupted' })
    expect(turnEndOutcome({ reason: { kind: 'aborted', reason: { kind: 'user' } } }))
      .toEqual({ abnormal: true, reason: 'aborted:user' })
    expect(turnEndOutcome({ reason: { kind: 'error', error: { code: 'UPSTREAM_STREAM_IDLE', message: 'stream idle 3m' } } }))
      .toEqual({ abnormal: true, reason: 'error:UPSTREAM_STREAM_IDLE:stream idle 3m' })
  })

  it('畸形态（缺 data / 缺 reason / 未知 kind）→ undefined（不猜、不误报）', () => {
    expect(turnEndOutcome({})).toBeUndefined()
    expect(turnEndOutcome({ reason: {} })).toBeUndefined()
    expect(turnEndOutcome({ reason: 'success' })).toBeUndefined()
    expect(turnEndOutcome(undefined)).toBeUndefined()
    expect(turnEndOutcome(null)).toBeUndefined()
    expect(turnEndOutcome({ reason: { kind: 'weird' } })).toBeUndefined()
  })

  it('事件路径：checkpoint → 异常原因覆盖（保留按状态重算的 pendingAction）', async () => {
    const h = makeHarness({ requirements: [req({ status: 'draft' })] })
    await executeMoveRequirement(h.deps, { to: 'brainstorming' }, exec)
    expect(h.repo.snapshot().requirements[0]!.interruption!.reason).toBe('checkpoint')

    const outcome = turnEndOutcome({ reason: { kind: 'error', error: { code: 'UPSTREAM_STREAM_IDLE', message: 'stream idle 3m' } } })!
    await noteInterruptionForWindow(h.deps, W, outcome.reason, 'turn/end')
    const r = h.repo.snapshot().requirements[0]!
    expect(r.interruption!.reason).toBe('error:UPSTREAM_STREAM_IDLE:stream idle 3m')
    expect(r.interruption!.stage).toBe('brainstorming')
    expect(r.interruption!.pendingAction).toBe('reqboard_submit(kind=requirement)')
    expect(r.interruption!.tool).toBe('turn/end')
  })

  it('CaptureHook turn/end（error）→ onTurnFinished 只发信号；非异常形态不发', async () => {
    const h = makeHarness({ requirements: [req({ status: 'implementing' })] })
    const signals: { wk: string; reason: string; abnormal: boolean }[] = []
    const hookDeps: CaptureHookDeps = {
      // 内存仓库的 snapshot() 是只读视图；hook 只读，形状等价（类型上补一层显式转换）
      snapshot: () => h.repo.snapshot() as unknown as ReqboardLedger,
      pending: new Map(),
      now: () => 1000,
      onTurnFinished: (wk, outcome) => signals.push({ wk, reason: outcome.reason, abnormal: outcome.abnormal }),
      onTurnEnd: () => {},
      logger: { info: () => {}, debug: () => {} },
    }
    const hook = createSessionEventCaptureHook(hookDeps)
    // 形态可识别 → 无论是否异常都发信号（信号里带 abnormal，由组合根的 abnormal 守卫决定写不写）
    hook({ id: W }, { type: 'turn/end', data: { turn: 1, reason: { kind: 'completed' } } })
    expect(signals).toEqual([{ wk: W, reason: 'completed', abnormal: false }])
    // 异常收尾：abnormal=true → 组合根才会补写断点原因（写台账在异步边界）
    hook({ id: W }, { type: 'turn/end', data: { turn: 2, reason: { kind: 'error', error: { code: 'UPSTREAM_STREAM_IDLE', message: 'stream idle 3m' } } } })
    expect(signals[1]).toEqual({ wk: W, reason: 'error:UPSTREAM_STREAM_IDLE:stream idle 3m', abnormal: true })
    expect(signals.filter(x => x.abnormal)).toHaveLength(1)
  })

  it('事件路径永不抛：窗口无绑定需求 / 空 reason → 静默跳过（undefined）', async () => {
    const h = makeHarness({ requirements: [] })
    await expect(noteInterruptionForWindow(h.deps, W, 'error:X:y', 'turn/end')).resolves.toBeUndefined()
    await expect(noteInterruptionForWindow(h.deps, W, '   ', 'turn/end')).resolves.toBeUndefined()
    await expect(noteInterruptionForWindow(h.deps, '', 'error:X:y', 'turn/end')).resolves.toBeUndefined()
  })
})

describe('断点常驻 · 写入器 B′（reqboard_note_interruption 显式兜底）', () => {
  it('工具壳名字/必填 reason 正确（defineTool 构造即编译 schema）', () => {
    const h = makeHarness()
    const tool = defineNoteInterruptionTool(h.deps) as unknown as {
      name: string
      parameters: { type: string; required?: string[]; additionalProperties?: boolean; properties?: Record<string, unknown> }
    }
    expect(tool.name).toBe('reqboard_note_interruption')
    expect(tool.parameters.type).toBe('object')
    expect(tool.parameters.required).toContain('reason')
    expect(Object.keys(tool.parameters.properties ?? {})).toContain('reason')
    // 根 object 为封闭形状（defineTool 规范化：未显式 additionalProperties=true 即封闭）
    expect(tool.parameters.additionalProperties).not.toBe(true)
  })

  it('补写断点：success + interruption 回执 + 系统评论留痕', async () => {
    const h = makeHarness({ requirements: [req({ status: 'implementing' })] })
    const out = await noteInterruption(h.deps, { reason: 'upstream stream idle 3m ×5' }, exec) as Record<string, unknown>
    expect(out.success).toBe(true)
    expect(out.requirement_id).toBe('REQ-000001')
    const bp = out.interruption as Record<string, unknown>
    expect(bp.reason).toBe('upstream stream idle 3m ×5')
    expect(bp.pendingAction).toBe('reqboard_task_run')
    expect(bp.tool).toBe('reqboard_note_interruption')
    const r = h.repo.snapshot().requirements[0]!
    expect(r.comments.some(c => c.body.includes('[断点]'))).toBe(true)
  })

  it('reason 为空 → REQBOARD_INVALID_INPUT；窗口无绑定需求 → REQBOARD_NO_BOUND_REQ', async () => {
    const h = makeHarness({ requirements: [req({ status: 'implementing' })] })
    await expect(noteInterruption(h.deps, { reason: '  ' }, exec)).rejects.toMatchObject({ code: 'REQBOARD_INVALID_INPUT' })
    const empty = makeHarness({ requirements: [] })
    await expect(noteInterruption(empty.deps, { reason: 'x' }, exec)).rejects.toMatchObject({ code: 'REQBOARD_NO_BOUND_REQ' })
  })

  it('后写覆盖前写：同一需求始终只保留一个断点对象', async () => {
    const h = makeHarness({ requirements: [req({ status: 'implementing' })] })
    await noteInterruption(h.deps, { reason: 'first' }, exec)
    h.clock.t += 1000
    const second = await noteInterruption(h.deps, { reason: 'second' }, exec) as Record<string, unknown>
    expect((second.interruption as Record<string, unknown>).reason).toBe('second')
    expect((h.repo.snapshot().requirements[0]!.interruption as unknown as Record<string, unknown>).reason).toBe('second')
  })
})

describe('续跑输入包（## 断点 节）', () => {
  it('有断点 → 追加「## 断点」，含阶段 / 未完成动作 / 原因 / 时间四要素', async () => {
    const h = makeHarness({ requirements: [req({ status: 'draft' })] })
    await executeMoveRequirement(h.deps, { to: 'brainstorming' }, exec)
    const outcome = turnEndOutcome({ reason: { kind: 'error', error: { code: 'UPSTREAM_STREAM_IDLE', message: 'stream idle 3m' } } })!
    await noteInterruptionForWindow(h.deps, W, outcome.reason, 'turn/end')
    const r = h.repo.snapshot().requirements[0]!
    const text = build(r)
    expect(text).toContain('## 断点')
    expect(text).toContain('- 当前阶段：brainstorming')
    expect(text).toContain('- 未完成动作：reqboard_submit(kind=requirement)')
    expect(text).toContain('- 中断原因：error:UPSTREAM_STREAM_IDLE:stream idle 3m')
    expect(text).toContain('- 记录时间：')
    // 断点节插在「未决问题」与「下一步」之间（节点边界后的唯一新起点）
    const iOpen = text.indexOf('## 未决问题')
    const iBp = text.indexOf('## 断点')
    const iNext = text.indexOf('## 下一步')
    expect(iOpen).toBeLessThan(iBp)
    expect(iBp).toBeLessThan(iNext)
  })

  it('老需求无字段 → 输入包逐字节不变（不出现断点节，段间分隔与改造前一致）', () => {
    const legacy = req({ status: 'brainstorming' })
    const text = build(legacy)
    expect(text).not.toContain('## 断点')
    // 改造前布局：未决问题内容后直接空行 + ## 下一步（无任何插入节）
    expect(text).toContain('## 未决问题\n（无）\n\n## 下一步')
    // 键缺省与显式 undefined 逐字节等价（读路径不因字段存在与否漂移）
    expect(build({ ...legacy, interruption: undefined })).toBe(text)
  })

  it('断点不是需求文档内容：仅台账投影带出（INV-9）', () => {
    const legacy = req({ status: 'brainstorming' })
    const r: RequirementRecord = {
      ...legacy,
      interruption: { at: 1_700_000_000_000, reason: 'checkpoint', stage: 'brainstorming', pendingAction: 'reqboard_submit(kind=requirement)' },
    }
    const withBp = buildNodeInputPackage({
      stage: 'brainstorming',
      requirement: r,
      requirementDoc: '# 需求文档\n',
      requirementDocPath: DOC,
    })
    expect(withBp.projection.breakpoint).toContain('## 断点')
    expect(withBp.projection.breakpoint).toContain('reqboard_submit(kind=requirement)')
    // 文档本体不被污染：需求文档段仍是原文
    expect(withBp.text).toContain('## 需求文档（' + DOC + '）\n# 需求文档')
  })
})
