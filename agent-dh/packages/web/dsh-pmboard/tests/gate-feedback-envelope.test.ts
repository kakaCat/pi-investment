/**
 * 拒绝信封三要素契约测试（REQ-260924213231-b1c4 T-5 · serves: FR-2）
 *
 * 零信任核对（design/architecture.md「闸门拒绝信封」§零信任核对）：对 I-9 枚举的每个 code
 * 真实触发闸门（不是直接调 envelope 造串），断言 message 同时含 ——（why 分隔）与
 * 补齐：（how 分隔），且 how 段命中可执行锚点（reqboard_* / templates/ / design_exempt）；
 * 同时锁 code 与 gaps 未因改文案而变化。
 *
 * I-9 覆盖的 code（12 个）：design_doc_incomplete、design_orphan、dangling_reference、
 * requirement_uncovered、requirement_missing_clauses、requirement_clause_sequence_gap、
 * requirement_clause_duplicates、REQBOARD_MISSING_REQUIRED_DOC、REQBOARD_ARTIFACT_NOT_OPENABLE、
 * REQBOARD_FILE_MISSING、design_contains_decomposition、REQBOARD_EVIDENCE_FAKE。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync, mkdirSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { envelope, GATE_HOW_ANCHOR } from '../src/application/internal/gate-feedback.js'
import {
  checkDesignCompletenessGate,
  checkDesignDecompositionGate,
  assertArtifactOpenable,
} from '../src/application/internal/design-gates.js'
import {
  assertClauseCoverageGate,
  checkDesignServesGate,
  checkNumberChainGate,
  checkRequirementDocFormatGate,
} from '../src/application/internal/content-gate-wiring.js'
import { definePlanSubmitTool, defineAskConfirmTool } from './helpers/tool-deps.js'
import type { RequirementRecord } from '../src/shared/protocol.js'

const W = 'session-t5-env'
const REQID = 'REQ-t5e'
const RDIR = 'docs/requirements/' + REQID
const REQP = RDIR + '/requirement.md'
const DDIR = RDIR + '/design'
const DESIGN_ALL = ['architecture.md', 'data-model.md', 'interfaces.md', 'test-cases.md', 'use-cases.md']

const REQ_DOC = [
  '---', 'req: ' + REQID, '---', '', '# 需求', '',
  '## 边界', '不做范围外的事。', '',
  '## 产品定义', 'x', '',
  '## 用户与角色', 'x', '',
  '## 功能点', '',
  '### FR-1: 甲', 'x', '',
  '### FR-4: 丁', 'x', '',
].join('\n')

const live = {
  id: REQID, category: 'feature',
  artifacts: [{ stage: 'brainstorming', kind: 'requirement', path: REQP, registeredAt: 1 }],
} as unknown as RequirementRecord

const art = (name: string, confirmed = true) => ({
  stage: 'design', kind: 'design', path: DDIR + '/' + name, registeredAt: 1,
  ...(confirmed ? { confirmedAt: 1 } : {}),
})

/** 设计文件全落盘的 files 视图。 */
function designFiles(): Record<string, string> {
  const o: Record<string, string> = {}
  for (const n of DESIGN_ALL) o[DDIR + '/' + n] = '# ' + n + '\n'
  return o
}

const fakeDocs = (files: Record<string, string>) => ({
  exists: (p: string) => Object.prototype.hasOwnProperty.call(files, p),
  read: async (p: string) => files[p] ?? '',
  list: (dir: string) => Object.keys(files)
    .filter(k => k.startsWith(dir + '/'))
    .map(k => ({ name: k.slice(dir.length + 1), isFile: true })),
})

interface GateLike { code: string; message: string; gaps?: string[] }

function must<T>(v: T | undefined, label: string): NonNullable<T> {
  if (v === undefined) throw new Error(label + '：闸门未触发（应被拒却放行）')
  return v as NonNullable<T>
}

async function thrown(fn: () => unknown): Promise<GateLike> {
  try {
    await fn()
  } catch (e) {
    const err = e as { code?: string; message: string }
    return { code: err.code ?? '(no-code)', message: err.message }
  }
  throw new Error('预期被拒，但调用成功了')
}

let dir: string
let store: ReqboardStore

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-envelope-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

async function seedReq(o: { id: string; status: string }): Promise<void> {
  const r = {
    id: o.id, title: '信封', description: '', category: 'feature', status: o.status,
    blocked: false, sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' }, statusHistory: [],
  } as unknown as RequirementRecord
  await store.mutate('seed', (l) => { l.requirements.push(r); return { requirements: [r] } })
}

