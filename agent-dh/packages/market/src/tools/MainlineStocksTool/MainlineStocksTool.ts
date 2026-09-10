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
    // 2026-09-11 修复（REQ-342799）：后端板块字典与 sector_analysis 返回的行业名并不一致
    //（实测『船舶制造』可查，『电力行业』『玻璃行业』报 Sector not found），旧实现直接抛原始错误、无任何指引。
    const wanted = args.sector.trim();
    let res: any;
    try {
      res = await this.qv2.getSectorStocks(wanted);
    } catch (e: any) {
      const msg = String(e?.message ?? e);
      if (!/not found/i.test(msg)) throw e;
      const candidates = await this.suggestSectors(wanted);
      let lastErr: any = e;
      for (const c of candidates) {
        try { res = await this.qv2.getSectorStocks(c); lastErr = null; break; } catch (e2: any) { lastErr = e2; }
      }
      if (!res) {
        throw new Error(
          'mainline_stocks 无法定位板块 "' + wanted + '"：' + msg + '。' +
          (candidates.length ? '已尝试相近候选：' + candidates.join('、') + '。' : '') +
          '提示：本工具的板块字典与 sector_analysis 返回的行业名不一致，请先看 sector_analysis 的 name 再传参；' +
          '仍失败时说明该板块不在成分股字典中（不是数据为空）。',
        );
      }
    }

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
   * 板块名候选（2026-09-11，REQ-342799）：仅在后端报 not found 时用于重试，不改变调用语义。
   * 取 sector_analysis 的行业列表做『去后缀精确 → 包含 → 被包含』三级匹配。
   */
  private async suggestSectors(wanted: string): Promise<string[]> {
    try {
      const list: any = await this.qv2.getSectorAnalysis({});
      const inds: any[] = list?.data?.industries ?? list?.industries ?? [];
      const norm = (s: any) => String(s ?? '').replace(/行业|板块|Ⅱ|Ⅲ|Ⅰ|\(.*?\)/g, '').trim();
      const w = norm(wanted);
      if (!w) return [];
      const exact = inds.filter((x) => x?.name && norm(x.name) === w).map((x) => x.name);
      const fuzzy = inds.filter((x) => x?.name && norm(x.name).includes(w)).map((x) => x.name);
      const loose = inds.filter((x) => x?.name && norm(x.name) && w.includes(norm(x.name))).map((x) => x.name);
      return [...new Set([...exact, ...fuzzy, ...loose])].slice(0, 5);
    } catch {
      return [];
    }
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
