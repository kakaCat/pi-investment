/**
 * serves: FR-1, FR-3
 *
 * REQ-31e11f B 类验收问题修补单测（#5/#6/#7/#8/#9）；REQ-a8d582 起承接 FR-1/FR-3 的
 * 按钮可见性与确认文案用例。
 * 覆盖：文档记录并入 req.artifacts（按 stage 排序去重）/ 审批入口外置到常驻操作条
 * （折叠区不再藏着按钮）/ 评论 data-actor 人机区分 / 窗口 chip 可点且失败有明确反馈。
 * 渲染函数零 DOM 依赖，Node 环境直接跑。
 */
import { describe, it, expect } from 'vitest'
import { buildReqDetail, buildListView } from '../src/client/view.ts'
import { jumpResultMessage, verifyConfirmCopy } from '../src/client/board-mount.ts'
import type { BoardState, RequirementRecord, StageArtifact } from '../src/client/types.ts'

const T0 = 1700000000000
const HOUR = 3600_000

let seq = 0
const rid = (p: string) => p + '-' + String(++seq).padStart(6, '0')

function makeReq(over: Partial<RequirementRecord> = {}): RequirementRecord {
  return {
    id: rid('REQ'), title: '需求', description: '', status: 'draft',
    blocked: false, comments: [], version: 1,
    createdAt: T0, updatedAt: T0,
    createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
    ...over,
  }
}

function makeArtifact(over: Partial<StageArtifact> = {}): StageArtifact {
  return {
    stage: 'brainstorming', kind: 'requirement',
    path: 'docs/requirements/REQ-x/requirement.md',
    registeredAt: T0, registeredBy: { kind: 'agent' },
    ...over,
  }
}

function makeState(over: Partial<BoardState> = {}): BoardState {
  return { revision: 1, requirements: [], tasks: [], ready: {}, ...over }
}

/** 抽出文档区里按序渲染的路径（collectReqDocs 的可见结果）。 */
function docPaths(html: string): string[] {
  const out: string[] = []
  const re = /data-doc-path="([^"]+)"/g
  let m: RegExpExecArray | null
  while ((m = re.exec(html)) !== null) out.push(m[1])
  return out
}

/** 抽出详情头常驻操作条的 HTML 片段（到其收尾 </div> 为止）。 */
function actionBar(html: string): string {
  const i = html.indexOf('dsh-pm-action-bar')
  if (i < 0) return ''
  const j = html.indexOf('</div>', i)
  return j < 0 ? html.slice(i) : html.slice(i, j)
}

const basePlan = {
  path: 'docs/requirements/REQ-x/plan.md',
  summary: '目标：修补验收问题',
  tasks: [],
  submittedAt: T0,
  submittedBy: { kind: 'agent' as const },
}

// -- #6/#7 文档记录补全 -----------------------------------------------------

