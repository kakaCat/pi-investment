/**
 * 需求自动推进决策（rollup 规约，REQ-47939a t3）——派生状态的唯一实现处。
 *
 * 从 host/rollup.ts 抽出**纯决策**部分：给定只读台账视图 → 返回该推进哪些需求（决策列表），
 * 不碰台账、不发通知、不留痕。副作用（写状态/写时间线/写评论）留在 host rollup.ts 的
 * apply* 函数里执行。拆分理由：规则要能独立单测（INV-5），且"决策"必须是可冻结入参的纯函数。
 *
 * 设计边界（RFC 014 §3 设计决策一：派生 + 闸门混合）：
 *  - **派生**：由台账内客观事实推导、不需要人点头的转移 → 本模块以 system 身份建议推进，
 *    实际执行时 assertReqTransition 会校验 system 白名单；
 *  - **闸门**：需求文档确认 / 计划批准 / 人工验收 / 归档 → HUMAN_ONLY_REQ_TRANSITIONS
 *    代码级仅人可操作，本模块**不可能**越过（它只会产出白名单内的 R1/R2/R3）。
 *
 * 两条自动推进规则：
 *  R1 接手推进（draft → brainstorming）：需求已被绑定窗口接手并继续推进工作
 *     （hook 观察到该窗口出现直接人类消息）→ 立项完成，进入需求分析。触发在
 *     rollup-hook（唯一信号源是会话事件，不在本模块）。
 *  R2 实施完成（implementing → accepting）：需求处于实施态、且其全部未取消任务
 *     均为 done（至少 1 个任务）→ 自动进入验收，等人做功能验收（人工闸门）。
 *
 * 为什么集中在此而不是各路由里散写：状态推导规则必须单点可测——规则增长时只改
 * 本文件 + 补 rollup.test.ts，路由只负责在 mutate 内调用 applyTaskRollup。
 *
 * 纯函数（零 I/O、零副作用、不碰时间与随机数）：入参 Object.freeze 后调用不抛。
 */

import { fmt } from '../text/fmt.js'
import type { RequirementStatus } from '../requirement/RequirementStatus.js'
import type { TaskStatus } from '../task/TaskStatus.js'

/** 派生规则编号（R1 接手 / R2 实施完成 / R3 计划落库进拆分）。 */
export type RollupRule = 'R1' | 'R2' | 'R3'

/** 一条推进决策（只描述"从哪到哪、为什么"，不执行）。 */
export interface RollupMove {
  reqId: string
  from: RequirementStatus
  to: RequirementStatus
  rule: RollupRule
  /** 推进理由（写入评论留痕，文案与搬迁前逐字一致）。 */
  reason: string
}

/** 决策所需的最小只读投影（domain 不依赖 shared 的完整记录类型）。 */
export interface RollupRequirementLike {
  id: string
  status: RequirementStatus
  sourceSessionId?: string
}
export interface RollupTaskLike {
  requirementId: string
  status: TaskStatus
}
export interface RollupTriageLike {
  resultRequirementId?: string
  resultRequirementIds?: readonly string[]
}
export interface RollupView {
  readonly requirements: readonly RollupRequirementLike[]
  readonly tasks: readonly RollupTaskLike[]
  readonly triages: readonly RollupTriageLike[]
}

/** 需求的未取消任务（canceled 不参与完成度判定）。 */
function activeTasksOf(view: RollupView, reqId: string): RollupTaskLike[] {
  return view.tasks.filter(t => t.requirementId === reqId && t.status !== 'canceled')
}

/**
 * R1 接手推进：需求处于 draft 且已被某窗口接手工作 → brainstorming。
 * 返回推进决策（未推进 → undefined）。窗口绑定校验由调用方负责
 * （rollup-hook 只对本窗口 sourceSessionId 匹配的需求调用）。
 */
export function planPickupAdvance(view: RollupView, reqId: string): RollupMove | undefined {
  const req = view.requirements.find(r => r.id === reqId)
  if (req === undefined || req.status !== 'draft') return undefined
  return {
    reqId,
    from: 'draft',
    to: 'brainstorming',
    rule: 'R1',
    reason: '需求已被绑定窗口接手并继续推进工作，自动进入需求分析（探边界 → 设计 → 待人批准）',
  }
}

