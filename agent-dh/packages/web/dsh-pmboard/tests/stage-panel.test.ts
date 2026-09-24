/**
 * stage-panel.ts v4 渲染单元测试（REQ-31e11f 节点详情重设计：单节点工作记录）。
 * serves: FR-4（REQ-81aabd 设计文档 ✅已交/⬜未交 渲染）。
 *
 * 覆盖：
 *   1. 8 个节点渲染器各自产出非空 HTML（含 dsh-pm-stage-body {stage} 锚点）
 *   2. 面板头：状态符 + 节点名 + 状态一句话（stageHeadSummary 逐节点）
 *   3. 实施列表：执行者（w-xxx 窗口 / sub w-xxx subagent）+ 时间 + 失败标红
 *   4. 产物文档行：可点击链接（data-action="open-doc"）；缺失必备产物红字
 *   5. 动态：相对时间 + 操作者（人/窗口/subagent）
 *   6. 追溯链可见（requirement → plan → … 顺序）；同类多份（design）显示文件名
 *   7. 分类跳过节点（enabled=false → skipped）
 *   8. renderStageNode：行状态推导 + 面板渲染
 *   9. 健壮性：body 字段缺失不抛错
 */
import { describe, it, expect } from 'vitest'
import {
  renderStagePanel,
  renderStageNode,
  stageRowState,
  stageHeadSummary,
  StageRenderers,
  STAGE_LABELS,
  isStageSkippedForCategory,
  getStagesForCategory,
} from '../src/client/stage-panel.js'
import type {
  StageDetail,
  StageOverview,
  StageArtifact,
  StageKey,
  StageTaskExecution,
} from '../src/shared/protocol.js'
import { ALL_STAGE_KEYS } from '../src/shared/protocol.js'

// ---------------------------------------------------------------------------
// 测试工厂
// ---------------------------------------------------------------------------

function makeArtifact(overrides: Partial<StageArtifact> = {}): StageArtifact {
  return {
    stage: 'brainstorming',
    kind: 'requirement',
    path: 'docs/requirements/REQ-test/requirement.md',
    registeredAt: 1693000000000,
    registeredBy: { kind: 'agent', sessionId: 'session-test' },
    ...overrides,
  }
}

function makeStageDetail(overrides: Partial<StageDetail> = {}): StageDetail {
  return {
    stage: 'draft',
    enabled: true,
    artifacts: [],
    pendingConfirmation: false,
    timeline: [],
    body: { title: '测试需求', description: '测试描述' },
    ...overrides,
  } as StageDetail
}

function makeTask(overrides: Partial<StageTaskExecution> = {}): StageTaskExecution {
  return {
    id: 't-aaa001', title: '任务一', status: 'todo', phase: 'implement', side: 'backend',
    dependsOn: [], acceptance: '', executions: [],
    ...overrides,
  } as StageTaskExecution
}

function makeOverview(currentStage: StageKey = 'implementing'): StageOverview {
  const bodies: Record<string, unknown> = {
    draft: { title: '测试需求', category: 'feature', description: 'd', createdAt: 1693000000000 },
    brainstorming: { requirementDoc: 'docs/requirements/REQ-test/requirement.md', comments: [] },
    design: { plan: { summary: 's', path: 'docs/requirements/REQ-test/plan.md', tasks: [{ key: 't1', title: '任务一' }], submittedAt: 1693000000000, approvedAt: 1693000100000 } },
    decomposing: { tasks: [makeTask()], planTasks: [] },
    implementing: { tasks: [makeTask({ status: 'done' }), makeTask({ id: 't-bbb002', title: '任务二构建部署', status: 'in_progress', executions: [{ id: 'e1', sessionId: 'session-8913546f-bd1a-4ca5-a737-deb0b429e5bf', trigger: 'manual', startedAt: Date.now() - 120000, outcome: 'running' }] })], byWindow: {} },
    accepting: {},
    archived: {},
  }
  return {
    requirementId: 'REQ-test',
    category: 'feature',
    currentStage,
    stages: ALL_STAGE_KEYS.map(stage => ({
      stage, enabled: true, artifacts: [], pendingConfirmation: false, timeline: [],
      body: bodies[stage],
    }) as unknown as StageDetail),
  }
}

// ---------------------------------------------------------------------------
// 测试：注册表与标签
// ---------------------------------------------------------------------------