describe('文档记录并入节点产物（#6/#7）', () => {
  const artifacts: StageArtifact[] = [
    makeArtifact({ stage: 'implementing', kind: 'task_detail', path: 'docs/requirements/REQ-x/tasks/t-1.md' }),
    makeArtifact({ stage: 'done', kind: 'archive', path: 'docs/requirements/REQ-x/archive' }),
    makeArtifact({ stage: 'brainstorming', kind: 'requirement', path: 'docs/requirements/REQ-x/requirement.md' }),
    makeArtifact({ stage: 'accepting', kind: 'verification', path: 'docs/requirements/REQ-x/verification.md' }),
    makeArtifact({ stage: 'design', kind: 'plan', path: 'docs/requirements/REQ-x/plan.md' }),
    makeArtifact({ stage: 'decomposing', kind: 'decomposition', path: 'docs/requirements/REQ-x/decomposition.md' }),
  ]

  it('artifacts 按 stage 流水线序进入文档区，且与 docLinks/archive.docs 去重', () => {
    const req = makeReq({
      status: 'archived',
      artifacts,
      docLinks: { requirement: 'docs/requirements/REQ-x/requirement.md' },
      archive: {
        dir: 'docs/requirements/REQ-x',
        docs: [{ kind: 'retro', path: 'docs/requirements/REQ-x/retro.md' }],
        mergedInto: [], indexEntry: '修补', submittedAt: T0, submittedBy: { kind: 'agent' },
      },
    })
    expect(docPaths(buildReqDetail(req, [], T0))).toEqual([
      'docs/requirements/REQ-x/requirement.md',
      'docs/requirements/REQ-x/plan.md',
      'docs/requirements/REQ-x/decomposition.md',
      'docs/requirements/REQ-x/tasks/t-1.md',
      'docs/requirements/REQ-x/verification.md',
      'docs/requirements/REQ-x/archive',
      'docs/requirements/REQ-x/retro.md',
    ])
  })

  it('产物种类带上可读标签（2026-09-21：decomposition 标签改「拆分计划」，旧 plan 标「拆分计划（旧版）」）', () => {
    const html = buildReqDetail(makeReq({ status: 'archived', artifacts }), [], T0)
    for (const label of ['需求文档', '拆分计划（旧版）', '拆分计划', '任务卡', '验收材料', '归档材料']) {
      expect(html).toContain(label)
    }
  })

  it('无 artifacts 时保留既有来源（docLinks + plan.path）', () => {
    const req = makeReq({
      status: 'design',
      docLinks: { ui: 'docs/ui.md' },
      plan: basePlan,
    })
    expect(docPaths(buildReqDetail(req, [], T0))).toEqual(['docs/ui.md', 'docs/requirements/REQ-x/plan.md'])
  })
})

// -- #8 审批入口外置 --------------------------------------------------------

describe('审批入口外置到常驻操作条（#8）', () => {
  it('计划待批：批准/退回在操作条里，且位于任何折叠区之前；折叠区不再放按钮', () => {
    const req = makeReq({ id: 'REQ-bar1', status: 'design', plan: basePlan })
    const html = buildReqDetail(req, [], T0)
    expect(html).toContain('dsh-pm-action-bar')
    const bar = actionBar(html)
    expect(bar).toContain('data-action="plan-approve"')
    expect(bar).toContain('data-action="plan-reject"')
    expect(html.indexOf('dsh-pm-action-bar')).toBeLessThan(html.indexOf('<details'))
    // 折叠区仍是内容入口，但不再藏审批按钮
    expect(html.slice(html.indexOf('<details'))).not.toContain('data-action="plan-approve"')
    expect(html.slice(html.indexOf('<details'))).not.toContain('data-action="plan-reject"')
  })

  it('验收态已交材料：操作条给 verify-pass/verify-rework，且不重复给等价的 move-req', () => {
    const req = makeReq({
      id: 'REQ-bar2', status: 'accepting',
      verification: { summary: '已交付', evidence: ['npm test → 370 passed'], submittedAt: T0, submittedBy: { kind: 'agent' } },
    })
    const html = buildReqDetail(req, [], T0)
    const bar = actionBar(html)
    expect(bar).toContain('data-action="verify-pass"')
    expect(bar).toContain('data-action="verify-rework"')
    // REQ-f0579a t3 断言精确化：原断言「无任何 move-req」与 2026-09-20「立项取消全在途态渲染置首」
    // 裁定冲突（b2b37d9b 实现时未同步本断言）。两条裁定合并后的精确语义：
    // 验收态不给**阶段推进类** move-req（verify-pass 已覆盖），但破坏性的「立项取消」
    // （data-to=canceled，仅人可操作）允许存在。故只校验 move-req 的 data-to 集合 ⊆ {canceled}。
    const moveTos = [...bar.matchAll(/data-action="move-req" data-to="([^"]+)"/g)].map(m => m[1])
    expect(moveTos.every(to => to === 'canceled')).toBe(true)
    expect((bar.match(/data-action="verify-pass"/g) ?? []).length).toBe(1)
    expect(html.slice(html.indexOf('<details'))).not.toContain('data-action="verify-pass"')
  })

  it('验收态尚未交材料：操作条照样给 verify-pass（REQ-a8d582 FR-3 显示条件只看阶段）', () => {
    const req = makeReq({ id: 'REQ-bar3', status: 'accepting' })
    const bar = actionBar(buildReqDetail(req, [], T0))
    // 旧实现"未交材料就不铺按钮、只写一行提示"已被用户 2026-09-20 的订正推翻：
    // 判据是**验收阶段**，不是"已交验收材料"。不合格/缺材料的风险不再靠隐藏按钮回避，
    // 改由点击后的确认弹框 + 覆盖留痕承担（见 verifyConfirmCopy 的用例）。
    expect(bar).toContain('data-action="verify-pass"')
    expect(bar).toContain('data-action="verify-rework"')
    expect(bar).not.toContain('才会出现「验收通过」')
    // REQ-f0579a t3 断言精确化（同上一条）：不允许推进类 move-req，允许「立项取消」。
    const moveTos = [...bar.matchAll(/data-action="move-req" data-to="([^"]+)"/g)].map(m => m[1])
    expect(moveTos.every(to => to === 'canceled')).toBe(true)
  })

  it('已完成且材料已备：操作条给 archive-req，折叠区无重复按钮', () => {
    const req = makeReq({
      id: 'REQ-bar4', status: 'done',
      archive: {
        dir: 'docs/requirements/REQ-x', docs: [], mergedInto: [],
        indexEntry: '修补完成', submittedAt: T0, submittedBy: { kind: 'agent' },
      },
    })
    const html = buildReqDetail(req, [], T0)
    expect(actionBar(html)).toContain('data-action="archive-req"')
    expect((html.match(/data-action="archive-req"/g) ?? []).length).toBe(1)
    expect(html.slice(html.indexOf('<details'))).not.toContain('data-action="archive-req"')
  })

  it('终态（archived）已无可用人工操作 → 不渲染空操作条', () => {
    expect(buildReqDetail(makeReq({ status: 'archived' }), [], T0)).not.toContain('dsh-pm-action-bar')
  })

  it('已批准的计划的详情：操作条不再出现 plan-approve', () => {
    const req = makeReq({
      id: 'REQ-bar5', status: 'decomposing',
      plan: { ...basePlan, approvedAt: T0 + HOUR, approvedBy: { kind: 'human' } },
    })
    expect(buildReqDetail(req, [], T0 + 2 * HOUR)).not.toContain('data-action="plan-approve"')
  })
})

