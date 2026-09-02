/**
 * DecisionAuditTool - 决策审计工具（记录 + 评估）
 */

import { BaseTool, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { decisionAuditPrompt, DecisionAuditParams } from './prompt';

export class DecisionAuditTool extends BaseTool<DecisionAuditParams, any> {
  protected readonly metadata: ToolMetadata = {
    name: 'decision_audit',
    category: 'intelligence',
    version: '1.0.0',
    timeoutMs: 30000,
  };

  protected readonly prompt = decisionAuditPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: DecisionAuditParams): ValidationResult {
    if (args.action === 'record') {
      const missing: string[] = [];
      if (!args.decision_type) missing.push('decision_type（决策类型）');
      if (!args.reasoning) missing.push('reasoning（决策推理）');
      if (missing.length > 0) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          issue: `decision_audit record 缺少必填参数: ${missing.join('、')}`,
        };
      }
    } else if (args.action === 'evaluate') {
      if (!args.decision_id && (args.days === undefined || args.days === null)) {
        // days 有默认值，允许两者都不传（后端默认 7）
      }
      if (args.days !== undefined && (!Number.isInteger(args.days) || args.days < 1 || args.days > 90)) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'days',
          issue: 'days 必须是 1~90 的整数',
          received: String(args.days),
          expected: '1 ~ 90',
          example: '7',
        };
      }
    }
    return { success: true };
  }

  protected async execute(args: DecisionAuditParams, _context: ToolContext): Promise<any> {
    if (args.action === 'record') {
      const result = await this.qv2.recordDecision({
        decision_type: args.decision_type!,
        reasoning: args.reasoning!,
        context: args.context,
        parameters: args.parameters,
        related_entity_type: args.related_entity_type,
        related_entity_id: args.related_entity_id,
      });
      return sanitizeLossless({
        success: true,
        action: 'record',
        decision_id: result?.decision_id ?? result?.id ?? result?.decisionId,
        data: result,
      });
    }

    // evaluate
    const result = await this.qv2.evaluateDecisions({
      decision_id: args.decision_id,
      days: args.days,
    });
    return sanitizeLossless({
      success: true,
      action: 'evaluate',
      data: result,
    });
  }

  protected wrap(data: any, _context: ToolContext): ToolResponse<any> {
    return { success: true, data };
  }
}
