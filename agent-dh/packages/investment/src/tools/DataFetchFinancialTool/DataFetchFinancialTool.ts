/**
 * DataFetchFinancialTool - 获取股票财务数据工具
 */

import { BaseTool, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { dataFetchFinancialPrompt, DataFetchFinancialParams, DataFetchFinancialResult } from './prompt';

export class DataFetchFinancialTool extends BaseTool<DataFetchFinancialParams, DataFetchFinancialResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'data_fetch_financial',
    category: 'data',
    version: '2.1.0',
    timeoutMs: 15000,
  };

  protected readonly prompt = dataFetchFinancialPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: DataFetchFinancialParams): ValidationResult {
    if (!args.symbol || !/^\d{6}$/.test(args.symbol)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbol',
        issue: 'symbol 必须是6位纯数字',
        received: args.symbol,
        expected: '6位数字（例如 600519）',
        example: '600519',
      };
    }
    return { success: true };
  }

  protected async execute(
    args: DataFetchFinancialParams,
    context: ToolContext
  ): Promise<DataFetchFinancialResult> {
    // 2026-08-30 修复：/api/v2/stock/{symbol}/financials 的 sina-web 指标源失效（全 null），
    // 优先用 provider sina-statements（真实报表），失败再退回原接口。
    let rawData: any = null;
    let pe = 0;
    let pb = 0;
    try {
      const statements = await this.qv2.getFinancialStatements(args.symbol);
      rawData = statements?.data ?? statements;
    } catch {
      rawData = await this.qv2.getFinancialData(args.symbol);
    }

    // 2026-09-01：PE/PB 取自 /api/v2/stock/{symbol}/financials（后端已从 stocks 表
    // 补充 pe/pb 字段，见 financials_async.py）——此前硬编码 0，估值维度失真。
    try {
      const fin = await this.qv2.getFinancialData(args.symbol);
      pe = Number(fin?.pe) || 0;
      pb = Number(fin?.pb) || 0;
    } catch {
      // 补取失败保持 0，不阻断主流程
    }

    // 兼容两种结构：income_statement/balance_sheet（旧）或 income/balance（sina-statements）
    const latest_income = rawData?.income_statement?.[0] ?? rawData?.income?.[0];
    const latest_balance = rawData?.balance_sheet?.[0] ?? rawData?.balance?.[0];

    if (!latest_income) {
      throw new Error('未获取到财务数据');
    }

    const num = (v: any): number => (typeof v === 'number' && Number.isFinite(v) ? v : 0);
    const get = (row: any, zh: string, en: string): number => num(row?.[zh] ?? row?.[en]);

    const revenue = get(latest_income, '营业总收入', 'revenue');
    const income = get(latest_income, '营业收入', 'revenue');
    const cost = get(latest_income, '营业成本', 'operating_cost');
    const net_profit = get(latest_income, '归属于母公司所有者的净利润', 'parent_net_profit');
    const total_assets = get(latest_balance, '资产总计', 'total_assets');
    const total_liabilities = get(latest_balance, '负债合计', 'total_liabilities');
    const equity = get(latest_balance, '归属于母公司股东权益合计', 'total_equity');

    const revenueY = revenue / 100000000;
    const netProfitY = net_profit / 100000000;
    const totalAssetsY = total_assets / 100000000;
    const totalLiabilitiesY = total_liabilities / 100000000;
    const round2 = (v: number): number => (Number.isFinite(v) ? Math.round(v * 100) / 100 : 0);

    return sanitizeLossless({
      symbol: args.symbol,
      name: rawData?.name || args.symbol,
      report_date: String(latest_income['报告日'] ?? latest_income.report_date ?? ''),
      revenue: round2(revenueY),
      net_profit: round2(netProfitY),
      total_assets: round2(totalAssetsY),
      total_liabilities: round2(totalLiabilitiesY),
      roe: equity > 0 ? round2((net_profit / equity) * 100) : 0,
      eps: round2(get(latest_income, '基本每股收益', 'basic_eps')),
      pe_ttm: round2(pe), // 2026-09-01：从 stocks 表补充（此前硬编码 0）
      pb: round2(pb), // 2026-09-01：从 stocks 表补充（此前硬编码 0）
      debt_ratio: total_assets > 0 ? round2((total_liabilities / total_assets) * 100) : 0,
      gross_margin: income > 0 ? round2(((income - cost) / income) * 100) : 0,
    } as unknown as DataFetchFinancialResult);
  }

  protected wrap(data: DataFetchFinancialResult): ToolResponse<DataFetchFinancialResult> {
    return { success: true, data };
  }
}