// -- REQ-a8d582 FR-1/FR-4：「验收通过」确认文案装配 ---------------------------

describe('「验收通过」二次确认文案（REQ-a8d582 FR-1/FR-4）', () => {
  const sheetWith = (items: { id: string; status: 'passed' | 'failed' | 'pending' }[]): any => ({
    version: 3, generatedAt: T0,
    items: items.map(i => ({
      id: i.id, source: { kind: 'requirement' as const },
      criterion: '【任务】验收：跑 npx vitest run 看到全绿', evidence: [], status: i.status,
    })),
  })

  it('有不合格项：文案含通过/不通过/未裁决计数，且给出覆盖说明', () => {
    const req = makeReq({
      id: 'REQ-vc1', status: 'accepting',
      verification: {
        summary: '交付', evidence: ['npx vitest run 全绿'], submittedAt: T0, submittedBy: { kind: 'agent' },
        sheet: sheetWith([
          { id: 'v3-1', status: 'passed' },
          { id: 'v3-2', status: 'failed' },
          { id: 'v3-3', status: 'pending' },
        ]),
      },
    })
    const copy = verifyConfirmCopy(req)
    expect(copy.message).toContain('通过 1')
    expect(copy.message).toContain('不通过 1')
    expect(copy.message).toContain('未裁决 1')
    expect(copy.message).toContain('覆盖通过')
    expect(copy.overrideDetail).toContain('不通过 1 项 / 未裁决 1 项')
  })

  it('全过且材料齐全：不是覆盖（不给 overrideDetail），也不出现"不合格/覆盖"字样', () => {
    const req = makeReq({
      id: 'REQ-vc2', status: 'accepting',
      verification: {
        summary: '交付', evidence: ['npx vitest run 全绿'], submittedAt: T0, submittedBy: { kind: 'agent' },
        sheet: sheetWith([{ id: 'v3-1', status: 'passed' }, { id: 'v3-2', status: 'passed' }]),
      },
    })
    const copy = verifyConfirmCopy(req)
    expect(copy.overrideDetail).toBeUndefined()
    expect(copy.message).not.toContain('不合格')
    expect(copy.message).not.toContain('覆盖')
  })

  it('没有验收材料：文案讲清"没有验收证据"，并给出覆盖说明', () => {
    const copy = verifyConfirmCopy(makeReq({ id: 'REQ-vc3', status: 'accepting' }))
    expect(copy.message).toContain('没有验收证据')
    expect(copy.overrideDetail).toContain('尚无验收材料')
  })
})

