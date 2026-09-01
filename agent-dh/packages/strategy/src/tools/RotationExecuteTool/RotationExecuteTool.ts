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
        expected: '[{ action, strategy_id?, strategy_name?, symbol?, weight? }]',
      };
    }

    // 2026-09-01：action 与后端 strategy_rotation_engine 对齐（activate/deactivate/adjust_weight）；
    // 策略级动作需要 strategy_id 或 strategy_name 定位策略（不再强制 symbol）。
    for (let i = 0; i < args.proposals.length; i++) {
      const p = args.proposals[i];
      if (!p.action || !['activate', 'deactivate', 'adjust_weight'].includes(p.action)) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: `proposals[${i}].action`,
          issue: 'action 必须是 activate/deactivate/adjust_weight',
          received: p.action,
          expected: 'activate | deactivate | adjust_weight',
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
