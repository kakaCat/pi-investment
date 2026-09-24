/**
 * 「执行流程」对照表与求值器（REQ-260923134706-e72f / FR-6）——「agent 是否按规定的流程执行」的
 * **规定 vs 实际**合规对照。规定 = 阶段提示词片段原文（actions[].cite 防漂移锚点，锁死于
 * tests/node-panel-process-map.test.ts）；实际 = 真实台账记录（artifacts/timeline/tasks/验收单/归档），
 * evaluateActions 求值产出 ✅/⬜+出处。上下文管理 = 规定压缩口径 + 真实隔离留痕。
 * 数据诚实：无记录一律 ⬜/空态，绝不伪造 ✅；不声称是工具调用日志（PTC 内部调用呈现为 run_code 不落库）。
 *
 * @module dsh-pmboard/client/node-panel-process
 */
import {
  type StageDetail,
  type MainStageKey,
  type ArtifactKind,
  ALL_STAGE_KEYS,
} from '../shared/protocol.js'
import { esc } from './html.js'
import { displayDocPath } from './open-doc.ts'
import type { InjectionInfoEntry } from './injection-info.ts'

/** 隔离留痕的 client 只读投影（不 import host 模块，与 InjectionInfoEntry 同款纪律）。 */
export interface IsolationLogEntry {
  at: number
  windowKey: string
  stage: string
  /** replaced / skipped / rejected / fallback */
  status: string
  reason: string
  routeKey: string
  packageChars: number
  range?: { start: number; end: number }
  artifactSeq?: number
  replacementSeq?: number
}

/** 规定动作的「实际」判定（对 StageDetail 求值，全部只读）。 */
export type ProcessCheck =
  | { kind: 'artifact-registered'; artifactKind: ArtifactKind }
  | { kind: 'artifact-confirmed'; artifactKind: ArtifactKind }
  | { kind: 'advanced-beyond' }
  | { kind: 'tasks-decomposed' }
  | { kind: 'tasks-started' }
  | { kind: 'tasks-finished' }
  | { kind: 'sheet-decided' }
  | { kind: 'archive-merged' }
  | { kind: 'archive-indexed' }
  | { kind: 'always' }

export interface ProcessActionSpec {
  /** 人读动作名（含真实工具名）。 */
  label: string
  /** 防漂移锚点：必须在该阶段片段语料中出现的原文（draft 无片段语料，可为空）。 */
  cite: string
  check: ProcessCheck
}

export interface StageProcessSpec {
  /** 上下文管理「规定」侧（压缩/保留/下阶段注入）。 */
  contextPolicy: string[]
  actions: ProcessActionSpec[]
}

const act = (label: string, cite: string, check: ProcessCheck): ProcessActionSpec => ({ label, cite, check })

/**
 * 七节点的「规定的流程」。draft 无阶段提示词（立项由 CaptureTool 引导段驱动），
 * 其动作为结构性事实（需求存在即 ✅），cite 留空由守护测试跳过。
 */
