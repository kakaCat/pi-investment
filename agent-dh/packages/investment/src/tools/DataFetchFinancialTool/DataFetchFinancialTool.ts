/**
 * DataFetchFinancialTool - 获取股票财务数据工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { dataFetchFinancialPrompt, DataFetchFinancialParams, DataFetchFinancialResult } from './prompt';

export class DataFetchFinancialTool extends BaseTool<DataFetchFinancialParams, DataFetchFinancialResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'data_fetch_financial',
    category: 'data',
    version: '2.0.0',
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
    const rawData = await this.qv2.getFinancialData(args.symbol);

    // 后端返回的是嵌套结构，需要转换为扁平格式
    // 取最新一期数据（income_statement[0], balance_sheet[0]）
    const latest_income = rawData.income_statement?.[0];
    const latest_balance = rawData.balance_sheet?.[0];

    if (!latest_income) {
      throw new Error('未获取到财务数据');
    }

    // 计算资产负债率
    const debt_ratio = latest_balance?.total_liabilities && latest_balance?.total_assets
      ? (latest_balance.total_liabilities / latest_balance.total_assets) * 100
      : 0;

    // 转换为工具期望的扁平格式
    return {
      symbol: args.symbol,
      name: rawData.name || args.symbol,
      report_date: latest_income.report_date,
      revenue: (latest_income.revenue || 0) / 100000000, // 转换为亿元
      net_profit: (latest_income.parent_net_profit || 0) / 100000000, // 转换为亿元
      total_assets: (latest_balance?.total_assets || 0) / 100000000, // 转换为亿元
      total_liabilities: (latest_balance?.total_liabilities || 0) / 100000000, // 转换为亿元
      roe: latest_income.weighted_roe || 0,
      eps: latest_income.basic_eps || 0,
      pe_ttm: 0, // 后端未返回，需要额外计算或从其他接口获取
      pb: 0, // 后端未返回，需要额外计算或从其他接口获取
      debt_ratio: debt_ratio,
      gross_margin: latest_income.gross_margin || 0,
    } as DataFetchFinancialResult;
  }

  protected wrap(data: DataFetchFinancialResult): ToolResponse<DataFetchFinancialResult> {
    return { success: true, data };
  }
}
