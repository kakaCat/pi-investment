/**
 * 项目看板 client 视图纯函数单测 —— 数据 → innerHTML 的渲染正确性。
 * 覆盖：泳道看板 / 需求详情（DAG + 任务列 + 闸门）/ 任务详情 / 待归类 / 空态错误。
 * 渲染函数零 DOM 依赖（纯字符串），Node 环境直接跑。
 */
import { describe, it, expect } from 'vitest'
import {
  buildBoard, buildReqDetail, buildTaskDetail, buildTriage, buildEmpty, buildError,
  toReqCards, LANE_STATUSES,
} from '../src/client/view.ts'
import type { BoardState, RequirementRecord, RequirementStatus, TaskRecord, TriageRecord } from '../src/client/types.ts'

// -- 测试数据构造 ---------------------------------------------------------

let seq = 0
const rid = (p: string) => `${p}-${String(++seq).padStart(6, '0')}`

function makeReq(over: Partial<RequirementRecord> = {}): RequirementRecord {
  return {
    id: rid('REQ'), title: '需求', description: '', status: 'draft',
    blocked: false, comments: [], version: 1,
    createdAt: 1700000000000, updatedAt: 1700000000000,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    ...over,
  }
}

function makeTask(over: Partial<TaskRecord> = {}): TaskRecord {
  return {
    id: rid('t'), requirementId: 'REQ-000001', title: '任务', description: '',
    phase: 'implement', side: 'fullstack', dependsOn: [],
    scope: { apis: [], tables: [], files: [] },
    acceptance: '', context: '',
    status: 'todo', blocked: false, executions: [], comments: [], version: 1,
    createdAt: 1700000000000, updatedAt: 1700000000000,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    ...over,
  }
}

function makeState(over: Partial<BoardState> = {}): BoardState {
  return { revision: 1, requirements: [], tasks: [], ready: {}, ...over }
}

function makeTriage(over: Partial<TriageRecord> = {}): TriageRecord {
  return {
    id: rid('tri'), sessionId: 'session-abc', firstMessageText: '消息',
    suggestedAction: 'create_req', score: 75, status: 'pending',
    createdAt: 1700000000000, comments: [],
    ...over,
  }
}

// -- 泳道看板 -------------------------------------------------------------

describe('buildBoard', () => {
  it('renders 6 lanes with correct status labels', () => {
    const html = buildBoard(makeState())
    for (const s of LANE_STATUSES) {
      expect(html).toContain(`data-lane="${s}"`)
    }
    expect(html).toContain('项目看板')
    expect(html).toContain('data-action="new-req"')
  })

  it('places requirement cards in their status lane', () => {
    const req = makeReq({ id: 'REQ-000001', status: 'implementing', title: '实施中的需求' })
    const html = buildBoard(makeState({ requirements: [req] }))
    expect(html).toContain('data-lane="implementing"')
    expect(html).toContain('REQ-000001')
    expect(html).toContain('实施中的需求')
  })

  it('renders task progress n/m on card', () => {
    const req = makeReq({ id: 'REQ-000001', status: 'implementing' })
    const t1 = makeTask({ id: 't-000001', requirementId: 'REQ-000001', status: 'done' })
    const t2 = makeTask({ id: 't-000002', requirementId: 'REQ-000001', status: 'todo' })
    const html = buildBoard(makeState({ requirements: [req], tasks: [t1, t2] }))
    expect(html).toContain('1/2')
  })

  it('excludes archived and canceled from lanes, shows in archived bar', () => {
    const open = makeReq({ id: 'REQ-000001', status: 'done' })
    const archived = makeReq({ id: 'REQ-000002', status: 'archived' })
    const canceled = makeReq({ id: 'REQ-000003', status: 'canceled' })
    const html = buildBoard(makeState({ requirements: [open, archived, canceled] }))
    expect(html).toContain('dsh-pm-archived-bar')
    expect(html).toContain('REQ-000002')
    expect(html).toContain('REQ-000003')
    // archived/canceled 不在泳道卡片里（lane-cards 段无其 id 的卡片）
    const laneSection = html.split('dsh-pm-archived-bar')[0]
    expect(laneSection).not.toContain('REQ-000002')
  })

  it('escapes HTML in title (XSS guard)', () => {
    const req = makeReq({ id: 'REQ-000001', title: '<script>alert(1)</script>' })
    const html = buildBoard(makeState({ requirements: [req] }))
    expect(html).not.toContain('<script>')
    expect(html).toContain('&lt;script&gt;')
  })

  it('renders blocked/paused/ready flags', () => {
    const req = makeReq({ id: 'REQ-000001', status: 'implementing', blocked: true, blockedReason: '依赖未就绪', paused: true })
    const task = makeTask({ id: 't-000001', requirementId: 'REQ-000001', status: 'todo' })
    const html = buildBoard(makeState({
      requirements: [req], tasks: [task], ready: { 'REQ-000001': ['t-000001'] },
    }))
    expect(html).toContain('阻塞')
    expect(html).toContain('暂停')
    expect(html).toContain('1 ready')
    expect(html).toContain('is-blocked')
  })

  it('renders session chip from latest execution', () => {
    const req = makeReq({ id: 'REQ-000001', status: 'implementing' })
    const task = makeTask({
      id: 't-000001', requirementId: 'REQ-000001', status: 'in_progress',
      executions: [{ id: 'e-1', sessionId: 'session-xyz', trigger: 'manual', startedAt: 1700000000000, outcome: 'running' }],
    })
    const html = buildBoard(makeState({ requirements: [req], tasks: [task] }))
    expect(html).toContain('data-action="jump-session"')
    expect(html).toContain('session-xyz')
  })
})

