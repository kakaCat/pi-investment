/**
 * 父卡懒展开（REQ-4842fe t6 / FR-3）：父卡开工时**同事务**落子卡链。
 *
 * 为什么懒展开而不是拆分时就落：计划批准的是任务表，拆分时偷落子卡会变成"批了 A 落库 B"
 * （requirement 1.2 的反面教材）；开工时才出现于看板，且与状态变更同一 revision（原子）。
 *
 * 幂等（INV-3）：名下已有子卡即跳过——重复开工不产生第二套。
 *
 * @module dsh-pmboard/application/internal/lazy-expand
 */
import { fmt } from '../../domain/text/fmt.js'
import {
  buildSubtaskSpecs,
  stagesForCardType,
  type SubtaskSpec,
  stagesForPhase,
  stagesForSide,
  validateExplicitStages,
  type StageKind,
} from '../../domain/task/SubtaskTemplate.js'
import type { IdFactory } from '../ports.js'
import {
  recordStatus,
  type RequirementRecord,
  type TaskRecord,
} from '../../shared/protocol.js'

/**
 * 解析该父卡应落哪些子卡：显式 stages 优先（FR-1b；**`[]` = 明确无链**）→ 卡 phase → 卡 side（纯文档卡）→ 需求分类兜底。
 *
 * 为什么是这个顺序（REQ-260928185112-e20d 实测）：同一需求下所有父卡曾一律吃需求分类的 4 段，
 * 于是"零调用方"的新增卡照样落联调段、doc 卡也落联调+测试段、验证卡还先落 dev 段——
 * 6 张联调卡共 24.7 min **零落盘产出**。phase 描述的是"这张卡自己是什么活"，比需求分类更贴近实际。
 *
 * 第四层"这张卡有没有接口面"**不在这里推断**：它是计划侧才能声明的事实（skipIntegration / stages），
 * 代码从端侧猜"要不要与别的模块对接"必然猜错，猜错就是**静默削段**——宁可保守保留。
 */
export function resolveSubtaskStages(
  parent: Pick<TaskRecord, 'stages' | 'skipIntegration' | 'phase' | 'side'>,
  requirement: Pick<RequirementRecord, 'category'> | undefined,
): StageKind[] {
  let stages: readonly StageKind[]
  // 判据必须是 `!== undefined`：`[]` = 显式声明无链（solo）→ 返回空集、不落任何子卡；
  // `undefined` = 未指定 → 走映射表。旧判据 `.length > 0` 会把"明确不要链"当成"没写"，
  // 静默改回默认 4 段——这正是"不需子卡"与"未生成"分不清的根因（2026-09-28 卡片层契约）。
  if (parent.stages !== undefined) {
    const verdict = validateExplicitStages(parent.stages)
    if (!verdict.ok) throw Object.assign(new Error(verdict.error), { code: 'REQBOARD_STAGES_INVALID' })
    stages = verdict.value
  } else {
    stages = stagesForPhase(parent.phase) ?? stagesForSide(parent.side) ?? stagesForCardType(requirement?.category)
  }
  // 联调卡沿用既有 skipIntegration 语义（其余卡不允许跳过）。
  if (parent.skipIntegration === true) stages = stages.filter((s) => s !== 'integrate')
  return [...stages]
}

function childImplementation(parent: TaskRecord, label: string, acceptance: string): string {
  const impl = (parent.implementation ?? '').trim()
  return impl.length > 0
    ? fmt('{impl}\n\n[子卡阶段·{label}] 只做本阶段；验收：{acceptance}', { impl, label, acceptance })
    : fmt('[子卡阶段·{label}] 验收：{acceptance}', { label, acceptance })
}

/**
 * 造一张子卡记录（expandSubtasks 与 regenerateChain **共用**）——字段构造只此一处：
 * 补链若另写一套，极易漏 parentId/stageKind，子卡会被下游当成平级卡（本仓已踩过：装配器漏投影
 * 导致线上 35 张卡「父卡=35 子卡=0」）。
 */
function makeChild(parent: TaskRecord, spec: SubtaskSpec, dependsOn: string[], now: number, ids: IdFactory): TaskRecord {
  const actor = { kind: 'system' as const }
  const child: TaskRecord = {
    id: ids.task(),
    requirementId: parent.requirementId,
    title: fmt('{parent}·{stage}', { parent: parent.title, stage: spec.title }).slice(0, 120),
    description: fmt('子卡阶段：{label}', { label: spec.title }),
    phase: parent.phase,
    side: parent.side,
    dependsOn,
    scope: { apis: [...parent.scope.apis], tables: [...parent.scope.tables], files: [...parent.scope.files] },
    acceptance: spec.acceptance,
    implementation: childImplementation(parent, spec.title, spec.acceptance),
    context: parent.context,
    parentId: parent.id,
    stageKind: spec.stageKind,
    attempt: 0,
    revisions: [],
    status: 'todo',
    blocked: false,
    executions: [],
    comments: [],
    version: 1,
    createdAt: now,
    updatedAt: now,
    createdBy: actor,
    updatedBy: actor,
    statusHistory: [],
  }
  recordStatus(child, 'todo', now, actor)
  return child
}

