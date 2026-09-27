/**
 * reqboard_run_status 工具提示词
 */

export const RUN_STATUS_PROMPT = `查询实施链运行状态（只读）：传 requirement_id 或 run_id 查询当前运行快照。

适用于：
- 投递后想知道「跑到哪了」（调用 reqboard_task_run 后用 run_id 查询）
- 检查需求是否有 active run（用 requirement_id 查询）
- 诊断链是否卡住（查看 jobStatus/pauseReason）

返回体：
- runId: 运行 ID；**无 active run 时该键整体省略**（不发 null）
- stepIndex: 当前步骤索引
- currentSubtaskId: 当前正在执行的子卡 ID
- nextReady: 下一批 ready 的任务 ID 列表
- jobStatus: Job 状态（running/completed/failed/not_found）
- pauseReason: 暂停原因（如果已暂停）
- autoRun: 是否自动运行

无 active run 时**不报错**，返回 {success:true, snapshot:{stepIndex:0, nextReady, jobStatus:'not_found', autoRun:false}}
（**注意**：无 active run 时 runId 键**整体省略**，不要读成 null；该形状**不含** status/reason——
prompt 与 schema 曾声称会返回 status:'terminated'/reason，那是从未被产出的形状，已改正）。

（该契约曾因 snapshot.runId 原样透传 null、而 schema 声明为 string，被工具输出校验转成硬错误——
已修：不是 string 的字段整体省略，而不是发 null。改动时请保持"降级形状必须能通过自己的 schema"。）`;