export const STAGE_PROCESS: Record<MainStageKey, StageProcessSpec> = {
  draft: {
    contextPolicy: [
      '压缩策略：立项上下文短，不压缩',
      '保留内容：需求标题 / 分类 / 来源窗口',
      '下阶段注入：需求分析提示词 + requirement.md 模板地址',
    ],
    actions: [
      act('立项四问作答（reqboard_capture）', '', { kind: 'always' }),
      act('创建需求记录并绑定窗口', '', { kind: 'always' }),
      act('生成需求 ID 与文档目录', '', { kind: 'always' }),
    ],
  },
  brainstorming: {
    contextPolicy: [
      '压缩策略：保留需求文档与关键讨论',
      '保留内容：需求背景 / 目标 / 范围 / 约束',
      '下阶段注入：设计提示词 + design/ 模板地址',
    ],
    actions: [
      act('编写 requirement.md（需求文档）', 'requirement.md', { kind: 'artifact-registered', artifactKind: 'requirement' }),
      act('提交产物 reqboard_submit(kind=requirement)', 'reqboard_submit(kind=requirement)', { kind: 'artifact-registered', artifactKind: 'requirement' }),
      act('人工确认 reqboard_ask_confirm(kind=requirement)', 'reqboard_ask_confirm(target=artifact, kind=requirement)', { kind: 'artifact-confirmed', artifactKind: 'requirement' }),
      act('确认后推进到设计', '下一步：design', { kind: 'advanced-beyond' }),
    ],
  },
  design: {
    contextPolicy: [
      '压缩策略：保留设计文档链接与拆分口径',
      '保留内容：技术方案 / 接口契约',
      '下阶段注入：拆分提示词 + decomposition 模板',
    ],
    actions: [
      act('编写设计文档并落盘 design/ 目录', 'design/', { kind: 'artifact-registered', artifactKind: 'design' }),
      act('提交设计产物（自动登记 kind=design）', 'reqboard_ask_confirm(target=artifact, kind=design)', { kind: 'artifact-registered', artifactKind: 'design' }),
      act('人工确认设计文档（G2）', 'reqboard_ask_confirm(target=artifact, kind=design)', { kind: 'artifact-confirmed', artifactKind: 'design' }),
      act('交棒拆分阶段', '下一步：decomposing', { kind: 'advanced-beyond' }),
    ],
  },
  decomposing: {
    contextPolicy: [
      '压缩策略：保留任务清单与依赖关系',
      '保留内容：DAG 层级 / 任务概要',
      '下阶段注入：实施提示词 + 任务卡模板',
    ],
    actions: [
      act('编写拆分计划 decomposition.md', 'decomposition.md', { kind: 'artifact-registered', artifactKind: 'decomposition' }),
      act('提交计划 reqboard_submit(kind=plan)', 'reqboard_submit(kind=plan)', { kind: 'artifact-registered', artifactKind: 'decomposition' }),
      act('人工批准 reqboard_ask_confirm(target=plan)', 'reqboard_ask_confirm(target=plan)', { kind: 'artifact-confirmed', artifactKind: 'decomposition' }),
      act('批准后任务卡自动落库', 'reqboard_decompose', { kind: 'tasks-decomposed' }),
      act('推进到实施阶段', '下一步：implementing', { kind: 'advanced-beyond' }),
    ],
  },
  implementing: {
    contextPolicy: [
      '压缩策略：节点隔离——上一节点上下文整段替换为输入包',
      '保留内容：任务卡文档 / 关键输出',
      '下阶段注入：验收提示词 + verification 模板',
    ],
    actions: [
      act('照卡开工 reqboard_task_move(to=in_progress)', 'reqboard_task_move(to=in_progress)', { kind: 'tasks-started' }),
      act('完工汇报 reqboard_task_report', 'reqboard_task_report', { kind: 'tasks-finished' }),
      act('自测通过（跑相关测试/命令）', 'reqboard_task_report', { kind: 'tasks-finished' }),
      act('交棒验收 reqboard_submit(kind=verification)', 'reqboard_submit(kind=verification)', { kind: 'advanced-beyond' }),
    ],
  },
  accepting: {
    contextPolicy: [
      '压缩策略：保留验收结论与关键证据',
      '保留内容：验收单通过率 / 不通过原因',
      '下阶段注入：归档提示词 + archive 模板',
    ],
    actions: [
      act('自检清单逐条给证据', 'reqboard_submit(kind=verification)', { kind: 'artifact-registered', artifactKind: 'verification' }),
      act('提交验收材料 reqboard_submit(kind=verification)', 'reqboard_submit(kind=verification)', { kind: 'artifact-registered', artifactKind: 'verification' }),
      act('逐项裁决 reqboard_accept_sheet', 'reqboard_accept_sheet', { kind: 'sheet-decided' }),
      act('全部通过后归档（人工闸门 G4）', '下一步：archived', { kind: 'advanced-beyond' }),
    ],
  },
  archived: {
    contextPolicy: [
      '压缩策略：完全压缩（流程终态）',
      '保留内容：归档索引 / 一句话结论',
      '下阶段注入：无（流程结束）',
    ],
    actions: [
      act('整理需求目录并提交归档材料 reqboard_submit(kind=archive)', 'reqboard_submit(kind=archive)', { kind: 'artifact-registered', artifactKind: 'archive' }),
      act('合并进项目文档（mergedInto 真写进去）', 'mergedInto', { kind: 'archive-merged' }),
      act('写入归档索引（indexEntry）', 'reqboard_submit(kind=archive)', { kind: 'archive-indexed' }),
    ],
  },
}

