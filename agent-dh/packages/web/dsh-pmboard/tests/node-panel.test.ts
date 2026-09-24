/**
 * node-panel.ts 渲染单元测试（REQ-260923134706-e72f / t4，TC-1…TC-6）。
 *
 * 覆盖：
 *   TC-1 面板头两层：REQ 胶囊 + 标题行；状态胶囊 + 一句话 + 相对时间；7 节点状态词正确
 *   TC-2 折叠默认态：基础信息 <details open>、执行流程 <details>（收起）；实施节点无基础信息块、有 [流程图][泳道] 切换
 *   TC-3 六节点基础信息内容（立项字段/产物清单/设计逐份/拆分 DAG/验收统计/归档块）
 *   TC-4 执行流程三段齐全；提示词片段条目带 open-doc；路由壳显示「路由壳」；无留痕空态
 *   TC-5 执行动作对照：有/无台账记录 → ✅/⬜ 与出处（不冤枉 agent：无记录必须 ⬜）
 *   TC-6 无底部三按钮、无遮罩；含 × 关闭按钮（× 在 conversation-progress 壳上，此处断言面板根结构无 foot）
 */
import { describe, it, expect } from 'vitest'
import { renderNodePanel } from '../src/client/node-panel.js'
import type { StageDetail, StageOverview, StageKey, StageArtifact, StageTaskExecution } from '../src/shared/protocol.js'
import { ALL_STAGE_KEYS } from '../src/shared/protocol.js'

function makeArtifact(over: Partial<StageArtifact> = {}): StageArtifact {
  return { stage: 'brainstorming', kind: 'requirement', path: 'docs/requirements/REQ-test/requirement.md', registeredAt: 1693000000000, registeredBy: { kind: 'agent' }, ...over }
}
function makeTask(over: Partial<StageTaskExecution> = {}): StageTaskExecution {
  return { id: 't-aaa001', title: '任务一', status: 'todo', phase: 'implement', side: 'backend', dependsOn: [], acceptance: '', executions: [], ...over } as StageTaskExecution
}
function makeOverview(currentStage: StageKey = 'implementing', over: Partial<Record<StageKey, Partial<StageDetail>>> = {}): StageOverview {
  const bodies: Record<string, unknown> = {
    draft: { title: '插件 bundle 化', category: 'feature', description: '拆分插件', sourceWindow: 'w-abc123', createdAt: 1693000000000 },
    brainstorming: { requirementDoc: 'docs/requirements/REQ-test/requirement.md', comments: [] },
    design: { category: 'feature', designDocs: [{ name: 'architecture.md', path: 'docs/requirements/REQ-test/design/architecture.md', submitted: true }, { name: 'data-model.md', path: 'docs/requirements/REQ-test/design/data-model.md', submitted: false }] },
    decomposing: { decompositionDoc: 'docs/requirements/REQ-test/decomposition.md', tasks: [makeTask(), makeTask({ id: 't-bbb002', title: '任务二', dependsOn: ['t-aaa001'] })], planTasks: [] },
    implementing: { tasks: [makeTask({ status: 'done' }), makeTask({ id: 't-bbb002', title: '任务二', status: 'in_progress', executions: [{ id: 'e1', trigger: 'manual', startedAt: Date.now() - 60000, outcome: 'running' }] })], byWindow: {} },
    accepting: { verification: { summary: '交付完成', evidence: ['测试绿'], submittedAt: 1693000000000, submittedBy: { kind: 'agent' }, sheet: { version: 2, generatedAt: 1693000000000, generatedBy: { kind: 'agent' }, items: [
      { id: 'i1', source: { kind: 'requirement' }, criterion: 'a', status: 'passed' },
      { id: 'i2', source: { kind: 'requirement' }, criterion: 'b', status: 'failed' },
      { id: 'i3', source: { kind: 'requirement' }, criterion: 'c', status: 'pending' },
    ] } } },
    archived: { archive: { dir: 'docs/requirements/REQ-test', docs: [{ kind: 'requirement', path: 'docs/requirements/REQ-test/requirement.md' }], mergedInto: ['docs/architecture/project-manual.md'], indexEntry: '实现了节点面板', submittedAt: 1693000000000, submittedBy: { kind: 'agent' }, archivedAt: 1693100000000 } },
  }
  return {
    requirementId: 'REQ-test', category: 'feature', currentStage,
    stages: ALL_STAGE_KEYS.map(stage => {
      const base = { stage, enabled: true, artifacts: [], pendingConfirmation: false, timeline: [{ status: stage, at: Date.now() - 3600000, by: { kind: 'human' } }], body: bodies[stage] }
      return { ...base, ...(over[stage] ?? {}) } as unknown as StageDetail
    }),
  }
}

