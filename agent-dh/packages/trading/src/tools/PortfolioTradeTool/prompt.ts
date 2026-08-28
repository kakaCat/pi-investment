/**
 * PortfolioTradeTool - 提示词定义
 *
 * 工具描述：执行虚拟仓买卖委托
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface PortfolioTradeParams {
  action: 'BUY' | 'SELL';
  symbol: string;
  quantity: number;
  price?: number;
  reason?: string;
  account_name?: string;
}

export interface PortfolioTradeResult {
  order_id: string;
  action: string;
  symbol: string;
  quantity: number;
  price: number;
  amount: number;
  status: 'filled' | 'partial' | 'rejected';
  timestamp: string;
}

export const portfolioTradePrompt: ToolPrompt<PortfolioTradeParams, PortfolioTradeResult> = {
  description:
    '执行虚拟仓买卖委托（写操作，立即成交并改变持仓）。' +
    '执行前应先确认：用 account_info 查可用资金、用 position_list 查可卖数量、用 risk_controller 计算建议仓位。',

  useCases: [
    '买入看好的标的建仓',
    '卖出持仓止盈或止损',
    '调仓换股',
    '清仓离场',
  ],

  examples: [
    {
      title: '买入贵州茅台',
      params: {
        action: 'BUY',
        symbol: '600519',
        quantity: 100,
        reason: 'R-001 买入前确认：资金充足、仓位合规',
      },
      expectedResult: '订单ID: xxx, 成交价: 1850.00, 状态: filled',
    },
    {
      title: '卖出持仓止损',
      params: {
        action: 'SELL',
        symbol: '600519',
        quantity: 100,
        reason: '止损：跌破支撑位',
      },
      expectedResult: '订单ID: xxx, 成交价: 1820.00, 状态: filled',
    },
  ],

  notes: [
    '⚠️  宪法第1条：仅 A股交易日 9:30-11:30、13:00-15:00 可执行买卖委托',
    '⚠️  R-008：下单前必须检索历史经验',
    '⚠️  买入前会自动检查：熔断状态、仓位上限、ST禁区',
    '💡 大额订单考虑用 algo_execute 拆单以降低冲击',
  ],

  relatedTools: ['account_info', 'position_list', 'risk_controller'],

  parameters: {
    action: {
      type: 'string',
      description: 'BUY：买入；SELL：卖出',
      required: true,
      enum: ['BUY', 'SELL'],
      example: 'BUY',
    },
    symbol: {
      type: 'string',
      description: 'A股6位数字股票代码，如 600519',
      required: true,
      example: '600519',
    },
    quantity: {
      type: 'integer',
      description: '交易数量（股），买入必须是100的整数倍',
      required: true,
      example: 100,
    },
    price: {
      type: 'number',
      description: '委托价格（元）。不传则按市价成交',
      required: false,
      example: 1850.0,
    },
    reason: {
      type: 'string',
      description: '决策依据（强烈建议填写）：引用规则ID + 理由',
      required: false,
      example: 'R-001 买入前确认：资金充足、仓位合规',
    },
    account_name: {
      type: 'string',
      description: '账户名称，默认 agent_virtual',
      required: false,
      default: 'agent_virtual',
      example: 'agent_virtual',
    },
  },

  output: {
    schema: {
      type: 'object',
      properties: {
        order_id: { type: 'string', description: '订单ID' },
        action: { type: 'string', description: '操作方向' },
        symbol: { type: 'string', description: '股票代码' },
        quantity: { type: 'integer', description: '成交数量' },
        price: { type: 'number', description: '成交价格' },
        amount: { type: 'number', description: '成交金额' },
        status: { type: 'string', description: '状态：filled/partial/rejected' },
        timestamp: { type: 'string', description: '成交时间' },
      },
      additionalProperties: true,
    },
    render: (args: PortfolioTradeParams, value: PortfolioTradeResult) => {
      if (value.status === 'filled') {
        return [{
          type: 'text',
          text:
            `✅ 交易成功\n` +
            `操作: ${value.action} ${value.symbol}\n` +
            `数量: ${value.quantity}股\n` +
            `价格: ¥${value.price.toFixed(2)}\n` +
            `金额: ¥${value.amount.toFixed(2)}\n` +
            `订单ID: ${value.order_id}\n` +
            `时间: ${value.timestamp}`,
        }];
      }

      if (value.status === 'partial') {
        return [{
          type: 'text',
          text: `⚠️  部分成交: ${value.symbol} ${value.quantity}股，订单ID: ${value.order_id}`,
        }];
      }

      return [{
        type: 'text',
        text: `❌ 交易被拒绝: ${value.symbol}，订单ID: ${value.order_id}`,
      }];
    },
  },
};
