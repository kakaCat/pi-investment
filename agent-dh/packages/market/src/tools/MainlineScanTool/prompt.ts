/**
 * MainlineScanTool - 市场主线扫描工具
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

// 参数类型
export interface MainlineScanParams {
  days?: number; // 板块表现统计窗口（交易日），默认 5
}

// 返回结果类型
export interface MainlineScanResult {
  date: string; // 日期
  mainlines: Array<{
    rank: number;
    sector: string;
    code?: string;
    change_pct?: number;
    market_cap?: number;
    type?: string;
    basis: string;
  }>;
  skipped?: boolean; // true=今日已落库，未重复写入
  [key: string]: any;
}

/**
 * ToolPrompt 定义
 */
export const mainlineScanPrompt: ToolPrompt<MainlineScanParams, MainlineScanResult> = {
  description: '识别当日市场主线 Top3（强势板块聚类：涨幅+资金流向），落库时间序列（scope=market:mainline）。催化剂关联（政策/事件）由盘后例程的 LLM 结合 web_search 补充。幂等：同日重复调用跳过。供：主线→标的映射（M2-1）、每日复盘主线一致率统计。',

  useCases: [
    '识别当日市场主线 Top3',
    '落库时间序列供后续分析',
    '供主线→标的映射使用',
    '每日复盘主线一致率统计',
  ],

  examples: [
    'mainline_scan() // 使用默认5日窗口识别当日主线',
    'mainline_scan({ days: 10 }) // 使用10日窗口识别当日主线',
  ],
  notes: [
    '每日盘后例程调用一次',
    '幂等：同日重复调用跳过',
    '催化剂关联由盘后例程 LLM 结合 web_search 补充',
  ],
  relatedTools: ['mainline_stocks'],

  parameters: {
    days: {
      type: 'integer',
      description: '板块表现统计窗口（1-30 交易日），默认 5',
      default: 5,
      minimum: 1,
      maximum: 30,
      example: 5,
    },
  },

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        date: { type: 'string', description: '日期（YYYY-MM-DD）' },
        mainlines: {
          type: 'array',
          items: { type: 'object', additionalProperties: true },
          description: '主线列表 Top3',
        },
        skipped: { type: 'boolean', description: 'true=今日已落库，未重复写入' },
      },
      additionalProperties: true,
    },
    render: (_args: MainlineScanParams, data: MainlineScanResult) => [{
      type: 'text',
      text: JSON.stringify(data, null, 2),
    }],
  },
};
