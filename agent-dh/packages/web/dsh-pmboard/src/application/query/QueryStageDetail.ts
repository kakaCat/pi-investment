/**
 * 节点详情装配器（Application 层，模板模式）。
 *
 * 设计来源：REQ-31e11f §3.2——「骨架固定、内容可变」用 Template Method 落地：
 *   - assemble(req, ledger, stage) 固定骨架：节点头 + 分类启用标记 + 时间线切片 +
 *     操作者标注 + 产物列表 + pendingConfirmation 标记；
 *   - buildBody() 抽象步由各节点装配器实现，产出 protocol.ts StageDetail 判别联合
 *     对应成员。
 *
 * 分类感知：flowProfileFor/stageEnabledFor 判定该分类是否启用该节点——跳过的节点
 * 返回 enabled:false 的 StageDetail（body 给空对象），不报错（UI 标灰"本分类跳过"）。
 *
 * 双端共享同一份 StageDetail shape（domain 层单一定义）——看板详情抽屉与会话框
 * 节点面板消费同一接口同一形状，从机制上消除两套口径。
 *
 * @module dsh-pmboard/host/stage-detail
 */
import {
  ALL_STAGE_KEYS,
  ARTIFACT_CONFIRM_GATES,
  flowProfileFor,
  stageEnabledFor,
  windowCodeFromSessionId,
  type ArchiveStageBody,
  type AcceptStageBody,
  type BrainstormStageBody,
  type DecomposeStageBody,
  type DoneStageBody,
  type DraftStageBody,
  type ImplementStageBody,
  type DesignStageBody,
  type PlanTask,
  type RequirementRecord,
  type StageArtifact,
  type StageDetail,
  type StageKey,
  type StageOverview,
  type StageTaskExecution,
  type StageTaskRef,
  type StatusEvent,
  type TaskRecord,
} from '../../shared/protocol.js'
import { designDocStatus, designDocPolicyOf, EMPTY_DESIGN_DOC_POLICY } from '../internal/design-docs.js'
import type { DesignDocPolicy } from '../internal/category-doc-sets.js'
import type { LedgerView, UseCaseDeps } from '../ports.js'

/** 装配器上下文：需求 + 台账（取任务/时间线切片用）+ 可选设计文档策略（REQ-2d1c74，host 侧读 front-matter 注入）。 */
export interface AssembleContext {
  req: RequirementRecord
  ledger: Pick<LedgerView, 'tasks'>
  /** 设计文档集策略（sides/design_exempt）；缺省 = 空策略（只有必交、无豁免） */
  designDocPolicy?: DesignDocPolicy
}

/**
 * 模板基类：固定 assemble 骨架，buildBody 为可变步。
 *
 * 骨架顺序：分类启用判定 → 节点头(stage/enabled) → 时间线切片 → 操作者标注 →
 * 产物列表 → pendingConfirmation 标记 → buildBody()。
 */
abstract class StageDetailAssembler {
  abstract readonly stage: StageKey

  assemble(ctx: AssembleContext): StageDetail {
    const { req, ledger } = ctx
    const enabled = stageEnabledFor(req.category, this.stage)
    const tokens = req.tokenUsage?.byStage?.[this.stage]
    const base = {
      stage: this.stage,
      enabled,
      artifacts: artifactsForStage(req, this.stage),
      pendingConfirmation: pendingConfirmationFor(req, this.stage),
      timeline: timelineForStage(req, this.stage),
      ...(tokens !== undefined ? { tokens } : {}),
    }
    // 分类跳过：body 给空对象（契约要求对应成员存在），UI 标灰不算缺失
    const body = enabled ? this.buildBody(req, ledger, ctx) : ({} as never)
    return { ...base, body } as StageDetail
  }

  /** 可变步：各节点装配器实现，产出 StageDetail 判别联合对应 body 成员。 */
  protected abstract buildBody(
    req: RequirementRecord,
    ledger: Pick<LedgerView, 'tasks'>,
    ctx: AssembleContext,
  ): StageDetail['body']
}

