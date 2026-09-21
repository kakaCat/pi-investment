/**
 * 验收单逐项裁决（REQ-2e9473 W6 补充）：路由（看板勾选）与会话工具（弹框答复）
 * 共用的**单一实现**——避免两条通道逻辑漂移。
 *
 * 语义（REQ-a8d582 FR-2 起）：逐项 passed/failed（不通过必填意见）→ **只写验收单**。
 *
 * 为什么不再自动打回：以前"有一项不通过就立刻打回 implementing + 批量建返工任务"，等于
 * 系统替人做了"退回"这个决定，还顺手让看板的「验收通过」按钮消失。现在两条状态迁移都由
 * 人的动作触发——退回走 handleVerifyDecision(pass=false)（在那里建返工卡，见
 * materializeReworkFromSheet），通过走 handleVerifyDecision(pass=true)。
 *
 * REQ-47939a t4：**裁决规则**（意见必填 / 项状态更新 / 返工规格）已迁至
 * domain/workflow/AcceptanceSheetSpec.ts；本文件只做台账校验（需求/状态/版本）与
 * 落地（生成任务 id、写状态事件与评论）——规则单点，副作用单点。
 *
 * @module dsh-pmboard/host/verdicts
 */
import {
  asScope, newTaskId, recordStatus,
  type ActorRef, type ReqboardLedger, type RequirementRecord, type TaskRecord, type TokenSnapshot,
} from '../../shared/protocol.js'
import { hasErrorCode, REQBOARD_ERROR_CODES } from '../../domain/errors.js'
import {
  applyVerdicts as applySheetVerdicts,
  reworkSpecsFor,
  type ReworkTaskSpec,
} from '../../domain/workflow/AcceptanceSheetSpec.js'
import { transitionRequirement } from './token-usage.js'
import { REWORK_REQ_STATUS } from '../../domain/requirement/RequirementStatus.js'

export interface VerdictInput {
  itemId: string
  status: 'passed' | 'failed'
  opinion?: string
}

export interface ApplyVerdictsResult {
  requirement: RequirementRecord
  reworkTasks: TaskRecord[]
  pending: number
  passed: number
  failed: number
}

export class VerdictError extends Error {
  readonly code: string
  constructor(message: string, code: string) {
    super(message)
    this.code = code
  }
}

/** 返工规格 → 落库任务记录（id 冲突重试；状态事件与时间戳由 host 负责）。 */
function materializeReworkTask(
  ledger: ReqboardLedger,
  reqId: string,
  spec: ReworkTaskSpec,
  actor: ActorRef,
  nowTs: number,
): TaskRecord {
  let tid = newTaskId()
  for (let g = 0; g < 50 && ledger.tasks.some(t => t.id === tid); g++) tid = newTaskId()
  const task: TaskRecord = {
    id: tid,
    requirementId: reqId,
    title: spec.title,
    description: spec.description,
    phase: spec.phase as TaskRecord['phase'],
    side: spec.side as TaskRecord['side'],
    dependsOn: [],
    scope: (spec.scope ?? asScope({})) as TaskRecord['scope'],
    acceptance: spec.acceptance,
    implementation: spec.implementation,
    context: spec.context,
    status: 'todo',
    blocked: false,
    executions: [],
    comments: [],
    version: 1,
    createdAt: nowTs,
    updatedAt: nowTs,
    createdBy: actor,
    updatedBy: actor,
  }
  recordStatus(task, 'todo', nowTs, actor, '验收不通过 → 自动生成返工任务（W6）')
  ledger.tasks.push(task)
  return task
}

/**
 * 在 mutate 内应用逐项裁决（就地修改 ledger）。
 * @param actor 裁决人（看板=human / 会话弹框=human+sessionId）
 * @param commentId 评论 id 生成器
 */
