/**
 * Market Sentiment Analysis Tool
 *
 * Analyzes market sentiment indicators: panic/fear index, margin trading activity,
 * northbound capital flows, market news sentiment, and hot stock trends.
 * Provides a composite sentiment score (0-100) to quantify market fear/greed levels,
 * helping avoid panic selling during extreme fear or greedy chasing at market tops.
 *
 * This tool now delegates to the quantsys CLI market.sentiment command.
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantCli } from "../../quant/quant-cli-client.js";

export const testMarketSentimentTool: ToolDefinition = {
  name: "test_market_sentiment",
  label: "分析市场情绪",
  description:
    "Analyze market sentiment indicators (fear/greed index, margin trading, northbound capital flow). " +
    "Provides a composite sentiment score (0-100) to quantify market fear/greed levels, helping users " +
    "avoid panic selling during extreme fear or chasing bubbles during extreme greed. " +
    "Returns sentiment score, individual indicator breakdown, and actionable advice. " +
    "Use this before making major buy/sell decisions to understand market emotion context.",
  parameters: Type.Object({}),
  execute: async (_toolCallId, _params: any) => {
    try {
      const response = await runQuantCli("market", "sentiment", {});
      return {
        content: [{ type: "text" as const, text: JSON.stringify(response, null, 2) }],
        details: response,
      };
    } catch (error) {
      return {
        content: [
          {
            type: "text" as const,
            text: `市场情绪分析失败: ${error instanceof Error ? error.message : String(error)}`,
          },
        ],
        details: { error: error instanceof Error ? error.message : String(error) },
      };
    }
  },
};
