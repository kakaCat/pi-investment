/**
 * LearningAnalyzeTool - 经验分析工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import { learningAnalyzePrompt, LearningAnalyzeParams, LearningAnalyzeResult } from './prompt';

export class LearningAnalyzeTool extends BaseTool<LearningAnalyzeParams, LearningAnalyzeResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'learning_analyze',
    category: 'learning',
    version: '1.0.0',
    timeoutMs: 20000,
  };

  protected readonly prompt = learningAnalyzePrompt;

  constructor(
    private analyzeExperiences: (scope: string, focus: string, minSamples: number) => Promise<any>
  ) {
    super();
  }

  protected validate(args: LearningAnalyzeParams): ValidationResult {
    const validFocus = ['failures', 'successes', 'patterns', 'all'];
    if (args.focus && !validFocus.includes(args.focus)) {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.VALIDATION_ERROR,
          field: 'focus',
          issue: `focus 必须是: ${validFocus.join(', ')}`,
          expected: validFocus.join(' | '),
        },
      };
    }
    return { success: true };
  }

  protected async execute(args: LearningAnalyzeParams, _context: ToolContext): Promise<LearningAnalyzeResult> {
    const scope = args.scope || 'recent';
    const focus = args.focus || 'patterns';
    const minSamples = args.min_samples || 5;

    const result = await this.analyzeExperiences(scope, focus, minSamples);

    return {
      success: true,
      patterns: Array.isArray(result?.patterns) ? result.patterns : [],
      suggestions: (Array.isArray(result?.suggestions) ? result.suggestions : [])
        .map((s: any) => String(s ?? '')),
      sample_count: typeof result?.sample_count === 'number' ? result.sample_count : 0,
    };
  }

  protected wrap(result: LearningAnalyzeResult): ToolResponse<LearningAnalyzeResult> {
    return { success: true, data: result };
  }
}
