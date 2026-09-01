import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { stockIntelPrompt, StockIntelParams, StockIntelResult } from './prompt';

export class StockIntelTool extends BaseTool<StockIntelParams, StockIntelResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'stock_intel',
    category: 'data',
    version: '1.0.0',
    timeoutMs: 60000,
  };

  protected readonly prompt = stockIntelPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: StockIntelParams): ValidationResult {
    if (!args.symbol || !/^\d{6}$/.test(args.symbol)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbol',
        issue: 'symbol 必填且须为 6 位数字',
        received: args.symbol,
        expected: '6位数字，如 600519',
      };
    }
    const validKinds = ['announcements', 'news', 'insider', 'all'];
    if (args.kind && !validKinds.includes(args.kind)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'kind',
        issue: 'kind 非法',
        received: args.kind,
        expected: validKinds.join(' | '),
      };
    }
    return { success: true };
  }

  protected async execute(args: StockIntelParams, _context: ToolContext): Promise<StockIntelResult> {
    const kind = args.kind || 'all';
    const symbol = args.symbol;
    const degraded: string[] = [];

    const want = (k: string) => kind === 'all' || kind === k;

    const [annRes, newsRes, insiderRes] = await Promise.all([
      want('announcements') ? this.qv2.getStockAnnouncements(symbol) : Promise.resolve(null),
      want('news') ? this.qv2.getStockNews(symbol) : Promise.resolve(null),
      want('insider') ? this.qv2.getInsiderTrades(symbol) : Promise.resolve(null),
    ]);

    const announcements = annRes?.success ? this.extractRows(annRes) : [];
    const news = newsRes?.success ? this.extractRows(newsRes) : [];
    const insider = insiderRes?.success ? this.extractRows(insiderRes) : [];

    if (annRes && !annRes.success) degraded.push(`announcements: ${annRes.error || 'failed'}`);
    if (newsRes && !newsRes.success) degraded.push(`news: ${newsRes.error || 'failed'}`);
    if (insiderRes && !insiderRes.success) degraded.push(`insider: ${insiderRes.error || 'failed'}`);

    const available = announcements.length > 0 || news.length > 0 || insider.length > 0;

    // 信号摘要：高管增持/减持计数
    let insiderSignal = '';
    if (insider.length) {
      const text = JSON.stringify(insider);
      const buyCount = (text.match(/增持|买入/g) || []).length;
      const sellCount = (text.match(/减持|卖出/g) || []).length;
      insiderSignal = `内部人交易 ${insider.length} 条（增持×${buyCount} 减持×${sellCount}）`;
    }

    const parts: string[] = [];
    if (announcements.length) parts.push(`公告 ${announcements.length} 条`);
    if (news.length) parts.push(`新闻 ${news.length} 条`);
    if (insiderSignal) parts.push(insiderSignal);

    return {
      symbol,
      available,
      announcements: announcements.length ? announcements : undefined,
      news: news.length ? news : undefined,
      insider_trades: insider.length ? insider : undefined,
      summary: parts.length ? parts.join('；') : undefined,
      degraded_sources: degraded.length ? degraded : undefined,
      note: available ? undefined : '三源均无数据或不可用',
    };
  }

  private extractRows(res: any): Array<Record<string, any>> {
    const d = res?.data;
    if (!d) return [];
    if (Array.isArray(d)) return d;
    if (Array.isArray(d.data)) return d.data;
    if (Array.isArray(d.records)) return d.records;
    return [];
  }
}
