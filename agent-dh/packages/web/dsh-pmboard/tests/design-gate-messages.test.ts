/**
 * G2 闸门文案分化单测（REQ-260924213231-b1c4 T-5 · serves: FR-2）
 *
 * 验收口径（design/test-cases.md TC-2/TC-3/TC-4 + 父卡 acceptance）：
 *  - TC-2 文档落盘但未登记 → 拒绝消息含「未登记」+ `reqboard_submit(kind=design)`；
 *  - TC-3 已登记未落章 → 拒绝消息含「待确认」+ `reqboard_ask_confirm`；
 *  - 两串不相同（同一条 `design_doc_incomplete`，两种病因两种话——A2）；
 *  - TC-4 全部落章但磁盘多出一份未登记 → ask_confirm 早返回 confirmed=true / advanced=false
 *    且 `gate_failure.gaps` 点名未登记件（消解「已确认，未重复弹框」与 move 汇报的互相矛盾）。
 *
 * 关于「待确认」的落点：move/看板全路径上 `assertArtifactGates` 的 `artifact_not_confirmed`
 * 门先于 G2 完整性门拦截（见 tests/design-completeness-gate.test.ts「已登记但未确认」例），
 * 故「待确认」文案同时锁在**闸门函数** `checkDesignCompletenessGate` 这一层。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync, mkdirSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { FileDocRepository } from '../src/adapters/FileDocRepository.js'
import { defineMoveTool, defineAskConfirmTool } from './helpers/tool-deps.js'
import { checkDesignCompletenessGate } from '../src/application/internal/design-gates.js'
import type { RequirementRecord, StageArtifact } from '../src/shared/protocol.js'

const W = 'session-t5-001'
const REQ = 'REQ-t50001'
const DESIGN5 = ['architecture.md', 'data-model.md', 'interfaces.md', 'test-cases.md', 'use-cases.md']
const DESIGN4 = DESIGN5.slice(0, 4) // 缺 use-cases.md
const DESIGN_DIR = 'docs/requirements/' + REQ + '/design'

let dir: string
let store: ReqboardStore

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-g2-msg-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

function reqDoc(): string {
  return '---\nreq: ' + REQ + '\n---\n\n# 需求\n\n## 边界\n不做范围外的事。\n\n## 产品定义\nx\n\n## 用户与角色\nx\n\n## 功能点\n\n### FR-1: 甲\nx\n'
}

function writeDocset(designNames: readonly string[]): void {
  mkdirSync(join(dir, 'docs/requirements', REQ, 'design'), { recursive: true })
  writeFileSync(join(dir, 'docs/requirements', REQ, 'requirement.md'), reqDoc())
  for (const n of designNames) writeFileSync(join(dir, DESIGN_DIR, n), '# ' + n + '\n')
}

interface SeedOpts { registered: readonly string[]; unconfirmed?: readonly string[] }

async function seed(opts: SeedOpts): Promise<void> {
  const unconfirmed = new Set(opts.unconfirmed ?? [])
  const artifacts: StageArtifact[] = opts.registered.map(name => ({
    stage: 'design', kind: 'design', path: DESIGN_DIR + '/' + name,
    registeredAt: 1, registeredBy: { kind: 'agent', sessionId: W },
    ...(unconfirmed.has(name) ? {} : { confirmedAt: 1, confirmedBy: { kind: 'human' } }),
  }) as StageArtifact)
  const r = {
    id: REQ, title: 'G2 文案', description: '', category: 'feature',
    status: 'design', blocked: false, sourceSessionId: W,
    comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' }, statusHistory: [],
    artifacts,
  } as unknown as RequirementRecord
  await store.mutate('seed', (l) => { l.requirements.push(r); return { requirements: [r] } })
}

const run = (tool: { execute: (a: unknown, e: unknown) => Promise<any> }, args: unknown) =>
  tool.execute(args, { agent: { id: W } })

const moveTool = () => defineMoveTool({ store, now: () => 1000, workspaceRoot: dir } as never) as never as { execute: (a: unknown, e: unknown) => Promise<any> }

const askTool = () => defineAskConfirmTool({
  store, now: () => 1000, workspaceRoot: dir,
  userQuestions: () => ({ ask: async () => ({ answers: [{ id: 'confirm', selected: ['确认，进入拆分'] }] }) }),
} as never) as never as { execute: (a: unknown, e: unknown) => Promise<any> }

const ASK_ARGS = { target: 'artifact', kind: 'design', question: '设计文档已完成，是否确认进入拆分？', options: ['确认，进入拆分', '需要修改'] }

/** 捕获拒绝（返回 code/message；没抛 = 用例失败）。 */
async function rejection(fn: () => Promise<unknown>): Promise<{ code?: string; message: string }> {
  try {
    await fn()
  } catch (e) {
    const err = e as { code?: string; message: string }
    return { code: err.code, message: err.message }
  }
  throw new Error('预期被拒，但调用成功了')
}

