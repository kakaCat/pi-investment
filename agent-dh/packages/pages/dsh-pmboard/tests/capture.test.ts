/**
 * capture.ts 窗口捕获判定单测（B 方案：仅 unbound 且无 pending 的窗口注入引导）。
 * 覆盖：windowKeyFromContext（agent.id 优先 / scope 兜底 / 缺失返回 undefined）、
 * isWindowBound（sourceSessionId 直挂 / triage 锚点两路）、hasPendingSuggestion、
 * captureSectionText 分支（bound → '' / hasPending → '' / unbound → 引导文本）+ pending
 * 第三参注入分支（确定性消息 hook 命中 → 引用消息原文的针对性立项提示）。
 */
import { describe, it, expect } from 'vitest'
import {
  boundSectionText,
  windowKeyFromContext,
  isWindowBound,
  hasPendingSuggestion,
  captureSectionText,
  captureGuidanceText,
  capturePromptForMessage,
  pendingSuggestionFor,
  openRequirementsFor,
} from '../src/host/capture.js'
import { emptyLedger, type ReqboardLedger, type RequirementRecord, type TriageRecord } from '../src/shared/protocol.js'

function req(over: Partial<RequirementRecord>): RequirementRecord {
  return {
    id: 'REQ-000001', title: 't', description: '', status: 'draft', blocked: false,
    version: 1, createdAt: 1, updatedAt: 1,
    ...over,
  } as RequirementRecord
}

function tri(over: Partial<TriageRecord>): TriageRecord {
  return {
    id: 'tri-000001', sessionId: 'session-a', firstMessageText: 'm',
    suggestedAction: 'create_req', score: 90, status: 'pending', createdAt: 1, comments: [],
    ...over,
  } as TriageRecord
}

const W = 'session-abc-123'

describe('windowKeyFromContext', () => {
  it('agent.id 优先', () => {
    expect(windowKeyFromContext({ agent: { id: 'session-x' }, scope: 's' })).toBe('session-x')
  })
  it('无 agent.id 时 scope 兜底', () => {
    expect(windowKeyFromContext({ scope: 's' } as any)).toBe('s')
    expect(windowKeyFromContext({ agent: { id: '' }, scope: 's' } as any)).toBe('s')
  })
  it('两者缺失返回 undefined', () => {
    expect(windowKeyFromContext(undefined)).toBeUndefined()
    expect(windowKeyFromContext({} as any)).toBeUndefined()
  })
})

describe('isWindowBound', () => {
  it('sourceSessionId 直挂 open req → bound', () => {
    const l: ReqboardLedger = { ...emptyLedger(), requirements: [req({ sourceSessionId: W, status: 'implementing' })] }
    expect(isWindowBound(l, W)).toBe(true)
  })
  it('sourceSessionId 直挂已结束 req（done/archived/canceled）→ 不 bound', () => {
    for (const status of ['done', 'archived', 'canceled']) {
      const l: ReqboardLedger = { ...emptyLedger(), requirements: [req({ sourceSessionId: W, status } as any)] }
      expect(isWindowBound(l, W), status).toBe(false)
    }
  })
  it('triage 锚点：confirm 产出仍 open 的 req → bound（bind 场景）', () => {
    const l: ReqboardLedger = {
      ...emptyLedger(),
      requirements: [req({ id: 'REQ-000002', sourceSessionId: 'other', status: 'reviewing' })],
      triages: [tri({ sessionId: W, status: 'confirmed', resultRequirementId: 'REQ-000002', resultRequirementIds: ['REQ-000002'] })],
    }
    expect(isWindowBound(l, W)).toBe(true)
  })
  it('其他窗口的 req/triage 不影响本窗口判定', () => {
    const l: ReqboardLedger = {
      ...emptyLedger(),
      requirements: [req({ sourceSessionId: 'session-other', status: 'implementing' })],
      triages: [tri({ sessionId: 'session-other', status: 'confirmed', resultRequirementId: 'REQ-000001' })],
    }
    expect(isWindowBound(l, W)).toBe(false)
  })
})

describe('hasPendingSuggestion / pendingSuggestionFor', () => {
  it('本窗口有 pending 卡 → true；非 pending / 其他窗口不算', () => {
    const l: ReqboardLedger = {
      ...emptyLedger(),
      triages: [
        tri({ sessionId: W, status: 'pending', createdAt: 100 }),
        tri({ sessionId: 'session-other', status: 'pending' }),
        tri({ sessionId: W, status: 'confirmed' }),
      ],
    }
    expect(hasPendingSuggestion(l, W)).toBe(true)
    expect(hasPendingSuggestion(l, 'session-other')).toBe(true)
    expect(hasPendingSuggestion(l, 'session-nobody')).toBe(false)
    expect(pendingSuggestionFor(l, W)?.createdAt).toBe(100)
    expect(pendingSuggestionFor(l, 'session-nobody')).toBeUndefined()
  })
})

