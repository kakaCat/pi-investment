import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { fundFlowPrompt, FundFlowParams, FundFlowResult } from './prompt';

export class FundFlowTool extends BaseTool<FundFlowParams, FundFlowResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'fund_flow',
    category: 'data',
    version: '1.0.0',
    timeoutMs: 45000,
  };

  protected readonly prompt = fundFlowPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: FundFlowParams): ValidationResult {
    if (args.symbol !== undefined && !/^\d{6}$/.test(args.symbol)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbol',
        issue: 'symbol 须为 6 位数字股票代码',
        received: args.symbol,
        expected: '6位数字，如 600519',
      };
    }
    if (args.days !== undefined && (typeof args.days !== 'number' || args.days < 1 || args.days > 30)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'days',
        issue: 'days 必须是 1-30',
        received: args.days,
        expected: '1-30',
      };
    }
    return { success: true };
  }

  protected async execute(args: FundFlowParams, _context: ToolContext): Promise<FundFlowResult> {
    const degraded: string[] = [];

    // 板块资金流模式
    if (!args.symbol) {
      const res = await this.qv2.getSectorFlow();
      if (!res.success) {
        return {
          mode: 'sector',
          available: false,
          degraded_sources: res.attempted_sources ?? ['unknown'],
          note: res.error || '板块资金流数据源暂不可用',
        };
      }
      const rows = this.extractRows(res);
      return {
        mode: 'sector',
        available: rows.length > 0,
        sector_flow: rows,
        summary: rows.length ? `板块资金流 ${rows.length} 条` : '数据源返回空',
        source: res.source,
        // 2026-09-11（REQ-342799）：后端 /api/market/sector-flow 的窗口由 indicator 决定（默认『今日』），
        // 源不返回精确数据日期 → 显式标注，避免被当作任意日期或历史区间使用。
        window_indicator: '今日（数据源为最近交易日快照，未返回精确日期）',
        freshness_note: '板块资金流无日期字段，新鲜度未知；如需精确日期请用个股模式（fund_flow({symbol})）',
      } as any;
    }

    // 个股模式：资金流 + 两融 并发拉取
    const days = args.days ?? 5;
    const [flowRes, marginRes] = await Promise.all([
      this.qv2.getStockFundFlow(args.symbol, days),
      this.qv2.getStockMargin(args.symbol, days),
    ]);

    const fundFlow = flowRes.success ? this.extractRows(flowRes) : [];
    const margin = marginRes.success ? this.extractRows(marginRes) : [];
    if (!flowRes.success) degraded.push(`fund-flow: ${flowRes.error || 'failed'}`);
    if (!marginRes.success) degraded.push(`margin: ${marginRes.error || 'failed'}`);

    const available = fundFlow.length > 0 || margin.length > 0;
    let summary = '';
    if (fundFlow.length) {
      const latest = fundFlow[0];
      const main = latest.mainNetInflow;
      summary = `最新主力净流入 ${main ?? '?'}万（${latest.date}）`;
    }
    if (margin.length) {
      const m0 = margin[0];
      summary += `${summary ? '；' : ''}两融余额 ${m0.totalBalance ?? '?'}万（${m0.date}）`;
    }

    // 2026-09-11 修复（REQ-342799）：实测个股资金流最新只到 2026-09-09（当时为 09-11），
    // 旧实现仅把日期写进 summary 文本、不标注新鲜度，容易被当成当日资金流使用。
    const latestDate = fundFlow.find((r: any) => r?.date)?.date ?? null;
    const stalenessDays = latestDate
      ? Math.round((Date.now() - new Date(latestDate + 'T00:00:00+08:00').getTime()) / 86400000)
      : null;

    return {
      mode: `stock:${args.symbol}`,
      available,
      data_date: latestDate,
      staleness_days: stalenessDays,
      freshness_note: latestDate
        ? (stalenessDays !== null && stalenessDays >= 2
          ? '资金流最新日期 ' + latestDate + '，距调用日 ' + stalenessDays + ' 天 → 非当日数据，勿当今日资金流使用'
          : '资金流日期 ' + latestDate)
        : '数据源未返回日期字段，新鲜度未知',
      fund_flow: fundFlow,
      margin,
      summary: summary || undefined,
      degraded_sources: degraded.length ? degraded : undefined,
      note: available ? undefined : '个股资金流与两融数据源均暂不可用',
    };
  }

  /**
   * data_provider 层包裹结构不一，统一提取记录数组。实测四种形态（2026-09-10）：
   *   1) res.data 直接是数组
   *   2) res.data.data 是数组（个股资金流 / 两融：{symbol, days, data: [...], ...}）
   *   3) res.data.records 是数组
   *   4) res.data.data 是 { records: [...], total } 嵌套对象（板块资金流全景）
   * 修复背景：板块模式曾因形态 4 未被识别 → extractRows 返回 [] → available=false
   * → render 误报「数据源暂不可用」——实际后端接口正常（curl 200 全量 90 条）。
   */
  private extractRows(res: any): Array<Record<string, any>> {
    const d = res?.data;
    if (!d) return [];
    if (Array.isArray(d)) return d;
    if (Array.isArray(d.data)) return d.data;
    if (Array.isArray(d.records)) return d.records;
    if (d.data && typeof d.data === 'object' && Array.isArray(d.data.records)) return d.data.records;
    return [];
  }
}