const docsReader = () => new FileDocRepository({ workspaceRoot: dir })

describe('TC-2/TC-3 两种病因两种话（同一 code，两串不相同）', () => {
  it('TC-2 未登记：move 拒绝消息含「未登记」+ reqboard_submit(kind=design)，且带 why/how 信封', async () => {
    writeDocset(DESIGN5)
    await seed({ registered: DESIGN4 })
    const err = await rejection(() => run(moveTool(), { to: 'decomposing' }))
    expect(err.code).toBe('design_doc_incomplete')
    expect(err.message).toContain('design_doc_incomplete')
    expect(err.message).toContain('未登记')
    expect(err.message).toContain('reqboard_submit(kind=design)')
    expect(err.message).toContain('——')
    expect(err.message).toContain('补齐：')
  })

  it('TC-3 待确认：move 拒绝消息含「待确认」+ reqboard_ask_confirm', async () => {
    writeDocset(DESIGN5)
    await seed({ registered: DESIGN5, unconfirmed: ['use-cases.md'] })
    const err = await rejection(() => run(moveTool(), { to: 'decomposing' }))
    expect(err.code).toBe('REQBOARD_ARTIFACT_NOT_CONFIRMED')
    expect(err.message).toContain('待确认')
    expect(err.message).toContain('reqboard_ask_confirm')
  })

  it('TC-3 待确认（闸门函数层）：checkDesignCompletenessGate 同 code 出「待确认」+ 确认命令', async () => {
    writeDocset(DESIGN5)
    await seed({ registered: DESIGN5, unconfirmed: ['use-cases.md'] })
    const gate = await checkDesignCompletenessGate(docsReader() as never, store.snapshot().requirements[0])
    expect(gate?.code).toBe('design_doc_incomplete')
    expect(gate?.message).toContain('待确认')
    expect(gate?.message).toContain('reqboard_ask_confirm(target=artifact, kind=design)')
    expect(gate?.message).toContain('——')
    expect(gate?.message).toContain('补齐：')
  })

  it('同一条 design_doc_incomplete，「未登记」与「待确认」两串不相同', async () => {
    writeDocset(DESIGN5)
    const base = { id: REQ, category: 'feature' } as unknown as RequirementRecord
    const arts = (names: readonly string[], unconfirmed: string[]) => names.map(name => ({
      stage: 'design', kind: 'design', path: DESIGN_DIR + '/' + name, registeredAt: 1,
      ...(unconfirmed.includes(name) ? {} : { confirmedAt: 1 }),
    }))
    const unregistered = await checkDesignCompletenessGate(docsReader() as never, {
      ...base, artifacts: arts(DESIGN4, []),
    } as never)
    const unconfirmed = await checkDesignCompletenessGate(docsReader() as never, {
      ...base, artifacts: arts(DESIGN5, ['use-cases.md']),
    } as never)
    expect(unregistered?.code).toBe('design_doc_incomplete')
    expect(unconfirmed?.code).toBe('design_doc_incomplete')
    expect(unregistered?.message).toContain('未登记')
    expect(unconfirmed?.message).toContain('待确认')
    expect(unregistered?.message).not.toBe(unconfirmed?.message)
  })
})

describe('TC-4 ask_confirm 早返回补 G2 缺口（不再与 move 互相矛盾）', () => {
  it('全部落章 + 磁盘多一份未登记 → confirmed=true, advanced=false, gaps 点名未登记件', async () => {
    writeDocset(DESIGN5)
    await seed({ registered: DESIGN4 })
    const out = await run(askTool(), ASK_ARGS)
    expect(out.success).toBe(true)
    expect(out.confirmed).toBe(true)
    expect(out.advanced).toBe(false)
    expect(out.gate_failure?.code).toBe('design_doc_incomplete')
    expect((out.gate_failure?.gaps ?? []).join(' ')).toContain('use-cases.md 未登记')
    expect(out.note).toContain('已确认，未重复弹框')
    expect(out.note).toContain('仍有 1 份未登记')
  })

  it('全部落章且磁盘无新增 → 早返回不带 gate_failure（不制造噪声）', async () => {
    writeDocset(DESIGN5)
    await seed({ registered: DESIGN5 })
    const out = await run(askTool(), ASK_ARGS)
    expect(out.confirmed).toBe(true)
    expect(out.advanced).toBe(false)
    expect(out.gate_failure).toBeUndefined()
    expect(out.note).not.toContain('未登记')
  })
})
