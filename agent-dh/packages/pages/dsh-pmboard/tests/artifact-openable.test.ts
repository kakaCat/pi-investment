/**
 * 产物登记可打开性校验单测（REQ-2d1c74 T-4 · serves FR-5）
 *
 * 验收口径：不存在路径报 REQBOARD_FILE_MISSING，brace/越界路径报 REQBOARD_ARTIFACT_NOT_OPENABLE，
 * 消息含 normalized 路径与原因；submit（requirement/plan/archive）与 ArtifactSync 两入口都覆盖。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, rmSync, mkdirSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import { discoverArtifacts, reqDirRel } from '../src/adapters/ArtifactSync.js'
import { assertArtifactOpenable } from '../src/application/internal/design-gates.js'
import { FileDocRepository } from '../src/adapters/FileDocRepository.js'
import { defineRequirementSubmitTool, definePlanSubmitTool, defineArchiveSubmitTool } from './helpers/tool-deps.js'
import type { RequirementRecord, StageArtifact } from '../src/shared/protocol.js'

const W = 'session-open-001'
const REQ = 'REQ-ab0001' // 归档目录约定要求 REQ-xxxxxx（6 位 hex）

let dir: string
let store: ReqboardStore

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-openable-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

async function seed(status: string, category = 'feature'): Promise<void> {
  const r = {
    id: REQ, title: '可打开性', description: '', category, status,
    blocked: false, sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' }, statusHistory: [],
    artifacts: [{ stage: 'brainstorming', kind: 'requirement', path: 'docs/requirements/' + REQ + '/requirement.md', registeredAt: 1 } as StageArtifact],
  } as unknown as RequirementRecord
  await store.mutate('seed', (l) => { l.requirements.push(r); return { requirements: [r] } })
}

const run = (tool: { execute: (a: unknown, e: unknown) => Promise<any> }, args: unknown) =>
  tool.execute(args, { agent: { id: W } })

function toolDeps() {
  return { store, now: () => 1000, workspaceRoot: dir } as never
}

describe('assertArtifactOpenable（纯函数口径：先形态、后存在）', () => {
  const docs = new FileDocRepository({ workspaceRoot: '/' })
  const realDocs = () => new FileDocRepository({ workspaceRoot: dir })

  it('空串 / 反斜杠 / .. / brace → REQBOARD_ARTIFACT_NOT_OPENABLE，消息含 normalized 与原因', () => {
    expect(() => assertArtifactOpenable(docs, '')).toThrow(/REQBOARD_ARTIFACT_NOT_OPENABLE/)
    expect(() => assertArtifactOpenable(docs, 'docs\\\\x.md')).toThrow(/REQBOARD_ARTIFACT_NOT_OPENABLE/)
    expect(() => assertArtifactOpenable(docs, '../etc/passwd')).toThrow(/\.\. 或反斜杠/)
    expect(() => assertArtifactOpenable(docs, 'docs/{a,b}.md')).toThrow(/brace/)
    expect(() => assertArtifactOpenable(docs, 'docs/{a,b}.md')).toThrow(/normalized=docs\/{a,b}\.md/)
    expect(() => assertArtifactOpenable(docs, 'docs/**/*.md')).toThrow(/REQBOARD_ARTIFACT_NOT_OPENABLE/)
  })

  it('工作区外绝对路径 → REQBOARD_ARTIFACT_NOT_OPENABLE（越界）', () => {
    expect(() => assertArtifactOpenable(realDocs(), '/etc/hosts')).toThrow(/工作区之外/)
    expect(() => assertArtifactOpenable(realDocs(), '/etc/hosts')).toThrow(/REQBOARD_ARTIFACT_NOT_OPENABLE/)
  })

  it('不存在 → REQBOARD_FILE_MISSING，消息含 normalized；存在 → 返回 normalized 路径', () => {
    expect(() => assertArtifactOpenable(realDocs(), 'docs/requirements/' + REQ + '/requirement.md')).toThrow(/REQBOARD_FILE_MISSING/)
    expect(() => assertArtifactOpenable(realDocs(), 'docs/requirements/' + REQ + '/requirement.md')).toThrow(/未落盘或路径写错/)
    mkdirSync(join(dir, 'docs/requirements', REQ), { recursive: true })
    writeFileSync(join(dir, 'docs/requirements', REQ, 'requirement.md'), '# x\n')
    expect(assertArtifactOpenable(realDocs(), 'docs/requirements/' + REQ + '/requirement.md'))
      .toBe('docs/requirements/' + REQ + '/requirement.md')
    // 工作区内绝对路径 → 归一为相对路径（台账以归一值登记）
    expect(assertArtifactOpenable(realDocs(), join(dir, 'docs/requirements', REQ, 'requirement.md')))
      .toBe('docs/requirements/' + REQ + '/requirement.md')
  })
})