const REQ = { id: 'REQ-test', title: '节点面板测试', category: 'feature' }
function panel(stage: StageKey, over: Partial<Record<StageKey, Partial<StageDetail>>> = {}, extra: Record<string, unknown> = {}) {
  return renderNodePanel({ overview: makeOverview(stage, over), stage, requirement: REQ, ...extra })
}

describe('TC-1 面板头两层', () => {
  it('REQ 胶囊 + 标题行、状态胶囊 + 一句话 + 时间', () => {
    const html = panel('implementing')
    expect(html).toContain('dsh-pm-np-req')
    expect(html).toContain('REQ-test')
    expect(html).toContain('节点面板测试')
    expect(html).toContain('dsh-pm-np-head')
    expect(html).toContain('实施中')
    expect(html).toContain('dsh-pm-np-head-time')
  })
  it('7 节点状态词正确', () => {
    const expectWord: Record<string, string> = { draft: '已立项', brainstorming: '已分析', design: '已设计', decomposing: '已拆分', implementing: '实施中', accepting: '待验收', archived: '已归档' }
    for (const [stage, word] of Object.entries(expectWord)) {
      expect(panel(stage as StageKey), stage).toContain('>' + word + '<')
    }
  })
})

describe('TC-4 未到达节点的状态词（FR-10）', () => {
  it('pending 节点显示「未开始」，不借用该节点的完成态词', () => {
    // 当前阶段 implementing → 后面的 accepting 是未到达节点
    const html = renderNodePanel({ overview: makeOverview('implementing'), stage: 'accepting', requirement: REQ })
    expect(html).toContain('data-state="pending"')
    expect(html).toContain('>未开始<')
    expect(html).not.toContain('>待验收<')
  })
  it('current / done 节点取词不变', () => {
    const ov = makeOverview('implementing')
    expect(renderNodePanel({ overview: ov, stage: 'implementing', requirement: REQ })).toContain('>实施中<')
    expect(renderNodePanel({ overview: ov, stage: 'design', requirement: REQ })).toContain('>已设计<')
  })
  it('分类跳过节点仍说「本分类跳过」，状态词不改', () => {
    const html = panel('design', { design: { enabled: false } })
    expect(html).toContain('data-state="skipped"')
    expect(html).toContain('本分类跳过')
  })
})

describe('FR-9 · TC-6/TC-7 文档行：已交可点、未交占位', () => {
  it('TC-6：已交设计文档行渲染为可点条目（open-doc + 目标路径），未交行不可点', () => {
    const html = panel('design')
    expect(html).toContain('data-action="open-doc" data-path="docs/requirements/REQ-test/design/architecture.md"')
    expect(html).toContain('data-submitted="yes"')
    // 未交（data-model.md）保持灰字占位，不带打开动作
    expect(html).toContain('data-submitted="no"')
    expect(html).not.toContain('data-action="open-doc" data-path="docs/requirements/REQ-test/design/data-model.md"')
  })
  it('TC-7：无 decompositionDoc 时出现「未交」占位行', () => {
    const html = panel('decomposing', { decomposing: { body: { decompositionDoc: undefined, tasks: [makeTask()], planTasks: [] } } })
    expect(html).toContain('⬜ 拆分计划：decomposition.md（未交）')
    expect(html).not.toContain('data-action="open-doc" data-path="docs/requirements/REQ-test/decomposition.md"')
  })
  it('TC-7b：有 decompositionDoc 时可点开，且不出现「未交」占位', () => {
    const html = panel('decomposing')
    expect(html).toContain('data-action="open-doc" data-path="docs/requirements/REQ-test/decomposition.md"')
    expect(html).not.toContain('（未交）')
  })
})