// ---------------------------------------------------------------------------
// 产物 / 时间线 / 确认门（骨架共用步）
// ---------------------------------------------------------------------------

/** 该 stage 已登记的产物（按登记时间升序）。 */
function artifactsForStage(req: RequirementRecord, stage: StageKey): StageArtifact[] {
  return (req.artifacts ?? []).filter(a => a.stage === stage)
}

/**
 * pendingConfirmation：该 stage 是某道 ARTIFACT_CONFIRM_GATES 的源头（from 端）且
 * 对应 kind 的产物存在但未 confirmedAt。
 *
 * 例：stage='brainstorming'，门 'brainstorming>design' 要求 kind='requirement'——
 * 若 req.artifacts 里有 {stage:'brainstorming', kind:'requirement'} 且未确认 → true。
 */
function pendingConfirmationFor(req: RequirementRecord, stage: StageKey): boolean {
  const profile = flowProfileFor(req.category)
  for (const [transition, kind] of Object.entries(ARTIFACT_CONFIRM_GATES)) {
    const [from] = transition.split('>')
    if (from !== stage) continue
    // 该分类未启用此门 → 不算待确认
    if (!profile.confirmGates.includes(transition)) continue
    const artifact = (req.artifacts ?? []).find(a => a.stage === stage && a.kind === kind)
    if (artifact !== undefined && artifact.confirmedAt === undefined) return true
  }
  return false
}

/** 该 stage 的状态事件切片（谁在何时为何进入该阶段；含 inferred 标注）。 */
function timelineForStage(req: RequirementRecord, stage: StageKey): StatusEvent[] {
  return (req.statusHistory ?? []).filter(e => e.status === stage)
}

/** 操作者标注辅助：把 ActorRef 转成可读字符串（human/agent:sessionId/system）。 */
function actorLabel(by: { kind: string; sessionId?: string } | undefined): string | undefined {
  if (by === undefined) return undefined
  if (by.kind === 'agent' && by.sessionId) {
    return `agent:${windowCodeFromSessionId(by.sessionId)}`
  }
  return by.kind
}

// ---------------------------------------------------------------------------
// 8 节点装配器
// ---------------------------------------------------------------------------

/** 立项：需求卡（标题/分类/描述）+ 立项窗口 + 时间。 */
class DraftStageAssembler extends StageDetailAssembler {
  readonly stage = 'draft' as const
  protected buildBody(req: RequirementRecord): DraftStageBody {
    return {
      title: req.title,
      ...(req.category !== undefined ? { category: req.category } : {}),
      description: req.description,
      ...(req.sourceSessionId !== undefined
        ? { sourceWindow: windowCodeFromSessionId(req.sourceSessionId) }
        : {}),
      createdAt: req.createdAt,
    }
  }
}

/** 需求分析：需求文档（路径）+ 共创会话 + 评论留痕。 */
class BrainstormStageAssembler extends StageDetailAssembler {
  readonly stage = 'brainstorming' as const
  protected buildBody(req: RequirementRecord): BrainstormStageBody {
    const requirementDoc = (req.artifacts ?? []).find(
      a => a.stage === 'brainstorming' && a.kind === 'requirement',
    )?.path ?? req.docLinks?.requirement
    return {
      ...(requirementDoc !== undefined ? { requirementDoc } : {}),
      ...(req.reviewSessionId !== undefined ? { reviewSessionId: req.reviewSessionId } : {}),
      comments: req.comments,
    }
  }
}

/** 设计：计划文档（路径）+ 完整 PlanRecord（含任务表与批准/退回留痕）+ 分类（文档集要求）
 *  + 设计文档逐份交付状态（REQ-81aabd FR-2：已交/未交，纯展示，不影响推进条件）。 */
