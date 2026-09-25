/**
 * reqboard_run_status 工具提示词
 */

export const RUN_STATUS_PROMPT = `查询实施链运行状态（只读）：传 requirement_id 或 run_id 查询当前运行快照。

适用于：
- 投递后想知道「跑到哪了」（调用 reqboard_task_run 后用 run_id 查询）
- 检查需求是否有 active run（用 requirement_id 查询）
- 诊断链是否卡住（查看 jobStatus/pauseReason）

返回体：
- runId: 运行 ID（无 active run 时为 null）
- stepIndex: 当前步骤索引
- currentSubtaskId: 当前正在执行的子卡 ID
- nextReady: 下一批 ready 的任务 ID 列表
- jobStatus: Job 状态（running/completed/failed/not_found）
- pauseReason: 暂停原因（如果已暂停）
- autoRun: 是否自动运行

无 active run 时返回 {success:true, snapshot:{status:'terminated', reason:...}}，不报错。`;
