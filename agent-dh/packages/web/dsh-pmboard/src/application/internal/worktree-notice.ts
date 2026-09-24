/**
 * 事件型 worktree 提示词投递（REQ-260923222557-d3b0 FR-2/FR-3）。
 *
 * 为什么是独立助手：两个触发点（子任务完成、需求归档）必须走**同一条**投递与降级路径，
 * 否则一处抛错阻断转移、另一处静默——与 onStagePrompt 同语义（失败只留痕）。
 *
 * 纪律：deps.delivery 缺省（组合根未装配/测试未注入）= 不投递、返回 false；
 * 投递实现抛错也被吞掉——状态转移的成败**绝不取决于提示词能否送达**。
 *
 * @module dsh-pmboard/application/internal/worktree-notice
 */
import type { UseCaseDeps } from '../ports.js'
import {
  renderWorktreePrompt,
  type WorktreeEvent,
  type WorktreeEventContext,
} from '../../domain/prompt/worktree-events.js'

/** 投递一次事件型 worktree 提示；返回是否送达（false = 未装配/窗口为空/投递失败，均不抛）。 */
export function deliverWorktreeNotice(
  deps: UseCaseDeps,
  windowKey: string,
  event: WorktreeEvent,
  ctx: WorktreeEventContext,
): boolean {
  const port = deps.delivery
  if (port === undefined || windowKey.length === 0) return false
  try {
    return port.deliver(windowKey, { text: renderWorktreePrompt(event, ctx) }).delivered
  } catch {
    return false
  }
}