describe('StageRenderers 注册表', () => {
  it('包含全部 8 个节点渲染器', () => {
    for (const stage of ALL_STAGE_KEYS) {
      expect(StageRenderers[stage]).toBeDefined()
      expect(typeof StageRenderers[stage].renderBody).toBe('function')
    }
  })

  it('STAGE_LABELS 包含全部 7 个节点标签', () => {
    expect(Object.keys(STAGE_LABELS)).toHaveLength(7)
    expect(STAGE_LABELS.draft).toBe('立项')
    expect(STAGE_LABELS.implementing).toBe('实施')
    expect(STAGE_LABELS.archived).toBe('归档')
  })
})

// ---------------------------------------------------------------------------
// 测试：面板骨架
// ---------------------------------------------------------------------------

describe('renderStagePanel 骨架', () => {
  it('产出 dsh-pm-stage-panel 根 + 面板头（节点名 + 状态一句话）', () => {
    const html = renderStagePanel(makeStageDetail())
    expect(html).toContain('dsh-pm-stage-panel')
    expect(html).toContain('dsh-pm-sn-head')
    expect(html).toContain('已立项')
  })

  it('面板头右侧带最近动态时间（相对时间）', () => {
    const html = renderStagePanel(makeStageDetail({
      timeline: [{ status: 'draft', at: Date.now() - 5 * 60000, by: { kind: 'human' } }],
    }))
    expect(html).toContain('dsh-pm-sn-time')
    expect(html).toContain('5 分钟前')
  })

  it('pendingConfirmation → 红色警示行', () => {
    const html = renderStagePanel(makeStageDetail({ pendingConfirmation: true }))
    expect(html).toContain('dsh-pm-sn-warn')
    expect(html).toContain('有产物待人工确认')
  })

  it('分类跳过节点：data-state=skipped + 不适用提示', () => {
    const html = renderStagePanel(makeStageDetail({ stage: 'brainstorming', enabled: false, body: {} as never }))
    expect(html).toContain('data-state="skipped"')
    expect(html).toContain('该阶段在当前分类流程中不适用')
  })
})

// ---------------------------------------------------------------------------
// 测试：各节点专属内容
// ---------------------------------------------------------------------------