// -- #9 评论人机协同 --------------------------------------------------------

describe('评论采集与人机区分（#9）', () => {
  const req = makeReq({
    id: 'REQ-cmt', status: 'implementing',
    comments: [
      { id: 'c1', body: '人工意见：按钮藏太深', createdAt: T0, createdBy: { kind: 'human' } },
      { id: 'c2', body: '窗口回复：已外置', createdAt: T0 + 1000, createdBy: { kind: 'agent', sessionId: 'session-1cee2467-x' } },
      { id: 'c3', body: '系统：状态自动推进', createdAt: T0 + 2000, createdBy: { kind: 'system' } },
    ],
  })

  it('人工/窗口/系统评论都展示，且用 data-actor 区分', () => {
    const html = buildReqDetail(req, [], T0)
    expect(html).toContain('人工意见：按钮藏太深')
    expect(html).toContain('窗口回复：已外置')
    expect(html).toContain('系统：状态自动推进')
    expect(html).toContain('data-actor="human"')
    expect(html).toContain('data-actor="agent"')
    expect(html).toContain('data-actor="system"')
    expect(html).toContain('<span class="dsh-pm-comment-who" data-actor="human">人</span>')
    expect(html).toContain('<span class="dsh-pm-comment-who" data-actor="agent">窗口 w-1cee2467</span>')
    expect(html).toContain('<span class="dsh-pm-comment-who" data-actor="system">系统</span>')
  })

  it('详情有面向「人」的评论输入框（POST /comment actor=human）', () => {
    const html = buildReqDetail(req, [], T0)
    expect(html).toContain('<div class="dsh-pm-comment-form" data-actor="human">')
    expect(html).toContain('data-action="add-comment" data-target="req" data-id="REQ-cmt"')
  })
})

// -- #5 窗口 chip 跳转 ------------------------------------------------------

describe('窗口 chip 可点且失败有明确反馈（#5）', () => {
  const sid = 'session-1cee2467-95f9-46ec-9cd8-8577932e7060'

  it('来源会话未归档：chip 是可点的 jump-session 按钮', () => {
    const req = makeReq({ id: 'REQ-win1', status: 'implementing', sourceSessionId: sid })
    const html = buildListView(makeState({ requirements: [req] }), T0)
    expect(html).toContain('data-action="jump-session" data-sid="' + sid + '"')
    expect(html).not.toContain('data-archived="true"')
  })

  it('来源会话已归档：chip 仍可点（不下线成无 action 的灰 span），带 data-archived 供明确提示', () => {
    const req = makeReq({ id: 'REQ-win2', status: 'implementing', sourceSessionId: sid })
    const html = buildListView(makeState({ requirements: [req] }), T0, {}, new Set([sid]))
    expect(html).toContain('data-action="jump-session" data-sid="' + sid + '"')
    expect(html).toContain('data-archived="true"')
    expect(html).toContain('is-archived')
    expect(html).toContain('已归档')
    // 旧实现：归档 chip 渲染成 <span ... aria-disabled>，点了完全没反应
    expect(html).not.toMatch(/<span[^>]*is-archived/)
  })

  it('jumpResultMessage：可跳不打扰，不可跳必须说清原因', () => {
    expect(jumpResultMessage('opened', sid)).toBe('')
    expect(jumpResultMessage('archived', sid)).toContain('已归档')
    expect(jumpResultMessage('missing', sid)).toContain('不在当前会话列表')
    expect(jumpResultMessage('unavailable', sid)).toContain('暂不可用')
    expect(jumpResultMessage('missing', sid)).toContain('session-1cee2467')
  })
})
