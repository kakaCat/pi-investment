/**
 * Manipulation Detection Tool Prompt
 *
 * 操纵检测 - 检测个股操纵迹象（拉高出货/对倒/异常放量），识别操纵周期（M7-3）
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

export interface ManipulationDetectParams {
  symbol: string;
  days?: number;
}

export interface ManipulationDetectResult {
  symbol: string;
  risk_level: string;
  signals: string[];
  volume_anomaly: boolean;
  price_pump: boolean;
  wash_trade: boolean;
  description: string;
}

export const manipulationDetectPrompt: ToolPrompt<ManipulationDetectParams, ManipulationDetectResult> = {
  description: '检测个股操纵迹象（异常放量/拉高出货/对倒交易），评估操纵风险等级。用于识别游资拉高出货陷阱、避免高位接盘。',

  useCases: [
    '识别拉高出货陷阱',
    '评估个股操纵风险',
    '识别操纵后超跌机会',
  ],

  examples: [
    {
      title: '检测某只股票的操纵迹象',
      params: { symbol: '600519', days: 20 },
      expectedResult: '返回操纵风险等级与信号列表',
    },
  ],

  notes: [
    '💡 基于量价异常识别操纵信号',
  ],

  relatedTools: [],

  parameters: {
    symbol: {
      type: 'string',
      description: '股票代码（6位数字）',
      example: '600519',
    },
    days: {
      type: 'number',
      description: '检测回溯天数',
      default: 20,
    },
  },

  output: {
    schema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        symbol: { type: 'string' },
        risk_level: { type: 'string' },
        signals: { type: 'array', items: { type: 'string' } },
        volume_anomaly: { type: 'boolean' },
        price_pump: { type: 'boolean' },
        wash_trade: { type: 'boolean' },
        description: { type: 'string' },
      },
    },
    render: (_args: ManipulationDetectParams, data: ManipulationDetectResult) => [{
      type: 'text',
      text: [
        `## 操纵检测 ${data.symbol}`,
        '',
        `**风险等级**: ${data.risk_level}`,
        `**异常放量**: ${data.volume_anomaly ? '是' : '否'} | **拉高出货**: ${data.price_pump ? '是' : '否'} | **对倒嫌疑**: ${data.wash_trade ? '是' : '否'}`,
        ...(data.signals?.length ? ['', '**信号**:', ...data.signals.map((s: string) => `- ${s}`)] : []),
        '',
        data.description ?? '',
      ].join('\n'),
    }],
  },
};
