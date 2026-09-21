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
  validateExplicitStages,
  type StageKind,
} from '../../domain/task/SubtaskTemplate.js'
import type { IdFactory } from '../ports.js'
import {
  recordStatus,
  type ReqboardLedger,
  type RequirementRecord,
  type TaskRecord,
} from '../../shared/protocol.js'

/** 解析该父卡应落哪些子卡：显式 stages 优先（FR-1b），否则按需求分类走映射表。 */
export function resolveSubtaskStages(
  parent: Pick<TaskRecord, 'stages' | 'skipIntegration'>,
  requirement: Pick<RequirementRecord, 'category'> | undefined,
): StageKind[] {
  let stages: readonly StageKind[]
  if (parent.stages !== undefined && parent.stages.length > 0) {
    const verdict = validateExplicitStages(parent.stages)
    if (!verdict.ok) throw Object.assign(new Error(verdict.error), { code: 'REQBOARD_STAGES_INVALID' })
    stages = verdict.value
  } else {
    stages = stagesForCardType(requirement?.category)
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
 * 落子卡链（调用方须在 mutate 事务内调用；不 push 到 ledger 之外）。
 * 返回新建的子卡（已有子卡 / 自身是子卡 → 返回空数组，幂等）。
 */
export function expandSubtasks(
  ledger: ReqboardLedger,
  parent: TaskRecord,
  requirement: Pick<RequirementRecord, 'category'> | undefined,
  now: number,
  ids: IdFactory,
): TaskRecord[] {
  if (parent.parentId !== undefined) return []
  if (ledger.tasks.some((t) => t.parentId === parent.id)) return []
  const stages = resolveSubtaskStages(parent, requirement)
  const specs = buildSubtaskSpecs(stages)
  const actor = { kind: 'system' as const }
  const created: TaskRecord[] = []
  for (const spec of specs) {
    const id = ids.task()
    // 链首继承父卡外部依赖（跨父卡顺序由父卡层表达）；其余依赖前一张子卡。
    const dependsOn = spec.dependsOnIndex === null
      ? [...parent.dependsOn]
      : [created[spec.dependsOnIndex]?.id ?? ''].filter((x) => x.length > 0)
    const child: TaskRecord = {
      id,
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
    ledger.tasks.push(child)
    created.push(child)
  }
  return created
}