describe('TC-2 折叠默认态与实施双视图', () => {
  it('基础信息 details open、执行流程 details 收起', () => {
    const html = panel('design')
    expect(html).toContain('<details class="dsh-pm-np-fold" open>')
    // 执行流程折叠无 open 属性（默认收起）：存在不带 open 的 details 且为执行流程
    expect(html).toContain('<details class="dsh-pm-np-fold"><summary><span class="dsh-pm-np-fold-icon">▸</span><span class="dsh-pm-np-fold-text">🔄 执行流程</span>')
  })
  it('实施节点无基础信息块、有 [流程图][泳道] 切换', () => {
    const html = panel('implementing')
    expect(html).not.toContain('ℹ️ 基础信息')
    expect(html).toContain('dsh-pm-np-tabs')
    expect(html).toContain('data-action="np-switch-view" data-view="flow"')
    expect(html).toContain('data-action="np-switch-view" data-view="list"')
    expect(html).toContain('data-pane="flow"')
    expect(html).toContain('data-pane="list"')
  })
})

describe('TC-3 六节点基础信息内容', () => {
  it('draft：描述/分类/文档位置/来源窗口/创建时间', () => {
    const html = panel('draft')
    for (const s of ['📝 需求描述', '🏷️ 分类', '📂 文档位置', '👤 来源窗口', '📅 创建时间', 'w-abc123', 'feature']) expect(html).toContain(s)
  })
  it('brainstorming：产物清单 open-doc', () => {
    const html = panel('brainstorming', { brainstorming: { artifacts: [makeArtifact()] } })
    expect(html).toContain('dsh-pm-np-docitem')
    expect(html).toContain('data-action="open-doc" data-path="docs/requirements/REQ-test/requirement.md"')
  })
  it('design：逐份 ✅已交 / ⬜未交', () => {
    const html = panel('design')
    expect(html).toContain('data-submitted="yes"')
    expect(html).toContain('data-submitted="no"')
    expect(html).toContain('architecture.md')
    expect(html).toContain('data-model.md')
  })
  it('decomposing：拆分计划 + DAG 分层', () => {
    const html = panel('decomposing')
    expect(html).toContain('decomposition.md')
    expect(html).toContain('DAG 层级')
    expect(html).toContain('dsh-pm-np-dag-layer')
    expect(html).toContain('第 1 层')
  })
  it('DAG 节点 = 上编号下说明卡片，可点击打开任务卡文档（用户裁定 t8）', () => {
    // 给任务挂任务卡文档 → 节点应可点击（body.tasks 覆盖，保留 decompositionDoc）
    const withDoc = panel('decomposing', { decomposing: { body: {
      decompositionDoc: 'docs/requirements/REQ-test/decomposition.md',
      tasks: [
        makeTask({ cardDoc: 'docs/requirements/REQ-test/tasks/t-aaa001.md' }),
        makeTask({ id: 't-bbb002', title: '任务二', dependsOn: ['t-aaa001'], cardDoc: 'docs/requirements/REQ-test/tasks/t-bbb002.md' }),
      ],
      planTasks: [],
    } } })
    // 内层复用泳道卡片类（与泳道图上下结构一致）：上编号下说明
    expect(withDoc).toContain('dsh-pm-np-card-id')
    expect(withDoc).toContain('dsh-pm-np-card-title')
    expect(withDoc).toContain('>t-aaa001<')           // 上：编号
    expect(withDoc).toContain('任务一')                 // 下：说明
    expect(withDoc).toContain('data-action="open-doc" data-path="docs/requirements/REQ-test/tasks/t-aaa001.md"')
    // 无任务卡 → 不可点击 + 编号旁灰色图标标记（2026-09-24 用户裁定：不再用标题「（无任务卡）」后缀）
    const noDoc = panel('decomposing', { decomposing: { body: { decompositionDoc: undefined, tasks: [makeTask()], planTasks: [] } } })
    expect(noDoc).not.toContain('dsh-pm-np-dag-node" data-status="todo" data-action="open-doc"')
    expect(noDoc).not.toContain('（无任务卡）')
    expect(noDoc).toContain('dsh-pm-np-nodoc')
    // 有任务卡 → 不出现标记
    expect(withDoc).not.toContain('dsh-pm-np-nodoc')
  })
  it('实施节点 DAG 视图 tab 统一叫 DAG（不再叫流程图）', () => {
    const html = panel('implementing')
    expect(html).toContain('>DAG</button>')
    expect(html).not.toContain('>流程图</button>')
    expect(html).toContain('data-pane="flow"')
  })
  it('accepting：验收材料 + 验收单统计', () => {
    const html = panel('accepting')
    expect(html).toContain('验收单 v2')
    expect(html).toContain('共 3 项')
    expect(html).toContain('通过 1')
    expect(html).toContain('不通过 1')
    expect(html).toContain('待裁决 1')
  })
  it('archived：归档徽标 + 文档 + 合并去向 + 一句话结论', () => {
    const html = panel('archived')
    expect(html).toContain('已归档')
    expect(html).toContain('归档文档')
    expect(html).toContain('合并到项目')
    expect(html).toContain('docs/architecture/project-manual.md')
    expect(html).toContain('实现了节点面板')
  })
})

