/**
 * 节点输入包装配（REQ-260926140539-457b FR-8 / design/interfaces.md §3.1）。
 *
 * Dive 模式在每个节点启动时不再实时解析一堆文档，而是读预构建的 RTM 快照：
 *   - full 模式：完整 inputs / outputs / traceability / coverage（首次注入用）；
 *   - compressed 模式：只留"要判断什么"的最小信息（循环检查用，~10:1 压缩）。
 *
 * RTM 缺失时不抛异常：next_action 如实说明"数据缺失"，由调用方决定是否降级重生成（FR-9）。
 *
 * @module @pi-investment/reqboard/dive/node-input
 */
import { getRTMPath, readRTM, requirementsDir } from '../rtm/file-io.js'
import { RTM_STAGE_ORDER, type Coverage, type RTMTaskDetail } from '../rtm/types.js'
import { readStageRTM } from '../stage-overview/rtm-reader.js'

/** 注入模式。 */
export type NodeInputMode = 'full' | 'compressed'

/** 注入节点输入包的数据块。 */
export interface NodeInput {
  stage: string
  requirement_id: string
  mode: NodeInputMode
  previous_stage?: string
  /** 本节点状态（compressed 模式为 { progress, current_tasks }）。 */
  status?: unknown
  inputs?: unknown
  outputs?: unknown
  traceability?: unknown
  coverage?: unknown
  /** 下一步行动建议（由 generateNextAction 生成）。 */
  next_action?: string
}

/** 压缩后的覆盖度：只留 rate 与 uncovered（FR-8 压缩规则）。 */
export interface CompactCoverage {
  rate: number
  uncovered: string[]
}

function asRecord(v: unknown): Record<string, unknown> | undefined {
  return typeof v === 'object' && v !== null && !Array.isArray(v) ? (v as Record<string, unknown>) : undefined
}

function asArray(v: unknown): unknown[] {
  return Array.isArray(v) ? v : []
}

function num(v: unknown): number {
  return typeof v === 'number' && Number.isFinite(v) ? v : 0
}

function str(v: unknown): string {
  return typeof v === 'string' ? v : ''
}

/** 阶段顺序中的上一节点（draft 无上游）。 */
export function previousStageOf(stage: string): string | undefined {
  const order = RTM_STAGE_ORDER as readonly string[]
  const i = order.indexOf(stage)
  return i > 0 ? order[i - 1] : undefined
}

/** 阶段顺序中的下一节点（done 无下游）。 */
export function nextStageOf(stage: string): string | undefined {
  const order = RTM_STAGE_ORDER as readonly string[]
  const i = order.indexOf(stage)
  return i >= 0 && i < order.length - 1 ? order[i + 1] : undefined
}

/** 取某个覆盖度块（design / implementation / testing）。 */
export function coverageAt(rtm: unknown, key: string): Coverage | undefined {
  const cov = asRecord(asRecord(rtm)?.coverage)
  const block = asRecord(cov?.[key])
  if (block === undefined) return undefined
  if (typeof block.rate !== 'number') return undefined
  return {
    total: num(block.total),
    covered: num(block.covered),
    uncovered: asArray(block.uncovered).map(str),
    rate: num(block.rate),
  }
}

/** brainstorming 节点的 FR 列表（full 与 compressed 都用）。 */
function frIds(rtm: Record<string, unknown> | undefined): string[] {
  const outputs = asRecord(rtm?.outputs)
  const reqs = asArray(outputs?.requirements)
  return reqs.map(r => str(asRecord(r)?.id)).filter(id => id.length > 0)
}

/** brainstorming 产物是否已落章。 */
function artifactConfirmed(rtm: Record<string, unknown> | undefined): boolean {
  const status = asRecord(rtm?.status)
  const artifacts = asArray(status?.artifacts)
  return artifacts.some(a => asRecord(a)?.confirmed === true)
}

/**
 * 下一步行动建议（FR-8 决策逻辑的"人话"出口）。
 * RTM 缺失时不伪造判断，如实说明缺哪份数据。
 */
export function generateNextAction(stage: string, stageRTM: unknown): string {
  const rtm = asRecord(stageRTM)
  if (rtm === undefined) return `RTM 数据缺失（rtm-${stage}.yml），按台账继续当前节点`

  switch (stage) {
    case 'brainstorming': {
      const frs = frIds(rtm)
      return artifactConfirmed(rtm)
        ? `需求已确认，识别到 ${frs.length} 个功能点，准备进入 design`
        : `等待需求产物确认（已提取 ${frs.length} 个功能点）`
    }
    case 'design': {
      const c = coverageAt(rtm, 'design')
      if (c === undefined) return '设计覆盖度未知，请先提交设计文档'
      return c.rate >= 100
        ? '所有 FR 都有设计，可以准备拆分'
        : `还有 ${c.uncovered.length} 个 FR 缺少设计：${c.uncovered.join('、')}`
    }
    case 'decomposing': {
      const c = coverageAt(rtm, 'implementation')
      if (c === undefined) return '实施覆盖度未知，请先批准拆分计划'
      return c.rate >= 100
        ? '所有设计章节都有任务，可以开工'
        : `还有 ${c.uncovered.length} 个设计章节缺少任务：${c.uncovered.join('、')}`
    }
    case 'implementing': {
      const s = asRecord(rtm.status)
      const total = num(s?.tasks_total)
      const done = num(s?.tasks_done)
      const doing = num(s?.tasks_in_progress)
      if (total === 0) return '暂无任务'
      return done >= total
        ? '所有任务已完成，可以进入验收'
        : `任务进度 ${done}/${total}（${doing} 个进行中），继续执行`
    }
    case 'accepting': {
      const c = coverageAt(rtm, 'testing')
      if (c === undefined) return '测试覆盖度未知，请先提交验收材料'
      return c.rate >= 80
        ? `测试覆盖度 ${c.rate}%，可以归档`
        : `测试覆盖度 ${c.rate}%（< 80%），缺少测试的任务：${c.uncovered.join('、')}`
    }
    default:
      return '继续当前节点'
  }
}