describe('submit 入口：登记即拦（不再等人点看才发现）', () => {
  it('requirement_submit：伪路径拒（brace）；越界拒（..）；不存在报 FILE_MISSING；合法放行', async () => {
    await seed('brainstorming')
    const tool = defineRequirementSubmitTool(toolDeps()) as never as { execute: (a: unknown, e: unknown) => Promise<any> }

    await expect(run(tool, { path: 'docs/{a,b}.md' })).rejects.toThrow(/REQBOARD_ARTIFACT_NOT_OPENABLE/)
    await expect(run(tool, { path: '../outside.md' })).rejects.toThrow(/REQBOARD_ARTIFACT_NOT_OPENABLE/)
    await expect(run(tool, { path: 'docs/requirements/' + REQ + '/ghost.md' })).rejects.toThrow(/REQBOARD_FILE_MISSING/)

    // 合法：落盘 + 形态合法（含 FR 编号过格式门）→ 登记成功且路径为 normalized
    mkdirSync(join(dir, 'docs/requirements', REQ), { recursive: true })
    writeFileSync(join(dir, 'docs/requirements', REQ, 'requirement.md'), '# 需求\n\n### FR-1: 甲\nx\n')
    const out = await run(tool, {})
    expect(out.success).toBe(true)
    expect(out.artifact?.path).toBe('docs/requirements/' + REQ + '/requirement.md')
  })

  it('plan_submit：现状不查存在性已补齐——没落盘的计划路径报 FILE_MISSING；落盘后放行', async () => {
    await seed('decomposing')
    const tool = definePlanSubmitTool(toolDeps()) as never as { execute: (a: unknown, e: unknown) => Promise<any> }
    const planPath = 'docs/requirements/' + REQ + '/decomposition.md'

    await expect(run(tool, { path: planPath, summary: '拆分计划' })).rejects.toThrow(/REQBOARD_FILE_MISSING/)
    await expect(run(tool, { path: 'docs/{a,b}.md', summary: '拆分计划' })).rejects.toThrow(/REQBOARD_ARTIFACT_NOT_OPENABLE/)

    // 落盘计划与文档集（feature 门禁链需要：编号串联 / serves / 文档集）
    mkdirSync(join(dir, 'docs/requirements', REQ, 'design'), { recursive: true })
    writeFileSync(join(dir, 'docs/requirements', REQ, 'requirement.md'),
      '# 需求\n\n## 边界\nx\n\n## 产品定义\nx\n\n## 用户与角色\nx\n\n## 功能点\n\n### FR-1: 甲\nx\n')
    for (const n of ['architecture.md', 'data-model.md', 'interfaces.md', 'test-cases.md', 'use-cases.md']) {
      writeFileSync(join(dir, 'docs/requirements', REQ, 'design', n), '# ' + n + '\n')
    }
    writeFileSync(join(dir, 'docs/requirements', REQ, 'decomposition.md'), '# 拆分计划\n')
    const out = await run(tool, { path: planPath, summary: '拆分计划' })
    expect(out.success).toBe(true)
    const req = store.snapshot().requirements[0]
    expect(req.plan?.path).toBe(planPath)
  })

  it('archive_submit：目录不存在 / 清单内文档不存在报 FILE_MISSING；伪路径报 NOT_OPENABLE；齐活放行', async () => {
    await seed('archived', 'bug')
    const tool = defineArchiveSubmitTool(toolDeps()) as never as { execute: (a: unknown, e: unknown) => Promise<any> }
    const reqDir = 'docs/requirements/' + REQ
    const base = {
      dir: reqDir,
      merged_into: ['docs/guides/x.md'],
      index_entry: '一句话结论',
    }

    // 目录不存在（docs 清单形态完整以过材料校验，命中的是目录存在性检查）
    const fullDocs = () => [
      { kind: 'requirement', path: reqDir + '/requirement.md' },
      { kind: 'verification', path: reqDir + '/verification.md' },
      { kind: 'retro', path: reqDir + '/retro.md' },
    ]
    await expect(run(tool, { ...base, docs: fullDocs() }))
      .rejects.toThrow(/REQBOARD_FILE_MISSING/)

    // 目录在、清单内文档不存在
    mkdirSync(join(dir, 'docs/requirements', REQ), { recursive: true })
    writeFileSync(join(dir, 'docs/requirements', REQ, 'requirement.md'), '# 需求\n')
    await expect(run(tool, { ...base, docs: fullDocs() })).rejects.toThrow(/REQBOARD_FILE_MISSING/)

    // 补齐三份文档后测伪路径（清单形态完整 + 一条 brace 伪路径 → 命中可打开性校验而非材料/存在性校验）
    writeFileSync(join(dir, 'docs/requirements', REQ, 'verification.md'), '# 验收\n')
    writeFileSync(join(dir, 'docs/requirements', REQ, 'retro.md'), '# 复盘\n')
    await expect(run(tool, { ...base, docs: [...fullDocs(), { kind: 'notes', path: 'docs/{a,b}.md' }] }))
      .rejects.toThrow(/REQBOARD_ARTIFACT_NOT_OPENABLE/)

    // 齐活（bug 类：requirement/verification/retro 必填）
    const out = await run(tool, { ...base, docs: fullDocs() })
    expect(out.success).toBe(true)
  })
})

describe('ArtifactSync 入口：自动发现路径形态防御过滤', () => {
  it('brace/通配形态的文件名不登记；正常文件照常登记', async () => {
    await seed('design')
    const abs = join(dir, reqDirRel(REQ))
    mkdirSync(abs, { recursive: true })
    writeFileSync(join(abs, 'prototype.html'), '<html/>')
    writeFileSync(join(abs, 'proto-{a,b}.html'), '<html/>') // brace 形态
    const req = store.snapshot().requirements[0]
    const found = discoverArtifacts(req, abs, reqDirRel(REQ))
    const paths = found.map(a => a.path)
    expect(paths.some(p => p.endsWith('prototype.html'))).toBe(true)
    expect(paths.some(p => p.includes('{'))).toBe(false)
  })
})
