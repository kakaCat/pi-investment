import { BaseTool, type ToolMetadata, type ValidationResult, type ToolContext, type ToolResponse, ErrorType } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { dataQualityReportPrompt, type DataQualityReportParams, type DataQualityReportResult } from './prompt';

export class DataQualityReportTool extends BaseTool<DataQualityReportParams, DataQualityReportResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'data_quality_report',
    category: 'data-manager',
    version: '1.0.0',
    timeoutMs: 20000,
  };

  protected readonly prompt = dataQualityReportPrompt;

  constructor(private quantsysClient: QuantsysV2Client) {
    super();
  }

  protected validate(params: DataQualityReportParams): ValidationResult {
    const errors: string[] = [];

    if (params.data_type) {
      const validTypes = ['quote', 'kline', 'financial', 'all'];
      if (!validTypes.includes(params.data_type)) {
        errors.push(`data_type 必须是 ${validTypes.join(', ')} 之一`);
      }
    }

    if (params.days !== undefined) {
      if (!Number.isInteger(params.days) || params.days < 1 || params.days > 30) {
        errors.push('days 必须是 1-30 之间的整数');
      }
    }

    if (errors.length > 0) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        issue: errors.join('; '),
      };
    }

    return { success: true };
  }

  protected async execute(
    params: DataQualityReportParams,
    context: ToolContext
  ): Promise<DataQualityReportResult> {
    const dataType = params.data_type || 'all';
    const days = params.days || 7;

    const response = await this.quantsysClient.getDataQualityReport({
      data_type: dataType,
      days,
    });

    return response as DataQualityReportResult;
  }

  protected wrap(data: DataQualityReportResult, context: ToolContext): ToolResponse<DataQualityReportResult> {
    const { data_type, overall_score, missing_data, delayed_data, anomalies } = data;

    const score = typeof overall_score === 'number' ? overall_score : 0;
    let message = `数据质量报告（${data_type}）: 评分 ${score.toFixed(1)}`;
    if (missing_data.length > 0) message += `, ${missing_data.length} 处缺失`;
    if (delayed_data.length > 0) message += `, ${delayed_data.length} 处延迟`;
    if (anomalies.length > 0) message += `, ${anomalies.length} 处异常`;

    return {
      success: true,
      data,
      message,
      metadata: {
        data_type,
        overall_score,
        issues: missing_data.length + delayed_data.length + anomalies.length,
      },
    };
  }
}