// -- toReqCards -----------------------------------------------------------

describe('toReqCards', () => {
  it('aggregates done/total/ready per requirement', () => {
    const req = makeReq({ id: 'REQ-000001', status: 'implementing' })
    const done = makeTask({ id: 't-000001', requirementId: 'REQ-000001', status: 'done' })
    const todo = makeTask({ id: 't-000002', requirementId: 'REQ-000001', status: 'todo' })
    const cards = toReqCards(makeState({
      requirements: [req], tasks: [done, todo], ready: { 'REQ-000001': ['t-000002'] },
    }))
    expect(cards).toHaveLength(1)
    expect(cards[0].doneCount).toBe(1)
    expect(cards[0].totalCount).toBe(2)
    expect(cards[0].readyIds).toEqual(['t-000002'])
  })

  it('filters out archived and canceled requirements', () => {
    const open = makeReq({ id: 'REQ-000001', status: 'draft' })
    const archived = makeReq({ id: 'REQ-000002', status: 'archived' })
    const cards = toReqCards(makeState({ requirements: [open, archived] }))
    expect(cards).toHaveLength(1)
    expect(cards[0].req.id).toBe('REQ-000001')
  })
})

// -- 需求详情 -------------------------------------------------------------

describe('buildReqDetail', () => {
  it('renders title, status, and gate hint for reviewing', () => {
    const req = makeReq({ id: 'REQ-000001', status: 'reviewing', title: '评审需求' })
    const html = buildReqDetail(req, [])
    expect(html).toContain('评审需求')
    expect(html).toContain('data-detail-req="REQ-000001"')
    expect(html).toContain('dsh-pm-gate')
    expect(html).toContain('data-action="move-req" data-to="decomposing"')
  })

  it('renders DAG layers by dependency depth', () => {
    const req = makeReq({ id: 'REQ-000001', status: 'implementing' })
    const a = makeTask({ id: 't-000001', requirementId: 'REQ-000001', title: 'A' })
    const b = makeTask({ id: 't-000002', requirementId: 'REQ-000001', title: 'B', dependsOn: ['t-000001'] })
    const c = makeTask({ id: 't-000003', requirementId: 'REQ-000001', title: 'C', dependsOn: ['t-000002'] })
    const html = buildReqDetail(req, [a, b, c])
    expect(html).toContain('dsh-pm-dag')
    expect(html).toContain('L0')
    expect(html).toContain('L1')
    expect(html).toContain('L2')
    expect(html).toContain('t-000001')
    expect(html).toContain('t-000003')
  })

  it('renders task columns grouped by status', () => {
    const req = makeReq({ id: 'REQ-000001', status: 'implementing' })
    const todo = makeTask({ id: 't-000001', requirementId: 'REQ-000001', status: 'todo', title: '待办任务' })
    const done = makeTask({ id: 't-000002', requirementId: 'REQ-000001', status: 'done', title: '已完成' })
    const html = buildReqDetail(req, [todo, done])
    expect(html).toContain('data-col="todo"')
    expect(html).toContain('data-col="done"')
    expect(html).toContain('待办任务')
    expect(html).toContain('已完成')
  })

  it('renders comment form with req target', () => {
    const req = makeReq({ id: 'REQ-000001', status: 'implementing' })
    const html = buildReqDetail(req, [])
    expect(html).toContain('data-action="add-comment" data-target="req" data-id="REQ-000001"')
  })

  it('escapes HTML in description', () => {
    const req = makeReq({ id: 'REQ-000001', status: 'implementing', description: '<img onerror=alert(1)>' })
    const html = buildReqDetail(req, [])
    expect(html).not.toContain('<img')
    expect(html).toContain('&lt;img')
  })
})

