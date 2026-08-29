import { BaseTool, ToolResponse, ValidationResult, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { marketAlertPrompt, type MarketAlertParams } from './prompt';

export class MarketAlertTool extends BaseTool<MarketAlertParams, any[]> {
  protected readonly metadata: ToolMetadata = {
    name: 'market_alert',
    category: 'intelligence',
    version: '1.0.0',
    timeoutMs: 10000,
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

    return {
      success: true,
      data,
      message: `共 ${data.length} 条告警（high: ${levelCounts.high}, medium: ${levelCounts.medium}, low: ${levelCounts.low}）`,
      metadata: {
        total: data.length,
        by_level: levelCounts,
      },
    };
  }
}
