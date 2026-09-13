/**
 * SlippageReportTool - 滑点报告工具提示词和类型定义
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

/**
 * 参数类型
 */
export interface SlippageReportParams {
  symbol?: string;
}

/**
 * 返回值类型
 */
export interface SlippageReportResult {
  total_fills: number;
  avg_slippage_pct: number;
  max_slippage_pct: number;
  by_symbol: Array<{
    symbol: string;
    fills: number;
    avg_slippage_pct: number;
    max_slippage_pct: number;
    [key: string]: any;
  }>;
  [key: string]: any;
}

/**
 * 工具提示词
 */
export const slippageReportPrompt: ToolPrompt<SlippageReportParams, SlippageReportResult> = {
  description: '滑点追踪报告（数据源=v2 挂单记录 simulation_pending_orders 的决策价/成交价；Agent OS 的 trade:slippage 记忆仅为兜底）——成交笔数、平均/最大滑点、逐笔明细。滑点=成交价 vs 决策时价（方向归一：正值=买贵/卖便宜）。供：评估模拟盘与真实成交的差距（P6 接真金前必看）、执行质量复盘。',

  useCases: [
    '评估模拟盘与真实成交的差距',
    '执行质量复盘',
    '分析不同标的的滑点表现',
  ],

  examples: [
    {
      title: '查看全部标的滑点',
      params: {},
      expectedResult: '返回全部成交记录的滑点统计',
    },
    {
      title: '查看单个标的滑点',
      params: {
        symbol: '600519',
      },
      expectedResult: '返回该标的的滑点统计',
    },
  ],

  notes: [
    '滑点 = 成交价 vs 决策时价（正值 = 买贵/卖便宜）',
    '数据来源：trade:slippage 落库记录',
    '接入真实账户前必看的执行质量指标',
    '只读操作，不会修改任何数据',
  ],

  relatedTools: [
    'trade_monitor',
    'algo_execute',
    'trade_verify',
  ],

  parameters: {
    symbol: {
      type: 'string',
      description: '可选：只看某只标的',
    },
    days: {
      type: 'number',
      description: '回溯天数（1-365），默认 30',
      default: 30,
    },
    account_name: {
      type: 'string',
      description: '账户名（默认本实例投资账户）',
    },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        // ⚠️ 2026-09-13（w-c8cae280）：**无成交时后端返回 null**（avg/max/total 无定义），
        // 而这些字段原先声明为 number → 工具在"没有滑点数据"这个最常见的情形下必然失败。
        // 实测报错：value.avg_slippage_bps / max_slippage_bps / cost_bps_total must be a number。
        // 规则：**schema 要比数据宽，不能比数据严**（可空字段一律 oneOf [type, null]）。
        total_fills: { oneOf: [{ type: 'number' }, { type: 'null' }], description: '参与统计的成交笔数（决策价与成交价都有值）' },
        missing_decision_price: { oneOf: [{ type: 'number' }, { type: 'null' }], description: '已成交但缺决策价的笔数（单列，不按 0 计入均值）' },
        avg_slippage_bps: { oneOf: [{ type: 'number' }, { type: 'null' }], description: '平均滑点（基点；正=买贵/卖便宜=成本）；无成交为 null' },
        max_slippage_bps: { oneOf: [{ type: 'number' }, { type: 'null' }], description: '最大滑点（基点）；无成交为 null' },
        cost_bps_total: { oneOf: [{ type: 'number' }, { type: 'null' }], description: '滑点合计（基点）；无成交为 null' },
        records: { type: 'array', description: '逐笔：决策价/成交价/滑点/来源', items: { type: 'object', additionalProperties: true } },
        source: { oneOf: [{ type: 'string' }, { type: 'null' }], description: '数据来源（v2挂单记录 / Agent OS 记忆兜底）' },
      },
    },
    render: (_args, value) => [{
      type: 'text',
      text: JSON.stringify(value, null, 2),
    }],
  },
};
