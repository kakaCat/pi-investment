/**
 * DataFetchFinancialTool - 获取股票财务数据
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface DataFetchFinancialParams {
  symbol: string;
}

export interface DataFetchFinancialResult {
  symbol: string;
  name: string;
  report_date: string;
  revenue: number;
  net_profit: number;
  total_assets: number;
  total_liabilities: number;
  roe: number;
  eps: number;
  pe_ttm: number;
  pb: number;
  debt_ratio: number;
  gross_margin: number;
  [key: string]: any;
}

export const dataFetchFinancialPrompt: ToolPrompt<DataFetchFinancialParams, DataFetchFinancialResult> = {
  description: '获取股票最新一期财务数据：营收、净利润、总资产、ROE、EPS、PE-TTM、PB、资产负债率、毛利率等核心指标。适用于：基本面分析、价值投资筛选、评估公司盈利能力与财务健康度。数据随财报季更新（季报/年报），非实时；判断短期价格走势应结合 data_fetch_quote 与 data_fetch_kline。',

  useCases: [
    '基本面分析',
    '价值投资筛选',
    '评估盈利能力和财务健康度',
  ],

  examples: [
    {
      title: '获取贵州茅台财务数据',
      params: { symbol: '600519' },
      expectedResult: 'ROE: 25%, PE: 30, PB: 10',
    },
  ],

  notes: [
    '💡 数据随财报季更新，非实时',
    '💡 短期价格走势应结合行情数据',
  ],

  relatedTools: ['data_fetch_quote', 'data_fetch_kline'],

  parameters: {
    symbol: {
      type: 'string',
      description: 'A股6位数字股票代码，如 600519',
      required: true,
      example: '600519',
    },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        symbol: { type: 'string', description: '股票代码' },
        name: { type: 'string', description: '公司名称' },
        report_date: { type: 'string', description: '报告期' },
        revenue: { type: 'number', description: '营业收入（亿元）' },
        net_profit: { type: 'number', description: '净利润（亿元）' },
        total_assets: { type: 'number', description: '总资产（亿元）' },
        total_liabilities: { type: 'number', description: '总负债（亿元）' },
        roe: { type: 'number', description: 'ROE（%）' },
        eps: { type: 'number', description: 'EPS（元）' },
        pe_ttm: { type: 'number', description: 'PE-TTM' },
        pb: { type: 'number', description: 'PB' },
        debt_ratio: { type: 'number', description: '资产负债率（%）' },
        gross_margin: { type: 'number', description: '毛利率（%）' },
      },
      additionalProperties: true,
    },
    render: (args: DataFetchFinancialParams, data: DataFetchFinancialResult) => {
      let output = `## ${data.name} (${data.symbol}) 财务数据\n\n`;
      output += `**报告期**: ${data.report_date}\n\n`;

      output += `### 💰 盈利能力\n`;
      output += `- **营业收入**: ${data.revenue.toFixed(2)} 亿元\n`;
      output += `- **净利润**: ${data.net_profit.toFixed(2)} 亿元\n`;
      output += `- **ROE**: ${data.roe.toFixed(2)}%\n`;
      output += `- **EPS**: ${data.eps.toFixed(2)} 元\n`;
      output += `- **毛利率**: ${data.gross_margin.toFixed(2)}%\n\n`;

      output += `### 📊 估值指标\n`;
      output += `- **PE-TTM**: ${data.pe_ttm.toFixed(2)}\n`;
      output += `- **PB**: ${data.pb.toFixed(2)}\n\n`;

      output += `### 🏦 资产负债\n`;
      output += `- **总资产**: ${data.total_assets.toFixed(2)} 亿元\n`;
      output += `- **总负债**: ${data.total_liabilities.toFixed(2)} 亿元\n`;
      output += `- **资产负债率**: ${data.debt_ratio.toFixed(2)}%\n`;

      return [{ type: 'text', text: output }];
    },
  },
};