/**
 * R0 启动对账：把历史上「已挂窗口但仍停在 draft」的需求按同一套规则补齐推进。
 * 用途：插件启动时跑一次（对齐 RFC 014 §7「启动对账」），让升级前积压的需求立刻
 * 反映真实状态，而不是等人逐条点。只动 draft + 已挂窗口（sourceSessionId 或
 * triage 锚点）的需求——人工建卡、且从未被窗口接手的仍留在立项。
 */
export function planPickupReconcile(view: RollupView): RollupMove[] {
  const bound = new Set<string>()
  for (const r of view.requirements) {
    if (typeof r.sourceSessionId === 'string' && r.sourceSessionId.length > 0) bound.add(r.id)
  }
  for (const t of view.triages) {
    const anchors: unknown[] = [t.resultRequirementId, ...(Array.isArray(t.resultRequirementIds) ? t.resultRequirementIds : [])]
    for (const a of anchors) if (typeof a === 'string' && a.length > 0) bound.add(a)
  }
  const moves: RollupMove[] = []
  for (const req of view.requirements) {
    if (req.status !== 'draft' || !bound.has(req.id)) continue
    moves.push({
      reqId: req.id,
      from: 'draft',
      to: 'brainstorming',
      rule: 'R1',
      reason: '启动对账：该需求已由窗口立项并接手，自动进入需求分析（后续由窗口按里程碑自行推进）',
    })
  }
  return moves
}

/**
 * 任务驱动的派生推进（R2/R3）—— 让需求跟着任务事实自己走，不需要人点中间步骤：
 *  R3 design + 已有任务（已批准的计划落库）        → decomposing
 *  R2 implementing + 全部未取消任务 done（≥1 个）  → accepting
 * 2026-09-14 五门裁定（REQ-31e11f）：decomposing>implementing 已入人工确认门
 * （拆分清单须人确认），R4 自动推进移除——需求停在拆分态等人确认，不再随任务开工自动推进。
 * 一次调用内循环至稳定（上限 3 步/需求），使「拆分+全部完成」这类跨越在一次 rollup 内收敛
 * （当前语义下每条需求最多产出 1 步：design 推进后即停 decomposing；见上方断点）。
 * 返回推进决策列表（按台账需求顺序）。
 */
export function planRollup(view: RollupView, onlyReqId?: string): RollupMove[] {
  const moves: RollupMove[] = []
  for (const req of view.requirements) {
    if (onlyReqId !== undefined && req.id !== onlyReqId) continue
    if (req.status !== 'design' && req.status !== 'decomposing' && req.status !== 'implementing') continue
    for (let step = 0; step < 3; step++) {
      const tasks = activeTasksOf(view, req.id)
      if (tasks.length === 0) break
      if (req.status === 'design') {
        // 任务能落库 ⇔ 计划已获人批准（decompose 的代码级前置条件）→ 进入拆分态
        moves.push({
          reqId: req.id,
          from: 'design',
          to: 'decomposing',
          rule: 'R3',
          reason: fmt('已按批准的计划落库 {count} 个任务，自动进入拆分', { count: tasks.length }),
        })
        // 与搬迁前的循环等价：推进后下一轮命中 decomposing → break（decomposing>implementing 是人工门）
        break
      }
      if (req.status === 'decomposing') {
        // 2026-09-14 五门裁定：decomposing>implementing 是人工确认门（拆分清单须人确认），
        // 不再自动推进。需求停在拆分态，等人确认拆分清单后由看板/reqboard_move 推进。
        break
      }
      // implementing
      if (!tasks.every(t => t.status === 'done')) break
      moves.push({
        reqId: req.id,
        from: 'implementing',
        to: 'accepting',
        rule: 'R2',
        reason: fmt('全部 {count} 个实施任务已完成，自动进入验收', { count: tasks.length }),
      })
      break
    }
  }
  return moves
}
