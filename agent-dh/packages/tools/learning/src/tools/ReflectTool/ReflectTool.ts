/**
 * ReflectTool - 目标对齐反思工具（结构化质检，零 I/O 纯计算）
 */

import { BaseTool, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import { reflectPrompt, ReflectParams } from './prompt';

export class ReflectTool extends BaseTool<ReflectParams, any> {
  protected readonly metadata: ToolMetadata = {
    name: 'reflect',
    category: 'learning',
    version: '1.0.0',
    timeoutMs: 5000,
  };

  protected readonly prompt = reflectPrompt;

  protected validate(args: ReflectParams): ValidationResult {
    if (!args.original_goal || !args.work_summary) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        issue: 'original_goal 和 work_summary 都是必填（反思必须对照原始目标）',
      };
    }
    return { success: true };
  }

  protected async execute(args: ReflectParams, _context: ToolContext): Promise<any> {
    const gaps = args.gaps ?? [];
    const evidence = args.evidence ?? [];

    // 结构化判定：证据充分且无自报差距 → aligned；有差距 → gaps_found；无证据 → partial
    const verdict = gaps.length > 0
      ? 'gaps_found'
      : evidence.length > 0
        ? 'aligned'
        : 'partial';

    const checklist = [
      { item: '回答了用户的原始问题（而非相关问题）', hint: `原始目标: ${args.original_goal}` },
      { item: '所有关键数字/结论有工具数据支撑（非编造）', hint: evidence.length > 0 ? `证据 ${evidence.length} 条` : '⚠️ 未提供证据' },
      { item: '输出包含可执行的下一步（价位/动作/时间点）', hint: '买卖点类问题必须有具体价位' },
      { item: '风险与不确定性已标注', hint: '弱信号/数据陈旧/样本不足需明示' },
    ];

    const nextSteps = gaps.length > 0
      ? gaps.map((g) => `补齐差距：${g}`)
      : verdict === 'aligned'
        ? ['向用户交付结果']
        : ['补充证据或向用户说明不确定性'];

    return sanitizeLossless({
      verdict,
      original_goal: args.original_goal,
      work_summary: args.work_summary,
      gaps,
      evidence_count: evidence.length,
      checklist,
      next_steps: nextSteps,
      reminder: '⚠️ reflect 是检查点不是终点——拿到结果后必须继续（交付/补齐/解释）',
    });
  }

  protected wrap(data: any, _context: ToolContext): ToolResponse<any> {
    return { success: true, data };
  }
}
