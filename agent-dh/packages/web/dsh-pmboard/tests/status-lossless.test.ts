/**
 * reqboard_status 返回体必须 lossless（REQ-260927100007-b8ba t10 / FR-10）。
 *
 * 实测：application/internal/rtm-health.ts 的 checkRTMHealth 在**无失败记录**时返回
 * last_failure: undefined（own property）。JSON.stringify 会静默丢掉它，但 PTC 绑定层的
 * lossless 校验会拦下 → 已绑定窗口的 reqboard_status **必然**报
 * "returned invalid output: value is not lossless JSON"（未绑定时不展开 rtm_health，故长期未被发现）。
 */
import { describe, it, expect } from 'vitest'
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { defineStatusTool } from './helpers/tool-deps.js'
import { emptyLedger, type ReqboardLedger, type RequirementRecord } from '../src/shared/protocol.js'

const W = 'session-abc-123'

/** 递归扫描「值为 undefined 的属性」（与 PTC lossless 校验同口径）。 */
function undefinedPaths(v: unknown, path = ''): string[] {
  const out: string[] = []
  if (v === undefined) { out.push(path || '<root>'); return out }
  if (Array.isArray(v)) {
    v.forEach((x, i) => out.push(...undefinedPaths(x, path + '[' + i + ']')))
    return out
  }
  if (typeof v === 'object' && v !== null) {
    for (const [k, val] of Object.entries(v as Record<string, unknown>)) {
      if (val === undefined) { out.push(path.length > 0 ? path + '.' + k : k); continue }
      out.push(...undefinedPaths(val, path.length > 0 ? path + '.' + k : k))
    }
  }
  return out
}

async function runStatus(opts: { withFailureRecord?: boolean } = {}): Promise<any> {
  const root = mkdtempSync(join(tmpdir(), 'pmboard-status-lossless-'))
  try {
    // 已绑定窗口 + implementing：rtm_health 才会被展开（open.length > 0）
    const dir = join(root, 'docs', 'requirements', 'REQ-lossless')
    mkdirSync(dir, { recursive: true })
    for (const f of ['rtm-lifecycle.yml', 'rtm-brainstorming.yml', 'rtm-design.yml', 'rtm-decomposing.yml', 'rtm-implementing.yml']) {
      writeFileSync(join(dir, f), 'x')
    }
    if (opts.withFailureRecord === true) {
      const stateDir = join(root, '.dsh-data', 'state')
      mkdirSync(stateDir, { recursive: true })
      writeFileSync(join(stateDir, 'rtm-failures.json'), JSON.stringify([
        { requirement_id: 'REQ-lossless', trigger: 'task:status', timestamp: 1, error: 'boom', attempts: 1 },
      ]))
    }
    const req = {
      id: 'REQ-lossless', title: '需求', description: '', status: 'implementing',
      blocked: false, sourceSessionId: W, comments: [], version: 1, createdAt: 1, updatedAt: 1,
      createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
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

describe('reqboard_status lossless（FR-10）', () => {
  it('无失败记录：rtm_health 省略 last_failure 键（不是 undefined），整包无 undefined 属性', async () => {
    const out = await runStatus()
    expect(out.bound).toBe(true)
    expect(out.rtm_health).toBeDefined()
    expect(Object.prototype.hasOwnProperty.call(out.rtm_health, 'last_failure')).toBe(false)
    expect(undefinedPaths(out)).toEqual([])
  })

  it('有失败记录：last_failure 完整呈现，且整包仍无 undefined 属性', async () => {
    const out = await runStatus({ withFailureRecord: true })
    expect(out.rtm_health.last_failure).toMatchObject({ trigger: 'task:status', error: 'boom', attempts: 1 })
    expect(undefinedPaths(out)).toEqual([])
  })
})