class DesignStageAssembler extends StageDetailAssembler {
  readonly stage = 'design' as const
  protected buildBody(req: RequirementRecord, _ledger: Pick<LedgerView, 'tasks'>, ctx: AssembleContext): DesignStageBody {
    // REQ-2d1c74 FR-1/FR-2：投影带条件必交徽标与豁免理由——策略由 host 侧读 requirement.md
    // front-matter 注入（designDocPolicyOf），缺省空策略时行为与扩展前一致。
    return {
      ...(req.plan !== undefined ? { plan: req.plan } : {}),
      ...(req.category !== undefined ? { category: req.category } : {}),
      ...(req.category !== undefined ? { designDocs: designDocStatus(req, req.category, ctx.designDocPolicy ?? EMPTY_DESIGN_DOC_POLICY) } : {}),
    }
  }
}

/** 拆分：拆分文档 + 落库任务 DAG + 与计划任务表对照。 */
class DecomposeStageAssembler extends StageDetailAssembler {
  readonly stage = 'decomposing' as const
  protected buildBody(
    req: RequirementRecord,
    ledger: Pick<LedgerView, 'tasks'>,
  ): DecomposeStageBody {
    const tasks = ledger.tasks.filter(t => t.requirementId === req.id)
    const decompositionDoc = (req.artifacts ?? []).find(
      a => a.stage === 'decomposing' && a.kind === 'decomposition',
    )?.path
    return {
      ...(decompositionDoc !== undefined ? { decompositionDoc } : {}),
      tasks: tasks.map(t => toStageTaskRef(t)),
      planTasks: req.plan?.tasks ?? [],
    }
  }
}

/** 实施：每任务执行记录（窗口码/claimedBy/executions）+ 按窗口分组。 */
class ImplementStageAssembler extends StageDetailAssembler {
  readonly stage = 'implementing' as const
  protected buildBody(
    req: RequirementRecord,
    ledger: Pick<LedgerView, 'tasks'>,
  ): ImplementStageBody {
    const tasks = ledger.tasks
      .filter(t => t.requirementId === req.id)
      .map(t => toStageTaskExecution(t))
    const byWindow: Record<string, string[]> = {}
    for (const t of tasks) {
      // 任务归属窗口：claimedBy（执行窗口）优先；否则按执行记录里的 sessionId 归组；
      // 都没有 → 'unassigned'（未领取）
      const windows = new Set<string>()
      if (t.claimedBy !== undefined) windows.add(windowCodeFromSessionId(t.claimedBy))
      for (const e of t.executions) {
        if (e.sessionId !== undefined) windows.add(windowCodeFromSessionId(e.sessionId))
      }
      if (windows.size === 0) windows.add('unassigned')
      for (const w of windows) {
        ;(byWindow[w] ??= []).push(t.id)
      }
    }
    return { tasks, byWindow }
  }
}

/** 验收：验收材料 + 人工 pass/rework 结论。 */
class AcceptStageAssembler extends StageDetailAssembler {
  readonly stage = 'accepting' as const
  protected buildBody(req: RequirementRecord): AcceptStageBody {
    return {
      ...(req.verification !== undefined ? { verification: req.verification } : {}),
    }
  }
}

/** 完成：里程碑时间 + 验收结论摘要。 */
class DoneStageAssembler extends StageDetailAssembler {
  readonly stage = 'done' as const
  protected buildBody(req: RequirementRecord): DoneStageBody {
    const completedAt = timelineForStage(req, 'done')[0]?.at ?? req.updatedAt
    return {
      completedAt,
      ...(req.verification?.decision !== undefined
        ? { verificationDecision: req.verification.decision }
        : {}),
    }
  }
}

/** 归档：归档材料（目录/文档清单/合并去向/索引/说明书更新点/归档人）。 */
class ArchiveStageAssembler extends StageDetailAssembler {
  readonly stage = 'archived' as const
  protected buildBody(req: RequirementRecord): ArchiveStageBody {
    return {
      ...(req.archive !== undefined ? { archive: req.archive } : {}),
    }
  }
}

// ---------------------------------------------------------------------------
// TaskRecord → StageTaskRef / StageTaskExecution 映射
// ---------------------------------------------------------------------------