/**
 * 造子卡链（**只返回新建子卡，不落库**）。
 *
 * REQ-260927202051-f6df D4：任务已不在台账（v9 无 `tasks` 键），故本函数收**队列任务**作幂等判据，
 * 返回新建的子卡由调用方 append 进 `taskStore.mutate` 的草稿并 `return tasks` 落盘。
 * 幂等：已有子卡 / 自身是子卡 → 返回空数组。
 */
export function expandSubtasks(
  tasks: readonly TaskRecord[],
  parent: TaskRecord,
  requirement: Pick<RequirementRecord, 'category'> | undefined,
  now: number,
  ids: IdFactory,
): TaskRecord[] {
  if (parent.parentId !== undefined) return []
  if (tasks.some((t) => t.parentId === parent.id)) return []
  const stages = resolveSubtaskStages(parent, requirement)
  const specs = buildSubtaskSpecs(stages)
  const created: TaskRecord[] = []
  for (const spec of specs) {
    // 链首继承父卡外部依赖（跨父卡顺序由父卡层表达）；其余依赖前一张子卡。
    const dependsOn = spec.dependsOnIndex === null
      ? [...parent.dependsOn]
      : [created[spec.dependsOnIndex]?.id ?? ''].filter((x) => x.length > 0)
    // 不 push：任务由调用方经 taskStore.mutate 落队列（REQ-260927202051-f6df）
    created.push(makeChild(parent, spec, dependsOn, now, ids))
  }
  return created
}

/**
 * 链体检（只读，卡片层契约 2026-09-28）——诊断用，不写台账。
 *  expected：该卡按映射表应落的段；existing：已有子卡的 stageKind；missing：应有未有；
 *  solo：expected 为空（= 该卡显式声明 stages: []，本就不需链）。
 */
export function chainDiagnosis(
  tasks: readonly TaskRecord[],
  parent: TaskRecord,
  requirement: Pick<RequirementRecord, 'category'> | undefined,
): { expected: StageKind[]; existing: StageKind[]; missing: StageKind[]; solo: boolean } {
  const expected = [...resolveSubtaskStages(parent, requirement)]
  const existing: StageKind[] = []
  for (const k of tasks) {
    if (k.parentId !== parent.id) continue
    if (k.stageKind !== undefined && !existing.includes(k.stageKind)) existing.push(k.stageKind)
  }
  return {
    expected,
    existing,
    missing: expected.filter((s) => !existing.includes(s)),
    solo: expected.length === 0,
  }
}

/**
 * 再生成（补链，卡片层契约 2026-09-28）——**只补缺失阶段**，已有子卡（含 done）一律不动。
 *
 * 与 expandSubtasks 的分工：后者是"开工时首次展开"（有子卡即整体跳过），本函数是"事后补差集"。
 * 返回新建子卡（由调用方落队列）；solo 卡（stages: []）返回空集——**明确不落链**，调用方须回执说明。
 * 补出的卡按应有段序串联：前驱 = 上一段（已存在的用其 id，刚补的用新 id），链首继承父卡外部依赖。
 */
export function regenerateChain(
  tasks: readonly TaskRecord[],
  parent: TaskRecord,
  requirement: Pick<RequirementRecord, 'category'> | undefined,
  now: number,
  ids: IdFactory,
): TaskRecord[] {
  if (parent.parentId !== undefined) return []
  const expected = resolveSubtaskStages(parent, requirement)
  if (expected.length === 0) return []
  const existing = tasks.filter((t) => t.parentId === parent.id)
  if (existing.length === 0) return expandSubtasks(tasks, parent, requirement, now, ids)
  const byStage = new Map<string, string>()
  for (const k of existing) if (k.stageKind !== undefined) byStage.set(k.stageKind, k.id)
  const created: TaskRecord[] = []
  let prevId: string | undefined
  for (const spec of buildSubtaskSpecs(expected)) {
    const hit = byStage.get(spec.stageKind)
    if (hit !== undefined) { prevId = hit; continue }
    const dependsOn = prevId !== undefined ? [prevId] : [...parent.dependsOn]
    const child = makeChild(parent, spec, dependsOn, now, ids)
    created.push(child)
    prevId = child.id
  }
  return created
}