describe('各节点专属内容', () => {
  it('draft：标题 + 分类 + 描述', () => {
    const html = renderStagePanel(makeStageDetail({
      body: { title: '我的需求', category: 'feature', description: '详细描述' },
    }))
    expect(html).toContain('data-stage="draft"')
    expect(html).toContain('我的需求')
    expect(html).toContain('feature')
    expect(html).toContain('详细描述')
  })

  it('brainstorming：评论流（操作者 + 文本）', () => {
    const html = renderStagePanel(makeStageDetail({
      stage: 'brainstorming',
      body: { comments: [{ id: 'c1', body: '这个方案边界再想想', createdAt: 1, createdBy: { kind: 'human' } }] },
    }))
    expect(html).toContain('data-stage="brainstorming"')
    expect(html).toContain('这个方案边界再想想')
    expect(html).toContain('data-actor="human"')
  })

  it('brainstorming：无评论 → 暂无评论', () => {
    const html = renderStagePanel(makeStageDetail({ stage: 'brainstorming', body: { comments: [] } }))
    expect(html).toContain('暂无评论')
  })

  it('design：设计阶段只写设计文档（2026-09-21 裁定）', () => {
    const html = renderStagePanel(makeStageDetail({ stage: 'design', body: {} }))
    expect(html).toContain('设计阶段只写设计文档')
  })

  it('design：已批准 → 任务数 + 批准时间', () => {
    const html = renderStagePanel(makeStageDetail({
      stage: 'design',
      body: { plan: { summary: '目标做法', path: 'p.md', tasks: [{ key: 't1', title: 'x' }], submittedAt: 1693000000000, submittedBy: { kind: 'agent' }, approvedAt: 1693000100000, approvedBy: { kind: 'human' } } },
    }))
    expect(html).toContain('目标做法')
    expect(html).toContain('1 个任务')
    expect(html).toContain('批准：人')
  })

  it('design：逐份显示设计文档已交/未交（REQ-81aabd FR-2）', () => {
    const html = renderStagePanel(makeStageDetail({
      stage: 'design',
      body: {
        category: 'feature',
        designDocs: [
          { name: 'architecture.md', path: 'docs/requirements/REQ-x/design/architecture.md', submitted: true },
          { name: 'data-model.md', path: 'docs/requirements/REQ-x/design/data-model.md', submitted: false },
        ],
      },
    }))
    expect(html).toContain('data-design-doc="architecture.md" data-submitted="yes"')
    expect(html).toContain('data-design-doc="data-model.md" data-submitted="no"')
    expect(html).toContain('✅ 已交')
    expect(html).toContain('⬜ 未交')
  })

  it('design：条件必交带「条件·端侧」徽标，豁免项灰显并展示理由（REQ-2d1c74 FR-1）', () => {
    const html = renderStagePanel(makeStageDetail({
      stage: 'design',
      body: {
        category: 'feature',
        designDocs: [
          { name: 'architecture.md', path: 'docs/requirements/REQ-x/design/architecture.md', submitted: true },
          { name: 'frontend.md', path: 'docs/requirements/REQ-x/design/frontend.md', submitted: false, conditional: 'frontend' },
          { name: 'use-cases.md', path: 'docs/requirements/REQ-x/design/use-cases.md', submitted: false, exempted: '纯内部工具无用户场景' },
        ],
      },
    }))
    // 条件必交徽标
    expect(html).toContain('〔条件·frontend〕')
    // 豁免项：灰显 + 理由，且**不**按未交渲染（它不是缺口）
    expect(html).toContain('data-exempted="yes"')
    expect(html).toContain('已豁免：纯内部工具无用户场景')
    expect(html).not.toContain('data-design-doc="use-cases.md" data-submitted="no"')
  })

  it('decomposing：任务 + 依赖链', () => {
    const html = renderStagePanel(makeStageDetail({
      stage: 'decomposing',
      body: { tasks: [makeTask({ dependsOn: ['t-aaa000'] })], planTasks: [] },
    }))
    expect(html).toContain('data-stage="decomposing"')
    expect(html).toContain('t-aaa001')
    expect(html).toContain('dsh-pm-sn-dag-layer')
    expect(html).toContain('第 2 层')
  })

  it('decomposing：无任务 → 尚未提交拆分计划（2026-09-21 裁定：计划在拆分阶段提交）', () => {
    const html = renderStagePanel(makeStageDetail({ stage: 'decomposing', body: { tasks: [], planTasks: [] } }))
    expect(html).toContain('尚未提交拆分计划')
  })

  it('accepting：无材料 → 尚未提交验收材料', () => {
    const html = renderStagePanel(makeStageDetail({ stage: 'accepting', body: {} }))
    expect(html).toContain('尚未提交验收材料')
  })

  it('accepting：结论摘要 + 证据列表 + 审核意见', () => {
    const html = renderStagePanel(makeStageDetail({
      stage: 'accepting',
      body: { verification: { summary: '交付结论', evidence: ['npx vitest run → 384 过', 'curl :13080 → 200'], submittedAt: 1, submittedBy: { kind: 'agent' }, decision: 'rework', reviewNote: '样式需要重做' } },
    }))
    expect(html).toContain('交付结论')
    expect(html).toContain('npx vitest run')
    expect(html).toContain('审核意见')
    expect(html).toContain('样式需要重做')
  })

  // REQ-9f4a44：done 节点已移除，原「done：完成时间 + 验收结论」用例随之删除

  it('archived：目录 + 索引 + 合并去向链接', () => {
    const html = renderStagePanel(makeStageDetail({
      stage: 'archived',
      body: { archive: { dir: 'docs/requirements/REQ-test', docs: [], mergedInto: ['docs/architecture/x.md'], indexEntry: '一句话索引', submittedAt: 1, submittedBy: { kind: 'agent' } } },
    }))
    expect(html).toContain('docs/requirements/REQ-test')
    expect(html).toContain('一句话索引')
    expect(html).toContain('data-action="open-doc"')
  })
})

// ---------------------------------------------------------------------------
// 测试：实施列表（核心：做到哪/做了多少/还剩多少 + 谁做的）
// ---------------------------------------------------------------------------

