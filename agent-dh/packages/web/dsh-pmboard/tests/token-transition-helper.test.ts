/**
 * 单测：transitionRequirement 核心迁移助手（REQ-b545fe t1）。
 * 
 * 验收标准：
 * - 假快照调用断言 byStage 累加 + 事件带快照
 * - snap=undefined 调用断言不累加 + 事件无快照
 */
import { describe, expect, it } from 'vitest'
import { transitionRequirement, type TransitionOpts } from '../src/application/internal/token-usage.js'
import { emptyBuckets, type RequirementRecord, type TokenSnapshot } from '../src/shared/protocol.js'

/** 构造最小需求记录（只含迁移必需字段）。 */
function minReq(status: string): RequirementRecord {
  return {
    id: 'REQ-test',
    title: 'Test',
    description: '',
    category: 'bug',
    status: status as any,
    version: 1,
    createdAt: 1000,
    updatedAt: 1000,
    createdBy: { kind: 'human' },
    updatedBy: { kind: 'human' },
    statusHistory: [],
    comments: [],
    tasks: [],
    blocked: false,
  } as RequirementRecord
}

/** 构造递增假快照（projection 源，sessionId 一致）。 */
function fakeSnap(seq: number, sessionId: string): TokenSnapshot {
  return {
    at: 2000 + seq * 1000,
    sessionId,
    seq,
    totals: {
      uncachedInputTokens: seq * 100,
      outputTokens: seq * 50,
      cacheReadTokens: seq * 200,
      cacheWriteTokens: seq * 10,
    },
    source: 'projection',
  }
}

describe('transitionRequirement（REQ-b545fe t1）', () => {
  it('有快照：结算离开节点 + 迁移状态 + 事件带快照', () => {
    const req = minReq('draft')
    const wk = 'w-test'
    
    // 模拟进入 draft 的事件（带快照 seq=1）
    req.statusHistory!.push({
      status: 'draft',
      at: 2000,
      by: { kind: 'human' },
      tokenSnapshot: fakeSnap(1, wk),
    })
    
    // 离开 draft → brainstorming（快照 seq=3，差值应为 200/100/400/20）
    const opts: TransitionOpts = {
      at: 5000,
      actor: { kind: 'agent', sessionId: wk },
      reason: '测试推进',
      snap: fakeSnap(3, wk),
    }
    
    transitionRequirement(req, 'brainstorming', opts)
    
    // 断言：状态已迁移
    expect(req.status).toBe('brainstorming')
    expect(req.version).toBe(2)
    expect(req.updatedAt).toBe(5000)
    expect(req.updatedBy).toEqual({ kind: 'agent', sessionId: wk })
    
    // 断言：byStage[draft] 累加了差值（3-1=2 的倍数）
    expect(req.tokenUsage?.byStage?.draft).toEqual({
      uncachedInputTokens: 200,
      outputTokens: 100,
      cacheReadTokens: 400,
      cacheWriteTokens: 20,
    })
    
    // 断言：totals = byStage 之和（只有一个节点时等于该节点）
    expect(req.tokenUsage?.totals).toEqual(req.tokenUsage?.byStage?.draft)
    
    // 断言：新事件带快照
    expect(req.statusHistory).toBeDefined()
    const lastEvent = req.statusHistory![req.statusHistory!.length - 1]!
    expect(lastEvent.status).toBe('brainstorming')
    expect(lastEvent.tokenSnapshot).toEqual(fakeSnap(3, wk))
  })
  
  it('无快照：不结算 + 迁移状态 + 事件无快照', () => {
    const req = minReq('draft')
    
    // 离开 draft → brainstorming（无快照）
    const opts: TransitionOpts = {
      at: 5000,
      actor: { kind: 'system' },
      reason: '无会话推进',
      snap: undefined, // 调用方无会话上下文
    }
    
    transitionRequirement(req, 'brainstorming', opts)
    
    // 断言：状态已迁移
    expect(req.status).toBe('brainstorming')
    expect(req.version).toBe(2)
    expect(req.updatedAt).toBe(5000)
    
    // 断言：tokenUsage 未初始化（accumulateStageDelta 未调用）
    expect(req.tokenUsage).toBeUndefined()
    
    // 断言：新事件无快照
    expect(req.statusHistory).toBeDefined()
    const lastEvent = req.statusHistory![req.statusHistory!.length - 1]!
    expect(lastEvent.status).toBe('brainstorming')
    expect(lastEvent.tokenSnapshot).toBeUndefined()
  })
  
  it('快照 source=unavailable：不结算（accumulateStageDelta 返回 false）', () => {
    const req = minReq('draft')
    const wk = 'w-test'
    
    // 进入 draft 事件带可得快照
    req.statusHistory!.push({
      status: 'draft',
      at: 2000,
      by: { kind: 'human' },
      tokenSnapshot: fakeSnap(1, wk),
    })
    
    // 离开时快照不可得
    const opts: TransitionOpts = {
      at: 5000,
      actor: { kind: 'agent', sessionId: wk },
      snap: { at: 5000, totals: emptyBuckets(), source: 'unavailable' },
    }
    
    transitionRequirement(req, 'brainstorming', opts)
    
    // 断言：状态已迁移
    expect(req.status).toBe('brainstorming')
    
    // 断言：tokenUsage 已初始化但 byStage 不含 draft（结算失败）
    expect(req.tokenUsage?.byStage?.draft).toBeUndefined()
    
    // 断言：事件带快照（即使不可得也记录，供后续判定）
    expect(req.statusHistory).toBeDefined()
    const lastEvent = req.statusHistory![req.statusHistory!.length - 1]!
    expect(lastEvent.tokenSnapshot?.source).toBe('unavailable')
  })
})
