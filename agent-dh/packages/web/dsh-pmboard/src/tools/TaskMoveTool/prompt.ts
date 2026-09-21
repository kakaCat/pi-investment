/**
 * TaskMoveTool 提示词（REQ-47939a t8）——从 host/agent-tools.ts 的 defineTaskMoveTool description 原样搬入。
 * @module dsh-pmboard/tools/TaskMoveTool/prompt
 */
export const TASK_MOVE_PROMPT = '推进本窗口需求下的任务状态（todo → in_progress → integration/testing → in_review → done）。'
      + '开工时移到 in_progress（自动开一段执行记录），完成时移到 done；'
      + '任务全部 done 后需求会自动进入验收。'
      + '只有「取消任务/复活已取消任务」是人工闸门。'
