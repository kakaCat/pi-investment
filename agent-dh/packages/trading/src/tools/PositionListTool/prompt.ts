/**
 * PositionListTool - 提示词定义
 *
 * 工具描述：获取当前持仓明细
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface PositionListParams {
  account_name?: string;
}

export interface PositionItem {
  symbol: string;
  name: string;
  quantity: number;
  sharesAvailable: number;
  avgCost: number;
  currentPrice: number;
  totalCost: number;
  currentValue: number;
  profitLoss: number;
  profitLossPct: number;
  profitToday: number;
}

export type PositionListResult = PositionItem[];

export const positionListPrompt: ToolPrompt<PositionListParams, PositionListResult> = {
  description:
    '获取当前持仓明细：每只股票的持仓数量、可卖数量（受T+1限制）、成本价、现价、市值、盈亏。' +
    '适用于：调仓前核对持仓、止损检查时确认盈亏。卖出前必须确认 shares_available——当日买入的股份次日才可卖。',

  useCases: [
    '卖出前确认可卖数量（T+1限制）',
    '查看持仓盈亏情况',
    '调仓前核对持仓',
  ],

  examples: [
    {
      title: '查看持仓列表',
      params: {},
      expectedResult: '持仓3只：600519贵州茅台（+5%）、000858五粮液（-2%）、...',
    },
  ],

  notes: [
    '⚠️  卖出前必须确认 shares_available（T+1限制）',
    '💡 当日买入的股份次日才可卖',
  ],

  relatedTools: ['account_info', 'portfolio_trade'],

  parameters: {
    account_name: {
      type: 'string',
      description: '账户名称，默认 agent_virtual。除非配置了多账户，否则无需传入',
      default: 'agent_virtual',
      example: 'agent_virtual',
    },
  },

  output: {
    schema: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: true,
        properties: {
          symbol: { type: 'string', description: '股票代码' },
          name: { type: 'string', description: '股票名称' },
          quantity: { type: 'integer', description: '持仓数量（股）' },
          sharesAvailable: { type: 'integer', description: '可卖数量（股），受T+1限制' },
          avgCost: { type: 'number', description: '成本价（元）' },
          currentPrice: { type: 'number', description: '当前价（元）' },
          totalCost: { type: 'number', description: '总成本（元）' },
          currentValue: { type: 'number', description: '当前市值（元）' },
          profitLoss: { type: 'number', description: '盈亏（元）' },
          profitLossPct: { type: 'number', description: '盈亏比例（%）' },
          profitToday: { type: 'number', description: '今日盈亏（元）' },
        },
        additionalProperties: false,
      },
    },
    render: (args: PositionListParams, data: PositionListResult) => {
      // 空持仓处理
      if (data.length === 0) {
        return [{ type: 'text', text: '## 持仓列表\n\n当前无持仓' }];
      }

      // 统计分析
      let totalMarketValue = 0;
      let totalPnl = 0;
      let profitCount = 0;
      let lossCount = 0;
      let t1RestrictedCount = 0;

      for (const pos of data) {
        totalMarketValue += pos.currentValue;
        totalPnl += pos.profitLoss;
        if (pos.profitLoss > 0) profitCount++;
        if (pos.profitLoss < 0) lossCount++;
        if (pos.sharesAvailable < pos.quantity) t1RestrictedCount++;
      }

      const totalPnlPct = totalMarketValue > 0 ? (totalPnl / (totalMarketValue - totalPnl)) * 100 : 0;

      // 格式化输出
      let output = `## 持仓列表（${data.length} 只）\n\n`;

      // 持仓总览
      output += `### 📊 持仓总览\n`;
      output += `- **总市值**: ${(totalMarketValue / 10000).toFixed(2)} 万元\n`;
      output += `- **总盈亏**: ${totalPnl >= 0 ? '✅' : '❌'} ${(totalPnl / 10000).toFixed(2)} 万元 (${totalPnlPct.toFixed(2)}%)\n`;
      output += `- **盈利持仓**: ${profitCount} 只\n`;
      output += `- **亏损持仓**: ${lossCount} 只\n`;
      if (t1RestrictedCount > 0) {
        output += `- **T+1限制**: ${t1RestrictedCount} 只\n`;
      }
      output += `\n`;

      // 持仓明细表格
      output += `### 📋 持仓明细\n\n`;
      output += `| 代码 | 名称 | 数量 | 可卖 | 成本价 | 现价 | 市值(万) | 盈亏 | 盈亏率 |\n`;
      output += `|------|------|------|------|--------|------|----------|------|--------|\n`;

      // 按盈亏率排序（亏损在前）
      const sortedData = [...data].sort((a, b) => a.profitLossPct - b.profitLossPct);

      for (const pos of sortedData) {
        const pnlIcon = pos.profitLoss >= 0 ? '✅' : '❌';
        const t1Warning = pos.sharesAvailable < pos.quantity ? '⚠️' : '';

        output += `| ${pos.symbol} | ${pos.name} | ${pos.quantity} | ${pos.sharesAvailable}${t1Warning} | `;
        output += `${pos.avgCost.toFixed(2)} | ${pos.currentPrice.toFixed(2)} | `;
        output += `${(pos.currentValue / 10000).toFixed(2)} | `;
        output += `${pnlIcon} ${(pos.profitLoss / 10000).toFixed(2)}万 | `;
        output += `${pos.profitLossPct >= 0 ? '+' : ''}${pos.profitLossPct.toFixed(2)}% |\n`;
      }

      if (t1RestrictedCount > 0) {
        output += `\n⚠️ 标记为受T+1限制的股票当日不可卖出\n`;
      }

      return [{ type: 'text', text: output }];
    },
  },
};
