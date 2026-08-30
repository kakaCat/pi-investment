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
    // 2026-08-30 修复：后端实际返回 records 列表（无 missing_data/delayed_data/anomalies 顶层键），
    // 直接 .length 会 TypeError；且输出 schema 为 additionalProperties:false，必须映射为契约字段。
    const records: any[] = Array.isArray((data as any).records) ? (data as any).records : [];
    const scores = records
      .map((r: any) => r?.overall_score)
      .filter((n: any): n is number => typeof n === 'number');

    const data_type = (data as any).data_type ?? (context as any).data_type ?? 'all';
    const check_date = (data as any).check_date ?? records[0]?.check_date ?? '';
    const overall_score = typeof (data as any).overall_score === 'number'
      ? (data as any).overall_score
      : (scores.length > 0 ? Math.min(...scores) : 0);

    const missing_data = Array.isArray(data.missing_data)
      ? data.missing_data
      : records
          .filter((r: any) => (r?.removed_count ?? 0) > 0 || (r?.cleaned_count ?? 0) < (r?.original_count ?? 0))
          .map((r: any) => ({ symbol: r?.symbol ?? '', date: r?.check_date ?? '', type: r?.period ?? 'daily', removed_count: r?.removed_count ?? 0 }));
    const delayed_data = Array.isArray(data.delayed_data) ? data.delayed_data : [];
    const anomalies = Array.isArray(data.anomalies)
      ? data.anomalies
      : records
          .filter((r: any) => (r?.error_count ?? 0) > 0)
          .map((r: any) => ({ symbol: r?.symbol ?? '', date: r?.check_date ?? '', type: r?.period ?? 'daily', error_count: r?.error_count ?? 0 }));

    const mapped: DataQualityReportResult = {
      data_type,
      check_date,
      overall_score,
      missing_data,
      delayed_data,
      anomalies,
      summary: (data as any).summary ?? `数据质量报告（${data_type}）: ${records.length} 条检查记录, 综合评分 ${overall_score.toFixed(1)}`,
    };

    const score = typeof overall_score === 'number' ? overall_score : 0;
    let message = `数据质量报告（${data_type}）: 评分 ${score.toFixed(1)}`;
    if (missing_data.length > 0) message += `, ${missing_data.length} 处缺失`;
    if (delayed_data.length > 0) message += `, ${delayed_data.length} 处延迟`;
    if (anomalies.length > 0) message += `, ${anomalies.length} 处异常`;

    return {
      success: true,
      data: mapped,
      message,
      metadata: {
        data_type,
        overall_score,
        issues: missing_data.length + delayed_data.length + anomalies.length,
      },
    };
  }
}
