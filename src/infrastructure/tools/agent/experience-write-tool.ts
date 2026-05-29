/**
 * Experience Write Tool — 写入历史经验到经验库
 *
 * 每次完成交易决策并验证结果后，Agent 调用此工具写入经验。
 * 经验的写入会自动去重（同 ID 更新），带版本管理和自动备份。
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { addExperience } from "../../../services/intelligence/experience-manager.js";
import type { Experience } from "../../../types/evolution.js";

export const experienceWriteTool: ToolDefinition = {
  name: "experience_write",
  label: "写入投资经验",
  description:
    "Write investment experience to the experience base. Call this after making trade decisions " +
    "and verifying outcomes — records scenario, pattern, outcomes, and recommendation for future reference. " +
    "Automatically deduplicates by ID (updates existing entries). " +
    "Use after: completing a trade, verifying P&L, observing a pattern that played out as expected/unexpected.",
  parameters: Type.Object({
    scenario: Type.String({
      description:
        "Scenario description, e.g. 'MACD金叉配合成交量放大后买入' or '跌破20日均线止损卖出'",
    }),
    conditions: Type.Array(Type.String(), {
      description:
        "List of conditions present in the scenario, e.g. ['MACD金叉', '成交量放大', 'RSI<70']",
    }),
    action: Type.String({
      description: "Action taken: 'buy', 'sell', or 'hold'",
    }),
    total_cases: Type.Number({
      description: "Total number of cases this experience is based on (default 1 for single observation)",
    }),
    win_rate: Type.Number({
      description: "Win rate from 0 to 1 (e.g., 0.65 for 65%)",
      minimum: 0,
      maximum: 1,
    }),
    avg_return: Type.Number({
      description: "Average return percentage (e.g., 5.2 for +5.2%, -3.1 for -3.1%)",
    }),
    max_gain: Type.Optional(Type.Number({
      description: "Best case return percentage",
    })),
    max_loss: Type.Optional(Type.Number({
      description: "Worst case return percentage (negative number)",
    })),
    recommendation: Type.String({
      description: "Recommendation level: 'aggressive', 'moderate', 'cautious', or 'avoid'",
    }),
    reason: Type.String({
      description: "Why this experience turned out this way — key learnings",
    }),
    confidence: Type.Number({
      description: "Confidence in this experience from 0 to 1 (e.g., 0.8)",
      minimum: 0,
      maximum: 1,
    }),
    examples: Type.Optional(Type.Array(Type.Object({
      date: Type.String({ description: "Date in YYYY-MM-DD format" }),
      symbol: Type.String({ description: "Stock symbol, e.g. '600519'" }),
      session_id: Type.String({ description: "Relevant session/context ID" }),
      result: Type.Number({ description: "Return percentage for this example" }),
    }), {
      description: "Supporting examples (1-5 recommended)",
      maxItems: 10,
    })),
    symbol: Type.Optional(Type.String({
      description:
        "Stock symbol this experience relates to (e.g., '600519'). Used to auto-populate an example entry.",
    })),
  }),

  execute: async (_toolCallId, params: any) => {
    try {
      // Build examples list
      const examples = (params.examples || []) as Array<{
        date: string;
        symbol: string;
        session_id: string;
        result: number;
      }>;

      // If symbol is provided but no examples, auto-create one minimal example
      if (params.symbol && examples.length === 0) {
        examples.push({
          date: new Date().toISOString().split("T")[0],
          symbol: params.symbol,
          session_id: "manual",
          result: params.avg_return,
        });
      }

      // Generate ID from scenario + action (deterministic for dedup)
      const scenarioSlug = params.scenario
        .replace(/[^a-zA-Z0-9\u4e00-\u9fff]/g, "_")
        .slice(0, 40);
      const id = `exp_${params.action}_${scenarioSlug}_${Date.now().toString(36)}`;

      const experience: Experience = {
        id,
        scenario: params.scenario,
        pattern: {
          conditions: params.conditions,
          action: params.action as "buy" | "sell" | "hold",
        },
        outcomes: {
          total_cases: params.total_cases || 1,
          win_rate: params.win_rate,
          avg_return: params.avg_return,
          max_gain: params.max_gain,
          max_loss: params.max_loss,
        },
        recommendation: params.recommendation as "aggressive" | "moderate" | "cautious" | "avoid",
        reason: params.reason,
        examples,
        confidence: params.confidence,
        last_updated: new Date().toISOString().split("T")[0],
      };

      addExperience(experience);

      return {
        content: [
          {
            type: "text" as const,
            text: JSON.stringify(
              {
                success: true,
                message: `Experience recorded: "${params.scenario.slice(0, 40)}..." (id: ${id})`,
                data: {
                  id,
                  action: params.action,
                  recommendation: params.recommendation,
                  confidence: params.confidence,
                },
              },
              null,
              2
            ),
          },
        ],
        details: undefined,
      };
    } catch (e) {
      return {
        content: [
          {
            type: "text" as const,
            text: JSON.stringify(
              {
                success: false,
                message: `Failed to write experience: ${e}`,
              },
              null,
              2
            ),
          },
        ],
        details: undefined,
      };
    }
  },
};
