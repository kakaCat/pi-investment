/**
 * reqboard_status 输出契约：本窗口可自行推进的目标（next_actions）。
 * 用户反馈「agent 自己不能推进吗」——窗口必须能从工具输出里直接看到可推进项。
 */
import { describe, it, expect } from 'vitest'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { defineStatusTool } from './helpers/tool-deps.js'
import { emptyLedger, type ReqboardLedger, type RequirementRecord, type StageArtifact } from '../src/shared/protocol.js'

const W = 'session-abc-123'

function ledgerWith(status: RequirementRecord['status']): ReqboardLedger {
  const req = {
    id: 'REQ-abc123', title: '需求', description: '', status, blocked: false,
    sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
  } as RequirementRecord
  return { ...emptyLedger(), requirements: [req] }
}

async function run(status: RequirementRecord['status']) {
  const ledger = ledgerWith(status)
  const deps = {
    store: { read: async (fn: (l: ReqboardLedger) => unknown) => fn(ledger), snapshot: () => ledger },
    now: () => 1,
  } as never
  const tool = defineStatusTool(deps) as unknown as { execute: (a: unknown, e: unknown) => Promise<any> }
  return tool.execute({}, { agent: { id: W } })
}

describe('reqboard_status.next_actions（窗口可自行推进的动作）', () => {
  it('brainstorming → design 已入人工门（五门裁定），agent 仅可退回 draft', async () => {
    const out = await run('brainstorming')
    // 2026-09-14 五门裁定：需求文档确认 brainstorming>design 是人工确认门，
    // agent 的 next_actions 不再含 design（人确认需求文档后由看板推进）
    expect(out.next_actions).toEqual(['draft'])
    expect(out.note).toContain('reqboard_move')
  })

  it('draft → 提交评审；implementing → 进验收', async () => {
    expect((await run('draft')).next_actions).toEqual(['brainstorming'])
    expect((await run('implementing')).next_actions).toEqual(['accepting'])
  })

  it('终态与未绑定窗口：无 next_actions', async () => {
    expect((await run('archived')).next_actions).toEqual([])
  })
})

// ── design_docs[]（REQ-260924213231-b1c4 T-4 · serves FR-1 / interfaces.md I-2）────────────
// 「agent 不打开看板也能读出未登记 / 待确认 / 已落章」——逐份三态必须与磁盘+台账一致。

/** feature 的必交设计文档（category-doc-sets）——断言行集与顺序用。 */
const FEATURE_DESIGN5 = ['architecture.md', 'data-model.md', 'interfaces.md', 'test-cases.md', 'use-cases.md']

interface StatusFixture {
  id: string
  status?: RequirementRecord['status']
  category?: RequirementRecord['category']
  artifacts?: StageArtifact[]
  /** requirement.md 原文（front-matter 策略：sides / design_exempt）。 */
  requirementMd?: string
  /** 落盘到 design/ 的文件名。 */
  designFiles?: string[]
}

/** 用**独立临时工作区**跑一次 reqboard_status（磁盘与台账都可控）。 */
async function runFixture(f: StatusFixture): Promise<any> {
  const root = mkdtempSync(join(tmpdir(), 'pmboard-status-design-'))
  const dir = 'docs/requirements/' + f.id + '/design'
  try {
    if (f.designFiles !== undefined && f.designFiles.length > 0) {
      mkdirSync(join(root, dir), { recursive: true })
      for (const n of f.designFiles) writeFileSync(join(root, dir, n), '# ' + n + '\n')
    }
    if (f.requirementMd !== undefined) {
      mkdirSync(join(root, 'docs/requirements', f.id), { recursive: true })
      writeFileSync(join(root, 'docs/requirements', f.id, 'requirement.md'), f.requirementMd)
    }
    const req = {
      id: f.id, title: '需求', description: '', status: f.status ?? 'design', category: f.category,
      blocked: false, sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
      createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
      ...(f.artifacts !== undefined ? { artifacts: f.artifacts } : {}),
    } as unknown as RequirementRecord
    const ledger: ReqboardLedger = { ...emptyLedger(), requirements: [req] }
    const deps = {
      store: { read: async (fn: (l: ReqboardLedger) => unknown) => fn(ledger), snapshot: () => ledger },
      now: () => 1,
      workspaceRoot: root,
    } as never
    const tool = defineStatusTool(deps) as unknown as { execute: (a: unknown, e: unknown) => Promise<any> }
    return await tool.execute({}, { agent: { id: W } })
  } finally {
    rmSync(root, { recursive: true, force: true })
  }
}

