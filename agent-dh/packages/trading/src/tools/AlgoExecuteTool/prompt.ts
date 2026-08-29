/**
 * AlgoExecuteTool - 算法交易工具提示词和类型定义
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

/**
 * 参数类型
 */
export interface AlgoExecuteParams {
  action: 'BUY' | 'SELL';
  symbol: string;
  quantity: number;
  algo?: 'TWAP' | 'VWAP';
  duration?: number;
  account_name?: string;
}

/**
 * 返回值类型
 */
export interface AlgoExecuteResult {
  algo_order_id: string;
  algo: string;
  symbol: string;
  total_quantity: number;
  filled_quantity: number;
  avg_price: number;
  slices: Array<{
    order_id: string;
    quantity: number;
    price: number;
    timestamp: string;
    [key: string]: any;
  }>;
  status: string;
  [key: string]: any;
}

/**
 * 工具提示词
 */
export const algoExecutePrompt: ToolPrompt<AlgoExecuteParams, AlgoExecuteResult> = {
  description: '算法交易（大单拆分）：用 TWAP/VWAP 将大单拆成多笔小单分批成交，降低市场冲击、减少滑点。适用于：大额交易（>5000股或市值>50万）；高敏感标的（流动性差或波动大）。小单直接用 portfolio_trade。',

  useCases: [
    '大额交易降低市场冲击',
    '流动性差的标的分批成交',
    '避免单笔大单导致价格波动',
  ],

  examples: [
    {
      title: 'TWAP 买入 1000 股，30 分钟均匀分批',
      params: {
        action: 'BUY',
        symbol: '600519',
        quantity: 1000,
        algo: 'TWAP',
        duration: 30,
        account_name: 'agent_virtual',
      },
      expectedResult: '返回算法订单ID、拆分的子单列表、成交均价',
    },
    {
      title: 'VWAP 卖出 2000 股，按成交量加权分配',
      params: {
        action: 'SELL',
        symbol: '000001',
        quantity: 2000,
        algo: 'VWAP',
        account_name: 'agent_virtual',
      },
      expectedResult: '返回算法订单ID、拆分的子单列表、成交均价',
    },
  ],

  notes: [
    '建议用于大额交易（>5000股或市值>50万）',
    '小额交易直接用 portfolio_trade 更简单',
    '执行进度用 trade_monitor 跟踪',
    '时长越长市场冲击越小，但价格漂移风险越大',
  ],

  relatedTools: [
    'portfolio_trade',
    'trade_monitor',
    'account_info',
  ],

  parameters: {
    action: {
      type: 'string',
      description: 'BUY：买入；SELL：卖出',
      required: true,
      enum: ['BUY', 'SELL'],
    },
    symbol: {
      type: 'string',
      description: 'A股6位数字股票代码，如 600519',
      required: true,
    },
    quantity: {
      type: 'integer',
      description: '交易数量（股）。建议 >5000 股或市值 >50万 时使用算法交易',
      required: true,
    },
    algo: {
      type: 'string',
      description: '算法类型：TWAP=时间均匀分布（默认），VWAP=成交量加权',
      enum: ['TWAP', 'VWAP'],
      default: 'TWAP',
    },
    duration: {
      type: 'integer',
      description: '执行时长（分钟），默认 30 分钟。时长越长，冲击越小，但执行风险越大',
      default: 30,
    },
    account_name: {
      type: 'string',
      description: '账户名称，默认 agent_virtual',
      default: 'agent_virtual',
    },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        algo_order_id: { type: 'string', description: '算法订单ID' },
        algo: { type: 'string', description: '算法类型' },
        symbol: { type: 'string', description: '股票代码' },
        total_quantity: { type: 'integer', description: '总数量' },
        filled_quantity: { type: 'integer', description: '已成交数量' },
        avg_price: { type: 'number', description: '成交均价' },
        slices: { type: 'array', description: '拆分的子单列表' },
        status: { type: 'string', description: '状态' },
      },
      additionalProperties: true,
    },
    render: (args, value) => [{
      type: 'text',
      text: JSON.stringify(value, null, 2),
    }],
  },
};
