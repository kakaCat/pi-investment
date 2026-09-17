/**
 * TaskReportTool 提示词（REQ-47939a t8）——从 host/agent-tools.ts 的 defineTaskReportTool description 原样搬入。
 * @module dsh-pmboard/tools/TaskReportTool/prompt
 */
export const TASK_REPORT_PROMPT = '任务完成汇报：把"做了什么"结构化落到任务卡文档（docs/requirements/<REQ>/tasks/<task_id>.md），'
      + '并登记实施节点产物（kind=task_detail）。任务卡文档双角色：开工说明书（decompose 生成骨架）'
      + '+ 完工记录（本工具追加汇报）。参数：task_id=任务 id；summary=一句话做了什么；'
      + 'completed=完成项列表；files_changed=改动文件列表；next_step=下一步。'
      + '重复汇报幂等：追加新段落但不重复登记产物。'
      + '前置：任务属于本窗口绑定的需求。'