// ---------------------------------------------------------------------------
// 求值
// ---------------------------------------------------------------------------

/** 毫秒 → 相对时间（监控视角）。 */
function rel(ms: number, now: number = Date.now()): string {
  const diff = now - ms
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`
  const d = new Date(ms)
  const pad = (n: number) => String(n).padStart(2, '0')
  if (diff < 2 * 86400000) return `昨天 ${pad(d.getHours())}:${pad(d.getMinutes())}`
  return pad(d.getMonth() + 1) + '-' + pad(d.getDate())
}

const stageOrder = (stage: string): number => (ALL_STAGE_KEYS as readonly string[]).indexOf(stage)

export interface ActionVerdict { done: boolean; evidence: string }

/** 对 StageDetail 求值：每条规定动作 → ✅/⬜ + 出处一句话。纯函数，零 IO。 */
export function evaluateActions(payload: StageDetail, spec: StageProcessSpec): ActionVerdict[] {
  const artifacts = payload.artifacts ?? []
  const timeline = payload.timeline ?? []
  const body = payload.body as {
    tasks?: { status: string; executions?: unknown[] }[]
    verification?: { sheet?: { items?: { status: string }[] } }
    archive?: { mergedInto?: string[]; indexEntry?: string }
  }
  const tasks = Array.isArray(body.tasks) ? body.tasks : []

  const latestArtifact = (kind: ArtifactKind) =>
    artifacts.filter(a => a.kind === kind).sort((a, b) => b.registeredAt - a.registeredAt)[0]

  return spec.actions.map(a => {
    switch (a.check.kind) {
      case 'always':
        return { done: true, evidence: '结构性事实（需求已存在）' }
      case 'artifact-registered': {
        const art = latestArtifact(a.check.artifactKind)
        return art !== undefined
          ? { done: true, evidence: `已登记 ${rel(art.registeredAt)}` }
          : { done: false, evidence: '未见登记记录' }
      }
      case 'artifact-confirmed': {
        const kind = a.check.artifactKind
        const art = artifacts.find(x => x.kind === kind && x.confirmedAt !== undefined)
        return art !== undefined && art.confirmedAt !== undefined
          ? { done: true, evidence: `人已确认 ${rel(art.confirmedAt)}` }
          : { done: false, evidence: '未见确认记录' }
      }
      case 'advanced-beyond': {
        const idx = stageOrder(payload.stage)
        const later = timeline.filter(ev => stageOrder(ev.status) > idx).sort((x, y) => y.at - x.at)[0]
        return later !== undefined
          ? { done: true, evidence: `已推进 · ${rel(later.at)}` }
          : { done: false, evidence: '尚未推进' }
      }
      case 'tasks-decomposed':
        return tasks.length > 0
          ? { done: true, evidence: `${tasks.length} 个任务已落库` }
          : { done: false, evidence: '未见任务记录' }
      case 'tasks-started': {
        const started = tasks.filter(t => Array.isArray(t.executions) && t.executions.length > 0).length
        return started > 0
          ? { done: true, evidence: `${started} 个任务已开工` }
          : { done: false, evidence: '未见开工记录' }
      }
      case 'tasks-finished': {
        const done = tasks.filter(t => t.status === 'done').length
        return done > 0
          ? { done: true, evidence: `已完成 ${done}/${tasks.length}` }
          : { done: false, evidence: '尚无完成任务' }
      }
      case 'sheet-decided': {
        const items = body.verification?.sheet?.items
        if (!Array.isArray(items) || items.length === 0) return { done: false, evidence: '未见验收单' }
        const decided = items.filter(i => i.status !== 'pending').length
        return decided > 0
          ? { done: true, evidence: `已裁决 ${decided}/${items.length}` }
          : { done: false, evidence: '验收单待裁决' }
      }
      case 'archive-merged': {
        const n = body.archive?.mergedInto?.length ?? 0
        return n > 0
          ? { done: true, evidence: `已合并 ${n} 处` }
          : { done: false, evidence: '未见合并去向' }
      }
      case 'archive-indexed':
        return typeof body.archive?.indexEntry === 'string' && body.archive.indexEntry.length > 0
          ? { done: true, evidence: '索引条目已写入' }
          : { done: false, evidence: '未见索引条目' }
    }
  })
}

// ---------------------------------------------------------------------------
// 提示词片段解析
// ---------------------------------------------------------------------------

/** 路由壳判定：三段 id 且非 overrides 结尾 = include-only 合成片段（无独立文件）。 */
export function resolveFragmentRef(id: string): { id: string; kind: 'file' | 'shell' } {
  const shell = id.split('/').length === 3 && !id.endsWith('/overrides')
  return { id, kind: shell ? 'shell' : 'file' }
}

/** 该阶段「规定原文」的规范入口（模板链接，非留痕）。draft 无阶段提示词 → 空。 */
export function canonicalPromptRefs(stage: MainStageKey, category: string): { id: string; kind: 'file' }[] {
  if (stage === 'draft') return []
  const cat = category.length > 0 ? category : 'feature'
  return [
    { id: stage + '/light', kind: 'file' },
    { id: stage + '/' + cat, kind: 'file' },
    { id: 'common/iron-rules', kind: 'file' },
  ]
}

/**
 * 片段文件的工作区相对路径。
 *
 * 前缀按**工作区根**（服务端 deps.cwd = agent-dh profile 根）相对，不是插件包相对：
 * open-doc 链路（absolutizeDocPath）按工作区根绝对化，若发插件包相对的 `src/...`，
 * 会被拼成 <workspaceRoot>/src/... → 右侧栏「File not found」（2026-09-23 验收实测）。
 * 与 docs/requirements/** 的既有约定同口径。
 */
function fragmentDocPath(id: string): string {
  return 'packages/web/dsh-pmboard/src/domain/prompt/fragments/' + id + '.md'
}

// ---------------------------------------------------------------------------
// 渲染
// ---------------------------------------------------------------------------

export interface ProcessFoldContext {
  requirement: { id: string; title: string; promptDifficulty?: string | null; category?: string }
  injection: InjectionInfoEntry[]
  isolation: IsolationLogEntry[]
}

function renderInjectionSec(payload: StageDetail, ctx: ProcessFoldContext): string {
  const stage = payload.stage
  if (stage === 'draft') {
    return `<div class="dsh-pm-np-sec"><div class="dsh-pm-np-sec-title">📝 提示词注入</div>` +
      `<div class="dsh-pm-np-empty">立项无阶段纪律提示词（由 CaptureTool 立项引导驱动，不注入阶段片段）</div></div>`
  }
  const refs = canonicalPromptRefs(stage as MainStageKey, ctx.requirement.category ?? 'feature')
  const tpl = refs.length > 0
    ? `<div class="dsh-pm-np-inj-tpl">规定原文：` + refs.map(r =>
        '<button type="button" class="dsh-pm-np-doc" data-action="open-doc" data-path="' + esc(fragmentDocPath(r.id)) + '" title="' + esc(displayDocPath(fragmentDocPath(r.id))) + '">' + esc(r.id) + '</button>'
      ).join(' · ') + '</div>'
    : ''
  const entry = ctx.injection.filter(e => e.stage === stage).sort((a, b) => b.at - a.at)[0]
  let actual: string
  if (entry === undefined) {
    actual = '<div class="dsh-pm-np-empty">尚无注入留痕（该窗口本节点未触发注入，或留痕端口未装配）</div>'
  } else {
    const ids = Array.isArray(entry.fragmentIds) ? entry.fragmentIds : []
    const chips = ids.map(id => {
      const r = resolveFragmentRef(id)
      return r.kind === 'file'
        ? '<button type="button" class="dsh-pm-np-doc" data-action="open-doc" data-path="' + esc(fragmentDocPath(id)) + '" title="' + esc(displayDocPath(fragmentDocPath(id))) + '">' + esc(id) + '</button>'
        : `<span class="dsh-pm-np-shell" title="路由壳：按难度/类型拼装的合成片段，无独立文件">${esc(id)}（路由壳）</span>`
    }).join(' · ')
    actual =
      '<div class="dsh-pm-np-inj-entry">' +
        `<div class="dsh-pm-np-inj-meta">routeKey <code>${esc(entry.routeKey)}</code> · 命中 ${esc(entry.hitLevel)} · ${esc(String(entry.charCount))} 字符 · ${esc(rel(entry.at))}</div>` +
        '<div class="dsh-pm-np-inj-frags">' + chips + '</div>' +
      '</div>'
  }
  return `<div class="dsh-pm-np-sec"><div class="dsh-pm-np-sec-title">📝 提示词注入</div>${tpl}${actual}</div>`
}

function renderActionsSec(payload: StageDetail, ctx: ProcessFoldContext): string {
  const spec = STAGE_PROCESS[payload.stage as MainStageKey] ?? { contextPolicy: [], actions: [] }
  const verdicts = evaluateActions(payload, spec)
  const rows = spec.actions.map((a, i) => {
    const v = verdicts[i]
    return '<div class="dsh-pm-np-act" data-done="' + (v.done ? 'yes' : 'no') + '">' +
      '<span class="dsh-pm-np-act-mark">' + (v.done ? '✅' : '⬜') + '</span>' +
      '<span class="dsh-pm-np-act-label">' + esc(a.label) + '</span>' +
      '<span class="dsh-pm-np-act-ev">' + esc(v.evidence) + '</span>' +
    '</div>'
  }).join('')

  // 立项节点：用户选择（立项四问，真实记录）
  let choices = ''
  if (payload.stage === 'draft') {
    const body = (payload as Extract<StageDetail, { stage: 'draft' }>).body
    const lines: string[] = []
    if (typeof body.title === 'string' && body.title.length > 0) lines.push(`需求名称：${body.title}`)
    if (body.category !== undefined) lines.push(`需求类型：${body.category}`)
    if (typeof ctx.requirement.promptDifficulty === 'string' && ctx.requirement.promptDifficulty.length > 0) {
      lines.push(`提示词难度：${ctx.requirement.promptDifficulty}`)
    }
    lines.push(`文档位置：docs/requirements/${ctx.requirement.id}/`)
    choices = `<div class="dsh-pm-np-sec"><div class="dsh-pm-np-sec-title">👤 用户选择（立项四问）</div>` +
      lines.map(l => '<div class="dsh-pm-np-policy">' + esc(l) + '</div>').join('') + '</div>'
  }

  return `<div class="dsh-pm-np-sec"><div class="dsh-pm-np-sec-title">⚙️ 执行动作（规定 vs 实际）</div>${rows}</div>` + choices
}

function renderContextSec(payload: StageDetail, ctx: ProcessFoldContext): string {
  const spec = STAGE_PROCESS[payload.stage as MainStageKey] ?? { contextPolicy: [], actions: [] }
  const policy = spec.contextPolicy.map(l => '<div class="dsh-pm-np-policy">' + esc(l) + '</div>').join('')
  const entry = ctx.isolation.filter(e => e.stage === payload.stage).sort((a, b) => b.at - a.at)[0]
  const actual = entry === undefined
    ? '<div class="dsh-pm-np-empty">尚无隔离留痕</div>'
    : '<div class="dsh-pm-np-iso" data-status="' + esc(entry.status) + '">' +
        '<span class="dsh-pm-np-iso-status">' + esc(entry.status) + '</span>' +
        `<span class="dsh-pm-np-iso-meta">输入包 ${esc(String(entry.packageChars))} 字符 · ${esc(rel(entry.at))}</span>` +
        '<div class="dsh-pm-np-iso-reason">' + esc(entry.reason) + '</div>' +
      '</div>'
  return `<div class="dsh-pm-np-sec"><div class="dsh-pm-np-sec-title">🗜️ 上下文管理</div>${policy}${actual}</div>`
}

/** 渲染「🔄 执行流程」折叠块（默认收起）。纯函数。 */
export function renderProcessFold(payload: StageDetail, ctx: ProcessFoldContext): string {
  if (!payload.enabled) return ''
  return '<details class="dsh-pm-np-fold">' +
    `<summary><span class="dsh-pm-np-fold-icon">▸</span><span class="dsh-pm-np-fold-text">🔄 执行流程</span></summary>` +
    '<div class="dsh-pm-np-fold-body">' +
      renderInjectionSec(payload, ctx) +
      renderActionsSec(payload, ctx) +
      renderContextSec(payload, ctx) +
    '</div>' +
  '</details>'
}

/** 节点状态词（面板头状态胶囊）：与流程节点四态同色同口径。 */
export const STAGE_STATE_WORD: Record<MainStageKey, string> = {
  draft: '已立项',
  brainstorming: '已分析',
  design: '已设计',
  decomposing: '已拆分',
  implementing: '实施中',
  accepting: '待验收',
  archived: '已归档',
}
