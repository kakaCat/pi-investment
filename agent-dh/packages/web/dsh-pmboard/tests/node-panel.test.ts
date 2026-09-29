/**
 * node-panel.ts 渲染单元测试（REQ-260923134706-e72f / t4；REQ-260928222643-4d34 增补）。
 *
 * serves: FR-1, FR-2, FR-3, FR-6（REQ-260929010300-dbf9 迁移与兼容核验：两处 DAG 面板同源 + 类名集合逐项相同）
 *
 * 覆盖：
 *   TC-1 面板头两层 + 项目看板入口（serves: FR-1）
 *   TC-2 折叠默认态：基础信息 <details open>；面板不含「🔄 执行流程」（serves: FR-4）
 *   TC-2′ 分类跳过态同样带入口（入口写在共用 renderHead 的结构性保证）
 *   TC-3 六节点基础信息内容（立项字段/产物清单/设计逐份/拆分 DAG/验收统计/归档块）
 *   TC-4 未到达节点状态词（FR-10）
 *   TC-5 面板侧零引用两条留痕查询（静态断言，serves: FR-5）
 *   TC-5′ 反面断言：看板自己的消费方未被误删（恰好 1 处）
 *   TC-6 无底部三按钮、无遮罩
 */
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
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

// REQ-260928185112-e20d P1：泳道只列父卡；2026-09-29 裁定 E 起不再展示子卡链进度。
describe('泳道只列父卡（不再展示链进度）', () => {
  it('只列父卡，且卡片里不再有子卡链进度（card-chain / n/N）', () => {
    const html = panel('implementing', {
      implementing: { body: { tasks: [
        makeTask({ id: 't-p1', title: '父卡一', status: 'in_progress' }),
        makeTask({ id: 't-k1', title: '父卡一·研发', status: 'done', parentId: 't-p1', stageKind: 'dev' }),
        makeTask({ id: 't-k2', title: '父卡一·联调', status: 'in_progress', parentId: 't-p1', stageKind: 'integrate' }),
      ] } } as never,
    })
    // 只对**泳道**面板断言（从 data-pane="list" 起切片，排除 DAG 面板）。
    const swim = html.slice(html.indexOf('data-pane="list"'))
    // 2026-09-29 裁定 E：卡底子卡链进度（4 段色条 + n/N）不再展示。
    expect(swim).not.toContain('card-chain')
    expect(swim).not.toContain('1/2')
    expect(swim).toContain('dsh-pm-np-card-id">t-p1')
    expect(swim).not.toContain('dsh-pm-np-card-id">t-k1')
  })
})

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
  it('基础信息 details open；面板不再出现「🔄 执行流程」', () => {
    const html = panel('design')
    expect(html).toContain('<details class="dsh-pm-np-fold" open>')
    // REQ-260928222643-4d34 FR-4：执行流程折叠块整块下掉（连标题行都不出现）
    expect(html).not.toContain('🔄 执行流程')
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
  it('decomposing：拆分计划 + 真 DAG 面板骨架（不再按层分行列表）', () => {
    const html = panel('decomposing')
    expect(html).toContain('decomposition.md')
    expect(html).toContain('DAG 层级')
    expect(html).toContain('dsh-pm-dag-panel')
    // REQ-260929010300-dbf9：必须传面板专属常量（不是 dag-view 的缺省 id），否则回退到
    // 需求详情画布 id 也能"看起来对"，两处 block 的 id 隔离就此失效
    expect(html).toContain('id="np-dag-canvas-container"')
    expect(html).toContain('id="np-dag-canvas"')
    expect(html).not.toContain('id="dag-canvas"')
    expect(html).not.toContain('dsh-pm-np-dag-layer')
  })
  it('实施阶段 [DAG] 页签渲染同一真 DAG 面板（与拆分同源同结构）', () => {
    const html = panel('implementing')
    expect(html).toContain('dsh-pm-dag-panel')
    // 与拆分块同款钉死：两处都必须走 PANEL_DAG_CONTAINER_ID / PANEL_DAG_CANVAS_ID
    expect(html).toContain('id="np-dag-canvas-container"')
    expect(html).toContain('id="np-dag-canvas"')
    expect(html).not.toContain('id="dag-canvas"')
    expect(html).not.toContain('dsh-pm-np-dag-layer')
    expect(html).not.toContain('dsh-pm-np-dag-node')
  })
  it('两处 DAG 面板 DOM 类名集合逐项相同（同一构建函数的产物）', () => {
    // FR-6 判据「两处 DAG 面板 DOM 类名集合逐项相同」按**面板块**比较：先按平衡 div 切出
    // .dsh-pm-dag-panel 整块（面板外的页签/泳道类不掺进来），再逐类比对。
    // 只按 `dsh-pm-dag-` 前缀在全页过滤会漏掉面板内非该前缀的类（如按钮态 is-on），
    // 两处不一致时也可能"相等"；也不该让面板外的类参与比较。
    const dagPanel = (html: string): string => {
      const start = html.indexOf('<div class="dsh-pm-dag-panel"')
      expect(start, '未找到 .dsh-pm-dag-panel：骨架类名可能已漂移').toBeGreaterThanOrEqual(0)
      const re = /<\/?div\b[^>]*>/g
      re.lastIndex = start
      let depth = 0
      let m: RegExpExecArray | null
      while ((m = re.exec(html)) !== null) {
        depth += m[0].startsWith('</') ? -1 : 1
        if (depth === 0) return html.slice(start, m.index + m[0].length)
      }
      throw new Error('DAG 面板 div 未闭合')
    }
    const classSet = (html: string): string[] => {
      const set = new Set<string>()
      for (const m of html.matchAll(/class="([^"]*)"/g)) {
        for (const c of m[1].split(/\s+/)) if (c.length > 0) set.add(c)
      }
      return [...set].sort()
    }
    const impl = classSet(dagPanel(panel('implementing')))
    const dec = classSet(dagPanel(panel('decomposing')))
    // 骨架类在位（防"两个空集合相等"的假绿）
    for (const c of ['dsh-pm-dag-panel', 'dsh-pm-dag-head', 'dsh-pm-dag-canvas-wrap', 'dsh-pm-dag-canvas', 'dsh-pm-dag-legend']) {
      expect(impl).toContain(c)
    }
    expect(dec).toEqual(impl)
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

// REQ-260928222643-4d34 · serves: FR-1, FR-4
describe('项目看板入口（REQ-260928222643-4d34 FR-1 / FR-4）', () => {
  it('TC-1 入口存在、文案固定、带 data-action/data-req，且在同排相对时间之后', () => {
    const html = panel('design')
    expect(html).toContain('项目看板 ↗')
    expect(html).toContain('data-action="np-board-entry"')
    expect(html).toContain('data-req="REQ-test"')
    const headIdx = html.indexOf('dsh-pm-np-head')
    const timeIdx = html.indexOf('dsh-pm-np-head-time')
    const btnIdx = html.indexOf('dsh-pm-np-board-entry')
    expect(headIdx).toBeGreaterThanOrEqual(0)
    expect(timeIdx).toBeGreaterThan(headIdx)
    expect(btnIdx).toBeGreaterThan(timeIdx)
  })

  it('TC-1′ 无相对时间（timeline 为空）仍渲染入口', () => {
    const html = panel('design', { design: { timeline: [] } } as never)
    expect(html).toContain('项目看板 ↗')
    expect(html).not.toContain('dsh-pm-np-head-time')
  })

  it('TC-2′ 分类跳过节点同样带入口（两分支共用 renderHead）', () => {
    const html = panel('design', { design: { enabled: false } })
    expect(html).toContain('本分类跳过该节点')
    expect(html).toContain('项目看板 ↗')
    expect(html).toContain('data-action="np-board-entry"')
  })

  it('TC-3 7 个节点输出均不含「🔄 执行流程」', () => {
    // 验收口径固定为 7 个主节点：先钉住节点数，避免 ALL_STAGE_KEYS 漂移后「全绿」变成空转。
    expect(ALL_STAGE_KEYS.length).toBe(7)
    for (const stage of ALL_STAGE_KEYS) {
      expect(panel(stage as StageKey), stage).not.toContain('🔄 执行流程')
    }
  })
})

// REQ-260928222643-4d34 · serves: FR-5
describe('面板侧不再拉取注入/隔离留痕（REQ-260928222643-4d34 FR-5）', () => {
  const read = (rel: string): string => readFileSync(new URL(rel, import.meta.url), 'utf8')

  it('TC-5 面板侧零引用两条留痕查询', () => {
    const conv = read('../src/client/conversation-progress.ts')
    const panelSrc = read('../src/client/node-panel.ts')
    expect(conv).not.toContain('fetchInjectionInfo')
    expect(conv).not.toContain('fetchIsolationLog')
    expect(panelSrc).not.toContain('fetchInjectionInfo')
    expect(panelSrc).not.toContain('fetchIsolationLog')
  })

  it('TC-5′ 反面断言：看板自己的消费方未被误删（恰好 1 处）', () => {
    const board = read('../src/client/board-mount.ts')
    expect(board.split('fetchInjectionInfo').length - 1).toBe(1)
  })
})
