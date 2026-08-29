/**
 * ScreeningTool - 股票筛选工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { screeningPrompt, ScreeningParams, ScreeningResult } from './prompt';

export class ScreeningTool extends BaseTool<ScreeningParams, ScreeningResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'screening',
    category: 'strategy',
    version: '2.0.0',
    timeoutMs: 30000,
  };

  protected readonly prompt = screeningPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: ScreeningParams): ValidationResult {
    if (!args.criteria || typeof args.criteria !== 'object' || Object.keys(args.criteria).length === 0) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'criteria',
        issue: 'criteria 必须是非空对象',
        received: args.criteria,
        expected: '{ field: [min, max] }',
        example: '{ pe: [0, 20], roe: [15, null] }',
      };
    }

    if (args.limit !== undefined && (!Number.isInteger(args.limit) || args.limit <= 0)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'limit',
        issue: 'limit 必须是正整数',
        received: args.limit,
        expected: '正整数',
      };
    }

    return { success: true };
  }

  protected async execute(
    args: ScreeningParams,
    _context: ToolContext
  ): Promise<ScreeningResult> {
    return this.qv2.screenStocks({
      criteria: args.criteria,
      sort_by: args.sort_by,
      limit: args.limit || 50,
    }) as any;
  }

  protected wrap(data: ScreeningResult): ToolResponse<ScreeningResult> {
    return { success: true, data };
  }
}
