/**
 * Reqboard 需求状态自动推进（rollup）—— 派生状态的唯一实现处。
 *
 * 设计边界（RFC 014 §3 设计决策一：派生 + 闸门混合）：
 *  - **派生**：由台账内客观事实推导、不需要人点头的转移 → 本模块以 system 身份推进；
 *  - **闸门**：评审通过 / 拆分确认 / 人工验收 / 归档 → HUMAN_ONLY_REQ_TRANSITIONS
 *    代码级仅人可操作，本模块**不可能**越过（assertReqTransition 会抛 human_gate）。
 *
 * 两条自动推进规则：
 *  R1 接手推进（draft → reviewing）：需求已被绑定窗口接手并继续推进工作
 *     （hook 观察到该窗口出现直接人类消息）→ 立项完成，进入评审。触发在
 *     rollup-hook.ts（唯一信号源是会话事件，不在本模块）。
 *  R2 实施完成（implementing → accepting）：需求处于实施态、且其全部未取消任务
 *     均为 done（至少 1 个任务）→ 自动进入验收，等人做功能验收（人工闸门）。
 *
 * 为什么放在这里而不是各路由里散写：状态推导规则必须单点可测——规则增长时只改
 * 本文件 + 补 rollup.test.ts，路由只负责在 mutate 内调用 applyTaskRollup。
 *
 * @module dsh-pmboard/host/rollup
 */

import {
  assertReqTransition,
  type ReqboardLedger,
  type RequirementRecord,
  type RequirementStatus,
} from '../shared/protocol.js'

export interface RollupContext {
  now: number
  /** 评论 id 生成器（推进留痕用）。 */
  commentId: () => string
}

/** 需求的未取消任务（canceled 不参与完成度判定）。 */
function activeTasksOf(ledger: ReqboardLedger, reqId: string) {
  return ledger.tasks.filter(t => t.requirementId === reqId && t.status !== 'canceled')
}

/** 就地推进一条需求状态并留痕（调用方须已确认转移合法）。 */
function advance(
  req: RequirementRecord,
  to: RequirementStatus,
  reason: string,
  ctx: RollupContext,
): RequirementRecord {
  const from = req.status
  assertReqTransition(from, to, 'system')
  req.status = to
  req.version += 1
  req.updatedAt = ctx.now
  req.updatedBy = { kind: 'system' }
  req.comments.push({
    id: ctx.commentId(),
    body: `[自动推进] ${from} → ${to}：${reason}`,
    createdAt: ctx.now,
    createdBy: { kind: 'system' },
  })
  return req
}

/**
 * R1 接手推进：需求处于 draft 且已被某窗口接手工作 → reviewing。
 * 返回被推进的需求（未推进 → undefined）。窗口绑定校验由调用方负责
 * （rollup-hook 只对本窗口 sourceSessionId 匹配的需求调用）。
 */
export function applyPickupAdvance(
  ledger: ReqboardLedger,
  reqId: string,
  ctx: RollupContext,
): RequirementRecord | undefined {
  const req = ledger.requirements.find(r => r.id === reqId)
  if (req === undefined || req.status !== 'draft') return undefined
  return advance(req, 'reviewing', '需求已被绑定窗口接手并继续推进工作，自动进入评审（人工确认方案后进入拆分）', ctx)
}

/**
 * R0 启动对账：把历史上「已挂窗口但仍停在 draft」的需求按同一套规则补齐推进。
 * 用途：插件启动时跑一次（对齐 RFC 014 §7「启动对账」），让升级前积压的需求立刻
 * 反映真实状态，而不是等人逐条点。只动 draft + 已挂窗口（sourceSessionId 或
 * triage 锚点）的需求——人工建卡、且从未被窗口接手的仍留在立项。
 */
export function applyPickupReconcile(ledger: ReqboardLedger, ctx: RollupContext): RequirementRecord[] {
  const bound = new Set<string>()
  for (const r of ledger.requirements) {
    if (typeof r.sourceSessionId === 'string' && r.sourceSessionId.length > 0) bound.add(r.id)
  }
  for (const t of ledger.triages) {
    const anchors: unknown[] = [t.resultRequirementId, ...(Array.isArray(t.resultRequirementIds) ? t.resultRequirementIds : [])]
    for (const a of anchors) if (typeof a === 'string' && a.length > 0) bound.add(a)
  }
  const advanced: RequirementRecord[] = []
  for (const req of ledger.requirements) {
    if (req.status !== 'draft' || !bound.has(req.id)) continue
    advanced.push(
      advance(req, 'reviewing', '启动对账：该需求已由窗口立项并接手，自动提交评审（后续由窗口按里程碑自行推进）', ctx),
    )
  }
  return advanced
}

/**
 * 任务驱动的派生推进（R2/R3/R4）—— 让需求跟着任务事实自己走，不需要人点中间步骤：
 *  R3 reviewing + 已有任务（拆分结果落库）        → decomposing
 *  R4 decomposing + 有任务已进入执行（非 todo）    → implementing
 *  R2 implementing + 全部未取消任务 done（≥1 个）  → accepting
 * 一次调用内循环至稳定（上限 3 步/需求），使「拆分+全部完成」这类跨越在一次 rollup 内收敛。
 * 返回被推进的需求列表（含同一需求的多步推进记录）。
 */
export function applyTaskRollup(
  ledger: ReqboardLedger,
  ctx: RollupContext,
  onlyReqId?: string,
): RequirementRecord[] {
  const advanced: RequirementRecord[] = []
  for (const req of ledger.requirements) {
    if (onlyReqId !== undefined && req.id !== onlyReqId) continue
    if (req.status !== 'reviewing' && req.status !== 'decomposing' && req.status !== 'implementing') continue
    const before = req.status
    for (let step = 0; step < 3; step++) {
      const tasks = activeTasksOf(ledger, req.id)
      if (tasks.length === 0) break
      if (req.status === 'reviewing') {
        // 拆分结果落库 = 方案已过、进入拆分（闸门已按用户裁定放开为派生推进）
        advance(req, 'decomposing', `已落库 ${tasks.length} 个任务，自动进入拆分`, ctx)
        continue
      }
      if (req.status === 'decomposing') {
        if (!tasks.some(t => t.status !== 'todo')) break
        advance(req, 'implementing', '任务已开始执行，自动进入实施', ctx)
        continue
      }
      // implementing
      if (!tasks.every(t => t.status === 'done')) break
      advance(req, 'accepting', `全部 ${tasks.length} 个实施任务已完成，自动进入验收`, ctx)
      break
    }
    // 同一需求多步推进只上报一次（对象已是终态；逐步留痕在 comments 里）
    if (req.status !== before) advanced.push(req)
  }
  return advanced
}
