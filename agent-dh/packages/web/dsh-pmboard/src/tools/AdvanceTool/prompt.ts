/**
 * AdvanceTool 提示词（REQ-4842fe t10）——reqboard_task_run 的工具描述。
 * @module dsh-pmboard/tools/AdvanceTool/prompt
 */
export const ADVANCE_PROMPT = '推进本窗口需求下的自动实施链（REQ-260925110957-552d：投递式，立即返回）：'
  + '投递后台任务执行当前 ready 的一张子卡，立即返回 {status:"dispatched", job_id, run_id}。'
  + '⚠️ 投递≠完成：调用返回 <1s，实际执行在后台 ctx.jobs 中进行。'
  + '查询运行态：用 reqboard_run_status 工具（传 run_id 或 requirement_id）取执行进度。'
  + '父卡链全部子卡完成后自动汇总收尾，全部父卡完成后需求自动进入验收。'
  + '父卡开工时会自动展开固定子卡链（按需求类型）；已有子卡则幂等跳过。'
  + '失败即暂停并告警（不自动重试），需人工处置后再次调用本工具续跑。'
