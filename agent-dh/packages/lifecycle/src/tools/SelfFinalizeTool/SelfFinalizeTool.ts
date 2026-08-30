/**
 * SelfFinalizeTool - 终止工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import { selfFinalizePrompt, SelfFinalizeParams, SelfFinalizeResult } from './prompt';

export class SelfFinalizeTool extends BaseTool<SelfFinalizeParams, SelfFinalizeResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'self_finalize',
    category: 'lifecycle',
    version: '1.0.0',
    timeoutMs: 5000,
  };

  protected readonly prompt = selfFinalizePrompt;

  constructor(private scheduleFinalize: (reason: string, saveState: boolean) => Promise<any>) {
    super();
  }

  protected validate(args: SelfFinalizeParams): ValidationResult {
    if (!args.reason || args.reason.trim().length === 0) {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.VALIDATION_ERROR,
          field: 'reason',
          issue: 'reason 不能为空',
          expected: 'non-empty string',
        },
      };
    }
    return { success: true };
  }

  protected async execute(args: SelfFinalizeParams, _context: ToolContext): Promise<SelfFinalizeResult> {
    const saveState = args.save_state ?? true;
    await this.scheduleFinalize(args.reason, saveState);

    return {
      success: true,
      message: `终止已调度，原因：${args.reason}`,
      finalized: true,
    };
  }

  protected wrap(result: SelfFinalizeResult): ToolResponse<SelfFinalizeResult> {
    return { success: true, data: result };
  }
}
