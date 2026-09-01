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

    return {
      mode: `stock:${args.symbol}`,
      available,
      fund_flow: fundFlow,
      margin,
      summary: summary || undefined,
      degraded_sources: degraded.length ? degraded : undefined,
      note: available ? undefined : '个股资金流与两融数据源均暂不可用',
    };
  }

  /** data_provider 层包裹结构不一，统一提取记录数组 */
  private extractRows(res: any): Array<Record<string, any>> {
    const d = res?.data;
    if (!d) return [];
    if (Array.isArray(d)) return d;
    if (Array.isArray(d.data)) return d.data;
    if (Array.isArray(d.records)) return d.records;
    return [];
  }
}
