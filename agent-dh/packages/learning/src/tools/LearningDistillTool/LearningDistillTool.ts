/**
 * LearningDistillTool - 规则提炼工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import { learningDistillPrompt, LearningDistillParams, LearningDistillResult } from './prompt';

export class LearningDistillTool extends BaseTool<LearningDistillParams, LearningDistillResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'learning_distill',
    category: 'learning',
    version: '1.0.0',
    timeoutMs: 30000,
  };

  protected readonly prompt = learningDistillPrompt;

  constructor(
    private loadExperiencesBySource: (source: string) => Promise<any[]>,
    private distillRules: (options: any) => any[],
    private getDistillMethod: (format: string) => string,
    private validateRules: (rules: any[], experiences: any[]) => Record<string, any>
  ) {
    super();
  }

  protected validate(args: LearningDistillParams): ValidationResult {
    const validFormats = ['rule', 'prompt', 'code'];
    if (!args.target_format || !validFormats.includes(args.target_format)) {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.VALIDATION_ERROR,
          field: 'target_format',
          issue: `target_format 必须是: ${validFormats.join(', ')}`,
          expected: validFormats.join(' | '),
        },
      };
    }

    if (!args.source) {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.VALIDATION_ERROR,
          field: 'source',
          issue: 'source 是必需的',
          expected: 'string',
        },
      };
    }

    return { success: true };
  }

  protected async execute(args: LearningDistillParams, _context: ToolContext): Promise<LearningDistillResult> {
    const experiences = await this.loadExperiencesBySource(args.source);

    const rules = this.distillRules({
      experiences,
      targetFormat: args.target_format,
      minConfidence: args.min_confidence || 0.6,
      maxRules: args.max_rules || 10,
    });

    return {
      success: true,
      rules,
      source_count: experiences.length,
      distill_method: this.getDistillMethod(args.target_format),
      validation_stats: this.validateRules(rules, experiences),
    };
  }

  protected wrap(result: LearningDistillResult): ToolResponse<LearningDistillResult> {
    return { success: true, data: result };
  }
}
