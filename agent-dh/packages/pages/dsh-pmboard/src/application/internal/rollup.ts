/**
 * Reqboard 需求状态自动推进（rollup）—— 执行侧（REQ-47939a t3）。
 *
 * **决策**（推进哪条、为什么）已迁至 domain/workflow/RollupSpec.ts（纯函数，可冻入参单测）；
 * 本文件只负责把决策落到台账：写状态、写时间线、写评论。规则仍单点（RollupSpec），
 * 副作用仍单点（本文件的 advance）。
 *
 * 设计边界（RFC 014 §3 设计决策一：派生 + 闸门混合）：
 *  - **派生**：由台账内客观事实推导、不需要人点头的转移 → 以 system 身份推进；
 *  - **闸门**：需求文档确认 / 计划批准 / 人工验收 / 归档 → HUMAN_ONLY_REQ_TRANSITIONS
 *    代码级仅人可操作，本文件**不可能**越过（advance 里 assertReqTransition 会抛 human_gate）。
 *
 * 为什么放在这里而不是各路由里散写：状态推导规则必须单点可测——规则增长时只改
 * RollupSpec + 补 rollup.test.ts，路由只负责在 mutate 内调用 applyTaskRollup。
 *
 * @module dsh-pmboard/host/rollup
 */

import {
  assertReqTransition,
  type ReqboardLedger,
  type RequirementRecord,
  type RequirementStatus,
  type TokenSnapshot,
} from '../../shared/protocol.js'
import { transitionRequirement } from './token-usage.js'
import {
  planPickupAdvance,
  planPickupReconcile,
  planRollup,
  type RollupMove,
  type RollupView,
} from '../../domain/workflow/RollupSpec.js'

export interface RollupContext {
  now: number
  /** 评论 id 生成器（推进留痕用）。 */
  commentId: () => string
  /** 快照提供者（可选；REQ-b545fe t4）。use-case 调用方传快照函数，启动对账不传。 */
  snapshot?: (req: RequirementRecord) => TokenSnapshot | undefined
}

/** 台账 → 决策所需的最小只读投影（RollupSpec 不依赖完整记录类型）。 */
function viewOf(ledger: ReqboardLedger): RollupView {
  return { requirements: ledger.requirements, tasks: ledger.tasks, triages: ledger.triages }
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
  // REQ-b545fe t4：使用唯一迁移助手（快照提供者可选）
  transitionRequirement(req, to, {
    at: ctx.now,
    actor: { kind: 'system' },
    reason,
    snap: ctx.snapshot?.(req),
  })
  req.comments.push({
    id: ctx.commentId(),
    body: `[自动推进] ${from} → ${to}：${reason}`,
    createdAt: ctx.now,
    createdBy: { kind: 'system' },
  })
  return req
}

/**
 * 执行一批推进决策。逐条校验"当前状态仍是决策时的 from"（防并发错位），
 * 同一需求多步推进只上报一次（避免 change 载荷重复）。
 */
function applyMoves(ledger: ReqboardLedger, moves: readonly RollupMove[], ctx: RollupContext): RequirementRecord[] {
  const advanced: RequirementRecord[] = []
  const reported = new Set<string>()
  for (const move of moves) {
    const req = ledger.requirements.find(r => r.id === move.reqId)
    if (req === undefined || req.status !== move.from) continue
    advance(req, move.to, move.reason, ctx)
    if (!reported.has(req.id)) {
      reported.add(req.id)
      advanced.push(req)
    }
  }
  return advanced
}

/**
 * R1 接手推进：需求处于 draft 且已被某窗口接手工作 → brainstorming。
 * 返回被推进的需求（未推进 → undefined）。窗口绑定校验由调用方负责
 * （rollup-hook 只对本窗口 sourceSessionId 匹配的需求调用）。
 */
export function applyPickupAdvance(
  ledger: ReqboardLedger,
  reqId: string,
  ctx: RollupContext,
): RequirementRecord | undefined {
  const move = planPickupAdvance(viewOf(ledger), reqId)
  if (move === undefined) return undefined
  const req = ledger.requirements.find(r => r.id === move.reqId)
  if (req === undefined || req.status !== move.from) return undefined
  return advance(req, move.to, move.reason, ctx)
}

/**
 * R0 启动对账：把历史上「已挂窗口但仍停在 draft」的需求按同一套规则补齐推进。
 * 用途：插件启动时跑一次（对齐 RFC 014 §7「启动对账」），让升级前积压的需求立刻
 * 反映真实状态，而不是等人逐条点。只动 draft + 已挂窗口（sourceSessionId 或
 * triage 锚点）的需求——人工建卡、且从未被窗口接手的仍留在立项。
 */
export function applyPickupReconcile(ledger: ReqboardLedger, ctx: RollupContext): RequirementRecord[] {
  return applyMoves(ledger, planPickupReconcile(viewOf(ledger)), ctx)
}

/**
 * 任务驱动的派生推进（R2/R3）—— 让需求跟着任务事实自己走，不需要人点中间步骤：
 *  R3 design + 已有任务（已批准的计划落库）        → decomposing
 *  R2 implementing + 全部未取消任务 done（≥1 个）  → accepting
 * 2026-09-14 五门裁定（REQ-31e11f）：decomposing>implementing 已入人工确认门
 * （拆分清单须人确认），R4 自动推进移除——需求停在拆分态等人确认，不再随任务开工自动推进。
 * 一次调用内循环至稳定（上限 3 步/需求），使「拆分+全部完成」这类跨越在一次 rollup 内收敛。
 * 返回被推进的需求列表（同一需求只上报一次；逐步留痕在 comments 里）。
 */
export function applyTaskRollup(
  ledger: ReqboardLedger,
  ctx: RollupContext,
  onlyReqId?: string,
): RequirementRecord[] {
  return applyMoves(ledger, planRollup(viewOf(ledger), onlyReqId), ctx)
}
