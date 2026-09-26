/**
 * reqboard_clear_pause 工具提示词（REQ-260925212722-96e7）
 */
export const CLEAR_PAUSE_PROMPT = `清除 Dive 模式的 armed 状态，解除自动流程锁定，允许手动操作需求和任务。

适用于：Dive 模式 armed 时，需要手动干预（拆分、推进状态、推进任务）的场景。

调用后：
- dive.activation 设置为 'disarmed'
- dive.pausedReason 清除
- 可以手动调用 reqboard_decompose / reqboard_move / reqboard_task_move

参数：
- requirement_id（可选）：需求 id，不传则使用本窗口绑定的需求`
