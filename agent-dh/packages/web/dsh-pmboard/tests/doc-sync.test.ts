/**
 * 文档演进留痕单测（REQ-2e9473 t19/W8）：
 * 重登记必填 change_note；上游变更标记下游待同步；下游重交销标；推进时警告。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import {
  defineRequirementSubmitTool, definePlanSubmitTool, defineDecomposeTool, defineMoveTool,
  stubDocFile,
} from './helpers/tool-deps.js'
import type { RequirementRecord } from '../src/shared/protocol.js'

const W = 'session-abc-123'
let root: string
let store: ReqboardStore
let reqSubmit: any, planTool: any, decompose: any, move: any

beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), 'pmboard-docsync-'))
  store = new ReqboardStore({ file: join(root, 'dsh-reqboard.json') })
  const deps = { store, now: () => Date.now(), doneThrottleMs: 0, workspaceRoot: root } as never
  reqSubmit = defineRequirementSubmitTool(deps)
  planTool = definePlanSubmitTool(deps)
  decompose = defineDecomposeTool(deps)
  move = defineMoveTool(deps)
  // REQ-2d1c74 FR-5：plan_submit 起要求提交路径真实落盘
  stubDocFile('p.md', root)
})
afterEach(() => { rmSync(root, { recursive: true, force: true }) })

const REQ = 'REQ-ds1234'

async function seed(status = 'brainstorming'): Promise<void> {
  const r = {
    id: REQ, title: '文档留痕', description: '', status, category: 'feature', blocked: false,
    sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' }, statusHistory: [],
  } as unknown as RequirementRecord
  await store.mutate('seed', (l) => { l.requirements.push(r); return { requirements: [r] } })
}
const run = (tool: any, args: unknown) => tool.execute(args, { agent: { id: W } })
function writeReqFile(rel: string): void {
  const abs = join(root, 'docs/requirements', REQ, rel)
  mkdirSync(join(abs, '..'), { recursive: true })
  // 迁移（REQ-d3e61a T-13）：最小桩也要满足"分类文档集"门禁对根文档必填节的要求。
  // 本文件不读该内容（原先是占位符 'x'），故只是把桩做成**形态合法**的文档，不影响被测语义。
  const body = rel.endsWith('requirement.md')
    ? '# 需求\n\n## 1. 问题\n\n桩。\n\n## 2. 边界\n\n桩。\n\n## 3. 成功标准\n\n桩。\n\n## 4. 产品定义\n\n桩。\n\n## 5. 用户与角色\n\n桩。\n\n## 6. 功能点\n\n### FR-1: 文档留痕\n\n桩。\n'
    : 'x'
  writeFileSync(abs, body)
}

describe('文档演进留痕（t19）', () => {
  it('首次提交免 change_note；已确认后重写不传 → REQBOARD_CHANGELOG_REQUIRED', async () => {
    await seed()
    writeReqFile('requirement.md')
    await run(reqSubmit, { summary: '初版' })
    // 人确认
    await store.mutate('confirm', (l) => {
      const r = l.requirements[0]
      const a = r.artifacts!.find(x => x.kind === 'requirement')!
      a.confirmedAt = 1000
      r.status = 'design'
      return { requirements: [r] }
    })
    // 回 brainstorming 重写（模拟变更）
    await store.mutate('back', (l) => { l.requirements[0].status = 'brainstorming'; return { requirements: [l.requirements[0]] } })
    await expect(run(reqSubmit, { summary: '改了一版' })).rejects.toThrow(/REQBOARD_CHANGELOG_REQUIRED/)
  })

  it('变更传 change_note → 记 changelog + 作废旧确认 + 下游待同步', async () => {
    await seed()
    writeReqFile('requirement.md')
    await run(reqSubmit, { summary: '初版' })
    await store.mutate('confirm', (l) => {
      const r = l.requirements[0]
      r.artifacts!.find(x => x.kind === 'requirement')!.confirmedAt = 1000
      // 同时登记 plan/decomposition 产物（模拟下游已存在）
      r.artifacts!.push(
        { stage: 'design', kind: 'plan', path: 'p.md', registeredAt: 1, registeredBy: { kind: 'agent' } },
        { stage: 'decomposing', kind: 'decomposition', path: 'd.md', registeredAt: 1, registeredBy: { kind: 'agent' } },
      )
      r.status = 'brainstorming'
      return { requirements: [r] }
    })
    const out = await run(reqSubmit, { summary: '改了一版', change_note: '补了验收单逐项确认的需求' })
    expect(out.success).toBe(true)
    const req = store.snapshot().requirements[0]
    expect(req.artifacts!.find(x => x.kind === 'requirement')!.confirmedAt).toBeUndefined()
    expect(req.docSyncPending).toHaveLength(1)
    expect(req.docSyncPending![0].source).toBe('requirement')
    expect(req.docSyncPending![0].downstream).toEqual(['plan', 'decomposition'])
    expect(req.comments.some(c => c.body.includes('[文档变更]'))).toBe(true)
  })

  it('下游重交（plan_submit）→ 销 plan 标；decompose → 销 decomposition 标', async () => {
    await seed('decomposing') // 2026-09-21：拆分计划在拆分阶段提交
    // 迁移（REQ-d3e61a T-13）：feature 类型要求设计文档齐；本文件不读这些桩的内容，
    // 只是让桩形态合法（原先依赖上一个用例残留的 requirement.md，design 目录则完全没有）。
    writeReqFile('requirement.md')
    for (const d of ['architecture.md', 'data-model.md', 'interfaces.md', 'test-cases.md', 'use-cases.md']) writeReqFile('design/' + d)
    await store.mutate('seed-pending', (l) => {
      const r = l.requirements[0]
      r.docSyncPending = [{ source: 'requirement', downstream: ['plan', 'decomposition'], reason: 'x', at: 1 }]
      return { requirements: [r] }
    })
    await run(planTool, { path: 'p.md', summary: '设计 v2' })
    let req = store.snapshot().requirements[0]
    expect((req.docSyncPending ?? []).some(p => p.downstream.includes('plan'))).toBe(false)
    // 拆解销 decomposition 标
    await store.mutate('approve', (l) => {
      const r = l.requirements[0]
      r.plan!.approvedAt = 1
      r.plan!.approvedBy = { kind: 'human' }
      return { requirements: [r] }
    })
    // 条款覆盖门禁：桩文档有 FR-1，任务卡必须显式接收，否则 requirement_uncovered
    await run(decompose, { tasks: [{ key: 'a', title: 'x', acceptance: '单测绿', implementation: '改 x.ts', requirement_refs: ['FR-1'] }] })
    req = store.snapshot().requirements[0]
    expect(req.docSyncPending ?? []).toHaveLength(0)
  })

  it('有待同步标记时推进返回 doc_sync_warning', async () => {
    await seed('brainstorming')
    await store.mutate('seed-pending', (l) => {
      const r = l.requirements[0]
      r.docSyncPending = [{ source: 'requirement', downstream: ['plan'], reason: '改了范围', at: 1 }]
      // 放行闸门：requirement 产物已确认（否则 brainstorming→design 被人工门拦）
      r.artifacts = [{
        stage: 'brainstorming', kind: 'requirement', path: 'docs/requirements/' + REQ + '/requirement.md',
        registeredAt: 1, registeredBy: { kind: 'agent' }, confirmedAt: 2, confirmedBy: { kind: 'human' },
      } as never]
      return { requirements: [r] }
    })
    const out = await run(move, { to: 'design', reason: '推进' })
    expect(out.doc_sync_warning).toMatch(/待同步/)
    expect(out.doc_sync_pending).toHaveLength(1)
  })
})
