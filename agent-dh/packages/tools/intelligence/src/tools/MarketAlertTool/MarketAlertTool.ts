import { BaseTool, ToolResponse, ValidationResult, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { marketAlertPrompt, type MarketAlertParams } from './prompt';

export class MarketAlertTool extends BaseTool<MarketAlertParams, any[]> {
  protected readonly metadata: ToolMetadata = {
    name: 'market_alert',
    category: 'intelligence',
    version: '1.0.1',
    timeoutMs: 40000,
  };

  protected readonly prompt = marketAlertPrompt;

  constructor(private qv2Client: QuantsysV2Client) {
    super();
  }

  protected validate(params: MarketAlertParams): ValidationResult {
    // 参数校验
    if (params.limit !== undefined && (params.limit < 1 || params.limit > 100)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        issue: 'limit 必须在 1-100 之间',
      };
    }

    return { success: true };
  }

  protected async execute(params: MarketAlertParams, context: ToolContext): Promise<any[]> {
    const alerts = await this.qv2Client.getAlerts({
      level: params.level || 'all',
      limit: params.limit || 20,
    });
    return alerts;
  }

  protected wrap(data: any[], context: ToolContext): ToolResponse<any[]> {
    const levelCounts = {
      high: data.filter((a: any) => a.level === 'high').length,
      medium: data.filter((a: any) => a.level === 'medium').length,
      low: data.filter((a: any) => a.level === 'low').length,
    };

    const notification = {
      notify_worthy: data.filter((a: any) => a.notify_worthy === true).length,
      unchanged: data.filter((a: any) => a.notification_reason === 'unchanged').length,
      dedup_errors: data.filter((a: any) => a.dedup_status === 'error').length,
      unspecified: data.filter((a: any) => a.notify_worthy === undefined).length,
    };

    return {
      success: true,
      data,
      message: `共 ${data.length} 条活跃告警（high: ${levelCounts.high}, medium: ${levelCounts.medium}, low: ${levelCounts.low}）；新/变化 ${notification.notify_worthy} 条，持续未变 ${notification.unchanged} 条，去重异常 ${notification.dedup_errors} 条`,
      metadata: {
        total: data.length,
        by_level: levelCounts,
        notification,
      },
    };
  }
}
