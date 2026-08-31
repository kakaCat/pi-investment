/**
 * AccountInfoTool - 提示词定义
 *
 * 工具描述：获取虚拟账户资产总览
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface AccountInfoParams {
  account_name?: string;
}

export interface AccountInfoResult {
  accountName: string;
  totalValue: number;
  totalCost: number;
  totalMarketValue: number;
  totalPnl: number;
  totalPnlPct: number;
  dailyChange: number;
  positions: number;
  cash: number;
  liquidAssets: number;
  profitCount: number;
  lossCount: number;
  lastUpdated: string;
  /** 行情陈旧标记：true=本次行情拉取失败，市值/盈亏基于旧价 */
  priceStale?: boolean;
}

export const accountInfoPrompt: ToolPrompt<AccountInfoParams, AccountInfoResult> = {
  description:
    '获取虚拟账户资产总览：总资产、持仓市值、可用资金、总盈亏、当日涨跌、盈利/亏损持仓数。' +
    '适用于：交易前确认可用资金、盘后复盘账户整体表现。只读操作，可随时调用。查看逐只持仓明细用 position_list。',

  useCases: [
    '交易前确认可用资金',
    '盘后复盘账户表现',
    '查看总盈亏情况',
  ],

  examples: [
    {
      title: '查看账户信息',
      params: {},
      expectedResult: '总资产: 100万元, 可用资金: 20万元, 盈利: +5%',
    },
  ],

  notes: [
    '💡 只读操作，可随时调用',
    '💡 查看持仓明细用 position_list',
    '⏱️  lastUpdated 为调用时刻实时刷新的行情时间戳；priceStale=true 表示行情拉取失败、盈亏基于旧价',
  ],

  relatedTools: ['position_list', 'portfolio_trade'],

  parameters: {
    account_name: {
      type: 'string',
      description: '账户名称，默认 agent_virtual（Agent 虚拟交易账户）。除非配置了多账户，否则无需传入',
      default: 'agent_virtual',
      example: 'agent_virtual',
    },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        accountName: { type: 'string', description: '账户名称' },
        totalValue: { type: 'number', description: '总资产（元）' },
        totalCost: { type: 'number', description: '总成本（元）' },
        totalMarketValue: { type: 'number', description: '持仓市值（元）' },
        totalPnl: { type: 'number', description: '总盈亏（元）' },
        totalPnlPct: { type: 'number', description: '总盈亏比例（%）' },
        dailyChange: { type: 'number', description: '当日涨跌（元）' },
        positions: { type: 'integer', description: '持仓数量（只）' },
        cash: { type: 'number', description: '可用资金（元）' },
        liquidAssets: { type: 'number', description: '流动资产（元）' },
        profitCount: { type: 'integer', description: '盈利持仓数' },
        lossCount: { type: 'integer', description: '亏损持仓数' },
        lastUpdated: { type: 'string', description: '更新时间（调用时刻实时刷新）' },
        priceStale: { type: 'boolean', description: '行情陈旧标记：true=行情拉取失败，盈亏基于旧价' },
      },
      additionalProperties: true,
    },
    render: (args: AccountInfoParams, data: AccountInfoResult) => {
      let output = `## 账户总览 - ${data.accountName}\n\n`;

      // 资产概览
      output += `### 💰 资产概览\n`;
      output += `- **总资产**: ${(data.totalValue / 10000).toFixed(2)} 万元\n`;
      output += `- **持仓市值**: ${(data.totalMarketValue / 10000).toFixed(2)} 万元\n`;
      output += `- **可用资金**: ${(data.cash / 10000).toFixed(2)} 万元 (${((data.cash / data.totalValue) * 100).toFixed(1)}%)\n`;
      output += `- **流动资产**: ${(data.liquidAssets / 10000).toFixed(2)} 万元\n\n`;

      // 盈亏情况
      const pnlIcon = data.totalPnl >= 0 ? '📈' : '📉';
      const pnlColor = data.totalPnl >= 0 ? '✅' : '❌';
      output += `### ${pnlIcon} 盈亏情况\n`;
      output += `- **总盈亏**: ${pnlColor} ${(data.totalPnl / 10000).toFixed(2)} 万元 (${data.totalPnlPct.toFixed(2)}%)\n`;
      output += `- **总成本**: ${(data.totalCost / 10000).toFixed(2)} 万元\n`;
      output += `- **当日涨跌**: ${data.dailyChange >= 0 ? '+' : ''}${(data.dailyChange / 10000).toFixed(2)} 万元\n\n`;

      // 持仓统计
      output += `### 📊 持仓统计\n`;
      output += `- **持仓数量**: ${data.positions} 只\n`;
      output += `- **盈利持仓**: ${data.profitCount} 只\n`;
      output += `- **亏损持仓**: ${data.lossCount} 只\n`;
      if (data.positions > 0) {
        const winRate = ((data.profitCount / data.positions) * 100).toFixed(1);
        output += `- **胜率**: ${winRate}%\n`;
      }
      output += `\n**更新时间**: ${data.lastUpdated}\n`;

      return [{ type: 'text', text: output }];
    },
  },
};
