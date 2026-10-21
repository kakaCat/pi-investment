import type { ToolPrompt } from '@pi-investment/core-tool';

export interface DispatchTaskParams {
  /** 任务标题（也用于飞书报告标题） */
  title: string;
  /** 作业指导正文：做什么、边界、验收口径 */
  instruction: string;
  /** 事件名（区分来源，默认 agent_task） */
  event?: string;
  /** 处置 agent（默认 agent-dh 本实例） */
  target?: string;
  /** 是否要求收件人完成后发飞书简报（默认 true；静默巡检类任务设 false） */
  requires_report?: boolean;
  /** 报告紧急度 */
  urgency?: 'normal' | 'high' | 'critical';
}

export const dispatchTaskPrompt: ToolPrompt<DispatchTaskParams, any> = {
  description:
    '把一项工作任务派给处置 agent（2026-10-20 框架适配）。服务端统一加【任务】信封与【交付要求】' +
    '（需要报告时附四段式飞书简报要求），并留痕到 logs/agent-dispatch.jsonl。' +
    '用于：需要独立回合推进的活、需要交给另一个 agent 窗口接手的活、或系统只给了很短一句触发时。' +
    '⚠️ 本工具只负责「派出去」，不代执行；返回 status=ok 只代表通道收下，**不代表已执行**——' +
    '验收看对方会话回合 / 结果落库 / 飞书报告卡。',
  useCases: [
    {
      title: '派一个需要报告的活',
      description: '有明确交付物、需要完成后简报的任务',
      example: 'dispatch_task({ title: "盯盘积压清理", instruction: "逐条看 137 条 meta_review，别批量关", event: "watch_backlog_sweep" })',
    },
    {
      title: '派静默巡检',
      description: '无异常不打扰的巡检类任务（夜间哨兵/盘前检查）',
      example: 'dispatch_task({ title: "夜间挂单哨兵", instruction: "只读核查未授权挂单", requires_report: false })',
    },
    {
      title: '交给另一个 agent',
      description: '本窗口不便处理的活交给指定 agent',
      example: 'dispatch_task({ title: "执行止损", instruction: "...", target: "agent-ts" })',
    },
  ],
  parameters: {
    title: { type: 'string', required: true, description: '任务标题（简短可识别）', example: '盯盘积压清理（10-20 晚）' },
    instruction: {
      type: 'string', required: true,
      description: '作业指导：做什么、纪律边界、验收口径。越具体越不容易跑偏',
      example: '拉 meta_review 清单逐条评估；拿不准的不动；不得代下单',
    },
    event: { type: 'string', required: false, description: '事件名（默认 agent_task）', example: 'watch_backlog_sweep' },
    target: { type: 'string', required: false, description: '处置 agent 键（默认 agent-dh）', example: 'agent-ts' },
    requires_report: { type: 'boolean', required: false, description: '是否要求完成后飞书简报（默认 true）', example: 'true' },
    urgency: { type: 'string', required: false, description: 'normal|high|critical（默认 normal）', example: 'normal' },
  },
  output: {
    schema: { type: 'object', additionalProperties: true },
    render: (_args: any, data: any) => [
      { type: 'text', text: '任务派发结果（dispatch_task）：\n' + JSON.stringify(data, null, 2) },
    ],
  },
};
