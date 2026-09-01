/**
 * PePercentileTool - PE 历史分位工具
 */

import { BaseTool, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { pePercentilePrompt, PePercentileParams } from './prompt';

export class PePercentileTool extends BaseTool<PePercentileParams, any> {
  protected readonly metadata: ToolMetadata = {
    name: 'pe_percentile',
    category: 'data',
    version: '1.0.0',
    timeoutMs: 60000,
  };

  protected readonly prompt = pePercentilePrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: PePercentileParams): ValidationResult {
    if (!args.symbol || !/^\d{6}$/.test(args.symbol)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbol',
        issue: 'symbol 必须是6位数字股票代码',
        received: String(args.symbol ?? ''),
        expected: '6位数字',
        example: '601857',
      };
    }
    return { success: true };
  }

  protected async execute(args: PePercentileParams, _context: ToolContext): Promise<any> {
    const r: any = await this.qv2.getPePercentile(args.symbol);
    // 后端 camelCase → 工具层 snake_case 契约
    return sanitizeLossless({
      symbol: r.symbol ?? args.symbol,
      name: r.name,
      current_pe: r.currentPe ?? r.current_pe,
      current_price: r.currentPrice ?? r.current_price,
      percentile: r.percentile,
      min_pe: r.minPe ?? r.min_pe,
      max_pe: r.maxPe ?? r.max_pe,
      mean_pe: r.meanPe ?? r.mean_pe,
      median_pe: r.medianPe ?? r.median_pe,
      data_points: r.dataPoints ?? r.data_points,
      years: r.years,
      interpretation: r.interpretation,
    });
  }

  protected wrap(data: any, _context: ToolContext): ToolResponse<any> {
    return { success: true, data };
  }
}