describe('实施列表（执行者追溯）', () => {
  it('任务行：状态符 + id + 标题 + 执行者 + 时间', () => {
    const html = renderStagePanel(makeStageDetail({
      stage: 'implementing',
      body: {
        tasks: [makeTask({
          status: 'done',
          executions: [{ id: 'e1', sessionId: 'session-8913546f-bd1a-4ca5-a737-deb0b429e5bf', trigger: 'manual', startedAt: 1, endedAt: 1693000000000, outcome: 'succeeded' }],
        })],
        byWindow: {},
      },
    }))
    expect(html).toContain('dsh-pm-sn-task')
    expect(html).toContain('t-aaa001')
    expect(html).toContain('w-8913546f')
    expect(html).toContain('完成')
  })

  it('subagent 执行的任务：执行者标 sub 前缀', () => {
    const html = renderStagePanel(makeStageDetail({
      stage: 'implementing',
      body: {
        tasks: [makeTask({
          status: 'done',
          executions: [{ id: 'e1', sessionId: 'subagent-xyz', trigger: 'auto', startedAt: 1, endedAt: 1693000000000, outcome: 'succeeded' }],
        })],
        byWindow: {},
      },
    }))
    expect(html).toContain('sub w-subagent')
  })

  it('进行中任务：is-current 高亮 + 相对起点', () => {
    const html = renderStagePanel(makeStageDetail({
      stage: 'implementing',
      body: {
        tasks: [makeTask({
          status: 'in_progress',
          executions: [{ id: 'e1', sessionId: 'session-8913546f-bd1a-4ca5-a737-deb0b429e5bf', trigger: 'manual', startedAt: Date.now() - 5 * 60000, outcome: 'running' }],
        })],
        byWindow: {},
      },
    }))
    expect(html).toContain('is-current')
    expect(html).toContain('开发中')
    expect(html).toContain('5 分钟前')
  })

  it('失败任务：标红 + 失败次数（追溯问题）', () => {
    const html = renderStagePanel(makeStageDetail({
      stage: 'implementing',
      body: {
        tasks: [makeTask({
          status: 'in_progress',
          executions: [
            { id: 'e1', sessionId: 's1', trigger: 'auto', startedAt: 1, endedAt: 2, outcome: 'failed' },
            { id: 'e2', sessionId: 's1', trigger: 'auto', startedAt: 3, endedAt: 4, outcome: 'failed' },
            { id: 'e3', sessionId: 's1', trigger: 'auto', startedAt: 5, outcome: 'running' },
          ],
        })],
        byWindow: {},
      },
    }))
    expect(html).toContain('is-failed')
    expect(html).toContain('失败 2 次')
  })

  it('待开始任务：待开始', () => {
    const html = renderStagePanel(makeStageDetail({
      stage: 'implementing',
      body: { tasks: [makeTask()], byWindow: {} },
    }))
    expect(html).toContain('待开始')
  })

  it('多窗口分工：窗口分工汇总行', () => {
    const html = renderStagePanel(makeStageDetail({
      stage: 'implementing',
      body: {
        tasks: [makeTask()],
        byWindow: { 'w-aaa': ['t-1'], 'w-bbb': ['t-2', 't-3'] },
      },
    }))
    expect(html).toContain('窗口分工')
    expect(html).toContain('w-aaa 1 任务')
    expect(html).toContain('w-bbb 2 任务')
  })
})

// ---------------------------------------------------------------------------
// 测试：产物文档行 / 动态 / 追溯链
// ---------------------------------------------------------------------------

describe('产物文档行', () => {
  it('已登记产物 → 可点击链接', () => {
    const html = renderStagePanel(makeStageDetail({
      stage: 'brainstorming',
      artifacts: [makeArtifact()],
      body: { comments: [] },
    }))
    expect(html).toContain('dsh-pm-trace-chain')
    expect(html).toContain('data-action="open-doc"')
    expect(html).toContain('data-path="docs/requirements/REQ-test/requirement.md"')
    expect(html).toContain('需求文档')
  })

  it('缺失必备产物 → 红字标记', () => {
    const html = renderStagePanel(makeStageDetail({
      stage: 'brainstorming',
      artifacts: [],
      body: { comments: [] },
    }))
    expect(html).toContain('is-missing')
    expect(html).toContain('缺失')
  })

  it('无产物且无必备 → 不渲染产物行', () => {
    const html = renderStagePanel(makeStageDetail({ stage: 'draft' }))
    expect(html).not.toContain('dsh-pm-sn-docs')
  })
})

describe('动态', () => {
  it('事件行：相对时间 + 操作者 + 内容', () => {
    const html = renderStagePanel(makeStageDetail({
      timeline: [
        { status: 'draft', at: Date.now() - 3600000, by: { kind: 'human' }, reason: '立项：需求详情页操作' },
        { status: 'draft', at: Date.now() - 60000, by: { kind: 'agent', sessionId: 'session-8913546f-bd1a-4ca5-a737-deb0b429e5bf' } },
      ],
    }))
    expect(html).toContain('动态')
    expect(html).toContain('1 小时前')
    expect(html).toContain('立项：需求详情页操作')
    expect(html).toContain('w-8913546f')
  })

  it('无事件 → 不渲染动态块', () => {
    const html = renderStagePanel(makeStageDetail())
    expect(html).not.toContain('dsh-pm-sn-time2')
  })
})

