/**
 * LearningApplyTool - 规则应用工具
 */

import { BaseTool, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import { learningApplyPrompt, LearningApplyParams, LearningApplyResult } from './prompt';

export class LearningApplyTool extends BaseTool<LearningApplyParams, LearningApplyResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'learning_apply',
    category: 'learning',
    version: '1.0.0',
    timeoutMs: 15000,
  };

  protected readonly prompt = learningApplyPrompt;

  constructor(
    private applyRule: (ruleId: string, context: any, dryRun: boolean) => Promise<any>
  ) {
    super();
  }

  protected validate(args: LearningApplyParams): ValidationResult {
    if (!args.rule_id) {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.VALIDATION_ERROR,
          field: 'rule_id',
          issue: 'rule_id 是必需的',
          expected: 'string',
        },
      };
    }

    if (!args.context || typeof args.context !== 'object') {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.VALIDATION_ERROR,
          field: 'context',
          issue: 'context 必须是对象',
          expected: 'object',
        },
      };
    }

    return { success: true };
  }

  protected async execute(args: LearningApplyParams, _context: ToolContext): Promise<LearningApplyResult> {
    const dryRun = args.dry_run ?? false;
    const result = await this.applyRule(args.rule_id, args.context, dryRun);

    // 2026-08-30 修复：impact/action_taken 可能含 undefined，lossless 校验失败，递归清洗。
    return sanitizeLossless({
      success: true,
      applied: result.applied || false,
      action_taken: result.action_taken,
      impact: result.impact,
      message: result.message || (dryRun ? '模拟运行完成' : '规则已应用'),
    });
  }

  protected wrap(result: LearningApplyResult): ToolResponse<LearningApplyResult> {
    return { success: true, data: result };
  }
}
