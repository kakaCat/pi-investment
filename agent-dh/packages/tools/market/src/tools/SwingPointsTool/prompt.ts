/**
 * SwingPointsTool - ZigZag 波段买卖点分析工具
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

// 参数类型
export interface SwingPointsParams {
  symbol: string; // A股6位数字股票代码
  start_date?: string; // 开始日期 YYYY-MM-DD（默认回溯1年）
  end_date?: string; // 结束日期 YYYY-MM-DD（默认今天）
  min_change?: number; // 最小波动幅度 %（默认5，范围1-30）
}

// 返回结果类型
export interface SwingPointsResult {
  symbol: string;
  period: { start: string; end: string };
  min_change: number;
  kline_count?: number;
  swing_points: Array<{ date: string; price: number; type: 'high' | 'low'; change_pct: number }>;
  trades: Array<{ buy_date: string; buy_price: number; sell_date: string; sell_price: number; profit_pct: number; holding_days: number }>;
  summary: {
    total_trades: number; win_count: number; loss_count: number;
    win_rate: number; total_return: number; avg_return: number;
    max_return: number; max_loss: number; avg_holding_days: number;
  };
  latest_swing?: { date: string; price: number; type: 'high' | 'low' };
  message?: string;
  error?: string;
  suggestions?: string[];
  [key: string]: any;
}

/**
 * ToolPrompt 定义
 */
export const swingPointsPrompt: ToolPrompt<SwingPointsParams, SwingPointsResult> = {
  description: 'ZigZag 波段分析：基于历史价格波动识别拐点，配对成"低点买→高点卖"交易序列并统计胜率。适用于：回答"XX买卖点"、找历史验证过的买入区、评估标的波段特性（胜率/平均收益/持仓天数）、链式扫描时批量比较产业链各标的的波段弹性。解读参考：最近一个 low 拐点=当前处于上升段（参考下一卖点为前高），最近一个 high 拐点=处于回调段（等下一个 low）；多次出现的低位区=历史验证买区。',

  useCases: [
    '回答"XX股票买卖点"类问题（最高频场景）',
    '寻找历史验证过的买入区（多次出现的 low 拐点价位带）',
    '评估标的波段特性：胜率/平均收益/平均持仓天数',
    '链式扫描：批量跑产业链标的，按胜率+弹性排序挑最强',
  ],

  examples: [
    'swing_points({ symbol: "601857" }) // 中石油默认1年5%阈值波段分析',
    'swing_points({ symbol: "601857", min_change: 3 }) // 降低阈值抓更细波段',
    'swing_points({ symbol: "601857", start_date: "2025-01-01", end_date: "2026-09-01" })',
  ],

  notes: [
    '⚠️ 后视偏差：历史胜率由 ZigZag 配对算法构造性偏高（拐点确认后才能成交），实盘收益必低于回测统计，胜率仅用于横向比较标的波段特性，不构成收益承诺',
    '最后一个拐点可能是未确认极值（趋势仍在发展中），下单前须用 data_fetch_quote 核对现价与最近拐点的相对位置',
    'min_change 默认 5%：大盘蓝筹适用；小盘/题材股波动大建议 8-10%，抓精细波段可降到 3%',
    'K线数据不足时返回 error+suggestions（如代码错误、日期范围太窄），按建议修正',
    '结合 chip_analysis（支撑/压力位）与 regime（市场环境）综合判断，不单独作为买入依据',
  ],

  relatedTools: ['chip_analysis', 'data_fetch_kline', 'factor_calculate'],

  parameters: {
    symbol: {
      type: 'string',
      description: 'A股6位数字股票代码，如 601857',
      required: true,
      example: '601857',
    },
    start_date: {
      type: 'string',
      description: '开始日期 YYYY-MM-DD，默认回溯1年',
      example: '2025-01-01',
    },
    end_date: {
      type: 'string',
      description: '结束日期 YYYY-MM-DD，默认今天',
      example: '2026-09-01',
    },
    min_change: {
      type: 'number',
      description: '最小反转幅度 %（1-30），默认 5。小盘股建议 8-10，精细波段可 3',
      example: '5',
    },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        symbol: { type: 'string', description: '股票代码' },
        swing_points: { type: 'array', description: '拐点序列（date/price/type/change_pct）' },
        trades: { type: 'array', description: '配对交易序列（买低点→卖高点）' },
        summary: { type: 'object', additionalProperties: true, description: '胜率/收益统计' },
        latest_swing: { type: 'object', additionalProperties: true, description: '最近一个拐点' },
      },
      additionalProperties: true,
    },
    render: (_args: SwingPointsParams, data: SwingPointsResult) => [{
      type: 'text',
      text: JSON.stringify(data, null, 2),
    }],
  },
};
