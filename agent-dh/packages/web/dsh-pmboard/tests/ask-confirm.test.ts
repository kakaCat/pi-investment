/**
 * reqboard_ask_confirm 单测（REQ-2e9473 t07/W1，事故 A 修复）。
 * 覆盖：肯定答复 → 落章+推进原子完成；非肯定 → 不落章不推进；弹框通道降级
 * （服务缺失 / DELEGATED_CALLER）→ fallback=board；target=plan 批准+推进。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync, readFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { defineAskConfirmTool, defineMoveTool } from './helpers/tool-deps.js'
import { LIMITS } from '../src/domain/limits.js'
import type { RequirementRecord, RequirementStatus, StageArtifact } from '../src/shared/protocol.js'

const W = 'session-abc-123'
let dir: string
let store: ReqboardStore

function makeSvc(behavior: 'yes' | 'no' | 'delegated' | 'abort') {
  return {
    ask: async () => {
      if (behavior === 'delegated') throw Object.assign(new Error('owned child'), { code: 'DELEGATED_CALLER' })
      if (behavior === 'abort') throw Object.assign(new Error('aborted'), { code: 'ASK_ABORTED' })
      return {
        answers: [{
          id: 'confirm',
          selected: [behavior === 'yes' ? '确认，推进到下一阶段 (Recommended)' : '需要修改'],
        }],
      }
    },
  }
}

function makeTool(behavior?: 'yes' | 'no' | 'delegated' | 'abort') {
  const deps = {
    store,
    now: () => Date.now(),
    ...(behavior !== undefined ? { userQuestions: () => makeSvc(behavior) } : {}),
  } as never
  return defineAskConfirmTool(deps) as never as { execute: (a: unknown, e: unknown) => Promise<any> }
}

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-askconfirm-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

async function seed(status: RequirementStatus, withArtifact = true): Promise<void> {
  const r = {
    id: 'REQ-abc123', title: '看板需求', description: '', status, blocked: false,
    sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    statusHistory: [{ status: 'draft', at: 1, by: { kind: 'human' } }],
    ...(withArtifact
      ? { artifacts: [{ stage: 'brainstorming', kind: 'requirement', path: 'docs/requirements/REQ-abc123/requirement.md', registeredAt: 1 } as StageArtifact] }
      : {}),
  } as RequirementRecord
  await store.mutate('requirement-created', (l) => { l.requirements.push(r); return { requirements: [r] } })
}

const run = (tool: { execute: (a: unknown, e: unknown) => Promise<any> }, args: unknown) =>
  tool.execute(args, { agent: { id: W } })

const ARGS = { target: 'artifact', kind: 'requirement', question: '需求文档已完成，是否确认进入设计？' }

describe('reqboard_ask_confirm', () => {
  it('肯定答复 → 落章 + 自动推进（brainstorming → design），evidence 留痕', async () => {
    await seed('brainstorming')
    const out = await run(makeTool('yes'), ARGS)
    expect(out.confirmed).toBe(true)
    expect(out.advanced).toBe(true)
    expect(out.from).toBe('brainstorming')
    expect(out.to).toBe('design')
    const req = store.snapshot().requirements[0]
    expect(req.status).toBe('design')
    const art = req.artifacts![0]
    expect(art.confirmedAt).toBeDefined()
    expect(art.confirmedVia).toBe('session')
    expect(art.confirmedEvidence).toMatch(/reqboard_ask_confirm/)
  })

  it('选"需要修改" → 不落章、不推进、留痕', async () => {
    await seed('brainstorming')
    const out = await run(makeTool('no'), ARGS)
    expect(out.confirmed).toBe(false)
    expect(out.advanced).toBe(false)
    const req = store.snapshot().requirements[0]
    expect(req.status).toBe('brainstorming')
    expect(req.artifacts![0].confirmedAt).toBeUndefined()
    expect(req.comments.some(c => c.body.includes('未确认'))).toBe(true)
  })

  it('userQuestions 服务缺失 → fallback=board（不死锁，提示看板通道）', async () => {
    await seed('brainstorming')
    const out = await run(makeTool(undefined), ARGS)
    expect(out.confirmed).toBe(false)
    expect(out.fallback).toBe('board')
    expect(out.note).toMatch(/看板/)
  })

  it('subagent 调用（DELEGATED_CALLER）→ fallback=board 降级提示', async () => {
    await seed('brainstorming')
    const out = await run(makeTool('delegated'), ARGS)
    expect(out.confirmed).toBe(false)
    expect(out.fallback).toBe('board')
  })

  it('用户取消（ASK_ABORTED）→ 中性返回不报错、不推进', async () => {
    await seed('brainstorming')
    const out = await run(makeTool('abort'), ARGS)
    expect(out.confirmed).toBe(false)
    expect(out.fallback).toBeUndefined()
    expect(store.snapshot().requirements[0].status).toBe('brainstorming')
  })

  it('target=plan：肯定答复 → 批准计划 + 推进 design → decomposing', async () => {
    await seed('design', false)
    await store.mutate('seed-plan', (l) => {
      const r = l.requirements[0]
      r.plan = {
        path: 'p.md', summary: 's', submittedAt: 1, submittedBy: { kind: 'agent' },
        tasks: [{ key: 'a', title: 'x', acceptance: '单测绿', implementation: '改 x.ts' }],
      } as never
      return { requirements: [r] }
    })
    const out = await run(makeTool('yes'), { target: 'plan', question: '计划已完成，是否批准进入拆分？' })
    expect(out.confirmed).toBe(true)
    expect(out.advanced).toBe(true)
    expect(out.to).toBe('decomposing')
    const req = store.snapshot().requirements[0]
    expect(req.plan?.approvedAt).toBeDefined()
    expect(req.plan?.approvedVia).toBe('session')
  })

  it('闸门问题卡（t08）：move 被人工闸门拒绝时返回可直接喂给 ask_confirm 的问题卡', async () => {
    await seed('brainstorming') // 带 requirement 产物但未确认
    const move = defineMoveTool({ store, now: () => Date.now() } as never) as never as { execute: (a: unknown, e: unknown) => Promise<any> }
    try {
      await run(move, { to: 'design' })
      expect.unreachable('应被闸门拒绝')
    } catch (err) {
      const msg = (err as Error).message
      expect(msg).toMatch(/问题卡/)
      expect(msg).toMatch(/reqboard_ask_confirm/)
      expect(msg).toMatch(/kind: 'requirement'/)
      expect(msg).toMatch(/是否确认进入设计/)
    }
  })

  it('缺产物时落章失败（kind 对不上）', async () => {
    await seed('brainstorming', false)
    await expect(run(makeTool('yes'), ARGS)).rejects.toThrow(/没有 kind=requirement 的产物/)
  })
})

describe('T-E3: 弹框题干长度纪律（REQ-308b9a t5 / AC-7.6）', () => {
  it('超长题干被截到 popupQuestionMax（防选项被挤出可视区）', async () => {
    await seed('brainstorming')
    const seen: string[] = []
    const deps = {
      store,
      now: () => Date.now(),
      userQuestions: () => ({
        ask: async (qs: { question?: string }[]) => {
          seen.push(qs[0]?.question ?? '')
          return { answers: [{ id: 'confirm', selected: ['确认，推进到下一阶段 (Recommended)'] }] }
        },
      }),
    } as never
    const tool = defineAskConfirmTool(deps) as never as { execute: (a: unknown, e: unknown) => Promise<any> }
    await run(tool, { target: 'artifact', kind: 'requirement', question: '很长的题干'.repeat(100) })
    expect(seen).toHaveLength(1)
    expect(seen[0].length).toBeLessThanOrEqual(LIMITS.popupQuestionMax)
  })
})

describe('T-7: 确认门纪律与防重弹（REQ-260922213356-4a45 FR-9/FR-11）', () => {
  it('同一产物已确认 → 不再弹框（弹框端口调用 0 次）', async () => {
    await seed('brainstorming')
    const first = await run(makeTool('yes'), ARGS)
    expect(first.confirmed).toBe(true)
    let asked = 0
    const deps = {
      store,
      now: () => Date.now(),
      userQuestions: () => ({ ask: async () => { asked += 1; return { answers: [] } } }),
    } as never
    const tool = defineAskConfirmTool(deps) as never as { execute: (a: unknown, e: unknown) => Promise<any> }
    const out = await run(tool, ARGS)
    expect(asked).toBe(0)
    expect(out.confirmed).toBe(true)
    expect(String(out.note)).toContain('已确认')
  })

  it('iron-rules 含三条确认纪律（先答后确认 / 文字确认走 evidence / 同产物不重复弹框）', () => {
    const p = fileURLToPath(new URL('../src/domain/prompt/fragments/common/iron-rules.md', import.meta.url))
    const text = readFileSync(p, 'utf8')
    expect(text).toContain('确认门对话优先')
    expect(text).toContain('文字确认走 evidence')
    expect(text).toContain('同一产物不重复弹框')
  })
})