describe('追溯链', () => {
  it('按 requirement → plan → task_detail 顺序渲染', () => {
    const artifacts = [
      makeArtifact({ kind: 'requirement', path: 'docs/requirements/REQ-test/requirement.md', stage: 'brainstorming' }),
      makeArtifact({ kind: 'plan', path: 'docs/requirements/REQ-test/plan.md', stage: 'design' }),
      makeArtifact({ kind: 'task_detail', path: 'docs/requirements/REQ-test/tasks/t-1.md', stage: 'implementing' }),
    ]
    const html = renderStagePanel(makeStageDetail({ artifacts }))
    expect(html).toContain('dsh-pm-trace-chain')
    expect(html).toContain('dsh-pm-trace-arrow')
    const reqIdx = html.indexOf('requirement.md')
    const planIdx = html.indexOf('plan.md')
    // REQ-260922182638-0777 FR-5：任务卡不再折叠「×N」，逐张列出（无任务清单可匹配时降级「任务卡（t-xxx）」）
    const taskIdx = html.indexOf('任务卡（t-1）')
    expect(reqIdx).toBeGreaterThan(-1)
    expect(planIdx).toBeGreaterThan(reqIdx)
    expect(taskIdx).toBeGreaterThan(planIdx)
    expect(html).not.toContain('任务卡×')
  })

  it('同类多份（design）：显示各自中文文档名（FR-4 文件名中文化），不再四份全叫「设计文档」', () => {
    // 设计节点的交付物是一整套文档 → 同一 kind 下多条产物记录
    const names = ['architecture.md', 'data-model.md', 'interfaces.md', 'test-cases.md']
    const cnNames = ['架构文档', '数据模型', '接口文档', '测试用例']
    const artifacts = names.map(name =>
      makeArtifact({ kind: 'design', stage: 'design', path: 'docs/requirements/REQ-test/design/' + name }))
    const html = renderStagePanel(makeStageDetail({ stage: 'design', artifacts, body: {} as never }))
    // REQ-260922182638-0777 FR-4：按钮文字 = 中文文档名，不再裸显英文文件名；
    // 完整路径仍在 data-path / title（排查线索不丢）
    for (let i = 0; i < names.length; i++) {
      expect(html).toContain('data-path="docs/requirements/REQ-test/design/' + names[i] + '"')
      expect(html).toContain('>' + cnNames[i] + '</button>')
      expect(html).not.toContain('>' + names[i] + '</button>')
    }
    // 同一个词不再重复出现（此前 trace chain 上 4 个按钮全渲染成「设计文档」）
    expect(html).not.toContain('>设计文档<')
  })

  it('单份产物仍用种类名（人认的是「这一步交了没」）', () => {
    const artifacts = [
      makeArtifact({ kind: 'plan', stage: 'design', path: 'docs/requirements/REQ-test/plan.md' }),
      makeArtifact({ kind: 'decomposition', stage: 'decomposing', path: 'docs/requirements/REQ-test/decomposition.md' }),
    ]
    const html = renderStagePanel(makeStageDetail({ stage: 'design', artifacts, body: {} as never }))
    // 2026-09-21：decomposition 承载拆分计划；旧 plan 产物标「拆分计划（旧版）」
    expect(html).toContain('>拆分计划（旧版）</button>')
    expect(html).toContain('data-kind="decomposition"')
    expect(html).toContain('>拆分计划</button>')
  })

  // TC-006（REQ-260922182638-0777 / FR-4、FR-5）
  it('TC-006a：任务卡逐张展开且带任务名称（artifact.path ↔ cardDoc 匹配取 StageTaskRef.title）', () => {
    const artifacts = [
      makeArtifact({ kind: 'task_detail', stage: 'implementing', path: 'docs/requirements/REQ-test/tasks/t-aaa001.md' }),
      makeArtifact({ kind: 'task_detail', stage: 'implementing', path: 'docs/requirements/REQ-test/tasks/t-bbb002.md' }),
    ]
    const body = {
      tasks: [
        makeTask({ id: 't-aaa001', title: '实现映射模块', cardDoc: 'docs/requirements/REQ-test/tasks/t-aaa001.md' }),
        makeTask({ id: 't-bbb002', title: '收敛引用点', cardDoc: 'docs/requirements/REQ-test/tasks/t-bbb002.md' }),
      ],
      byWindow: {},
    } as never
    const html = renderStagePanel(makeStageDetail({ stage: 'implementing', artifacts, body }))
    // 逐张列出、各带任务名称与各卡路径（不再折叠）
    expect(html).toContain('>任务卡 · 实现映射模块</button>')
    expect(html).toContain('>任务卡 · 收敛引用点</button>')
    expect(html).toContain('data-path="docs/requirements/REQ-test/tasks/t-aaa001.md"')
    expect(html).toContain('data-path="docs/requirements/REQ-test/tasks/t-bbb002.md"')
    expect(html).not.toContain('任务卡×')
  })

  it('TC-006b：任务卡名称匹配不到时降级「任务卡（t-xxx）」编号形态', () => {
    const artifacts = [
      makeArtifact({ kind: 'task_detail', stage: 'implementing', path: 'docs/requirements/REQ-test/tasks/t-zzz999.md' }),
    ]
    const body = { tasks: [makeTask({ id: 't-aaa001', title: '别的任务', cardDoc: 'docs/requirements/REQ-test/tasks/t-aaa001.md' })], byWindow: {} } as never
    const html = renderStagePanel(makeStageDetail({ stage: 'implementing', artifacts, body }))
    expect(html).toContain('>任务卡（t-zzz999）</button>')
    expect(html).not.toContain('任务卡 · 别的任务')
    expect(html).not.toContain('任务卡×')
  })

  it('TC-006c：未知设计文件名中文兜底（「设计文档（foo.md）」），tooltip 保留完整路径', () => {
    const artifacts = [
      makeArtifact({ kind: 'design', stage: 'design', path: 'docs/requirements/REQ-test/design/foo.md' }),
    ]
    const html = renderStagePanel(makeStageDetail({ stage: 'design', artifacts, body: {} as never }))
    expect(html).toContain('>设计文档（foo.md）</button>')
    expect(html).toContain('data-path="docs/requirements/REQ-test/design/foo.md"')
  })

  it('TC-006d：缺失必备产物红字「（缺失）」行为保留', () => {
    // design 节点的必备产物 = design；一件都没交 → 红字「设计文档（缺失）」
    const html = renderStagePanel(makeStageDetail({ stage: 'design', artifacts: [], body: {} as never }))
    expect(html).toContain('is-missing')
    expect(html).toContain('设计文档（缺失）')
  })
})