function toStageTaskRef(t: TaskRecord): StageTaskRef {
  return {
    id: t.id,
    title: t.title,
    status: t.status,
    phase: t.phase,
    side: t.side,
    dependsOn: t.dependsOn,
    ...(t.dependsSummary !== undefined ? { dependsSummary: t.dependsSummary } : {}),
    acceptance: t.acceptance,
    ...(t.cardDoc !== undefined ? { cardDoc: t.cardDoc } : {}),
    ...(t.executorHint !== undefined ? { executorHint: t.executorHint } : {}),
  }
}

function toStageTaskExecution(t: TaskRecord): StageTaskExecution {
  return {
    ...toStageTaskRef(t),
    ...(t.claimedBy !== undefined ? { claimedBy: t.claimedBy } : {}),
    executions: t.executions,
  }
}

// ---------------------------------------------------------------------------
// 装配器注册表 + 入口
// ---------------------------------------------------------------------------

const ASSEMBLERS: Readonly<Record<StageKey, StageDetailAssembler>> = {
  draft: new DraftStageAssembler(),
  brainstorming: new BrainstormStageAssembler(),
  design: new DesignStageAssembler(),
  decomposing: new DecomposeStageAssembler(),
  implementing: new ImplementStageAssembler(),
  accepting: new AcceptStageAssembler(),
  done: new DoneStageAssembler(),
  archived: new ArchiveStageAssembler(),
}

/**
 * 装配某需求的某节点详情（模板入口）。
 *
 * - 需求不存在 → code=not_found（路由层转 404）；
 * - 分类跳过的节点 → enabled:false + 空 body（不报错，UI 标灰"本分类跳过"）。
 */
export function assembleStageDetail(
  req: RequirementRecord | undefined,
  ledger: Pick<LedgerView, 'tasks'>,
  stage: StageKey,
  opts?: { designDocPolicy?: DesignDocPolicy },
): StageDetail {
  if (req === undefined) {
    throw Object.assign(new Error('需求不存在'), { code: 'not_found' })
  }
  return ASSEMBLERS[stage].assemble({ req, ledger, ...(opts?.designDocPolicy !== undefined ? { designDocPolicy: opts.designDocPolicy } : {}) })
}

/**
 * 装配某需求的全流程一览（REQ-31e11f 节点详情重设计：一次看全）。
 * 按 ALL_STAGE_KEYS 顺序装配全部节点（含分类跳过节点），供监控时间线一次渲染。
 */
export function assembleStageOverview(
  req: RequirementRecord | undefined,
  ledger: Pick<LedgerView, 'tasks'>,
  opts?: { designDocPolicy?: DesignDocPolicy },
): StageOverview {
  if (req === undefined) {
    throw Object.assign(new Error('需求不存在'), { code: 'not_found' })
  }
  const ctx: AssembleContext = { req, ledger, ...(opts?.designDocPolicy !== undefined ? { designDocPolicy: opts.designDocPolicy } : {}) }
  return {
    requirementId: req.id,
    category: req.category,
    currentStage: req.status,
    stages: ALL_STAGE_KEYS.map(stage => ASSEMBLERS[stage].assemble(ctx)),
  }
}

// re-export（路由/测试直接用本模块即可拿到全套类型与工具）
export { actorLabel }
export type { PlanTask, StageArtifact, StageDetail, StageKey, StatusEvent }

// ---------------------------------------------------------------------------
// 查询投影入口（REQ-47939a t6）——只读台账，不产生任何副作用
// ---------------------------------------------------------------------------

/** 某需求某节点详情（需求不存在 → 抛 not_found，与 assembleStageDetail 同语义）。 */
export async function queryStageDetail(
  deps: UseCaseDeps,
  requirementId: string,
  stage: StageKey,
): Promise<StageDetail> {
  const snapshot = deps.repo.snapshot()
  const req = snapshot.requirements.find(r => r.id === requirementId)
  // REQ-2d1c74：host 侧读 requirement.md front-matter 注入设计文档策略（client 不碰 fs）
  const policy = req === undefined ? undefined : await designDocPolicyOf(deps.docs, req)
  return assembleStageDetail(req, snapshot, stage, { ...(policy !== undefined ? { designDocPolicy: policy } : {}) })
}
