/**
 * reqboard_requirement_submit（REQ-ff20ca t1）单测。
 *
 * 背景：registerArtifact 此前只在 decompose/plan_submit/verify_submit/task_report 中调用，
 * brainstorming 阶段的 requirement 产物**无任何登记入口** → 看板确认按钮 400 → 门永远过不去。
 * 本工具补上该入口，测试覆盖：首次登记 / 幂等 / 文件缺失 / 阶段纪律。
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { join } from 'node:path'
import { defineRequirementSubmitTool } from './helpers/tool-deps.js'
import { emptyLedger, type ReqboardLedger, type RequirementRecord } from '../src/shared/protocol.js'

const W = 'session-abc-123'
const REQ_ID = 'REQ-t1submit'
const REL_PATH = 'docs/requirements/' + REQ_ID + '/requirement.md'
const ABS_DIR = join(process.cwd(), 'docs/requirements', REQ_ID)

function ledgerWith(status: RequirementRecord['status']): ReqboardLedger {
  const req = {
    id: REQ_ID, title: '需求', description: '', status, blocked: false,
    sourceSessionId: W, comments: [], artifacts: [], version: 1, createdAt: 1, updatedAt: 1,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
  } as unknown as RequirementRecord
  return { ...emptyLedger(), requirements: [req] }
}

function makeTool(ledger: ReqboardLedger) {
  const deps = {
    store: {
      read: async (fn: (l: ReqboardLedger) => unknown) => fn(ledger),
      snapshot: () => ledger,
      // mutate 直接就地执行回调并回传 changed（工具读 result.changed.requirements[0]）
      mutate: async (_evt: string, fn: (l: ReqboardLedger) => unknown) => ({ changed: fn(ledger) }),
    },
    now: () => 1000,
  } as never
  const tool = defineRequirementSubmitTool(deps) as unknown as {
    execute: (a: unknown, e: unknown) => Promise<{ success?: boolean; registered?: boolean; artifact?: Record<string, string> }>
  }
  return (args: unknown = {}) => tool.execute(args, { agent: { id: W } })
}

describe('reqboard_requirement_submit（t1：brainstorming 产物登记入口）', () => {
  beforeEach(() => {
    mkdirSync(ABS_DIR, { recursive: true })
    writeFileSync(join(ABS_DIR, 'requirement.md'), '# 需求文档\n', 'utf8')
  })
  afterEach(() => { rmSync(ABS_DIR, { recursive: true, force: true }) })

  it('首次提交：登记 requirement 产物 + 追加台账动态 + registered=true', async () => {
    const ledger = ledgerWith('brainstorming')
    const out = await makeTool(ledger)({ summary: '测试摘要' })
    expect(out.success).toBe(true)
    expect(out.registered).toBe(true)
    expect(out.artifact).toMatchObject({ stage: 'brainstorming', kind: 'requirement', path: REL_PATH })
    const req = ledger.requirements[0]
    expect(req.artifacts?.length).toBe(1)
    expect(req.artifacts?.[0]?.kind).toBe('requirement')
    expect(req.artifacts?.[0]?.confirmedAt).toBeUndefined() // 登记≠确认：确认仍须人做
    expect(req.comments?.some(c => c.body.includes('[需求文档]'))).toBe(true)
  })

  it('幂等：同路径重复提交不重复登记（registered=false）', async () => {
    const ledger = ledgerWith('brainstorming')
    const run = makeTool(ledger)
    await run({})
    const out2 = await run({})
    expect(out2.registered).toBe(false)
    expect(ledger.requirements[0].artifacts?.length).toBe(1)
  })

  it('文件不存在：拒绝且不写台账', async () => {
    rmSync(ABS_DIR, { recursive: true, force: true })
    const ledger = ledgerWith('brainstorming')
    await expect(makeTool(ledger)({})).rejects.toThrow(/文档不存在/)
    expect(ledger.requirements[0].artifacts?.length).toBe(0)
  })

  it('非 brainstorming 状态：拒绝（阶段纪律）', async () => {
    const ledger = ledgerWith('decomposing')
    await expect(makeTool(ledger)({})).rejects.toThrow(/brainstorming/)
  })
})
