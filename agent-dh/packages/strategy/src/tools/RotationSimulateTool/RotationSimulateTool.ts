/**
 * RotationSimulateTool - 轮动模拟工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { rotationSimulatePrompt, RotationSimulateParams, RotationSimulateResult } from './prompt';

export class RotationSimulateTool extends BaseTool<RotationSimulateParams, RotationSimulateResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'rotation_simulate',
    category: 'strategy',
    version: '2.0.0',
    timeoutMs: 30000,
  };

  protected readonly prompt = rotationSimulatePrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: RotationSimulateParams): ValidationResult {
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
    args: RotationSimulateParams,
    _context: ToolContext
  ): Promise<RotationSimulateResult> {
    return this.qv2.simulateRotation({
      proposals: args.proposals,
      account_name: args.account_name || 'default',
      check_constraints: args.check_constraints !== false,
    }) as any;
  }

  protected wrap(data: RotationSimulateResult): ToolResponse<RotationSimulateResult> {
    return { success: true, data };
  }
}
