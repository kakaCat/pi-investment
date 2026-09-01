import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { dataFetchMacroPrompt, DataFetchMacroParams, DataFetchMacroResult } from './prompt';

export class DataFetchMacroTool extends BaseTool<DataFetchMacroParams, DataFetchMacroResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'data_fetch_macro',
    category: 'data',
    version: '2.0.0',
    timeoutMs: 60000,
  };

  protected readonly prompt = dataFetchMacroPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: DataFetchMacroParams): ValidationResult {
    const validIndicators = ['pmi', 'cpi', 'gdp'];
    if (!args.indicator || !validIndicators.includes(args.indicator)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'indicator',
        issue: 'indicator 必须是 pmi/cpi/gdp 之一',
        received: args.indicator,
        expected: 'pmi | cpi | gdp',
      };
    }
    return { success: true };
  }

  protected async execute(
    args: DataFetchMacroParams,
    context: ToolContext
  ): Promise<DataFetchMacroResult> {
    const macro = await this.qv2.getMacroData();
    const indicator = String(args.indicator).toLowerCase();
    // 2026-09-01 修复：/api/market/macro 返回 {data_type, data:{gdp,cpi,pmi}, source, timestamp}，
    // unwrap 后数据在 macro.data 内层；原取 macro[indicator] 恒 undefined → 报"后端未提供数据"。
    const inner: any = (macro as any)?.data ?? macro;
    const series = inner[indicator] as Array<Record<string, any>> | undefined;

    if (!Array.isArray(series) || series.length === 0) {
      return {
        indicator,
        data: [],
        latest: {},
        trend: 'unknown',
        update_time: (macro as any)?.timestamp || (macro as any)?.updateTime || new Date().toISOString(),
        note: `后端未提供 ${indicator} 数据`,
      };
    }

    // 数值列（排除期次标签列，如 "季度"/"月份"）
    const numericOf = (row: Record<string, any>): number[] =>
      Object.values(row).filter((v): v is number => typeof v === 'number');

    const latest = series[0];
    const latestVals = numericOf(latest);
    const prevVals = series.length > 1 ? numericOf(series[1]) : [];

    // 用首个可对比的数值列判断趋势
    let trend = 'stable';
    for (let i = 0; i < Math.min(latestVals.length, prevVals.length); i++) {
      if (latestVals[i] !== prevVals[i]) {
        trend = latestVals[i] > prevVals[i] ? 'up' : 'down';
        break;
      }
    }

    return {
      indicator,
      data: series,
      latest,
      trend,
      update_time: (macro as any)?.timestamp || (macro as any)?.updateTime || new Date().toISOString(),
    };
  }

  protected wrap(data: DataFetchMacroResult): ToolResponse<DataFetchMacroResult> {
    return { success: true, data };
  }
}
