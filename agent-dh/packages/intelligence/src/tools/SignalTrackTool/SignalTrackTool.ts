import { BaseTool, ToolResponse, ValidationResult, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { signalTrackPrompt, type SignalTrackParams } from './prompt';

export class SignalTrackTool extends BaseTool<SignalTrackParams, any> {
  protected readonly metadata: ToolMetadata = {
    name: 'signal_track',
    category: 'intelligence',
    version: '1.0.0',
    timeoutMs: 10000,
  };

  protected readonly prompt = signalTrackPrompt;

  constructor(private qv2Client: QuantsysV2Client) {
    super();
  }

  protected validate(params: SignalTrackParams): ValidationResult {
    const { action, symbol, price, source, grade } = params;

    if (action === 'record') {
      // record 必填参数校验
      if (!symbol || !price || !source || !grade) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          issue: 'record 需要参数：symbol, price, source, grade',
        };
      }

      // 价格校验
      if (price <= 0) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          issue: 'price 必须大于 0',
        };
      }

      // source 校验
      const validSources = ['strategy_execute', 'opportunity_scan', 'mainline_stocks', 'watch_rule'];
      if (!validSources.includes(source)) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          issue: `source 必须是以下之一：${validSources.join(', ')}`,
        };
      }
    }

    return { success: true };
  }

  protected async execute(params: SignalTrackParams, context: ToolContext): Promise<any> {
    const { action } = params;

    if (action === 'record') {
      // 记录买入信号
      const signal_date = params.signal_date || new Date().toISOString().slice(0, 10);

      const result = await this.qv2Client.recordSignal({
        signal_date,
        symbol: params.symbol!,
        price: params.price!,
        source: params.source!,
        grade: params.grade as 'A' | 'B' | 'C',
        reason: params.reason,
      });

      return {
        action: 'record',
        result: `已记录信号 ID ${result.signalId}: ${params.symbol} (${params.grade}级)`,
        details: result,
      };
    }

    if (action === 'update') {
      // 盘后回填表现
      const result = await this.qv2Client.updateSignalPerformance({
        signal_date: params.signal_date,
        lookback_days: params.lookback_days || 30,
      });

      return {
        action: 'update',
        result: `已更新 ${result.updated} 个信号的表现数据`,
        details: result,
      };
    }

    if (action === 'report') {
      // 统计报告
      const result = await this.qv2Client.getSignalReport({
        start_date: params.start_date,
        end_date: params.end_date,
        grade: params.grade as 'A' | 'B' | 'C' | undefined,
        source: params.source,
      });

      // 生成摘要
      const gradeStats = Object.entries(result.byGrade || {})
        .filter(([_, v]: any) => v.count > 0)
        .map(([grade, stats]: any) =>
          `${grade}级: ${stats.count}个, 5日胜率${stats.hitRate5D ? (stats.hitRate5D * 100).toFixed(1) : 'N/A'}%`
        )
        .join(', ');

      return {
        action: 'report',
        result: `统计 ${result.total} 个信号 (${result.dateRange.start} ~ ${result.dateRange.end})。${gradeStats || '无数据'}`,
        details: result,
      };
    }

    throw new Error(`未知 action: ${action}`);
  }

  protected wrap(data: any, context: ToolContext): ToolResponse<any> {
    return {
      success: true,
      data,
      message: data.result,
      metadata: {
        action: data.action,
      },
    };
  }
}
