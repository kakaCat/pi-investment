/**
 * 地址解析纯函数（REQ-260922213356-4a45 T-2 / design S-1、S-2、I-1、I-2）。
 *
 * 纯函数、零 I/O、不碰时间与随机数：只查静态表与入参台账投影。
 * 门禁同源由守护单测断言（见 registry.ts 头注），故本模块不 import 门禁规则与 shared 类型。
 *
 * @module dsh-pmboard/domain/template/resolve
 */
import { ALL_STAGE_PROMPT_KEYS } from '../stage/StagePromptSpec.js'
import { CATEGORIES, DEFAULT_CATEGORY, isPromptStage, type Category } from '../prompt/types.js'
import { fmt } from '../text/fmt.js'
import { NODE_TEMPLATES } from './registry.js'
import type { CurrentTaskRef, DocRef, TemplateRef, UpstreamSource } from './types.js'

/** 非可注入节点（入口态/终态）：调用方不应到达，到达时返回空集（不是错误）。 */
const NON_INJECTABLE: ReadonlySet<string> = new Set(['draft', 'done', 'canceled'])

/**
 * 按节点与类型取该节点该类型应产出的模板条目（I-1）。
 *
 * 语义：表只登记门禁启用的组合，故禁用组合自然返回空集（等价 stageEnabledFor=false）；
 * 未登记的类型（如 bug 的 design）返回空集，不臆造地址。
 * 非法 stage/category 响亮抛错，不静默当通配。
 */
export function resolveNodeTemplates(stage: string, category: Category | string | undefined): readonly TemplateRef[] {
  if (NON_INJECTABLE.has(stage)) return []
  if (!isPromptStage(stage)) {
    throw new Error(fmt('resolveNodeTemplates：非法节点 {stage}（合法：{legal}）', { stage: JSON.stringify(stage), legal: ALL_STAGE_PROMPT_KEYS.join('/') }))
  }
  const cat = category === undefined ? DEFAULT_CATEGORY : category
  if (!(CATEGORIES as readonly string[]).includes(cat)) {
    throw new Error(fmt('resolveNodeTemplates：非法类型 {cat}（合法：{legal}）', { cat: JSON.stringify(cat), legal: CATEGORIES.join('/') }))
  }
  return NODE_TEMPLATES[stage]?.[cat] ?? []
}

/** 产物种类 → 人读名（找不到映射回落 kind 原文；与 shared/artifact-labels 的一致性由守护单测断言）。 */
const KIND_TITLES: Readonly<Record<string, string>> = {
  requirement: '需求说明',
  design: '设计文档',
  plan: '拆分计划',
  decomposition: '拆分计划',
  task_detail: '任务卡',
  task_output: '任务产物',
  verification: '验收材料',
  archive: '归档材料',
  notes: '其他',
}

export function kindTitle(kind: string): string {
  return KIND_TITLES[kind] ?? kind
}

/**
 * 从台账投影取「开工前该先读」的上游产物地址（I-2 / S-2）。
 *
 * 只从 requirement.artifacts（已登记）与 currentTask.cardDoc 取；取不到不列出（禁止臆造）。
 * 顺序：先按上游节点顺序，再当前任务卡。
 */
export function resolveUpstreamDocs(
  requirement: UpstreamSource | undefined,
  stage: string,
  currentTask?: CurrentTaskRef,
): readonly DocRef[] {
  if (requirement === undefined) return []
  const stageIdx = (ALL_STAGE_PROMPT_KEYS as readonly string[]).indexOf(stage)
  if (stageIdx < 0) return []

  const order: { ref: DocRef; at: number; stageIdx: number }[] = []
  const seen = new Set<string>()
  const artifacts = requirement.artifacts ?? []
  for (let i = 0; i < artifacts.length; i++) {
    const a = artifacts[i]
    if (a === undefined) continue
    const path = (a.path ?? '').trim()
    if (path.length === 0 || seen.has(path)) continue
    const upstreamIdx = (ALL_STAGE_PROMPT_KEYS as readonly string[]).indexOf(a.stage ?? '')
    if (upstreamIdx < 0 || upstreamIdx >= stageIdx) continue
    seen.add(path)
    order.push({ ref: { kind: a.kind ?? 'notes', path, title: kindTitle(a.kind ?? 'notes') }, at: i, stageIdx: upstreamIdx })
  }
  order.sort((x, y) => (x.stageIdx - y.stageIdx) || (x.at - y.at))

  const cardDoc = (currentTask?.cardDoc ?? '').trim()
  if (cardDoc.length > 0 && !seen.has(cardDoc)) {
    order.push({ ref: { kind: 'task_detail', path: cardDoc, title: kindTitle('task_detail') }, at: Number.MAX_SAFE_INTEGER, stageIdx: stageIdx })
  }
  return order.map((o) => o.ref)
}
