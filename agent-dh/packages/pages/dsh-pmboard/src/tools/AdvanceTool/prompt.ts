/**
 * AdvanceTool 提示词（REQ-4842fe t10）——reqboard_task_run 的工具描述。
 * @module dsh-pmboard/tools/AdvanceTool/prompt
 */
export const ADVANCE_PROMPT = '推进本窗口需求下的自动实施链：执行当前 ready 的一张子卡（一次独立 workflow run）；'
  + '父卡链全部子卡完成后自动汇总收尾，全部父卡完成后需求自动进入验收。'
  + '父卡开工时会自动展开固定子卡链（按需求类型）；已有子卡则幂等跳过。'
  + '失败即暂停并告警（不自动重试），需人工处置后再次调用本工具续跑。'
