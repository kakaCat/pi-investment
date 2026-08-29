/**
 * RotationExecuteTool - 轮动执行工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { rotationExecutePrompt, RotationExecuteParams, RotationExecuteResult } from './prompt';

export class RotationExecuteTool extends BaseTool<RotationExecuteParams, RotationExecuteResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'rotation_execute',
    category: 'strategy',
    version: '2.0.0',
    timeoutMs: 60000,
  };

  protected readonly prompt = rotationExecutePrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: RotationExecuteParams): ValidationResult {
    if (!Array.isArray(args.proposals) || args.proposals.length === 0) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'proposals',
        issue: 'proposals 必须是非空数组',
        received: args.proposals,
        expected: '[{ action, symbol, weight? }]',
      };
    }

    for (let i = 0; i < args.proposals.length; i++) {
      const p = args.proposals[i];
      if (!p.action || !['buy', 'sell'].includes(p.action)) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: `proposals[${i}].action`,
          issue: 'action 必须是 buy 或 sell',
          received: p.action,
          expected: 'buy | sell',
        };
      }

      if (!p.symbol || typeof p.symbol !== 'string') {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: `proposals[${i}].symbol`,
          issue: 'symbol 必须是字符串',
          received: p.symbol,
          expected: '股票代码',
        };
      }
    }

    return { success: true };
  }

  protected async execute(
    args: RotationExecuteParams,
    _context: ToolContext
  ): Promise<RotationExecuteResult> {
    return this.qv2.executeRotation({
      proposals: args.proposals,
      account_name: args.account_name || 'default',
      dry_run: args.dry_run || false,
    }) as any;
  }

  protected wrap(data: RotationExecuteResult): ToolResponse<RotationExecuteResult> {
    return { success: true, data };
  }
}