const run = (tool: { execute: (a: unknown, e: unknown) => Promise<any> }, args: unknown) =>
  tool.execute(args, { agent: { id: W } })

describe('envelope 拼接契约（唯一入口）', () => {
  it('三要素按 <what> —— <why>。补齐：<how> 拼接，lead 可前置', () => {
    expect(envelope({ what: 'A.md', why: '缺章', how: '调 reqboard_submit' }))
      .toBe('A.md —— 缺章。补齐：调 reqboard_submit')
    expect(envelope({ lead: 'reqboard_move 未执行：', what: 'A.md', why: '缺章', how: '调 reqboard_submit' }))
      .toBe('reqboard_move 未执行：A.md —— 缺章。补齐：调 reqboard_submit')
  })
})

describe('TC-21 逐 code 三要素（真实触发闸门，不是拼串）', () => {
  it('I-9 的每个 code：含 —— 与 补齐：，且 how 命中可执行锚点', async () => {
    const cases: Array<{ label: string; code: string; produce: () => Promise<GateLike> }> = [
      {
        label: 'design_doc_incomplete（未登记）', code: 'design_doc_incomplete',
        produce: async () => must(await checkDesignCompletenessGate(
          fakeDocs({ [REQP]: REQ_DOC, ...designFiles() }) as never,
          { ...live, artifacts: DESIGN_ALL.slice(0, 4).map(n => art(n)) } as never,
        ), '未登记'),
      },
      {
        label: 'design_doc_incomplete（待确认）', code: 'design_doc_incomplete',
        produce: async () => must(await checkDesignCompletenessGate(
          fakeDocs({ [REQP]: REQ_DOC, ...designFiles() }) as never,
          { ...live, artifacts: DESIGN_ALL.map(n => art(n, n !== 'use-cases.md')) } as never,
        ), '待确认'),
      },
      {
        label: 'design_orphan', code: 'design_orphan',
        produce: async () => must(await checkDesignServesGate(
          fakeDocs({ [DDIR + '/architecture.md']: '# 架构\n\n## D-ARCH-1 有映射 serves: FR-1\n正文\n\n## D-ARCH-2 忘了标注\n正文\n' }) as never,
          live,
        ), 'design_orphan'),
      },
      {
        label: 'dangling_reference', code: 'dangling_reference',
        produce: async () => must((await checkNumberChainGate(
          fakeDocs({
            [REQP]: '# 需求\n\n**FR-1 甲**\n',
            [DDIR + '/architecture.md']: '# 架构\n\n## D-ARCH-1 悬空 serves: FR-99\n正文\n',
          }) as never,
          live,
        )).failure, 'dangling_reference'),
      },
      {
        label: 'requirement_uncovered', code: 'requirement_uncovered',
        produce: async () => must(await assertClauseCoverageGate(
          fakeDocs({ [REQP]: REQ_DOC }) as never,
          live,
          [{ requirement_refs: ['FR-1'] }] as never,
        ), 'requirement_uncovered'),
      },
      {
        label: 'requirement_missing_clauses', code: 'requirement_missing_clauses',
        produce: async () => must(await checkRequirementDocFormatGate(
          fakeDocs({ [REQP]: '# 需求\n\n没有编号\n' }) as never, live,
        ), 'requirement_missing_clauses'),
      },
      {
        label: 'requirement_clause_sequence_gap', code: 'requirement_clause_sequence_gap',
        produce: async () => must(await checkRequirementDocFormatGate(
          fakeDocs({ [REQP]: '# 需求\n\n**FR-1 甲**\n\n**FR-3 丙**\n' }) as never, live,
        ), 'requirement_clause_sequence_gap'),
      },
      {
        label: 'requirement_clause_duplicates', code: 'requirement_clause_duplicates',
        produce: async () => must(await checkRequirementDocFormatGate(
          fakeDocs({ [REQP]: '# 需求\n\n**FR-1 甲**\n\n**FR-1 重复**\n' }) as never, live,
        ), 'requirement_clause_duplicates'),
      },
      {
        label: 'design_contains_decomposition', code: 'design_contains_decomposition',
        produce: async () => must(await checkDesignDecompositionGate(
          fakeDocs({ [DDIR + '/architecture.md']: '# 架构\n\n## 拆分计划\n正文\n' }) as never, live,
        ), 'design_contains_decomposition'),
      },
      {
        label: 'REQBOARD_ARTIFACT_NOT_OPENABLE', code: 'REQBOARD_ARTIFACT_NOT_OPENABLE',
        produce: () => thrown(() => assertArtifactOpenable(fakeDocs({}) as never, DDIR + '/{a,b}.md')),
      },
      {
        label: 'REQBOARD_FILE_MISSING', code: 'REQBOARD_FILE_MISSING',
        produce: () => thrown(() => assertArtifactOpenable(fakeDocs({}) as never, DDIR + '/architecture.md')),
      },
      {
        label: 'REQBOARD_MISSING_REQUIRED_DOC', code: 'REQBOARD_MISSING_REQUIRED_DOC',
        produce: async () => {
          const id = 'REQ-t5e-doc'
          const rdir = 'docs/requirements/' + id
          mkdirSync(join(dir, rdir), { recursive: true })
          writeFileSync(join(dir, rdir, 'requirement.md'), '# 需求\n\n### FR-1: 甲\nx\n')
          writeFileSync(join(dir, rdir, 'decomposition.md'), '# 拆分计划\n')
          await seedReq({ id, status: 'decomposing' })
          const tool = definePlanSubmitTool({ store, now: () => 1000, workspaceRoot: dir } as never) as never as { execute: (a: unknown, e: unknown) => Promise<any> }
          return thrown(() => run(tool, { path: rdir + '/decomposition.md', summary: '目标：x；做法：y' }))
        },
      },
      {
        label: 'REQBOARD_EVIDENCE_FAKE', code: 'REQBOARD_EVIDENCE_FAKE',
        produce: async () => {
          await seedReq({ id: 'REQ-t5e-ev', status: 'design' })
          const tool = defineAskConfirmTool({
            store, now: () => 1000, workspaceRoot: dir, recentUserMsgs: new Map(),
          } as never) as never as { execute: (a: unknown, e: unknown) => Promise<any> }
          return thrown(() => run(tool, {
            target: 'artifact', kind: 'design', question: '确认？', options: ['确认'], evidence: '用户同意了',
          }))
        },
      },
    ]

    for (const c of cases) {
      const f = await c.produce()
      expect(f.code, c.label).toBe(c.code)
      expect(f.message, c.label).toContain('——')
      expect(f.message, c.label).toContain('补齐：')
      const how = f.message.slice(f.message.indexOf('补齐：') + '补齐：'.length)
      expect(GATE_HOW_ANCHOR.test(how), c.label + ' 的 how 缺可执行锚点：' + how).toBe(true)
    }
  })
})

