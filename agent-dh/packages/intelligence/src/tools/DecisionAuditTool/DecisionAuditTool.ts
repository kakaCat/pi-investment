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
    version: '1.1.0',  // 升级版本号
    timeoutMs: 30000,
  };

  protected readonly prompt = decisionAuditPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: DecisionAuditParams): ValidationResult {
    if (args.action === 'record') {
      // 新格式：decision_subtype + parameters 必填
      // 旧格式：decision_type 必填
      if (!args.decision_type && !args.decision_subtype) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'decision_type / decision_subtype',
          issue: 'decision_type 或 decision_subtype 至少一个必填',
          received: 'undefined',
          expected: 'trade_buy / observation / skip 等',
          example: 'decision_subtype: "observation"',
        };
      }
      if (!args.reasoning) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'reasoning',
          issue: 'reasoning 必填',
          received: 'undefined',
          expected: '为什么做这个决策，引用规则ID+数据依据',
          example: 'R-009 A级信号：主线+技术+资金三维共振',
        };
      }
      // 新格式必须有 parameters
      if (args.decision_subtype && !args.parameters) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'parameters',
          issue: '使用 decision_subtype 时 parameters 必填',
          received: 'undefined',
          expected: '{symbol, action, quantity, price} 或 {symbol, reason, watchDays} 等',
          example: '{symbol: "600519", action: "BUY", quantity: 100, price: 1850}',
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
        decision_type: args.decision_type,
        decision_subtype: args.decision_subtype,  // 新增
        reasoning: args.reasoning!,
        context: args.context,
        parameters: args.parameters,
        related_entity_type: args.related_entity_type,
        related_entity_id: args.related_entity_id,
      });
      
      return sanitizeLossless({
        success: true,
        action: 'record',
        decision_id: result?.decision_id ?? result?.data?.decision_id,
        data: result,
      });
    } else if (args.action === 'evaluate') {
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
    
    throw new Error(`Unknown action: ${args.action}`);
  }
}
