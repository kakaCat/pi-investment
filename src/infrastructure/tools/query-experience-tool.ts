/**
 * Query Experience Tool Definition
 *
 * Agent 工具：查询历史经验库
 */

import { Type } from '@sinclair/typebox';
import { queryAndFormatExperience } from '../../services/intelligence/experience-query.js';

export const queryExperienceTool = {
  name: 'query_experience',
  description: `查询历史经验库，获取类似场景的成功/失败案例。

使用场景：
- 在做买入/卖出决策前，查询类似情况的历史表现
- 评估某个技术形态或基本面条件的历史胜率
- 了解特定股票在类似条件下的历史表现

返回信息包括：
- 历史案例的胜率和平均收益
- 具体的成功/失败案例
- 基于历史数据的建议（aggressive/moderate/cautious/avoid）
- 置信度评分`,

  parameters: Type.Object({
    scenario: Type.String({
      description: '场景描述，例如："MACD金叉且成交量放大"、"跌破止损位"、"追涨买入"'
    }),
    symbol: Type.Optional(Type.String({
      description: '可选：股票代码，用于查询该股票的历史经验'
    })),
    conditions: Type.Optional(Type.Array(Type.String(), {
      description: '可选：条件列表，例如 ["RSI>70", "涨幅>5%"]'
    })),
    limit: Type.Optional(Type.Number({
      description: '返回结果数量限制，默认 5 条',
      default: 5
    }))
  }),

  handler: async (params: {
    scenario: string;
    symbol?: string;
    conditions?: string[];
    limit?: number;
  }) => {
    try {
      const result = queryAndFormatExperience(params);
      return result;
    } catch (e) {
      return `查询经验库失败: ${e instanceof Error ? e.message : String(e)}`;
    }
  }
};
