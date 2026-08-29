/**
 * MainlineStocksTool - 主线个股明细查询工具
 */

import { BaseTool } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { mainlineStocksPrompt, MainlineStocksParams, MainlineStocksResult } from './prompt';

/**
 * 主线个股明细查询工具类
 */
export class MainlineStocksTool extends BaseTool<MainlineStocksParams, MainlineStocksResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'mainline_stocks',
    category: 'market',
    version: '1.0.0',
    timeoutMs: 60000, // 板块个股查询可能较慢
  };

  protected readonly prompt = mainlineStocksPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(args: MainlineStocksParams): ValidationResult {
    if (!args.sector || typeof args.sector !== 'string' || args.sector.trim().length === 0) {
      return {
        success: false,
        issue: 'sector 参数必须是非空字符串',
      };
    }
    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(args: MainlineStocksParams, _context: ToolContext): Promise<MainlineStocksResult> {
    const days = args.days ?? 5;

    // 调用 quantsys-v2 获取板块成分股
    const res: any = await this.qv2.getSectorStocks(args.sector.trim());

    // 响应结构宽容解析
    const stocks: any[] = res?.stocks || res?.items || res?.components || [];

    const mappedStocks = stocks.map((s: any) => ({
      symbol: s.symbol ?? s['股票代码'] ?? s.code ?? '',
      name: s.name ?? s['股票名称'] ?? s.stock_name ?? '',
      change_pct: s.change_pct ?? s['涨跌幅'] ?? s.changePct ?? s.pct ?? null,
      volume: s.volume ?? s['成交量'] ?? s.vol ?? null,
      market_cap: s.market_cap ?? s['总市值'] ?? s.cap ?? null,
      industry: s.industry ?? s['所属行业'] ?? s.sector ?? null,
      note: s.note ?? null,
    }));

    return {
      sector: args.sector,
      stocks: mappedStocks,
      days,
    };
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: MainlineStocksResult, _context: ToolContext): ToolResponse<MainlineStocksResult> {
    return {
      success: true,
      data: result,
    };
  }
}