// -- 任务详情 -------------------------------------------------------------

describe('buildTaskDetail', () => {
  it('renders task attributes and back link to requirement', () => {
    const req = makeReq({ id: 'REQ-000001', status: 'implementing' })
    const task = makeTask({
      id: 't-000001', requirementId: 'REQ-000001', title: '任务A',
      phase: 'test', side: 'backend', acceptance: '单测全过',
      executions: [{ id: 'e-1', sessionId: 's-1', trigger: 'auto', startedAt: 1700000000000, outcome: 'succeeded', evidence: ['tests/output.log'] }],
    })
    const html = buildTaskDetail(task, req)
    expect(html).toContain('任务A')
    expect(html).toContain('data-detail-task="t-000001"')
    expect(html).toContain('data-action="back-req" data-req="REQ-000001"')
    expect(html).toContain('测试') // phase label
    expect(html).toContain('单测全过')
    expect(html).toContain('data-outcome="succeeded"')
    expect(html).toContain('tests/output.log')
    expect(html).toContain('data-action="jump-session" data-sid="s-1"')
  })

  it('renders comment form with task target', () => {
    const task = makeTask({ id: 't-000001' })
    const html = buildTaskDetail(task, undefined)
    expect(html).toContain('data-action="add-comment" data-target="task" data-id="t-000001"')
  })
})

// -- 待归类 ---------------------------------------------------------------

describe('buildTriage', () => {
  it('renders pending triage rows with action buttons', () => {
    const tri = makeTriage({ id: 'tri-000001', suggestedAction: 'bind_req', suggestedTargetId: 'REQ-000001', score: 88 })
    const html = buildTriage([tri], makeState())
    expect(html).toContain('tri-000001')
    expect(html).toContain('绑定需求 REQ-000001')
    expect(html).toContain('data-action="triage-confirm"')
    expect(html).toContain('data-action="triage-rebind"')
    expect(html).toContain('data-action="triage-reject"')
    expect(html).toContain('分 88')
  })

  it('excludes resolved triage from pending list', () => {
    const pending = makeTriage({ id: 'tri-000001', status: 'pending' })
    const resolved = makeTriage({ id: 'tri-000002', status: 'confirmed' })
    const html = buildTriage([pending, resolved], makeState())
    expect(html).toContain('tri-000001')
    expect(html).not.toContain('tri-000002')
  })

  it('renders rebind select with open requirements', () => {
    const tri = makeTriage({ id: 'tri-000001' })
    const req = makeReq({ id: 'REQ-000001', status: 'implementing', title: '开放需求' })
    const archived = makeReq({ id: 'REQ-000002', status: 'archived' })
    const html = buildTriage([tri], makeState({ requirements: [req, archived] }))
    expect(html).toContain('data-role="rebind-select"')
    expect(html).toContain('REQ-000001')
    expect(html).not.toContain('REQ-000002')
  })

  it('renders editable title/category prefill on agent-proposed create_req card', () => {
    const tri = makeTriage({
      id: 'tri-000009',
      suggestedAction: 'create_req',
      suggestedTitle: 'Agent 提议的标题',
      suggestedCategory: 'refactor',
      score: 100,
    })
    const html = buildTriage([tri], makeState())
    expect(html).toContain('data-role="triage-title"')
    expect(html).toContain('value="Agent 提议的标题"')
    expect(html).toContain('data-role="triage-category"')
    // 分类 select 预填 refactor（selected）
    expect(html).toContain('<option value="refactor" selected>重构</option>')
    // create_req 卡不渲染「改绑」按钮（无绑定目标）
    expect(html).not.toContain('data-action="triage-rebind"')
  })

  it('create_req card without structured suggestion falls back to first message as title', () => {
    const tri = makeTriage({ id: 'tri-000010', suggestedAction: 'create_req', firstMessageText: '原始消息文本' })
    const html = buildTriage([tri], makeState())
    expect(html).toContain('value="原始消息文本"')
    expect(html).toContain('<option value="feature" selected>功能</option>')
  })

  it('bind_req card keeps rebind action and no editable title input', () => {
    const tri = makeTriage({ id: 'tri-000011', suggestedAction: 'bind_req', suggestedTargetId: 'REQ-000001' })
    const html = buildTriage([tri], makeState())
    expect(html).not.toContain('data-role="triage-title"')
    expect(html).toContain('data-action="triage-rebind"')
  })

  it('escapes HTML in first message', () => {
    const tri = makeTriage({ id: 'tri-000001', firstMessageText: '<b>bold</b>' })
    const html = buildTriage([tri], makeState())
    expect(html).not.toContain('<b>')
    expect(html).toContain('&lt;b&gt;')
  })
})

