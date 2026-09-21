/**
 * DecisionHistoryTool - 决策历史查询工具
 */

import { BaseTool, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { decisionHistoryPrompt, DecisionHistoryParams } from './prompt';

export class DecisionHistoryTool extends BaseTool<DecisionHistoryParams, any> {
  protected readonly metadata: ToolMetadata = {
    name: 'decision_history',
    category: 'intelligence',
    version: '1.0.0',
    timeoutMs: 15000,
  };

  protected readonly prompt = decisionHistoryPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: DecisionHistoryParams): ValidationResult {
    const action = args.action || 'history';
    if (action === 'report' && (!args.entity_type || !args.entity_id)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        issue: 'decision_history report 模式必须传 entity_type 和 entity_id',
      };
    }
    return { success: true };
  }

  protected async execute(args: DecisionHistoryParams, _context: ToolContext): Promise<any> {
    // TODO: 处理非200响应 - 添加错误处理或降级逻辑（404/500等），参考 pe_percentile 改进方案
    // 每个工具的业务语义不同，需要根据具体场景设计降级策略
    const action = args.action || 'history';

    if (action === 'pending') {
      const items = await this.qv2.getPendingDecisions(args.days ?? 7);
      return sanitizeLossless({ action, count: items?.length ?? 0, items });
    }

    if (action === 'report') {
      const report = await this.qv2.getDecisionReport(args.entity_type!, args.entity_id!);
      return sanitizeLossless({ action, report });
    }

    const items = await this.qv2.getDecisionHistory({
      entity_type: args.entity_type,
      entity_id: args.entity_id,
      decision_type: args.decision_type,
      limit: args.limit,
    });
    return sanitizeLossless({ action, count: items?.length ?? 0, items });
  }

  protected wrap(data: any, _context: ToolContext): ToolResponse<any> {
    return { success: true, data };
  }
}
