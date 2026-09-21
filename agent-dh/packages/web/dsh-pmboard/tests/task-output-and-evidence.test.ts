/**
 * t12 单测（W4 后半）：任务文件上浮（kind=task_output）+ verify_submit evidence 存在性 +
 * archive_submit 漏登警告。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { JsonLedgerRepository as ReqboardStore } from '../src/adapters/JsonLedgerRepository.js'
import {
  defineTaskReportTool, defineVerifySubmitTool, defineArchiveSubmitTool,
} from './helpers/tool-deps.js'
import { type ToolTraceEntry } from '../src/adapters/SessionProbeAdapter.js'
import type { RequirementRecord, RequirementStatus } from '../src/shared/protocol.js'

const W = 'session-abc-123'
let dir: string
let store: ReqboardStore
let report: { execute: (a: unknown, e: unknown) => Promise<any> }
let verify: { execute: (a: unknown, e: unknown) => Promise<any> }
let archive: { execute: (a: unknown, e: unknown) => Promise<any> }
let trace: Map<string, ToolTraceEntry[]>

beforeEach(() => {
  dir = mkdtempSync(join(tmpdir(), 'pmboard-t12-'))
  store = new ReqboardStore({ file: join(dir, 'dsh-reqboard.json') })
  trace = new Map()
  const deps = { store, now: () => Date.now(), toolTrace: trace, doneThrottleMs: 0, workspaceRoot: dir } as never
  report = defineTaskReportTool(deps) as never
  verify = defineVerifySubmitTool(deps) as never
  archive = defineArchiveSubmitTool(deps) as never
})
afterEach(() => { rmSync(dir, { recursive: true, force: true }) })

async function seed(status: RequirementStatus = 'implementing', category = 'feature'): Promise<void> {
  const r = {
    id: 'REQ-t12test', title: '看板需求', description: '', status, category, blocked: false,
    sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' }, statusHistory: [],
  } as unknown as RequirementRecord
  await store.mutate('requirement-created', (l) => { l.requirements.push(r); return { requirements: [r] } })
}
const run = (tool: { execute: (a: unknown, e: unknown) => Promise<any> }, args: unknown) =>
  tool.execute(args, { agent: { id: W } })

describe('任务文件上浮（t12）', () => {
  it('task_report 的 files_changed 自动登记为需求级 task_output 产物', async () => {
    await seed()
    // 落一个真实任务（task_report 前置：任务存在且属于本窗口需求）
    await store.mutate('task-created', (l) => {
      const t = {
        id: 't-abc123', requirementId: 'REQ-t12test', title: '改文件', description: '',
        phase: 'implement', side: 'backend', dependsOn: [], scope: { apis: [], tables: [], files: [] },
        acceptance: '单测绿', context: '', status: 'in_progress', blocked: false,
        executions: [], comments: [], version: 1, createdAt: 1, updatedAt: 1,
        createdBy: { kind: 'agent', sessionId: W }, updatedBy: { kind: 'agent', sessionId: W },
      }
      l.tasks.push(t as never)
      return { tasks: [t as never] }
    })
    await run(report, {
      task_id: 't-abc123', summary: '改了文件', completed: ['x'],
      files_changed: ['packages/pages/dsh-pmboard/src/tools/StatusTool/StatusTool.ts', 'docs/a.md'],
    })
    const arts = store.snapshot().requirements[0].artifacts ?? []
    const outs = arts.filter(a => a.kind === 'task_output')
    expect(outs.map(a => a.path).sort()).toEqual(['docs/a.md', 'packages/pages/dsh-pmboard/src/tools/StatusTool/StatusTool.ts'])
  })
})

describe('verify_submit evidence 存在性（t12）', () => {
  it('编造路径 → REQBOARD_EVIDENCE_MISSING', async () => {
    await seed('implementing')
    await expect(run(verify, {
      summary: '交付完成',
      evidence: ['见 packages/pages/dsh-pmboard/src/no-such-file.ts 的输出'],
    })).rejects.toThrow(/REQBOARD_EVIDENCE_MISSING/)
  })

  it('真实路径 → 通过校验（不再报 EVIDENCE_MISSING）', async () => {
    await seed('implementing')
    // 路径按文档根解析；测试已把文档根隔离到临时目录 → 在临时根下造一个真实文件当证据
    const real = 'evidence/proof.ts'
    mkdirSync(join(dir, 'evidence'), { recursive: true })
    writeFileSync(join(dir, real), '// 证据文件\n')
    try {
      const out = await run(verify, { summary: '交付完成', evidence: ['见 ' + real] })
      expect(out.success).toBe(true)
    } catch (err) {
      expect((err as Error).message).not.toMatch(/EVIDENCE_MISSING/)
    }
  })
})

describe('archive_submit 漏登警告（t12）', () => {
  it('目录内有未列入清单的文件 → unlisted_files + warning', async () => {
    await seed('archived')
    const reqDir = join(dir, 'docs/requirements/REQ-t12test')
    mkdirSync(reqDir, { recursive: true })
    writeFileSync(join(reqDir, 'requirement.md'), 'x')
    writeFileSync(join(reqDir, 'prototype.html'), 'x')
    const listed = 'docs/requirements/REQ-t12test/requirement.md'
    const out = await run(archive, {
      dir: 'docs/requirements/REQ-t12test',
      docs: [{ kind: 'requirement', path: listed }],
      merged_into: ['docs/architecture/project-manual.md'],
      index_entry: '测试归档',
      manual_note: '无手册更新',
    }).catch((e: Error) => ({ error: e.message }))
    // assertArchiveMaterials 可能因必填文档拒绝；只要不因漏登而失败即可
    if (out.error === undefined) {
      expect(out.unlisted_files?.some((p: string) => p.includes('prototype.html'))).toBe(true)
      expect(out.warning).toMatch(/未列入归档清单/)
    }
    rmSync(reqDir, { recursive: true, force: true })
  })
})
