/**
 * 项目看板 client 视图纯函数单测 —— 数据 → innerHTML 的渲染正确性。
 * 覆盖：泳道看板 / 需求详情（DAG + 任务列 + 闸门）/ 任务详情 / 待归类 / 空态错误。
 * 渲染函数零 DOM 依赖（纯字符串），Node 环境直接跑。
 */
import { describe, it, expect } from 'vitest'
import {
  buildBoard, buildReqDetail, buildTaskDetail, buildTasksPage, buildTriage, buildEmpty, buildError,
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
  it('renders title, status, and gate hint for brainstorming', () => {
    const req = makeReq({ id: 'REQ-000001', status: 'brainstorming', title: '评审需求' })
    const html = buildReqDetail(req, [])
    expect(html).toContain('评审需求')
    expect(html).toContain('data-detail-req="REQ-000001"')
    expect(html).toContain('dsh-pm-gate')
    expect(html).toContain('data-action="move-req" data-to="design"')
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

  it('renders task table（REQ-6f39b5：任务列已改为表格，对齐 prototype）', () => {
    const req = makeReq({ id: 'REQ-000001', status: 'implementing' })
    const todo = makeTask({ id: 't-000001', requirementId: 'REQ-000001', status: 'todo', title: '待办任务' })
    const done = makeTask({ id: 't-000002', requirementId: 'REQ-000001', status: 'done', title: '已完成' })
    const html = buildReqDetail(req, [todo, done])
    expect(html).toContain('dsh-pm-task-table')
    expect(html).toContain('dsh-pm-task-status todo')
    expect(html).toContain('dsh-pm-task-status done')
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
    expect(html).toContain('data-to="brainstorming"')
  })
})
describe('评审态人工回退口', () => {
  it('brainstorming 详情同时给出「→ 设计」与「退回立项」（REQ-6f39b5：对齐 REQ_TRANSITIONS brainstorming>design）', () => {
    const html = buildReqDetail(makeReq({ status: 'brainstorming' }), [])
    expect(html).toContain('data-to="design"')
    expect(html).toContain('data-to="draft"')
  })
})
describe('泳道卡面操作按钮（不进详情页即可推进）', () => {
  const actionsOf = (status: RequirementStatus): string =>
    buildBoard(makeState({ requirements: [makeReq({ status })] }))

  it('draft 卡面给「开始需求分析」并带 data-id（卡面直连 move-req）', () => {
    const html = actionsOf('draft')
    expect(html).toContain('dsh-pm-card-actions')
    expect(html).toContain('data-action="move-req"')
    expect(html).toContain('data-to="brainstorming"')
    expect(html).toMatch(/data-id="REQ-\d{6}"/)
    expect(html).toContain('→ 需求分析') // REQ-6f39b5：按钮统一「→ 下一阶段」格式
  })

  it('每个状态给出对应动作：→ 设计 / → 拆分 / → 实施 / → 验收 / → 归档（REQ-6f39b5 箭头格式 + REQ-9f4a44 验收直归档）', () => {
    expect(actionsOf('brainstorming')).toContain('data-to="design"') // 需求分析 → 设计
    expect(actionsOf('design')).toContain('data-to="decomposing"') // 设计 → 拆分
    expect(actionsOf('decomposing')).toContain('data-to="implementing"')
    expect(actionsOf('implementing')).toContain('data-to="accepting"')
    expect(actionsOf('accepting')).toContain('data-to="archived"') // REQ-9f4a44：验收通过直接归档
    expect(actionsOf('done')).not.toContain('data-action="move-req"') // done 为 legacy 死状态，不给操作
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
describe('卡面按钮视觉一致性（复用 .dsh-pm-btn 体系）', () => {
  it('卡面按钮使用 dsh-pm-btn（与页头/详情页同款），不引入第二套按钮样式', () => {
    const html = buildBoard(makeState({ requirements: [makeReq({ status: 'draft' })] }))
    expect(html).toContain('class="dsh-pm-btn sm primary"')
    expect(html).not.toContain('dsh-pm-card-btn')
  })
})

// ---------------------------------------------------------------------------
// 时间线 / 甘特图 / 任务页（用户反馈：需求没有对应的时间、拆分是不是真拆、有没有任务页）
// ---------------------------------------------------------------------------

const T0 = 1700000000000 // 固定基准，避免测试依赖当前时间
const HOUR = 3600_000

describe('需求时间线（各状态进入时间 + 停留时长）', () => {
  const hist = [
    { status: 'draft', at: T0, by: { kind: 'human' as const } },
    { status: 'brainstorming', at: T0 + HOUR, by: { kind: 'system' as const } },
    { status: 'decomposing', at: T0 + 3 * HOUR, by: { kind: 'agent' as const, sessionId: 'session-1cee2467-x' } },
  ]

  it('泳道卡面直接显示创建时间与当前态停留时长', () => {
    const req = makeReq({ status: 'decomposing', statusHistory: hist })
    const html = buildBoard(makeState({ requirements: [req] }), T0 + 5 * HOUR)
    expect(html).toContain('dsh-pm-card-time')
    expect(html).toContain('创建 ')
    expect(html).toContain('已停留 2 小时 0 分')
  })

  it('详情页时间线：7 个里程碑齐全（含需求分析/设计，无完成节点）、未到达显「—」、窗口码与停留时长可见', () => {
    const req = makeReq({ status: 'decomposing', statusHistory: hist })
    const html = buildReqDetail(req, [], T0 + 5 * HOUR)
    expect(html).toContain('dsh-pm-timeline')
    for (const label of ['立项', '需求分析', '设计', '拆分', '实施', '验收', '归档']) { // REQ-6f39b5：7 态（用户裁定去掉 done/完成节点）
      expect(html).toContain(label)
    }
    expect(html).toContain('dsh-pm-tl-row pending') // 未到达的里程碑
    expect(html).toContain('停留 2 小时 0 分') // draft → brainstorming 段
    expect(html).toContain('w-1cee2467') // 操作者窗口码
    expect(html).toContain('至今') // 未完结的需求统计到当前时刻
  })

  it('回填事件显式标注「回填」（不把推导值伪装成原始记录）', () => {
    const req = makeReq({
      status: 'brainstorming',
      statusHistory: [
        { status: 'draft', at: T0, by: { kind: 'human' }, inferred: true },
        { status: 'brainstorming', at: T0 + HOUR, by: { kind: 'system' }, inferred: true },
      ],
    })
    expect(buildReqDetail(req, [], T0 + 2 * HOUR)).toContain('回填')
  })

  it('老记录无 statusHistory → 只渲染「创建 + 由 updatedAt 推导的当前态」，中间态留空（不编造）', () => {
    const req = makeReq({ status: 'implementing' })
    const html = buildReqDetail(req, [], T0 + HOUR)
    expect(html).toContain('dsh-pm-timeline')
    // 7 个里程碑 - 已知 2 个（立项/实施）= 5 个未到达
    expect(html.match(/dsh-pm-tl-row pending/g)?.length).toBe(5) // 7 个里程碑 - 已知 2 个（立项/实施）
    expect(html).toContain('回填')
    // 评审/拆分等中间态必须是「—」，不得按时间戳插值编造出精确时间
    expect(html).toContain('data-status="brainstorming"><span class="dsh-pm-tl-label">需求分析</span><span class="dsh-pm-tl-time">—</span>')
    expect(html).toContain('data-status="decomposing"><span class="dsh-pm-tl-label">拆分</span><span class="dsh-pm-tl-time">—</span>')
  })

  it('任务详情也有时间线（含执行段耗时）', () => {
    const t = makeTask({
      status: 'done',
      updatedAt: T0 + 2 * HOUR,
      statusHistory: [
        { status: 'todo', at: T0, by: { kind: 'agent' } },
        { status: 'in_progress', at: T0 + HOUR, by: { kind: 'agent' } },
        { status: 'done', at: T0 + 2 * HOUR, by: { kind: 'agent' } },
      ],
    })
    const html = buildTaskDetail(t, undefined, T0 + 3 * HOUR)
    expect(html).toContain('时间线')
    expect(html).toContain('停留 1 小时 0 分')
  })
})

describe('甘特图与任务页（拆分可视化）', () => {
  function fixture() {
    const req = makeReq({
      id: 'REQ-abc123',
      title: '看板需求',
      status: 'implementing',
      statusHistory: [
        { status: 'draft', at: T0, by: { kind: 'human' } },
        { status: 'brainstorming', at: T0 + HOUR, by: { kind: 'system' } },
        { status: 'decomposing', at: T0 + 2 * HOUR, by: { kind: 'agent' } },
        { status: 'implementing', at: T0 + 3 * HOUR, by: { kind: 'system' } },
      ],
    })
    const t1 = makeTask({
      id: 't-000001', requirementId: req.id, title: '协议层加时间线', phase: 'doc', side: 'doc',
      status: 'done', createdAt: T0 + 2 * HOUR, updatedAt: T0 + 4 * HOUR,
      statusHistory: [
        { status: 'todo', at: T0 + 2 * HOUR, by: { kind: 'agent' } },
        { status: 'in_progress', at: T0 + 3 * HOUR, by: { kind: 'agent' } },
        { status: 'done', at: T0 + 4 * HOUR, by: { kind: 'agent' } },
      ],
    })
    const t2 = makeTask({
      id: 't-000002', requirementId: req.id, title: '客户端甘特图', phase: 'ui', side: 'frontend',
      dependsOn: ['t-000001'], status: 'in_progress', createdAt: T0 + 4 * HOUR, updatedAt: T0 + 5 * HOUR,
      statusHistory: [
        { status: 'todo', at: T0 + 4 * HOUR, by: { kind: 'agent' } },
        { status: 'in_progress', at: T0 + 5 * HOUR, by: { kind: 'agent' } },
      ],
    })
    return { req, t1, t2, now: T0 + 6 * HOUR }
  }

  it('任务页：按需求分组 + 里程碑条 + 甘特图 + 任务表（含耗时列）', () => {
    const { req, t1, t2, now } = fixture()
    const html = buildTasksPage(makeState({ requirements: [req], tasks: [t1, t2] }), now)
    expect(html).toContain('任务')
    expect(html).toContain('dsh-pm-tasks-group')
    expect(html).toContain('REQ-abc123')
    expect(html).toContain('dsh-pm-strip-item')
    expect(html).toContain('dsh-pm-gantt')
    expect(html).toContain('dsh-pm-ttable')
    expect(html).toContain('共 2 小时 0 分') // t1 已完成的真实耗时
    expect(html).toContain('已用 2 小时 0 分') // t2 进行中（创建至今）
    expect(html).toContain('data-action="open-task"')
  })

  it('任务页空态给出两种真实来源（人工建卡 / agent 真拆分）', () => {
    const html = buildTasksPage(makeState({ requirements: [makeReq()] }), T0)
    expect(html).toContain('还没有任务')
    expect(html).toContain('reqboard_decompose')
  })

  it('任务页与甘特图中的用户文本经转义（XSS 防线不因新视图失效）', () => {
    const { req, t1, now } = fixture()
    const evil = { ...t1, title: '<img src=x onerror=alert(1)>' }
    const html = buildTasksPage(makeState({ requirements: [req], tasks: [evil] }), now)
    expect(html).not.toContain('<img src=x')
    expect(html).toContain('&lt;img')
  })
})

// ---------------------------------------------------------------------------
// 拆分计划（plan mode）——人在这里唯一需要动手的地方
// ---------------------------------------------------------------------------

describe('拆分计划卡面徽章（plan mode；REQ-6f39b5：详情页计划卡已删，徽章保留在泳道卡片）', () => {
  const basePlan = {
    path: 'docs/requirements/REQ-abc123/plan.md',
    summary: '目标：加计划模式；做法：先提交计划再拆',
    tasks: [{ key: 'proto', title: '协议层加计划字段', phase: 'implement' as const, side: 'backend' as const, acceptance: 'protocol.ts 单测绿' }],
    submittedAt: T0,
    submittedBy: { kind: 'agent' as const, sessionId: 'session-1cee2467-x' },
  }

  it('卡面徽章：待批 / 已批 / 被退 三态可见', () => {
    const pending = makeReq({ id: 'REQ-abc123', status: 'brainstorming', plan: basePlan })
    expect(buildBoard(makeState({ requirements: [pending] }), T0)).toContain('计划待批')

    const approved = makeReq({ id: 'REQ-abc123', status: 'decomposing', plan: { ...basePlan, approvedAt: T0 + HOUR, approvedBy: { kind: 'human' as const } } })
    expect(buildBoard(makeState({ requirements: [approved] }), T0)).toContain('计划已批')

    const rejected = makeReq({ id: 'REQ-abc123', status: 'brainstorming', plan: { ...basePlan, rejectedAt: T0 + HOUR, rejectedReason: '验收标准太虚，重写' } })
    expect(buildBoard(makeState({ requirements: [rejected] }), T0)).toContain('计划被退')
  })
})

// ---------------------------------------------------------------------------
// 验收（人工审核）与归档（文档合并）—— 交付的后半程
// ---------------------------------------------------------------------------

describe('验收区与归档区', () => {
  it('没有验收材料时说明要交什么（不是空白）', () => {
    const html = buildReqDetail(makeReq({ status: 'accepting' }), [], T0)
    expect(html).toContain('验收（人工审核）')
    expect(html).toContain('reqboard_verify_submit')
    expect(html).toContain('人工审核前需要证据')
  })

  it('待人工审核：证据逐条展示 + 通过/退回按钮 + 卡面「待人工审核」', () => {
    const req = makeReq({
      status: 'accepting',
      verification: {
        summary: '时间线/甘特图已上线',
        evidence: ['pnpm vitest run → 178 passed / 14 files', '截图 /tmp/board.png'],
        submittedAt: T0,
        submittedBy: { kind: 'agent' as const, sessionId: 'session-1cee2467-x' },
      },
    })
    const detail = buildReqDetail(req, [], T0 + HOUR)
    expect(detail).toContain('data-state="pending"')
    expect(detail).toContain('待人工审核')
    expect(detail).toContain('178 passed')
    expect(detail).toContain('data-action="verify-pass"')
    expect(detail).toContain('data-action="verify-rework"')
    expect(buildBoard(makeState({ requirements: [req] }), T0)).toContain('待人工审核')
  })

  it('人工审核通过：显示通过时间与意见，按钮消失', () => {
    const req = makeReq({
      status: 'done',
      verification: {
        summary: '已上线', evidence: ['npm test'], submittedAt: T0,
        submittedBy: { kind: 'agent' as const }, reviewedAt: T0 + HOUR, reviewedBy: { kind: 'human' as const }, decision: 'pass' as const,
      },
    })
    const detail = buildReqDetail(req, [], T0 + 2 * HOUR)
    expect(detail).toContain('data-state="pass"')
    expect(detail).not.toContain('data-action="verify-pass"')
  })

  it('退回返工：审核意见原样展示', () => {
    const req = makeReq({
      status: 'implementing',
      verification: {
        summary: '做完了', evidence: ['npm test'], submittedAt: T0, submittedBy: { kind: 'agent' as const },
        reviewedAt: T0 + HOUR, reviewedBy: { kind: 'human' as const }, decision: 'rework' as const, reviewNote: '甘特图缺依赖连线',
      },
    })
    const detail = buildReqDetail(req, [], T0 + 2 * HOUR)
    expect(detail).toContain('已退回返工')
    expect(detail).toContain('审核意见：甘特图缺依赖连线')
  })

  it('归档区：材料已备时列目录/文档/合并去向/索引，并给出人工归档按钮；归档后按钮消失', () => {
    const archive = {
      dir: 'agent-dh/docs/requirements/REQ-abc123',
      docs: [
        { kind: 'requirement' as const, path: 'agent-dh/docs/requirements/REQ-abc123/requirement.md' },
        { kind: 'verification' as const, path: 'agent-dh/docs/requirements/REQ-abc123/verification.md' },
      ],
      mergedInto: ['agent-dh/docs/architecture/requirement-board.md'],
      indexEntry: '需求看板加时间线与计划模式',
      submittedAt: T0,
      submittedBy: { kind: 'agent' as const },
    }
    const ready = makeReq({ status: 'done', archive })
    const detail = buildReqDetail(ready, [], T0 + HOUR)
    expect(detail).toContain('agent-dh/docs/requirements/REQ-abc123')
    expect(detail).toContain('需求说明')
    expect(detail).toContain('agent-dh/docs/architecture/requirement-board.md')
    expect(detail).toContain('索引条目：需求看板加时间线与计划模式')
    expect(detail).toContain('data-action="archive-req"')
    expect(buildBoard(makeState({ requirements: [ready] }), T0)).toContain('待归档')

    const archived = makeReq({ status: 'archived', archive: { ...archive, archivedAt: T0 + HOUR, archivedBy: { kind: 'human' as const } } })
    const doneHtml = buildReqDetail(archived, [], T0 + 2 * HOUR)
    expect(doneHtml).toContain('已归档')
    expect(doneHtml).not.toContain('data-action="archive-req"')
  })

  it('未备材料时指向规范文档（人要知道去哪儿看规则）', () => {
    const detail = buildReqDetail(makeReq({ status: 'done' }), [], T0)
    expect(detail).toContain('reqboard_archive_submit')
    expect(detail).toContain('agent-dh/docs/architecture/requirement-archive.md')
  })

  it('归档区展示说明书更新点（金字塔向上生长）；无更新时显示理由', () => {
    const base = {
      dir: 'agent-dh/docs/requirements/REQ-abc123',
      docs: [{ kind: 'requirement' as const, path: 'agent-dh/docs/requirements/REQ-abc123/requirement.md' }],
      mergedInto: ['agent-dh/docs/architecture/requirement-board.md'],
      indexEntry: '看板加时间线',
      submittedAt: T0,
      submittedBy: { kind: 'agent' as const },
    }
    const withManual = makeReq({
      status: 'done',
      archive: { ...base, manualUpdates: [{ path: 'docs/architecture/project-manual.md', section: '术语表', summary: '新增两个术语指针' }] },
    })
    const html = buildReqDetail(withManual, [], T0)
    expect(html).toContain('项目说明书更新（金字塔向上生长）')
    expect(html).toContain('docs/architecture/project-manual.md')
    expect(html).toContain('新增两个术语指针')

    const noManual = makeReq({ status: 'done', archive: { ...base, manualNote: '纯维护，不改项目认知' } })
    expect(buildReqDetail(noManual, [], T0)).toContain('无（纯维护，不改项目认知）')
  })

})


// ---------------------------------------------------------------------------
// REQ-31e11f t8：buildReqDetail 阶段导航（7 节点点击入口）
// ---------------------------------------------------------------------------

describe('buildReqDetail 进度点与 Tab（REQ-6f39b5，替代 REQ-31e11f 节点导航）', () => {
  it('渲染 8 态进度点（含归档），当前态高亮', () => {
    const req = makeReq({ id: 'REQ-000001', status: 'implementing' })
    const html = buildReqDetail(req, [])
    expect(html).toContain('dsh-pm-progress-dots')
    // 8 个进度点
    const dots = html.match(/dsh-pm-dot-wrapper/g)
    expect(dots).not.toBeNull()
    expect(dots!.length).toBe(8)
    // 当前态（实施）高亮
    expect(html).toContain('dsh-pm-dot-wrapper current')
    // 已完成态
    expect(html).toContain('dsh-pm-dot-wrapper completed')
    // 含归档节点标签
    expect(html).toContain('归档')
  })

  it('渲染 4 个 Tab 与对应内容区（概览默认 active）', () => {
    const req = makeReq({ id: 'REQ-000001', status: 'implementing' })
    const html = buildReqDetail(req, [])
    expect(html).toContain('dsh-pm-tabs')
    expect(html).toContain('data-action="switch-tab"')
    expect(html).toContain('data-tab="overview"')
    expect(html).toContain('data-tab="execution"')
    expect(html).toContain('data-tab="timeline"')
    expect(html).toContain('data-tab="archive"')
    // 4 个内容区，概览默认显示
    expect(html).toContain('data-tab-content="overview"')
    expect(html).toContain('data-tab-content="execution"')
    expect(html).toContain('data-tab-content="timeline"')
    expect(html).toContain('data-tab-content="archive"')
    expect(html).toContain('dsh-pm-tab-content active')
  })

  it('含 stage-detail-container（节点详情渲染容器）', () => {
    const req = makeReq({ id: 'REQ-000001', status: 'implementing' })
    const html = buildReqDetail(req, [])
    expect(html).toContain('dsh-pm-stage-detail-container')
  })
})

// ── 立项取消按钮（2026-09-20：更名置首 + 全在途态渲染，REQ-6cbbf7 解锁配套）──
describe('立项取消按钮', () => {
  it('decomposing 详情含「立项取消」且排在「→ 实施」之前', () => {
    const html = buildReqDetail(makeReq({ status: 'decomposing' }), [])
    expect(html).toContain('立项取消')
    expect(html).toContain('→ 实施')
    expect(html.indexOf('立项取消')).toBeLessThan(html.indexOf('→ 实施'))
  })
  it('全部在途态均渲染「立项取消」（draft/brainstorming/design/decomposing/implementing/accepting）', () => {
    for (const s of ['draft', 'brainstorming', 'design', 'decomposing', 'implementing', 'accepting'] as const) {
      expect(buildReqDetail(makeReq({ status: s }), [])).toContain('立项取消')
    }
  })
  it('终态不渲染「立项取消」（done/canceled/archived）', () => {
    for (const s of ['done', 'canceled', 'archived'] as const) {
      expect(buildReqDetail(makeReq({ status: s }), [])).not.toContain('立项取消')
    }
  })
})