// ---------------------------------------------------------------------------
// 测试：面板头一句话（stageHeadSummary）
// ---------------------------------------------------------------------------

describe('stageHeadSummary 面板头一句话', () => {
  it('implementing：x/y 完成 · 剩 z 个 · 进行中 id', () => {
    const text = stageHeadSummary(makeStageDetail({
      stage: 'implementing',
      body: {
        tasks: [
          makeTask({ status: 'done' }),
          makeTask({ id: 't-bbb002', status: 'in_progress' }),
          makeTask({ id: 't-ccc003' }),
        ],
        byWindow: {},
      },
    }))
    expect(text).toBe('1/3 完成 · 剩 2 个 · 进行中 t-bbb002')
  })

  it('design 旧管线兼容（有 plan）：计划待批准/已批准/被退回', () => {
    const mk = (plan: unknown) => stageHeadSummary(makeStageDetail({ stage: 'design', body: { plan } as never }))
    expect(mk({ tasks: [], submittedAt: 1 })).toBe('计划待批准')
    expect(mk({ tasks: [], submittedAt: 1, approvedAt: 2 })).toBe('计划已批准')
    expect(mk({ tasks: [], submittedAt: 1, rejectedAt: 2 })).toBe('计划被退回')
  })

  it('design 现管线（无 plan）：按设计文档交付/确认取词（FR-8 · TC-1/TC-3）', () => {
    const names = ['architecture.md', 'data-model.md', 'interfaces.md', 'test-cases.md', 'use-cases.md']
    const body = (submittedCount: number) => ({
      category: 'feature',
      designDocs: names.map((n, i) => ({ name: n, path: 'docs/requirements/REQ-test/design/' + n, submitted: i < submittedCount })),
    }) as never
    // 2/5 已交 → 「设计文档 2/5 已交」
    expect(stageHeadSummary(makeStageDetail({ stage: 'design', body: body(2) }))).toBe('设计文档 2/5 已交')
    // 交齐但未人工确认 → 待确认
    expect(stageHeadSummary(makeStageDetail({ stage: 'design', body: body(5) }))).toBe('待确认设计文档')
    // 交齐且 design 产物全部 confirmedAt → 设计已确认
    const artifacts = names.map(n => makeArtifact({ kind: 'design', stage: 'design', path: 'docs/requirements/REQ-test/design/' + n, confirmedAt: 1693000200000 }))
    expect(stageHeadSummary(makeStageDetail({ stage: 'design', body: body(5), artifacts }))).toBe('设计已确认')
    // 新管线需求也有 PlanRecord（拆分阶段产生），但设计文档已交且无 design 阶段 plan 产物
    // → 不得回落到计划文案（线上实测：本需求曾显示「计划已批准」）
    const withPlan = { category: 'feature', plan: { summary: 's', path: 'p', tasks: [], submittedAt: 1, approvedAt: 2 }, designDocs: names.map((n, i) => ({ name: n, path: 'docs/requirements/REQ-test/design/' + n, submitted: i < 5 })) } as never
    const arts = names.map(n => makeArtifact({ kind: 'design', stage: 'design', path: 'docs/requirements/REQ-test/design/' + n, confirmedAt: 1 }))
    expect(stageHeadSummary(makeStageDetail({ stage: 'design', body: withPlan, artifacts: arts }))).toBe('设计已确认')
    // 旧管线的识别锚点：设计阶段确有 plan 产物 → 计划文案优先
    const legacyArt = [makeArtifact({ kind: 'plan', stage: 'design', path: 'docs/requirements/REQ-test/plan.md' })]
    expect(stageHeadSummary(makeStageDetail({ stage: 'design', body: withPlan, artifacts: legacyArt }))).toBe('计划已批准')
    // 清单缺席 → 待提交设计文档
    expect(stageHeadSummary(makeStageDetail({ stage: 'design', body: { category: 'feature' } as never }))).toBe('待提交设计文档')
    // 已豁免的文档不计入分母
    const withExempt = { category: 'feature', designDocs: [
      { name: 'architecture.md', path: 'docs/requirements/REQ-test/design/architecture.md', submitted: true },
      { name: 'data-model.md', path: 'docs/requirements/REQ-test/design/data-model.md', submitted: false, exempted: '本需求不涉及数据层' },
    ] } as never
    expect(stageHeadSummary(makeStageDetail({ stage: 'design', body: withExempt }))).toBe('待确认设计文档')
  })

  it('accepting：待提交/待审核/通过/返工', () => {
    const mk = (v: unknown) => stageHeadSummary(makeStageDetail({ stage: 'accepting', body: { verification: v } as never }))
    expect(mk(undefined)).toBe('待提交验收材料')
    expect(mk({ evidence: [], submittedAt: 1 })).toBe('待人工审核')
    expect(mk({ evidence: [], submittedAt: 1, decision: 'pass' })).toBe('验收通过')
    expect(mk({ evidence: [], submittedAt: 1, decision: 'rework' })).toBe('验收被退回返工')
  })

  it('分类跳过 → 本分类跳过', () => {
    expect(stageHeadSummary(makeStageDetail({ enabled: false }))).toBe('本分类跳过')
  })
})

