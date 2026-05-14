/**
 * Check Stop Loss Trigger Tool
 *
 * Monitors portfolio holdings against stop-loss thresholds.
 * Automatically checks if any positions have triggered stop-loss conditions.
 */
import type { ToolDefinition } from "./index.js";
import { Type } from "@sinclair/typebox";
import { PortfolioService } from "../../services/portfolio/portfolio-service.js";

export const checkStopLossTriggerTool: ToolDefinition = {
  name: "check_stop_loss_trigger",
  label: "检查止损触发",
  description:
    "Check if any portfolio holdings have triggered stop-loss conditions. " +
    "Compares current prices against configured stop-loss thresholds for each position. " +
    "Returns list of positions that need stop-loss action, helping improve risk management execution. " +
    "Use this regularly to avoid letting losses expand.",
  parameters: Type.Object({}),
  execute: async (_toolCallId, _params: any) => {
    try {
      const piDir = ".pi-invest";
      const portfolioService = new PortfolioService(piDir);

      // Get current portfolio snapshot with real-time prices
      const snapshot = await portfolioService.getSnapshot();

      if (snapshot.holdings.length === 0) {
        return {
          content: [{
            type: "text" as const,
            text: "当前无持仓",
          }],
          details: undefined,
        };
      }

      // Check each holding for stop-loss trigger
      const triggered: Array<{
        symbol: string;
        name: string;
        currentPrice: number;
        avgCost: number;
        stopLoss: number;
        pnlPct: number;
        quantity: number;
        marketValue: number;
      }> = [];

      const warnings: Array<{
        symbol: string;
        name: string;
        currentPrice: number;
        avgCost: number;
        stopLoss: number;
        pnlPct: number;
        distanceToStopLoss: number;
      }> = [];

      for (const holding of snapshot.holdings) {
        // Read portfolio.json to get stop_loss field
        const portfolioData = portfolioService.getHoldings();
        const holdingData = portfolioData.find(h => h.symbol === holding.symbol);

        if (!holdingData || !holdingData.stop_loss) {
          // No stop loss configured for this position
          continue;
        }

        const stopLoss = Number(holdingData.stop_loss);
        const currentPrice = holding.current_price;

        // Check if stop loss triggered
        if (currentPrice <= stopLoss) {
          triggered.push({
            symbol: holding.symbol,
            name: holding.name,
            currentPrice,
            avgCost: holding.avg_cost,
            stopLoss,
            pnlPct: holding.pnl_pct,
            quantity: holding.quantity,
            marketValue: holding.market_value,
          });
        } else {
          // Check if approaching stop loss (within 3%)
          const distancePct = ((currentPrice - stopLoss) / stopLoss) * 100;
          if (distancePct < 3) {
            warnings.push({
              symbol: holding.symbol,
              name: holding.name,
              currentPrice,
              avgCost: holding.avg_cost,
              stopLoss,
              pnlPct: holding.pnl_pct,
              distanceToStopLoss: distancePct,
            });
          }
        }
      }

      // Format output
      let output = `# 止损检查报告\n\n`;

      if (triggered.length === 0 && warnings.length === 0) {
        output += `✅ 所有持仓均未触发止损条件\n`;
        return {
          content: [{
            type: "text" as const,
            text: output,
          }],
          details: { triggered: [], warnings: [] },
        };
      }

      if (triggered.length > 0) {
        output += `## ⚠️ 已触发止损 (${triggered.length}个)\n\n`;
        triggered.forEach(t => {
          output += `### ${t.name} (${t.symbol})\n`;
          output += `- 当前价: ¥${t.currentPrice.toFixed(2)}\n`;
          output += `- 止损价: ¥${t.stopLoss.toFixed(2)}\n`;
          output += `- 成本价: ¥${t.avgCost.toFixed(2)}\n`;
          output += `- 盈亏: ${t.pnlPct.toFixed(2)}%\n`;
          output += `- 持仓: ${t.quantity}股 (市值¥${t.marketValue.toFixed(0)})\n`;
          output += `- **建议: 立即执行止损卖出**\n\n`;
        });
      }

      if (warnings.length > 0) {
        output += `## ⚡ 接近止损 (${warnings.length}个)\n\n`;
        warnings.forEach(w => {
          output += `### ${w.name} (${w.symbol})\n`;
          output += `- 当前价: ¥${w.currentPrice.toFixed(2)}\n`;
          output += `- 止损价: ¥${w.stopLoss.toFixed(2)}\n`;
          output += `- 距离止损: ${w.distanceToStopLoss.toFixed(2)}%\n`;
          output += `- 盈亏: ${w.pnlPct.toFixed(2)}%\n`;
          output += `- **建议: 密切关注，准备止损**\n\n`;
        });
      }

      return {
        content: [{
          type: "text" as const,
          text: output,
        }],
        details: {
          triggered,
          warnings,
        },
      };
    } catch (e) {
      return {
        content: [{
          type: "text" as const,
          text: `止损检查失败: ${e instanceof Error ? e.message : String(e)}`,
        }],
        details: undefined,
      };
    }
  },
};