describe('TC-4 执行流程三段', () => {
  it('提示词注入/执行动作/上下文管理齐全', () => {
    const html = panel('design')
    expect(html).toContain('📝 提示词注入')
    expect(html).toContain('⚙️ 执行动作')
    expect(html).toContain('🗜️ 上下文管理')
  })
  it('提示词片段：file 带 open-doc，shell 显示路由壳', () => {
    const injection = [{ at: Date.now(), windowKey: 'w', stage: 'design', difficulty: 'heavy', category: 'feature', routeKey: 'design/heavy/feature', hitLevel: '①', fragmentIds: ['design/heavy', 'design/heavy/feature', 'common/iron-rules'], charCount: 3000, trimmed: [] }]
    const html = panel('design', {}, { injection })
    expect(html).toContain('data-path="packages/web/dsh-pmboard/src/domain/prompt/fragments/design/heavy.md"')
    expect(html).toContain('路由壳')
    expect(html).toContain('common/iron-rules')
  })
  it('无注入留痕 → 空态（不伪造）', () => {
    const html = panel('brainstorming')
    expect(html).toContain('尚无注入留痕')
  })
  it('draft 提示词注入如实说明无阶段提示词', () => {
    const html = panel('draft')
    expect(html).toContain('立项无阶段纪律提示词')
  })
})

describe('TC-5 执行动作对照（规定 vs 实际）', () => {
  it('有台账记录 → ✅ + 出处', () => {
    const html = panel('brainstorming', { brainstorming: { artifacts: [makeArtifact({ confirmedAt: Date.now() - 60000 })] } })
    expect(html).toContain('✅')
    expect(html).toContain('已登记')
    expect(html).toContain('人已确认')
  })
  it('无记录 → ⬜ 未见记录（不冤枉 agent）', () => {
    const html = panel('brainstorming')
    expect(html).toContain('⬜')
    expect(html).toContain('未见登记记录')
    expect(html).not.toContain('✅ 已登记')
  })
  it('实施节点：有开工/完成记录 → ✅', () => {
    const html = panel('implementing')
    expect(html).toContain('1 个任务已开工')
    expect(html).toContain('已完成 1/2')
  })
})

describe('TC-6 无底部按钮 / 无遮罩', () => {
  it('面板 HTML 无 foot/遮罩类', () => {
    const html = panel('implementing')
    expect(html).not.toContain('dsh-pm-sn-foot')
    expect(html).not.toContain('dsh-pm-overlay')
    expect(html).not.toContain('dsh-pm-modal')
    expect(html).not.toContain('打开看板')
  })
  it('分类跳过节点：只显示跳过说明，两段不渲染', () => {
    const html = panel('brainstorming', { brainstorming: { enabled: false } })
    expect(html).toContain('本分类跳过')
    expect(html).not.toContain('📝 提示词注入')
    expect(html).not.toContain('ℹ️ 基础信息')
  })
})
