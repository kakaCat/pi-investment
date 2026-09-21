import type { ToolPrompt } from '@pi-investment/core-tool';

export interface DataFetchMarketSentimentParams {}

export interface DataFetchMarketSentimentResult {
  sentiment_score: number;
  sentiment_level: string;
  fear_greed_index: number;
  advance_decline_ratio: number;
  market_phase: string;
  recommendation: string;
  indicators: Record<string, any>;
  [key: string]: any;
}

export const dataFetchMarketSentimentPrompt: ToolPrompt<DataFetchMarketSentimentParams, DataFetchMarketSentimentResult> = {
  description: '获取市场整体情绪指标：情绪评分、恐慌贪婪指数（0-100）、涨跌家数比、量能状态、波动率、新高新低比。适用于：判断市场恐慌/贪婪程度、评估短期系统性风险。',

  useCases: ['判断市场情绪', '评估系统性风险'],

  parameters: {},

  output: {
    schema: {
      type: 'object', additionalProperties: true,
      properties: {
        sentiment_score: { type: 'number' },
        sentiment_level: { type: 'string' },
        fear_greed_index: { type: 'number' },
        advance_decline_ratio: { type: 'number' },
        market_phase: { type: 'string' },
        recommendation: { type: 'string' },
        indicators: { type: 'object', additionalProperties: true},
      },
    },
    render: (args, data) => [{ type: 'text', text: JSON.stringify(data, null, 2) }],
  },
};