/** 压缩覆盖度块：只保留 rate / uncovered。 */
function compactCoverage(rtm: Record<string, unknown> | undefined): Record<string, CompactCoverage> | undefined {
  const cov = asRecord(rtm?.coverage)
  if (cov === undefined) return undefined
  const out: Record<string, CompactCoverage> = {}
  for (const [key, value] of Object.entries(cov)) {
    const block = asRecord(value)
    if (block === undefined || typeof block.rate !== 'number') continue
    out[key] = { rate: num(block.rate), uncovered: asArray(block.uncovered).map(str) }
  }
  return Object.keys(out).length > 0 ? out : undefined
}

/** 压缩产出：只留 id 列表。 */
function compactOutputs(stage: string, rtm: Record<string, unknown> | undefined): unknown {
  if (rtm === undefined) return undefined
  const outputs = asRecord(rtm.outputs)
  switch (stage) {
    case 'brainstorming':
    case 'design':
      return { requirements: frIds(rtm) }
    case 'decomposing':
      return { tasks: asArray(outputs?.tasks).map(t => str(asRecord(t)?.id)).filter(Boolean) }
    case 'accepting':
      return { test_cases: asArray(outputs?.test_cases).map(t => str(asRecord(t)?.id)).filter(Boolean) }
    default:
      return undefined
  }
}

/**
 * 压缩模式：只保留"当前卡在哪、还缺什么"（FR-8 压缩规则，~10:1）。
 * implementing 额外带上进行中任务的当前子阶段（读其详情文件，只读进行中的前 10 个）。
 */
export function assembleCompressed(
  workspaceRoot: string,
  stage: string,
  reqId: string,
  stageRTM: unknown,
): NodeInput {
  const rtm = asRecord(stageRTM)
  const base: NodeInput = {
    stage,
    requirement_id: reqId,
    mode: 'compressed',
    previous_stage: previousStageOf(stage),
    next_action: generateNextAction(stage, stageRTM),
  }
  if (rtm === undefined) return base

  const coverage = compactCoverage(rtm)
  const outputs = compactOutputs(stage, rtm)

  if (stage === 'implementing') {
    const s = asRecord(rtm.status)
    const tasks = asArray(rtm.tasks).map(asRecord).filter((t): t is Record<string, unknown> => t !== undefined)
    const inProgress = tasks.filter(t => t.status === 'in_progress').map(t => str(t.id)).filter(Boolean)
    return {
      ...base,
      status: {
        progress: `${num(s?.tasks_done)}/${num(s?.tasks_total)} done, ${num(s?.tasks_in_progress)} in_progress`,
        current_tasks: currentTaskPhases(workspaceRoot, reqId, inProgress),
      },
      ...(coverage !== undefined ? { coverage } : {}),
      ...(outputs !== undefined ? { outputs } : {}),
    }
  }

  return {
    ...base,
    ...(coverage !== undefined ? { coverage } : {}),
    ...(outputs !== undefined ? { outputs } : {}),
  }
}

/** 进行中任务的 `id@phase` 列表（读任务详情文件；上限 10 个，避免压缩模式变慢）。 */
function currentTaskPhases(workspaceRoot: string, reqId: string, ids: string[]): string[] {
  const out: string[] = []
  for (const id of ids.slice(0, 10)) {
    const detail = readRTM<RTMTaskDetail>(getRTMPath(requirementsDir(workspaceRoot, reqId), `rtm-implementing/${id}.yml`))
    const phase = detail?.task?.workflow?.find(w => w.status === 'in_progress')?.phase
    out.push(phase === undefined ? id : `${id}@${phase}`)
  }
  return out
}

/**
 * 装配节点输入包（FR-8）。
 *
 * @param workspaceRoot 工作区根（docs/requirements 所在处）
 * @param stage 当前节点
 * @param reqId 需求 id
 * @param mode full（首次注入） | compressed（循环检查）
 */
export function assembleNodeInput(
  workspaceRoot: string,
  stage: string,
  reqId: string,
  mode: NodeInputMode = 'full',
): NodeInput {
  const stageRTM = readStageRTM<Record<string, unknown>>(workspaceRoot, reqId, stage)

  if (mode === 'compressed') return assembleCompressed(workspaceRoot, stage, reqId, stageRTM)

  return {
    stage,
    requirement_id: reqId,
    mode: 'full',
    previous_stage: previousStageOf(stage),
    ...(stageRTM?.status !== undefined ? { status: stageRTM.status } : {}),
    ...(stageRTM?.inputs !== undefined ? { inputs: stageRTM.inputs } : {}),
    ...(stageRTM?.outputs !== undefined ? { outputs: stageRTM.outputs } : {}),
    ...(stageRTM?.traceability !== undefined ? { traceability: stageRTM.traceability } : {}),
    ...(stageRTM?.coverage !== undefined ? { coverage: stageRTM.coverage } : {}),
    next_action: generateNextAction(stage, stageRTM),
  }
}

/** 粗略 token 估算（4 字符 ≈ 1 token），用于度量压缩比。 */
export function estimateTokens(value: unknown): number {
  try {
    return Math.ceil(JSON.stringify(value).length / 4)
  } catch {
    return 0
  }
}
