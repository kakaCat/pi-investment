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
  description:
    '⚠️ **本工具当前不下单**（2026-09-13 实测）：后端 /api/orders/algo-execute 只生成 TWAP/VWAP ' +
    '切片计划并返回 filled_quantity=0，不接交易服务、不过 trade_guard、不动资金与持仓。' +
    '需要真实成交请用 portfolio_trade 分批下真实单（每笔仍走 R-001/R-002）。' +
    '保留本工具仅作切片计划参考；返回体含 executed=false 与 plan_only_note。',

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
        account_name: 'agent_brain',
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
        account_name: 'agent_brain',
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
      description: '账户名称，必填：agent-dh 自有账户 agent_brain（agent_virtual 属 agent-ts，禁止写入）',
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
