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

  /**
   * 价格/日期真实性校验（2026-09-11，REQ-342799）：与当日真实K线对账。
   * 规则：①该日必须存在K线（非交易日/无数据 → 拒绝）②|price/close-1| ≤ 15%（离谱价 → 拒绝）。
   * 取数通道异常时不阻塞写入，但返回 close=undefined 让调用方看到『未校验』。
   */
  private async checkPriceSanity(
    symbol: string,
    date: string,
    price: number,
  ): Promise<{ ok: boolean; reason?: string; close?: number }> {
    try {
      const raw: any = await (this.qv2Client as any).getKlines(symbol, date, date, 'daily');
      const rows: any[] = Array.isArray(raw) ? raw : (raw?.klines ?? []);
      const close = Number(rows?.[0]?.close);
      if (!rows.length || !Number.isFinite(close) || close <= 0) {
        return { ok: false, reason: '日期 ' + date + ' 在 ' + symbol + ' 的K线中不存在（非交易日或数据缺失）' };
      }
      const dev = Math.abs(price / close - 1);
      if (dev > 0.15) {
        return {
          ok: false,
          reason: 'price=' + price + ' 与 ' + date + ' 真实收盘 ' + close + ' 偏离 ' + (dev * 100).toFixed(1) + '%（阈值 15%）',
          close,
        };
      }
      return { ok: true, close };
    } catch {
      return { ok: true, close: undefined };
    }
  }
  protected async execute(params: SignalTrackParams, context: ToolContext): Promise<any> {
    const { action } = params;

    if (action === 'record') {
      // 记录买入信号
      const signal_date = params.signal_date || new Date().toISOString().slice(0, 10);

      // 2026-09-11 新增（REQ-342799 P1 续）：写入前与真实行情对账。
      // 起因：账本 16 条中 4 条 600519 为测试/自检写入——价格编造为 1800/1850.5（真实收盘约 1292，
      // 偏离 +43%），且 3 条日期落在非交易日（周末），却参与胜率统计，直接制造出
      // 『A 级 5 日胜率 0%、平均 -28.9%』这一假结论。信号账本是决策质量的唯一事实来源，
      // 写入不可对账的记录会污染仓位规则评估，故在此硬拦。
      const sanity = await this.checkPriceSanity(params.symbol!, signal_date, params.price!);
      if (!sanity.ok) {
        throw new Error(
          'signal_track(record) 拒绝写入：' + sanity.reason +
          '。请改用真实成交/行情价与交易日（REQ-342799：信号账本不得写入无法与行情对账的记录）。',
        );
      }
      const priceCheck = sanity.close
        ? 'verified(close=' + sanity.close + ', dev=' + (Math.abs(params.price! / sanity.close - 1) * 100).toFixed(2) + '%)'
        : 'bypassed(kline 不可用，未校验)';

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
        details: { ...result, price_check: priceCheck, signal_date },
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
