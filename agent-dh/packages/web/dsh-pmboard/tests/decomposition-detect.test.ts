/**
 * 拆分内容硬门禁单测（REQ-2d1c74 T-3 · serves FR-3）
 *
 * 验收口径：depends_on 表头命中、代码块示例不命中、中文散文不命中；
 * 三条确认通道（弹框/文字证据/看板一键）均抛 design_contains_decomposition 且不落章不推进。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync, mkdirSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { EventEmitter } from 'node:events'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { FileDocRepository } from '../src/adapters/FileDocRepository.js'
import { createReqboardHandler } from '../src/http/routes.js'
import { defineAskConfirmTool } from './helpers/tool-deps.js'
import { parseDocument, detectDecompositionFeatures } from '../src/application/internal/content-gates.js'
import { checkDesignDecompositionGate } from '../src/application/internal/design-gates.js'
import type { RequirementRecord, StageArtifact } from '../src/shared/protocol.js'

const W = 'session-fr3-001'
const REQ = 'REQ-fr3001'
const DESIGN5 = ['architecture.md', 'data-model.md', 'interfaces.md', 'test-cases.md', 'use-cases.md']
const DESIGN_DIR = 'docs/requirements/' + REQ + '/design'

let dir: string
let store: ReqboardStore

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-fr3-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

describe('detectDecompositionFeatures（纯判定，特征集 v1 宁漏勿冤）', () => {
  it('depends_on 表头命中', () => {
    const doc = parseDocument('| key | title | depends_on | acceptance |\n|---|---|---|---|\n| t1 | 甲 | — | 绿 |\n')
    expect(detectDecompositionFeatures(doc).join(' ')).toContain('depends_on')
  })

  it('acceptance + implementation 表头同时出现命中；单出現不命中', () => {
    const both = parseDocument('| key | acceptance | implementation |\n|---|---|---|\n| t1 | 绿 | 改 a |\n')
    expect(detectDecompositionFeatures(both).join(' ')).toContain('acceptance + implementation')
    const onlyAcc = parseDocument('| key | acceptance |\n|---|---|\n| t1 | 绿 |\n')
    expect(detectDecompositionFeatures(onlyAcc)).toEqual([])
  })

  it('H2+「拆分计划」「任务 DAG」标题命中；H1 与正文提及不命中', () => {
    const h2 = parseDocument('## 拆分计划\n\n正文\n')
    expect(detectDecompositionFeatures(h2).join(' ')).toContain('拆分计划')
    const h3 = parseDocument('### 任务 DAG\n\n正文\n')
    expect(detectDecompositionFeatures(h3).join(' ')).toContain('任务 DAG')
    const h1 = parseDocument('# 拆分计划\n\n正文\n')
    expect(detectDecompositionFeatures(h1)).toEqual([])
  })

  it('代码块内的示例表格/标题不命中（parseDocument 已剥离围栏）', () => {
    const fenced = parseDocument('设计讨论：\n\n\`\`\`markdown\n| key | depends_on |\n|---|---|\n| t1 | — |\n\n## 拆分计划\n\`\`\`\n')
    expect(detectDecompositionFeatures(fenced)).toEqual([])
  })

  it('中文散文提及字段名不命中；中文表头任务表不命中（已知限制，先保零误伤）', () => {
    const prose = parseDocument('本设计的任务依赖用 depends_on 概念表述，验收标准 acceptance 与实施方案 implementation 分开写。\n')
    expect(detectDecompositionFeatures(prose)).toEqual([])
    const cn = parseDocument('| 任务 | 依赖 | 验收标准 | 实施方案 |\n|---|---|---|---|\n| 甲 | — | 绿 | 改 a |\n')
    expect(detectDecompositionFeatures(cn)).toEqual([])
  })
})

function fakeDocs(files: Record<string, string>) {
  return {
    exists: (p: string) => files[p] !== undefined,
    read: async (p: string) => files[p],
    list: (d: string) => Object.keys(files)
      .filter(p => p.startsWith(d + '/'))
      .map(p => ({ name: p.slice(d.length + 1), isFile: true })),
  }
}

describe('checkDesignDecompositionGate（装配：扫 design/ 全部落盘文档）', () => {
  const req = { id: REQ, artifacts: [{}] } as unknown as RequirementRecord

  it('脏文档 → design_contains_decomposition，gaps 含文件与特征、指引挪到拆分阶段', async () => {
    const docs = fakeDocs({
      [DESIGN_DIR + '/interfaces.md']: '# 接口\n\n| key | depends_on |\n|---|---|\n| t1 | — |\n',
      [DESIGN_DIR + '/architecture.md']: '# 架构\n干净\n',
    })
    const failure = await checkDesignDecompositionGate(docs, req)
    expect(failure?.code).toBe('design_contains_decomposition')
    expect(failure?.gaps?.join(' ')).toContain('interfaces.md')
    expect(failure?.gaps?.join(' ')).toContain('depends_on')
    expect(failure?.message).toContain('挪到拆分阶段')
  })

  it('干净文档（含代码块示例与散文提及）→ 放行', async () => {
    const docs = fakeDocs({
      [DESIGN_DIR + '/architecture.md']: '# 架构\n散文提到 depends_on 不命中。\n\`\`\`\n| key | depends_on |\n|---|---|\n\`\`\`\n',
    })
    expect(await checkDesignDecompositionGate(docs, req)).toBeUndefined()
  })
})

// ── 三通道落章前拦截 ─────────────────────────────────────────────────────────

const DIRTY = '# 接口设计\n\n| key | title | depends_on |\n|---|---|---|\n| t1 | 甲 | — |\n'

function writeDocset(dirty: boolean): void {
  mkdirSync(join(dir, DESIGN_DIR), { recursive: true })
  writeFileSync(join(dir, 'docs/requirements', REQ, 'requirement.md'),
    '# 需求\n\n## 边界\nx\n\n## 产品定义\nx\n\n## 用户与角色\nx\n\n## 功能点\n\n### FR-1: 甲\nx\n')
  for (const n of DESIGN5) writeFileSync(join(dir, DESIGN_DIR, n), n === 'interfaces.md' && dirty ? DIRTY : '# ' + n + '\n')
}

async function seed(): Promise<void> {
  const artifacts = DESIGN5.map(n => ({
    stage: 'design', kind: 'design', path: DESIGN_DIR + '/' + n,
    registeredAt: 1, registeredBy: { kind: 'agent', sessionId: W },
  }) as StageArtifact)
  const r = {
    id: REQ, title: '拆分内容门', description: '', category: 'feature', status: 'design',
    blocked: false, sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' }, statusHistory: [], artifacts,
  } as unknown as RequirementRecord
  await store.mutate('seed', (l) => { l.requirements.push(r); return { requirements: [r] } })
}

function askTool() {
  const deps = {
    store, now: () => 1000, workspaceRoot: dir,
    userQuestions: () => ({ ask: async () => ({ answers: [{ id: 'confirm', selected: ['确认，进入拆分'] }] }) }),
  } as never
  return defineAskConfirmTool(deps) as never as { execute: (a: unknown, e: unknown) => Promise<any> }
}

const run = (tool: { execute: (a: unknown, e: unknown) => Promise<any> }, args: unknown) =>
  tool.execute(args, { agent: { id: W } })

function fakeReq(method: string, url: string, body?: unknown): any {
  const req = new EventEmitter() as any
  req.url = url
  req.method = method
  req[Symbol.asyncIterator] = async function* () {
    if (body !== undefined) yield Buffer.from(JSON.stringify(body), 'utf8')
  }
  return req
}

function fakeRes(): any {
  const res: any = new EventEmitter()
  res.statusCode = 0
  res.payload = undefined
  res.writeHead = (code: number) => { res.statusCode = code; return res }
  res.end = (text?: string) => { res.payload = text === undefined ? undefined : JSON.parse(text); return res }
  return res
}

function noConfirmed(): boolean {
  return (store.snapshot().requirements[0].artifacts ?? []).every(a => a.confirmedAt === undefined)
}

describe('三通道：落章前检出拆分内容 → 拒，不落章不推进', () => {
  beforeEach(async () => {
    writeDocset(true)
    await seed()
  })

  it('通道① 会话弹框（reqboard_ask_confirm）', async () => {
    await expect(run(askTool(), { target: 'artifact', kind: 'design', question: 'q', options: ['确认，进入拆分', '改'] }))
      .rejects.toThrow(/design_contains_decomposition/)
    expect(noConfirmed()).toBe(true)
    expect(store.snapshot().requirements[0].status).toBe('design')
  })

  it('通道② 会话文字证据（reqboard_confirm_artifact + evidence）', async () => {
    await expect(run(askTool(), { target: 'artifact', kind: 'design', evidence: '用户在 ask_user_question 中选择确认' }))
      .rejects.toThrow(/design_contains_decomposition/)
    expect(noConfirmed()).toBe(true)
    expect(store.snapshot().requirements[0].status).toBe('design')
  })

  it('通道③ 看板一键（POST req/artifact/confirm）', async () => {
    const handler = createReqboardHandler({
      store, now: () => 1000,
      docs: new FileDocRepository({ workspaceRoot: dir }),
      agents: () => ({ get: () => ({ id: W, session: {} }) }),
    })
    const res = fakeRes()
    await handler(fakeReq('POST', '/dashboard/api/reqboard/req/artifact/confirm', { id: REQ, kind: 'design' }), res)
    expect(res.statusCode).toBe(400)
    expect(res.payload.code).toBe('design_contains_decomposition')
    expect(res.payload.error).toContain('interfaces.md')
    expect(noConfirmed()).toBe(true)
    expect(store.snapshot().requirements[0].status).toBe('design')
  })
})
