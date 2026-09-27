/**
 * 挂起确认的判定口径**单点**（REQ-260927123256-196b · serves: FR-2 / FR-4）——停手守卫与回执
 * 共用同一份「台账是否已落章」谓词，杜绝两处口径漂移。
 *
 * 为什么要抽出来：`targetConfirmedInLedger` 原先私有在 ConfirmReceipt.ts（台账事实：target=plan 看
 * 计划批准章；target=artifact 看该 kind 全部产物是否成组落章）。停手守卫升级为「未作答 **且** 台账
 * 未落章才拦」后，同一判定要被回执与守卫同时使用——留两份拷贝必然漂移（判定口径只留一处）。
 *
 * 语义：
 *  - `livePendingConfirm` = 本窗口**仍然有意义**的未作答确认：已 settle / 已过期由注册表
 *    `pendingForWindow` 过滤（过期基准 (interruptedAt ?? createdAt) + ttl），台账已落章的陈旧记录
 *    在这里再被滤掉——人已通过看板/证据通道作答时，守卫必须放行（否则死锁）；
 *  - 台账查不到该需求时**保守留挂**（无法证明已落章 → 不静默释放守卫）。
 *
 * @module dsh-pmboard/application/internal/pending-guard
 */
import type { UseCaseDeps } from '../ports.js'
import type { PendingConfirmation, RequirementRecord } from '../../shared/protocol.js'

/**
 * 被停手守卫拦下的写路径名单（design/interfaces.md I-2 `pending_confirms[].blocked_tools`）。
 *
 * 挂载点与 design I-3 一致：`reqboard_submit` / `reqboard_decompose` / `reqboard_move` /
 * `reqboard_task_move`。`reqboard_status` 与 `reqboard_confirm_receipt` **刻意不在列**——
 * 否则人无法解除挂起。
 */
export const PENDING_CONFIRM_BLOCKED_TOOLS: readonly string[] = [
  'reqboard_submit',
  'reqboard_decompose',
  'reqboard_move',
  'reqboard_task_move',
]

/**
 * 一句话恢复指引（design/interfaces.md I-2 `pending_confirms[].recovery`，文案契约 FR-4）：
 * 必含「收到作答前不得产出下游产物」与两条可用路径（取回执 / 看板确认）。
 */
export const PENDING_CONFIRM_RECOVERY =
  '收到作答前不得产出下游产物。解除挂起：① 调 reqboard_confirm_receipt(ticket="pc-…") 取回执；'
  + '② 到项目看板点确认按钮。'

/**
 * 台账事实：target=plan 看计划批准章；target=artifact 看该 kind 全部产物是否成组落章。
 * （逐字提取自 ConfirmReceipt.ts:76-80——判定口径只留这一处。）
 */
export function targetConfirmedInLedger(req: RequirementRecord, rec: PendingConfirmation): boolean {
  if (rec.target === 'plan') return req.plan?.approvedAt !== undefined
  const arts = (req.artifacts ?? []).filter(a => a.kind === rec.kind)
  return arts.length > 0 && arts.every(a => a.confirmedAt !== undefined)
}

/**
 * 本窗口**仍然有意义**的挂起确认（没有则 undefined）：注册表的 `pendingForWindow` 已滤掉
 * 已 settle / 已过期 / 跨窗口；这里只再滤「台账已落章」的陈旧记录。
 *
 * 台账查不到目标需求 → 无法证明已落章，保守返回该记录（守卫继续拦，不静默释放）。
 */
export function livePendingConfirm(deps: UseCaseDeps, windowKey: string): PendingConfirmation | undefined {
  const pending = deps.pendingConfirms?.pendingForWindow(windowKey)
  if (pending === undefined) return undefined
  const req = deps.repo.snapshot().requirements.find(r => r.id === pending.requirementId)
  if (req === undefined) return pending
  if (targetConfirmedInLedger(req, pending)) return undefined
  return pending
}

/**
 * 停手守卫的拒绝文案（三要素：what=ticket+需求 id / why=不得产出下游产物 / how=三条恢复路径）。
 * 供 `assertNoPendingConfirm` 单点取用，避免文案与 `PENDING_CONFIRM_RECOVERY` 漂移。
 */
export function pendingConfirmRejectMessage(p: PendingConfirmation): string {
  return '本窗口有一个**待作答**的确认门（ticket=' + p.ticket + '，需求 ' + p.requirementId + '）——'
    + '收到作答前不得产出下游产物。解除挂起：① 调 reqboard_confirm_receipt(ticket="' + p.ticket + '") 取回执；'
    + '② 或在项目看板点确认按钮；③ 或重新发起 reqboard_ask_confirm 覆盖旧记录。'
}
