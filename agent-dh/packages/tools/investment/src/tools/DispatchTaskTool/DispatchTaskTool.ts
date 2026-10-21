import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { dispatchTaskPrompt, type DispatchTaskParams } from './prompt';

/**
 * 任务派发工具（2026-10-20 框架适配）。
 *
 * 为什么是工具而不是脚本：派活要成为**系统能力**——agent 自己能把活派出去
 * （另一个窗口/另一个 agent），系统到点只需给一句短触发。信封、报告要求、
 * 留痕都沉在服务端（qs_notification.application.agent_task_dispatch），
 * 工具只是调用面，避免"这次记得带报告、下次忘了"。
 *
 * 纪律：
 * - 只派不代执行：status=ok 只代表 wake 通道收下，不代表执行；
 * - 失败必须显式抛错——不能把"没派出去"当成"活已经交给别人了"。
 */
export class DispatchTaskTool extends BaseTool<DispatchTaskParams, any> {
  protected readonly metadata: ToolMetadata = {
    name: 'dispatch_task', category: 'action', version: '1.0.0', timeoutMs: 20000,
  };
  protected readonly prompt = dispatchTaskPrompt;
  constructor(private qv2: QuantsysV2Client) { super(); }

  protected validate(args: DispatchTaskParams): ValidationResult {
    const title = String(args?.title ?? '').trim();
    if (!title) {
      return { success: false, errorType: ErrorType.INPUT_ERROR, field: 'title',
               issue: 'title 不能为空', expected: '简短任务标题', example: '盯盘积压清理' };
    }
    if (title.length > 200) {
      return { success: false, errorType: ErrorType.INPUT_ERROR, field: 'title',
               issue: 'title 过长（>200）', received: String(title.length), expected: '≤200 字' };
    }
    const instruction = String(args?.instruction ?? '').trim();
    if (!instruction) {
      return { success: false, errorType: ErrorType.INPUT_ERROR, field: 'instruction',
               issue: 'instruction 不能为空（否则收件人不知道要做什么）', expected: '作业指导正文' };
    }
    const urgency = String(args?.urgency ?? 'normal');
    if (!['normal', 'high', 'critical'].includes(urgency)) {
      return { success: false, errorType: ErrorType.INPUT_ERROR, field: 'urgency',
               issue: `无效的 urgency: ${urgency}`, expected: 'normal|high|critical' };
    }
    if (args?.target !== undefined && !/^[a-z][a-z0-9-]{1,31}$/.test(String(args.target))) {
      return { success: false, errorType: ErrorType.INPUT_ERROR, field: 'target',
               issue: `无效的 target: ${args.target}`, expected: 'agent-dh|agent-ts 等 agent 键' };
    }
    return { success: true };
  }

  protected async execute(args: DispatchTaskParams, _c: ToolContext): Promise<any> {
    const res: any = await (this.qv2 as any).dispatchAgentTask({
      title: String(args.title).trim(),
      instruction: String(args.instruction),
      event: args.event ? String(args.event) : 'agent_task',
      target: args.target ? String(args.target) : 'agent-dh',
      requires_report: args.requires_report !== false,
      urgency: (args.urgency ?? 'normal') as 'normal' | 'high' | 'critical',
    });
    if (!res || res.success !== true) {
      throw new Error(
        `任务派发失败：${res?.error || res?.message || '未知原因'}（status=${res?.status ?? '?'}）。` +
        '**不要当作"已经派出去/对方会做"**——通道没确认收下，任务不会被执行。',
      );
    }
    return res;
  }
}

export function createDispatchTaskTool(qv2: QuantsysV2Client) {
  const tool = new DispatchTaskTool(qv2);
  return tool.toDSHToolDefinition();
}