// ---------------------------------------------------------------------------
// 测试：renderStageNode + stageRowState
// ---------------------------------------------------------------------------

describe('renderStageNode / stageRowState', () => {
  it('行状态推导：当前=current，之前=done，之后=pending', () => {
    const ov = makeOverview('implementing')
    expect(stageRowState(ov, 'draft')).toBe('done')
    expect(stageRowState(ov, 'design')).toBe('done')
    expect(stageRowState(ov, 'implementing')).toBe('current')
    expect(stageRowState(ov, 'accepting')).toBe('pending')
    expect(stageRowState(ov, 'archived')).toBe('pending')
  })

  it('分类跳过节点 → skipped', () => {
    const ov = makeOverview('implementing')
    ov.stages = ov.stages.map(s => s.stage === 'brainstorming' ? { ...s, enabled: false } : s)
    expect(stageRowState(ov, 'brainstorming')).toBe('skipped')
  })

  it('渲染指定节点面板：data-stage + data-state + 该节点内容', () => {
    const ov = makeOverview('implementing')
    const html = renderStageNode(ov, 'implementing')
    expect(html).toContain('data-stage="implementing"')
    expect(html).toContain('data-state="current"')
    expect(html).toContain('1/2 完成')
    expect(html).toContain('w-8913546f')
  })

  it('点已完成节点：绿✓状态', () => {
    const html = renderStageNode(makeOverview('implementing'), 'design')
    expect(html).toContain('data-state="done"')
    expect(html).toContain('计划已批准')
  })

  it('点未开始节点：pending 状态', () => {
    const html = renderStageNode(makeOverview('implementing'), 'accepting')
    expect(html).toContain('data-state="pending"')
    expect(html).toContain('待提交验收材料')
  })

  it('stage 不存在（如 canceled）→ 回退第一个节点不抛错', () => {
    const html = renderStageNode(makeOverview('implementing'), 'canceled' as StageKey)
    expect(html).toContain('dsh-pm-stage-panel')
  })
})

