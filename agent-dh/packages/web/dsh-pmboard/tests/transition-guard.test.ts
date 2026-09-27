/**
 * 状态流转收敛点校验（2026-09-27 补）。
 *
 * 背景事故：transitionRequirement 原先直接 req.status = to 且无任何校验，
 * 于是"批准计划"分支漏检即可让需求在**计划未落库**时进入 implementing，
 * 造成 DAG/泳道/实施覆盖度全空且零告警。本测试锁定收敛点的拦截行为。
 */
import { describe, it, expect } from 'vitest'
import { transitionRequirement } from '../src/application/internal/token-usage.js'
import type { RequirementRecord } from '../src/shared/protocol.js'

function req(status: string): RequirementRecord {
  return {
    id: 'REQ-guard-test',
    title: 't',
    description: '',
    status: status as never,
    blocked: false,
    comments: [],
    version: 1,
    createdAt: 0,
    updatedAt: 0,
    createdBy: { kind: 'system' },
    updatedBy: { kind: 'system' },
  } as RequirementRecord
}

const ACTOR = { kind: 'agent' } as never
const AT = 1_790_000_000_000

describe('transitionRequirement · 状态机校验', () => {
  it('非法转移必须抛 invalid_transition（draft → implementing 不在状态表内）', () => {
    const r = req('draft')
    expect(() => transitionRequirement(r, 'implementing', { at: AT, actor: ACTOR }))
      .toThrowError(/不允许从 draft 转移到 implementing/)
    expect(r.status).toBe('draft') // 状态未被改动
  })

  it('合法转移正常通过（decomposing → implementing）', () => {
    const r = req('decomposing')
    transitionRequirement(r, 'implementing', { at: AT, actor: { kind: 'human' } as never })
    expect(r.status).toBe('implementing')
  })

  it('越权：agent 发起 human-only 转移必须抛 human_gate（若该转移是人工门）', () => {
    // brainstorming → design 是五道人工确认门之一
    const r = req('brainstorming')
    expect(() => transitionRequirement(r, 'design', { at: AT, actor: ACTOR }))
      .toThrowError(/人工闸门|不允许/)
    expect(r.status).toBe('brainstorming')
  })

  it('逃生舱 allowIllegalTransition=true 可跳过（供迁移脚本等非业务写入）', () => {
    const r = req('draft')
    transitionRequirement(r, 'implementing', { at: AT, actor: ACTOR, allowIllegalTransition: true })
    expect(r.status).toBe('implementing')
  })

  it('每次校验都不得留下半迁移态（拒绝时版本/时间不变）', () => {
    const r = req('draft')
    const v0 = r.version
    const u0 = r.updatedAt
    try { transitionRequirement(r, 'archived', { at: AT, actor: ACTOR }) } catch { /* 预期 */ }
    expect(r.version).toBe(v0)
    expect(r.updatedAt).toBe(u0)
  })
})