// -- 空态/错误 ------------------------------------------------------------

describe('buildEmpty / buildError', () => {
  it('buildEmpty shows hint', () => {
    expect(buildEmpty()).toContain('暂无数据')
  })

  it('buildError escapes message', () => {
    expect(buildError('<script>')).not.toContain('<script>')
    expect(buildError('网络错误')).toContain('网络错误')
  })
})

// -- 窗口 ↔ 需求关联（sourceSessionId chip）---------------------------------

describe('窗口关联可见性', () => {
  it('卡片渲染来源窗口 chip（窗口码 w-xxxxxxxx + 跳转 data-sid）', () => {
    const req = makeReq({ sourceSessionId: 'session-1cee2467-95f9-46ec-9cd8-8577932e7060' })
    const html = buildBoard(makeState({ requirements: [req] }))
    expect(html).toContain('data-action="jump-session"')
    expect(html).toContain('data-sid="session-1cee2467-95f9-46ec-9cd8-8577932e7060"')
    expect(html).toContain('窗口 w-1cee2467')
  })

  it('人工建卡（无 sourceSessionId）不渲染窗口 chip', () => {
    const html = buildBoard(makeState({ requirements: [makeReq()] }))
    expect(html).not.toContain('dsh-pm-window')
  })

  it('详情页头部也显示来源窗口 chip', () => {
    const req = makeReq({ sourceSessionId: 'session-ac92e536-f709-466d-a5dd-aead9e70f6f7' })
    const html = buildReqDetail(req, [])
    expect(html).toContain('窗口 w-ac92e536')
    expect(html).toContain('data-sid="session-ac92e536-f709-466d-a5dd-aead9e70f6f7"')
  })

  it('draft 需求给出「提交评审」人工入口（自动推进之外的兜底）', () => {
    const html = buildReqDetail(makeReq({ status: 'draft' }), [])
    expect(html).toContain('data-action="move-req"')
    expect(html).toContain('data-to="reviewing"')
  })
})
describe('评审态人工回退口', () => {
  it('reviewing 详情同时给出「确认方案」与「退回立项」', () => {
    const html = buildReqDetail(makeReq({ status: 'reviewing' }), [])
    expect(html).toContain('data-to="decomposing"')
    expect(html).toContain('data-to="draft"')
  })
})
describe('泳道卡面操作按钮（不进详情页即可推进）', () => {
  const actionsOf = (status: RequirementStatus): string =>
    buildBoard(makeState({ requirements: [makeReq({ status })] }))

  it('draft 卡面给「提交评审」并带 data-id（卡面直连 move-req）', () => {
    const html = actionsOf('draft')
    expect(html).toContain('dsh-pm-card-actions')
    expect(html).toContain('data-action="move-req"')
    expect(html).toContain('data-to="reviewing"')
    expect(html).toMatch(/data-id="REQ-\d{6}"/)
    expect(html).toContain('提交评审')
  })

  it('每个状态给出对应人工动作：确认方案 / 确认拆分 / 提交验收 / 验收通过 / 归档', () => {
    expect(actionsOf('reviewing')).toContain('data-to="decomposing"')
    expect(actionsOf('decomposing')).toContain('data-to="implementing"')
    expect(actionsOf('implementing')).toContain('data-to="accepting"')
    expect(actionsOf('accepting')).toContain('data-to="done"')
    expect(actionsOf('done')).toContain('data-to="archived"')
  })

  it('卡面按钮 data-id 指向该卡自身需求（多卡互不串）', () => {
    const a = makeReq({ status: 'draft' })
    const b = makeReq({ status: 'accepting' })
    const html = buildBoard(makeState({ requirements: [a, b] }))
    expect(html).toContain(`data-id="${a.id}"`)
    expect(html).toContain(`data-id="${b.id}"`)
  })

  it('归档/取消态不进泳道，无卡面按钮', () => {
    const html = buildBoard(makeState({ requirements: [makeReq({ status: 'archived' })] }))
    expect(html).not.toContain('dsh-pm-card-actions')
  })
})
