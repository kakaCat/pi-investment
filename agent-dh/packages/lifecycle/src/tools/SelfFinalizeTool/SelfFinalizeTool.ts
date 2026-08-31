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
    version: '1.1.0',
    timeoutMs: 15000,
  };

  protected readonly prompt = selfFinalizePrompt;

  constructor(private scheduleFinalize: (reason: string, action: 'merge' | 'rollback' | 'exit', saveState: boolean) => Promise<any>) {
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
    if (args.action && !['merge', 'rollback', 'exit'].includes(args.action)) {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.VALIDATION_ERROR,
          field: 'action',
          issue: 'action 必须是 merge / rollback / exit',
          expected: 'merge | rollback | exit',
        },
      };
    }
    return { success: true };
  }

  protected async execute(args: SelfFinalizeParams, _context: ToolContext): Promise<SelfFinalizeResult> {
    const saveState = args.save_state ?? true;
    const action = args.action ?? 'merge';
    const result = await this.scheduleFinalize(args.reason, action, saveState);

    return {
      success: true,
      message: `终止已调度，原因：${args.reason}`,
      finalized: true,
      action: result?.action ?? action,
      merged_hash: result?.merged_hash,
    };
  }

  protected wrap(result: SelfFinalizeResult): ToolResponse<SelfFinalizeResult> {
    return { success: true, data: result };
  }
}
