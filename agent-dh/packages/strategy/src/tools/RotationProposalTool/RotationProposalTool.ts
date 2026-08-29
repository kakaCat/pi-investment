/**
 * RotationProposalTool - 轮动方案建议工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { rotationProposalPrompt, RotationProposalParams, RotationProposalResult } from './prompt';

export class RotationProposalTool extends BaseTool<RotationProposalParams, RotationProposalResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'rotation_proposal',
    category: 'strategy',
    version: '2.0.0',
    timeoutMs: 30000,
  };

  protected readonly prompt = rotationProposalPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: RotationProposalParams): ValidationResult {
    if (args.mode) {
      const validModes = ['conservative', 'balanced', 'aggressive'];
      if (!validModes.includes(args.mode)) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'mode',
          issue: 'mode 必须是 conservative/balanced/aggressive',
          received: args.mode,
          expected: 'conservative | balanced | aggressive',
        };
      }
    }

    if (args.max_positions !== undefined && (!Number.isInteger(args.max_positions) || args.max_positions <= 0)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'max_positions',
        issue: 'max_positions 必须是正整数',
        received: args.max_positions,
        expected: '正整数',
      };
    }

    return { success: true };
  }

  protected async execute(
    args: RotationProposalParams,
    _context: ToolContext
  ): Promise<RotationProposalResult> {
    return this.qv2.generateRotationProposal({
      account_name: args.account_name || 'default',
      mode: args.mode || 'balanced',
      max_positions: args.max_positions || 10,
    }) as any;
  }

  protected wrap(data: RotationProposalResult): ToolResponse<RotationProposalResult> {
    return { success: true, data };
  }
}