export function applyVerdicts(
  ledger: ReqboardLedger,
  reqId: string,
  version: number,
  verdicts: readonly VerdictInput[],
  actor: ActorRef,
  nowTs: number,
  commentId: () => string,
  /** token 快照（REQ-308b9a FR-8：自动回退要结算离开 accepting 节点的快照）。 */
  snap?: TokenSnapshot,
): ApplyVerdictsResult {
  const r = ledger.requirements.find(x => x.id === reqId)
  if (r === undefined) throw new VerdictError('需求 ' + reqId + ' 不存在', 'not_found')
  if (r.status !== 'accepting' && r.status !== 'implementing') {
    throw new VerdictError('需求 ' + reqId + ' 当前处于 ' + r.status + '，不在验收/返工态（先提交验收单）', 'bad_status')
  }
  const v = r.verification
  if (v === undefined || v.sheet === undefined) {
    throw new VerdictError('需求 ' + reqId + ' 还没有验收单（先 reqboard_verify_submit）', 'no_sheet')
  }
  const sheet = v.sheet
  if (sheet.version !== version) {
    throw new VerdictError('验收单版本不匹配：当前 v' + sheet.version + '，收到 v' + version + '（防并发错版）', 'version_mismatch')
  }
  // 项存在性预校验：保持既有传输码 item_not_found（域内 invalid_input 只留给"不通过缺意见"）。
  for (const verdict of verdicts) {
    if (!sheet.items.some(i => i.id === verdict.itemId)) {
      throw new VerdictError('验收项 ' + verdict.itemId + ' 不存在', 'item_not_found')
    }
  }
  let applied: ReturnType<typeof applySheetVerdicts>
  try {
    applied = applySheetVerdicts(sheet, verdicts, actor, nowTs, ledger.tasks)
  } catch (err) {
    if (hasErrorCode(err, REQBOARD_ERROR_CODES.invalidInput)) {
      // 保持既有传输码 opinion_required（工具层据此回执）；消息文案不变。
      throw new VerdictError((err as Error).message, 'opinion_required')
    }
    throw err
  }
  const pending = applied.pending
  // REQ-308b9a FR-8（**推翻 REQ-a8d582 FR-2**，用户订正①）：
  // 出现 failed → **同笔 mutate 内**自动回退实施 + 物化返工卡；不再等人点「退回返工」。
  // 原子性（AC-8.3）：物化或状态迁移抛错 → 整笔 mutate 回滚，不出现"状态改了卡没建"。
  const reworkTasks: TaskRecord[] = applied.failed > 0
    ? materializeReworkFromSheet(ledger, reqId, actor, nowTs)
    : []
  if (applied.failed > 0 && r.status !== REWORK_REQ_STATUS) {
    transitionRequirement(r, REWORK_REQ_STATUS, {
      at: nowTs,
      actor,
      reason: '验收不通过（' + applied.failed + ' 项）→ 自动回退实施并生成 ' + reworkTasks.length + ' 张返工卡（REQ-308b9a FR-8）',
      ...(snap !== undefined ? { snap } : {}),
    })
  }
  r.version += 1
  r.updatedAt = nowTs
  r.updatedBy = actor
  r.comments.push({
    id: commentId(),
    body: '[验收单] v' + sheet.version + ' 逐项裁决：通过 ' + applied.passed + ' 项，不通过 ' + applied.failed + ' 项，'
      + '不可验收 ' + applied.notVerifiable + ' 项，待验 ' + pending + ' 项'
      + (applied.failed > 0
          ? '（已自动回退实施并生成 ' + reworkTasks.length + ' 张返工任务）'
          : (pending === 0 ? '（全部已裁决 → 可点「验收通过」归档）' : '（挂起，稍后从断点续验）')),
    createdAt: nowTs,
    createdBy: actor,
  })
  return {
    requirement: r,
    reworkTasks,
    pending,
    passed: applied.passed,
    failed: applied.failed,
  }
}

/**
 * 「退回返工」路径：按当前验收单里**已判不通过**的项生成返工任务（REQ-a8d582 FR-2）。
 *
 * 为什么搬到这里：裁决本身不再改状态（见 applyVerdicts），返工卡必须跟着人的"退回"动作走——
 * 否则会重新出现"人还没决定、系统已经建了一堆卡"。规格仍单点在 domain/workflow/AcceptanceSheetSpec。
 */
export function materializeReworkFromSheet(
  ledger: ReqboardLedger,
  reqId: string,
  actor: ActorRef,
  nowTs: number,
): TaskRecord[] {
  const r = ledger.requirements.find(x => x.id === reqId)
  const sheet = r?.verification?.sheet
  if (r === undefined || sheet === undefined) return []
  return reworkSpecsFor(sheet, ledger.tasks).map(spec => materializeReworkTask(ledger, r.id, spec, actor, nowTs))
}
