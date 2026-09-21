/**
 * DecomposeTool 提示词（REQ-47939a t8）——从 host/agent-tools.ts 的 defineDecomposeTool description 原样搬入。
 * @module dsh-pmboard/tools/DecomposeTool/prompt
 */
export const DECOMPOSE_PROMPT = '拆分落库（plan mode 的执行端）：把**已获人批准的拆分计划**写成任务卡——'
      + '任务立即出现在看板「任务」页与甘特图里。默认不传 tasks = 直接落库批准的计划；'
      + '传 tasks 则 key 集合必须与批准的计划一致（防止「批了 A 落库 B」）。'
      + '前置条件：需求属于本窗口、处于需求分析/拆分/实施态，且计划已由人批准——'
      + '没有计划或计划未批准会被代码级拒绝（REQBOARD_PLAN_NOT_APPROVED）：'
      + '先 reqboard_plan_submit 提交计划，请人在看板点「批准计划」。'
