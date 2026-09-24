/**
 * 闸门拒绝信封（REQ-260924213231-b1c4 FR-2 / I-9）——拒绝消息三要素的**唯一拼接入口**。
 *
 * 为什么独立成模块：门禁拦下文档时只给结论（「未确认」「未交」「缺 serves」）等于把排查成本
 * 整段转给 agent（REQ-260924162957-2cd3 事故里 agent 只能盲试，正是这一点）。统一信封要求每条
 * 拒绝同时说清「**为什么被拦**」与「**怎么补齐**」：
 *
 * ```
 * <what 哪份文档 / 哪一条> —— <why 报错原因>。补齐：<how 可复制的一步>
 * ```
 *
 * 三要素缺一不可；`how` 必须是**可执行锚点**（`reqboard_*` 命令 / `templates/` / `design_exempt`），
 * 不接受「请检查文档」这类无法照做的空话——tests/gate-feedback-envelope.test.ts 逐 code 锁死。
 *
 * 边界（NFR-2）：本模块**不判定**任何闸门——判定逻辑一律不动，只把 `GateFailure.message` 的拼接
 * 收口到这里；`code` 与 `gaps` 结构不变。
 *
 * @module dsh-pmboard/application/internal/gate-feedback
 */
import { fmt } from '../../domain/text/fmt.js'

/** 拒绝信封三要素 + 可选工具前缀。 */
export interface GateFeedback {
  /** what：被拦对象（哪份文档 / 哪一条编号 / 哪个章节）。 */
  what: string
  /** why：报错原因（病因）——不得只写「未确认」「未交」。 */
  why: string
  /** how：可复制的一步补齐动作；须命中 `GATE_HOW_ANCHOR`。 */
  how: string
  /** 可选前缀（工具上下文，如 `reqboard_move 未执行：`）——调用方按各自工具名传。 */
  lead?: string
}

/**
 * `how` 的可执行锚点（TC-21 的机器判据）：`reqboard_*` 命令 / 模板路径 / 豁免写法。
 * 导出为唯一事实源，实现与测试共用同一份正则，避免两边各写一套而漂移。
 */
export const GATE_HOW_ANCHOR = /reqboard_[a-z_]+|templates\/|design_exempt/

/**
 * 三要素统一拼接：`<lead><what> —— <why>。补齐：<how>`。
 *
 * `lead` 缺省为空串（不含工具名的纯信封）；`what/why/how` 缺失由 `fmt` 直接抛错（不产出
 * "undefined" 脏文案）。
 */
export function envelope(f: GateFeedback): string {
  return fmt('{lead}{what} —— {why}。补齐：{how}', {
    lead: f.lead ?? '',
    what: f.what,
    why: f.why,
    how: f.how,
  })
}