describe('captureSectionText 三分支', () => {
  it('无 windowKey → 空', () => {
    expect(captureSectionText(emptyLedger(), undefined)).toBe('')
    expect(captureSectionText(emptyLedger(), {})).toBe('')
  })
  it('bound（直挂 implementing）→ 空', () => {
    const l: ReqboardLedger = { ...emptyLedger(), requirements: [req({ sourceSessionId: W, status: 'implementing' })] }
    expect(captureSectionText(l, { agent: { id: W } })).toBe('')
  })
  it('已有 pending 卡 → 空（不重复 nag）', () => {
    const l: ReqboardLedger = { ...emptyLedger(), triages: [tri({ sessionId: W, status: 'pending' })] }
    expect(captureSectionText(l, { agent: { id: W } })).toBe('')
  })
  it('unbound 且无 pending → 引导文本（含工具名、不含 {{变量}}）', () => {
    const text = captureSectionText(emptyLedger(), { agent: { id: W } })
    expect(text.length).toBeGreaterThan(0)
    expect(text).toContain('reqboard_create')
    expect(text).toContain('ask_user_question') // 两问弹框载体
    expect(text).not.toContain('{{')
    expect(captureGuidanceText(W)).toContain(W.slice(0, 16))
  })
})

describe('captureSectionText pending 注入（确定性消息 hook 命中）', () => {
  const msg = '帮我加一个告警中心页面，把市场告警做成可视化看板'
  it('unbound 无 pending + pending 命中本窗口 → 两问弹框立项提示（引用消息原文）', () => {
    const text = captureSectionText(emptyLedger(), { agent: { id: W } }, { windowKey: W, text: msg, capturedAt: 1 })
    expect(text).toContain('检测到用户新输入')
    expect(text).toContain('reqboard_create')
    expect(text).toContain('ask_user_question') // 两问弹框载体
    expect(text).toContain('需求名称')
    expect(text).toContain('需求类型')
    expect(text).toContain('feature') // 类型选项示例
    expect(text).toContain(msg) // 引用消息原文
    expect(text).not.toContain('{{')
    expect(text).not.toContain('未绑定需求') // 不是静态引导
  })
  it('pending 为其他窗口 → 维持静态引导', () => {
    const text = captureSectionText(emptyLedger(), { agent: { id: W } }, { windowKey: 'session-other', text: msg, capturedAt: 1 })
    expect(text).toContain('未绑定需求')
    expect(text).not.toContain('检测到用户新输入')
  })
  it('bound 优先于 pending 注入 → 空', () => {
    const l: ReqboardLedger = { ...emptyLedger(), requirements: [req({ sourceSessionId: W, status: 'implementing' })] }
    expect(captureSectionText(l, { agent: { id: W } }, { windowKey: W, text: msg, capturedAt: 1 })).toBe('')
  })
  it('hasPending 优先于 pending 注入 → 空（不重复 nag）', () => {
    const l: ReqboardLedger = { ...emptyLedger(), triages: [tri({ sessionId: W, status: 'pending' })] }
    expect(captureSectionText(l, { agent: { id: W } }, { windowKey: W, text: msg, capturedAt: 1 })).toBe('')
  })
  it('pending 文本为空 → 静态引导（不注入空引用）', () => {
    const text = captureSectionText(emptyLedger(), { agent: { id: W } }, { windowKey: W, text: '   ', capturedAt: 1 })
    expect(text).toContain('未绑定需求')
  })
  it('capturePromptForMessage 折叠空白并截断超长消息到 300 字', () => {
    const folded = capturePromptForMessage(W, '  很长的一句话   又是一句话  ')
    expect(folded).not.toContain('很长的一句话   又是一句话')
    expect(folded).toContain('很长的一句话 又是一句话') // 空白折叠为单空格
    const long = 'x'.repeat(400)
    const out = capturePromptForMessage(W, long)
    expect(out).toContain('x'.repeat(300))
    expect(out).not.toContain('x'.repeat(301))
  })
})

describe('openRequirementsFor（窗口→需求投影）', () => {
  it('合并 sourceSessionId 直挂与 triage 锚点，去重，排除已结束', () => {
    const l: ReqboardLedger = {
      ...emptyLedger(),
      requirements: [
        req({ id: 'REQ-000001', sourceSessionId: W, status: 'implementing' }),
        req({ id: 'REQ-000002', sourceSessionId: W, status: 'done' }),
        req({ id: 'REQ-000003', sourceSessionId: 'other', status: 'draft' }),
      ],
      triages: [
        tri({ sessionId: W, status: 'confirmed', resultRequirementId: 'REQ-000003', resultRequirementIds: ['REQ-000003', 'REQ-000001'] }),
      ],
    }
    const ids = openRequirementsFor(l, W).map(r => r.id).sort()
    expect(ids).toEqual(['REQ-000001', 'REQ-000003'])
  })
})
describe('boundSectionText（绑定窗口推进纪律）', () => {
  it('已绑定窗口 → 注入需求清单与推进纪律（窗口不再等人点按钮）', () => {
    const l: ReqboardLedger = {
      ...emptyLedger(),
      requirements: [req({ id: 'REQ-abc123', title: '修卡片', status: 'reviewing', sourceSessionId: W })],
    }
    const text = boundSectionText(l, { agent: { id: W } })
    expect(text).toContain('REQ-abc123')
    expect(text).toContain('reviewing')
    expect(text).toContain('reqboard_move')
    expect(text).toContain('取消需求')
  })

  it('未绑定窗口 / 无 windowKey → 空段（零噪音）', () => {
    expect(boundSectionText(emptyLedger(), { agent: { id: W } })).toBe('')
    expect(boundSectionText(emptyLedger(), {})).toBe('')
  })

  it('已结束需求（done/archived）不算绑定 → 空段', () => {
    const l: ReqboardLedger = { ...emptyLedger(), requirements: [req({ status: 'done', sourceSessionId: W })] }
    expect(boundSectionText(l, { agent: { id: W } })).toBe('')
  })
})