describe('TC-21 负例：code 与 gaps 结构未因改文案而变化（护栏强度不降）', () => {
  it('design_doc_incomplete.gaps 仍逐份点名，且区分未登记/待确认', async () => {
    const unreg = must(await checkDesignCompletenessGate(
      fakeDocs({ [REQP]: REQ_DOC, ...designFiles() }) as never,
      { ...live, artifacts: DESIGN_ALL.slice(0, 4).map(n => art(n)) } as never,
    ), '未登记')
    expect(unreg.code).toBe('design_doc_incomplete')
    expect(unreg.gaps).toEqual([DDIR + '/use-cases.md 未登记（产物簿无此条，先调 reqboard_submit(kind=design)）'])

    const unconf = must(await checkDesignCompletenessGate(
      fakeDocs({ [REQP]: REQ_DOC, ...designFiles() }) as never,
      { ...live, artifacts: DESIGN_ALL.map(n => art(n, n !== 'use-cases.md')) } as never,
    ), '待确认')
    expect(unconf.gaps).toEqual([DDIR + '/use-cases.md 待确认（已登记未落章，先调 reqboard_ask_confirm(target=artifact, kind=design)）'])
  })

  it('requirement_uncovered.gaps 仍是结构化编号清单', async () => {
    const f = must(await assertClauseCoverageGate(fakeDocs({ [REQP]: REQ_DOC }) as never, live, [{ requirement_refs: ['FR-1'] }] as never), 'uncovered')
    expect(f.gaps).toEqual(['FR-4'])
  })

  it('assertArtifactOpenable 仍抛原名 code（形态判定未动）', async () => {
    const brace = await thrown(() => assertArtifactOpenable(fakeDocs({}) as never, DDIR + '/{a,b}.md'))
    expect(brace.code).toBe('REQBOARD_ARTIFACT_NOT_OPENABLE')
    const missing = await thrown(() => assertArtifactOpenable(fakeDocs({}) as never, DDIR + '/architecture.md'))
    expect(missing.code).toBe('REQBOARD_FILE_MISSING')
  })
})
