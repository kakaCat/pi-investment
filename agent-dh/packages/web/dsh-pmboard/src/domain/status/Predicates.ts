/**
 * 状态判定（REQ-47939a t7 / INV-2）——**按意图命名**的判定函数，适配层只调用它们。
 *
 * 为什么不是"通用比较器 + 调用处传状态字面量"（首版就是这么写的，2026-09-17 改掉）：
 * 那只把**比较运算符**搬进了 domain，规则（"哪个状态算验收态"）仍写在适配层 —— 而 INV-2
 * 要的是规则单点。实测：首版在 src/http/routers/ 留下 25 处 `statusIs(x, 'accepting')` 这类写法；
 * 当时层边界门禁只查 `===` 不查 `!==`，于是**假绿**。门禁补齐后全部暴露，本模块据此改成命名判定，
 * 把"那个状态到底算不算 X"这句话只写在**这一处**。
 *
 * 约束：domain 不得 import shared/protocol（层门禁），故此处只收结构化最小投影（`{ status }`），
 * 不引用台账 Record 类型。
 *
 * @module dsh-pmboard/domain/status/Predicates
 */

type HasStatus = { status: string }

// ── 需求（RequirementStatus）───────────────────────────────────────────────

/** 是否处于验收态（人工审核中）。 */
export function isAccepting(req: HasStatus): boolean {
  return req.status === 'accepting'
}

/** 是否处于实施态。 */
export function isImplementing(req: HasStatus): boolean {
  return req.status === 'implementing'
}

/** 是否处于可提交/裁决验收的阶段（实施态或验收态）——verify 与 verdicts 的前置。 */
export function isVerifiableStage(req: HasStatus): boolean {
  return req.status === 'implementing' || req.status === 'accepting'
}

/** 是否已归档。 */
export function isArchived(req: HasStatus): boolean {
  return req.status === 'archived'
}

/** 是否已取消。 */
export function isCanceled(req: HasStatus): boolean {
  return req.status === 'canceled'
}

/** 是否未归档（含进行中与已取消——"这条需求还在册否"的宽松判定）。 */
export function isNotArchived(req: HasStatus): boolean {
  return req.status !== 'archived'
}

/** 是否为看板"活跃需求"（未归档且未取消）。 */
export function isActiveRequirement(req: HasStatus): boolean {
  return req.status !== 'archived' && req.status !== 'canceled'
}

/**
 * 是否处于**进行中**（未进入终态 done/archived/canceled）。
 * 窗口绑定判定与"会话框流程节点"选目标需求共用此判据——此前 `OPEN_STATUSES` 在
 * application/internal/window.ts 私下定义、路由层却引用了一个**不存在的名字**，
 * 结果 /session/:id/progress 运行时 ReferenceError（HTTP 500 → 流程节点不显示）。
 * 现单点于此。
 */
export function isOpenRequirement(req: HasStatus): boolean {
  return req.status !== 'done' && req.status !== 'archived' && req.status !== 'canceled'
}

/** 是否处于立项态。 */
export function isDraft(req: HasStatus): boolean {
  return req.status === 'draft'
}

// ── 任务（TaskStatus）──────────────────────────────────────────────────────

/** 是否处于开工态（已开始一次执行段）。 */
export function isInProgressTask(task: HasStatus): boolean {
  return task.status === 'in_progress'
}

/** 是否为**处理中**任务（既非 todo，也非 done/canceled）。 */
export function isUnfinishedTask(task: HasStatus): boolean {
  return task.status !== 'todo' && task.status !== 'done' && task.status !== 'canceled'
}

/** 目标状态是否为"开工"（开始一次执行段）。 */
export function startsExecutionSegment(to: string): boolean {
  return to === 'in_progress'
}

/** 目标状态是否会结束一次执行段（todo/done/canceled 都不代表"正在执行"）。 */
export function endsExecutionSegment(to: string): boolean {
  return to === 'todo' || to === 'done' || to === 'canceled'
}

/** 目标状态是否为"回退或取消"（执行段结算为 cancelled）。 */
export function isRollbackOrCancel(to: string): boolean {
  return to === 'canceled' || to === 'todo'
}

// ── 验收单项（VerificationItem.status）────────────────────────────────────

/** 单项是否通过。 */
export function isPassedItem(i: HasStatus): boolean {
  return i.status === 'passed'
}

/** 单项/状态字面量是否未通过。 */
export function isFailedItem(i: HasStatus | string): boolean {
  return (typeof i === 'string' ? i : i.status) === 'failed'
}

/** 单项是否待裁决。 */
export function isPendingItem(i: HasStatus): boolean {
  return i.status === 'pending'
}

/** 单项是否不可验收（无法按要求验，须带原因）。REQ-308b9a FR-9。 */
export function isNotVerifiableItem(i: HasStatus): boolean {
  return i.status === 'not_verifiable'
}

/** 是否为可裁决的单项状态（passed / failed / not_verifiable；pending 不是裁决结果）。 */
export function isDecidableItemStatus(status: string): boolean {
  return status === 'passed' || status === 'failed' || status === 'not_verifiable'
}

/** 待裁决项计数。 */
export function countPendingItems(items: readonly HasStatus[]): number {
  return items.filter(i => i.status === 'pending').length
}

/** 已通过项计数。 */
export function countPassedItems(items: readonly HasStatus[]): number {
  return items.filter(i => i.status === 'passed').length
}

/** 未通过项计数。 */
export function countFailedItems(items: readonly HasStatus[]): number {
  return items.filter(i => i.status === 'failed').length
}

/** 不可验收项计数。 */
export function countNotVerifiableItems(items: readonly HasStatus[]): number {
  return items.filter(i => i.status === 'not_verifiable').length
}

/** 是否全部项都已通过（"验收全过"这条规则的唯一实现）。 */
export function isEveryItemPassed(items: readonly HasStatus[]): boolean {
  return items.every(i => i.status === 'passed')
}

/** 是否全部项已裁决（无 pending）——REQ-308b9a FR-9 的放行判据。 */
export function isFullyDecidedItems(items: readonly HasStatus[]): boolean {
  return items.every(i => i.status !== 'pending')
}

// ── 任务计数（看板投影用；"done 才算完成"这条规则留在 domain）──────────────

/** 已完成任务计数。 */
export function countDoneTasks(tasks: readonly HasStatus[]): number {
  return tasks.filter(t => t.status === 'done').length
}

/** 处理中（未完成）任务计数。 */
export function countUnfinishedTasks(tasks: readonly HasStatus[]): number {
  return tasks.filter(isUnfinishedTask).length
}

// ── 产物（登记阶段）───────────────────────────────────────────────────────

/** 产物是否登记在验收阶段。 */
export function isAcceptingStage(stage: string): boolean {
  return stage === 'accepting'
}
