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
  shares_available: number;
  cost_price: number;
  current_price: number;
  market_value: number;
  pnl: number;
  pnl_pct: number;
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
          shares_available: { type: 'integer', description: '可卖数量（股），受T+1限制' },
          cost_price: { type: 'number', description: '成本价（元）' },
          current_price: { type: 'number', description: '当前价（元）' },
          market_value: { type: 'number', description: '市值（元）' },
          pnl: { type: 'number', description: '盈亏（元）' },
          pnl_pct: { type: 'number', description: '盈亏比例（%）' },
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
        totalMarketValue += pos.market_value;
        totalPnl += pos.pnl;
        if (pos.pnl > 0) profitCount++;
        if (pos.pnl < 0) lossCount++;
        if (pos.shares_available < pos.quantity) t1RestrictedCount++;
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
      const sortedData = [...data].sort((a, b) => a.pnl_pct - b.pnl_pct);

      for (const pos of sortedData) {
        const pnlIcon = pos.pnl >= 0 ? '✅' : '❌';
        const t1Warning = pos.shares_available < pos.quantity ? '⚠️' : '';

        output += `| ${pos.symbol} | ${pos.name} | ${pos.quantity} | ${pos.shares_available}${t1Warning} | `;
        output += `${pos.cost_price.toFixed(2)} | ${pos.current_price.toFixed(2)} | `;
        output += `${(pos.market_value / 10000).toFixed(2)} | `;
        output += `${pnlIcon} ${(pos.pnl / 10000).toFixed(2)}万 | `;
        output += `${pos.pnl_pct >= 0 ? '+' : ''}${pos.pnl_pct.toFixed(2)}% |\n`;
      }

      if (t1RestrictedCount > 0) {
        output += `\n⚠️ 标记为受T+1限制的股票当日不可卖出\n`;
      }

      return [{ type: 'text', text: output }];
    },
  },
};