const rowOf = (out: any, name: string): any => (out.design_docs as any[]).find(d => d.name === name)

describe('reqboard_status.design_docs（逐份登记态：磁盘 / 产物簿 / 确认章三源）', () => {
  const REQ = 'REQ-status-t4'
  const DIR = 'docs/requirements/' + REQ + '/design'
  const art = (name: string, extra: Record<string, unknown> = {}): StageArtifact => ({
    stage: 'design', kind: 'design', path: DIR + '/' + name, registeredAt: 1,
    registeredBy: { kind: 'agent', sessionId: W }, ...extra,
  } as unknown as StageArtifact)

  it('未登记 / 待确认 / 已落章 / 缺失 四态逐份与磁盘+台账一致', async () => {
    const out = await runFixture({
      id: REQ, category: 'feature',
      designFiles: ['architecture.md', 'data-model.md', 'interfaces.md'],
      artifacts: [
        art('data-model.md'),                     // 已登记未落章 → 待确认
        art('interfaces.md', { confirmedAt: 2 }), // 已落章
      ],
    })
    // 行集 = 该类型必交（含缺失项），顺序与 category-doc-sets 一致
    expect(out.design_docs.map((d: any) => d.name)).toEqual(FEATURE_DESIGN5)
    // 磁盘有、产物簿无 → 未登记
    expect(rowOf(out, 'architecture.md')).toMatchObject({ path: DIR + '/architecture.md', on_disk: true, registered: false, confirmed: false })
    // 已登记未落章 → 待确认
    expect(rowOf(out, 'data-model.md')).toMatchObject({ on_disk: true, registered: true, confirmed: false })
    // 已登记且落章 → 已落章
    expect(rowOf(out, 'interfaces.md')).toMatchObject({ on_disk: true, registered: true, confirmed: true })
    // 未落盘也没登记的必交项仍逐份列出（agent 知道还差哪份）
    expect(rowOf(out, 'test-cases.md')).toMatchObject({ on_disk: false, registered: false, confirmed: false })
    expect(rowOf(out, 'use-cases.md')).toMatchObject({ on_disk: false, registered: false, confirmed: false })
  })

  it('front-matter：sides=frontend 出条件必交项，design_exempt 带豁免理由', async () => {
    const out = await runFixture({
      id: REQ, category: 'feature',
      requirementMd: '---\nsides: frontend\ndesign_exempt: test-cases.md=本需求无测试点（已评审）\n---\n\n# 需求\n',
    })
    expect(rowOf(out, 'frontend.md')).toMatchObject({ conditional: 'frontend', on_disk: false, registered: false })
    expect(rowOf(out, 'backend.md')).toBeUndefined() // 未声明 backend
    expect(rowOf(out, 'test-cases.md')).toMatchObject({ exempted: '本需求无测试点（已评审）' })
  })

  it('未绑定窗口 → design_docs 为空数组（不瞎报）', async () => {
    expect((await run('archived')).design_docs).toEqual([])
  })

  it('未知/缺 category → 只报磁盘额外件，不瞎报必交清单', async () => {
    const out = await runFixture({ id: REQ, designFiles: ['extra.md'] })
    expect(out.design_docs.map((d: any) => d.name)).toEqual(['extra.md'])
    expect(rowOf(out, 'extra.md')).toMatchObject({ on_disk: true, registered: false, confirmed: false })
  })
})