// ---------------------------------------------------------------------------
// 测试：健壮性（body 字段缺失不抛错）
// ---------------------------------------------------------------------------

describe('健壮性', () => {
  it('implementing body.tasks 为 undefined → 不抛错', () => {
    const html = renderStagePanel(makeStageDetail({
      stage: 'implementing',
      body: { tasks: undefined as never, byWindow: {} },
    }))
    expect(html).toContain('暂无执行任务')
  })

  it('decomposing body.tasks 为 undefined → 不抛错', () => {
    const html = renderStagePanel(makeStageDetail({
      stage: 'decomposing',
      body: { tasks: undefined as never, planTasks: [] },
    }))
    expect(html).toContain('尚未提交拆分计划')
  })

  it('brainstorming body.comments 为 undefined → 不抛错', () => {
    const html = renderStagePanel(makeStageDetail({
      stage: 'brainstorming',
      body: { comments: undefined as never },
    }))
    expect(html).toContain('暂无评论')
  })

  it('7 节点空 body 均产出非空 HTML（含节点锚点类）', () => {
    const bodies: Record<string, Record<string, unknown>> = {
      draft: { title: 'T', description: 'D' },
      brainstorming: { comments: [] },
      design: {},
      decomposing: { tasks: [], planTasks: [] },
      implementing: { tasks: [], byWindow: {} },
      accepting: {},
      archived: {},
    }
    for (const stage of ALL_STAGE_KEYS) {
      const html = renderStagePanel(makeStageDetail({ stage, body: bodies[stage] as never }))
      expect(html.length, stage).toBeGreaterThan(50)
      expect(html, stage).toContain('data-stage="' + stage + '"')
    }
  })
})

// ---------------------------------------------------------------------------
// 测试：成组确认按钮（views/artifacts · REQ-2d1c74 FR-2）
// ---------------------------------------------------------------------------

describe('renderConfirmButton：kind=design 成组确认文案', () => {
  it('任一 design 产物无章 → 按钮写明「全部 N 份」；全有章 → 不渲染', async () => {
    const { renderConfirmButton } = await import('../src/client/views/artifacts.js')
    const designArts = ['architecture.md', 'data-model.md', 'interfaces.md', 'test-cases.md', 'use-cases.md']
      .map((n, i) => ({
        stage: 'design', kind: 'design', path: 'docs/requirements/REQ-x/design/' + n,
        registeredAt: 1,
        ...(i === 0 ? {} : { confirmedAt: 1, confirmedBy: { kind: 'human' } }),
      }))
    const req = {
      id: 'REQ-x', title: 'x', description: '', category: 'feature', status: 'design',
      blocked: false, comments: [], version: 1, createdAt: 1, updatedAt: 1,
      createdBy: { kind: 'human' }, updatedBy: { kind: 'human' },
      artifacts: designArts,
    } as unknown as import('../src/client/types.js').RequirementRecord
    const html = renderConfirmButton(req)
    expect(html).toContain('确认产物（全部 5 份）')
    expect(html).toContain('一键确认全部 5 份设计文档（成组确认）')
    // 全有章 → 不渲染
    const done = {
      ...req,
      artifacts: designArts.map(a => ({ ...a, confirmedAt: 1, confirmedBy: { kind: 'human' } })),
    } as unknown as import('../src/client/types.js').RequirementRecord
    expect(renderConfirmButton(done)).toBe('')
    // 首份有章但其余无章 → 仍然待确认（成组语义：第一份有章不算完）
    const partial = {
      ...req,
      artifacts: designArts.map((a, i) => ({
        stage: a.stage, kind: a.kind, path: a.path, registeredAt: 1,
        ...(i === 0 ? { confirmedAt: 1, confirmedBy: { kind: 'human' } } : {}),
      })),
    } as unknown as import('../src/client/types.js').RequirementRecord
    expect(renderConfirmButton(partial)).toContain('全部 5 份')
  })
})

// ---------------------------------------------------------------------------
// 测试：分类流程辅助
// ---------------------------------------------------------------------------

describe('分类流程辅助', () => {
  it('bug 分类跳过「需求分析」节点', () => {
    expect(isStageSkippedForCategory('bug', 'brainstorming')).toBe(true)
    expect(isStageSkippedForCategory('feature', 'brainstorming')).toBe(false)
  })

  it('getStagesForCategory 返回分类启用节点', () => {
    expect(getStagesForCategory('feature')).toEqual(ALL_STAGE_KEYS)
    expect(getStagesForCategory('bug')).not.toContain('brainstorming')
    expect(getStagesForCategory(undefined)).toEqual(ALL_STAGE_KEYS)
  })
})
