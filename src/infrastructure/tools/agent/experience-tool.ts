/**
 * Experience Tool Adapter - experience_query 工具定义
 *
 * 供 Agent 在决策时调用，查询历史经验作为参考
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { queryExperience } from "../../../services/intelligence/experience-manager.js";

export const experienceQueryTool: ToolDefinition = {
  name: "experience_query",
  label: "查询历史经验",
  description: "Query historical investment experiences from the experience base. " +
    "Use when making investment decisions to learn from past similar scenarios. " +
    "Returns relevant experiences with patterns, actions, and outcomes ranked by confidence.",
  parameters: Type.Object({
    scenario: Type.Optional(Type.String({
      description:
        "Scenario description to match (e.g., '突破前高', '跌破支撑位'). " +
        "Uses text similarity to find relevant experiences.",
    })),
    symbol: Type.Optional(Type.String({
      description:
        "Stock symbol to filter experiences (e.g., 'sh600519'). " +
        "Omit to search across all stocks.",
    })),
    conditions: Type.Optional(Type.Array(Type.String(), {
      description:
        "Market conditions to match (e.g., ['成交量放大', '均线多头排列']). " +
        "Filters experiences that match any of the provided conditions.",
    })),
  }),
  execute: async (_toolCallId, params: any) => {
    try {
      const results = queryExperience({
        scenario: params.scenario,
        symbol: params.symbol,
        conditions: params.conditions,
      });

      if (results.length === 0) {
        return {
          content: [{
            type: "text" as const,
            text: JSON.stringify({
              success: true,
              message: "No matching experiences found.",
              data: [],
            }, null, 2),
          }],
          details: null,
        };
      }

      // 格式化返回结果
      const formattedResults = results.map(exp => ({
        id: exp.id,
        scenario: exp.scenario,
        pattern: exp.pattern,
        outcomes: exp.outcomes,
        recommendation: exp.recommendation,
        reason: exp.reason,
        confidence: exp.confidence,
        last_updated: exp.last_updated,
      }));

      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            success: true,
            message: `Found ${results.length} relevant experience(s).`,
            data: formattedResults,
          }, null, 2),
        }],
        details: null,
      };
    } catch (e) {
      return {
        content: [{
          type: "text" as const,
          text: JSON.stringify({
            success: false,
            message: `Error querying experience: ${e}`,
            data: [],
          }, null, 2),
        }],
        details: null,
      };
    }
  },
};
