/**
 * pm 弹框**来源标志**（REQ-260924213231-b1c4 T-11 / FR-8 · I-7 / TC-14）——唯一注入点。
 *
 * 解决什么问题：同一个窗口里可能先后出现两种提问——pm 插件发起的门确认弹框（`reqboard_ask_confirm`
 * / `reqboard_accept_sheet` / 立项四问 / 失败处置），与宿主原生的 `ask_user_question`。两者在 UI 上
 * 长得一样，用户分不清「这条该不该按 pm 的流程答」。
 *
 * 为什么是**代码注入**而不是让 agent 自己在文案里写：正文 emoji 由 agent 手写，可以漏写、也可以
 * 被冒充；而 header 前缀由 pm 侧构造弹框时机械加上——**不读正文即可分辨，且 agent 伪造不了**
 * （见 design/use-cases.md UC-5 异常流、interfaces.md I-7）。
 *
 * 边界：只改 `AskQuestion.header` 文本，不动宿主 schema、不动 question 正文。
 *
 * @module dsh-pmboard/domain/text/pm-badge
 */

/** 来源标志固定前缀。**唯一出现处**——任何别处硬写这个字面量都是漂移。 */
export const PM_BADGE_PREFIX = '📋 PM · '

/**
 * 给 pm 侧构造的弹框 header 统一加上来源标志：`pmHeader('确认')` → `'📋 PM · 确认'`。
 *
 * 只加前缀，不做幂等去重：同一 header 重复调用会得到两个前缀——这是刻意的，重复注入
 * 属于调用方 bug，响亮可见胜过静默吞掉（对齐 fmt 缺变量直接抛错的口径）。
 */
export function pmHeader(text: string): string {
  return PM_BADGE_PREFIX + text
}
