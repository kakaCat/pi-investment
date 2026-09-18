/**
 * 验收单数据模型单测（REQ-2e9473 t13/W6）：verify_submit 生成逐项验收单
 * （每任务验收标准 + 需求级标准）、版本化、返工只含未过项。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { defineVerifySubmitTool } from './helpers/tool-deps.js'
import type { RequirementRecord, VerificationItem } from '../src/shared/protocol.js'

const W = 'session-abc-123'
let dir: string
let store: ReqboardStore
let verify: { execute: (a: unknown, e: unknown) => Promise<any> }

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-sheet-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
  verify = defineVerifySubmitTool({ store, now: () => Date.now() } as never) as never
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

async function seedWithTasks(): Promise<void> {
  const r = {
    id: 'REQ-abc123', title: '看板需求', description: '', status: 'implementing', category: 'feature',
    blocked: false, sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' }, statusHistory: [],
  } as unknown as RequirementRecord
  await store.mutate('seed', (l) => {
    l.requirements.push(r)
    const mk = (id: string, title: string, acceptance: string) => ({
      id, requirementId: r.id, title, description: '', phase: 'implement', side: 'backend',
      dependsOn: [], scope: { apis: [], tables: [], files: [] }, acceptance, context: '',
      status: 'done', blocked: false, executions: [], comments: [], version: 1,
      createdAt: 1, updatedAt: 1, createdBy: { kind: 'agent', sessionId: W }, updatedBy: { kind: 'agent', sessionId: W },
    })
    // 迁移（REQ-d3e61a T-9）：本文件不引用这两段文本，只求能满足"验收项可照着验"的门禁。
    l.tasks.push(mk('t-aaaaaa', '任务一', 'npx vitest run tests/reqboard.test.ts 全绿') as never, mk('t-bbbbbb', '任务二', 'npx vitest run tests/client-view.test.ts 全绿') as never)
    return { requirements: [r] }
  })
}
const run = (args: unknown) => verify.execute(args, { agent: { id: W } })

describe('验收单生成（t13）', () => {
  it('v1 含每任务验收标准 + 一条需求级标准，逐项带证据且 pending', async () => {
    await seedWithTasks()
    const out = await run({ summary: '交付完成', evidence: ['npx vitest run 全绿'] })
    expect(out.sheet_version).toBe(1)
    expect(out.sheet_items).toBe(3) // 2 任务 + 1 需求级
    const sheet = store.snapshot().requirements[0].verification!.sheet!
    expect(sheet.version).toBe(1)
    // v5（REQ-47939a t4）：source 由字符串改为判别联合
    expect(sheet.items.map(i => i.source)).toEqual([
      { kind: 'task', taskId: 't-aaaaaa' },
      { kind: 'task', taskId: 't-bbbbbb' },
      { kind: 'requirement' },
    ])
    // 迁移（REQ-d3e61a T-11）：同 domain/acceptance-sheet.test.ts——验的是顺序与来源，文案随格式升级。
    expect(sheet.items.map(i => i.criterion)).toEqual(['【任务一】验收：npx vitest run tests/reqboard.test.ts 全绿', '【任务二】验收：npx vitest run tests/client-view.test.ts 全绿', expect.stringMatching(/需求级/)])
    expect(sheet.items.every(i => i.status === 'pending')).toBe(true)
    expect(sheet.items.every(i => i.evidence.length === 1)).toBe(true)
    expect(sheet.items.every(i => /^v1-\d+$/.test(i.id))).toBe(true)
  })

  it('返工续验：上一版有未过项 → v2 带过「未过项 + 未裁决项」且 rework_only=true', async () => {
    await seedWithTasks()
    await run({ summary: '交付完成', evidence: ['npx vitest run 全绿'] })
    // 模拟用户裁决：第 2 项不通过
    await store.mutate('verdict', (l) => {
      const req = l.requirements[0]
      const items: VerificationItem[] = req.verification!.sheet!.items
      items[1].status = 'failed'
      items[1].opinion = '截图不清晰'
      items[0].status = 'passed'
      return { requirements: [req] }
    })
    const out2 = await run({ summary: '修复后重交', evidence: ['新截图路径'] })
    expect(out2.sheet_version).toBe(2)
    expect(out2.rework_only).toBe(true)
    // D-7 修复后：v2 = 未过项（t-bbbbbb）+ 未裁决的需求级项 —— 未验项不许被静默丢弃
    expect(out2.sheet_items).toBe(2)
    const v2 = store.snapshot().requirements[0].verification!.sheet!
    expect(v2.items).toHaveLength(2)
    expect(v2.items.map(i => i.source)).toEqual([
      { kind: 'task', taskId: 't-bbbbbb' },
      { kind: 'requirement' },
    ])
    expect(v2.items.every(i => i.status === 'pending')).toBe(true)
    expect(v2.items[0].opinion).toBeUndefined()
    // 历史留痕：v1 进 sheetHistory
    const hist = store.snapshot().requirements[0].verification!.sheetHistory!
    expect(hist).toHaveLength(1)
    expect(hist[0].version).toBe(1)
    expect(hist[0].items[1].status).toBe('failed')
  })
})
