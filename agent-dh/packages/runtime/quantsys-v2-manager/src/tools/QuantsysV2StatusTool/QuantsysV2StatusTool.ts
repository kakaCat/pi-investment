import { BaseTool, type ToolMetadata, type ValidationResult, type ToolContext, type ToolResponse, ErrorType } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { quantsysV2StatusPrompt, type QuantsysV2StatusParams, type QuantsysV2StatusResult } from './prompt';

export class QuantsysV2StatusTool extends BaseTool<QuantsysV2StatusParams, QuantsysV2StatusResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'quantsys_v2_status',
    category: 'quantsys-v2-manager',
    version: '2.0.0',
    timeoutMs: 15000,
  };

  protected readonly prompt = quantsysV2StatusPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(params: QuantsysV2StatusParams): ValidationResult {
    // 无参数，直接通过
    return { success: true };
  }

  protected async execute(
    params: QuantsysV2StatusParams,
    _context: ToolContext
  ): Promise<QuantsysV2StatusResult> {
    try {
      // 调用 quantsys-v2 的平台状态 API
      const response = await this.qv2.getPlatformStatus();

      return {
        running: response.status === 'running',
        status: response.status,
        db_connected: response.db_connected,
        holdings_count: response.holdings_count,
        recent_signals: response.recent_signals,
        model_loaded: response.model_loaded,
        recent_report: response.recent_report,
        balance: response.balance,
        timestamp: response.timestamp,
      };
    } catch (error: any) {
      // 如果 API 调用失败，说明服务不可用
      return {
        running: false,
        status: 'stopped',
        db_connected: false,
        holdings_count: 0,
        recent_signals: 0,
        model_loaded: false,
        recent_report: false,
        error: error.message,
        timestamp: new Date().toISOString(),
      };
    }
  }

  protected wrap(data: QuantsysV2StatusResult, _context: ToolContext): ToolResponse<QuantsysV2StatusResult> {
    return {
      success: true,
      data,
    };
  }
}
