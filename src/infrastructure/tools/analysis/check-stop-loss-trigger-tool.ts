/**
 * Check Stop Loss Trigger Tool
 *
 * Monitors portfolio holdings against stop-loss thresholds.
 * For each position, the tool:
 *   1. Checks if an explicit stop_loss price is stored in portfolio.json
 *   2. If not set, falls back to a configurable percentage drawdown from avg_cost
 *   3. Fetches real-time prices for all holdings (via PortfolioService)
 *   4. Flags positions that have already triggered (current price ≤ stop-loss)
 *   5. Flags positions approaching stop-loss (within 3% of threshold)
 *   6. Reports positions that are safe with distance-to-stop-loss info
 *
 * Use this regularly to avoid letting losses expand. Best combined with
 * schedule_next_check for periodic automated monitoring.
 *
 * Expected impact: reduce max drawdown by catching positions before deep losses
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";

// ── Types used by the pure logic functions ────────────────────────────────

/**
 * Minimal holding data needed for stop-loss checking.
 * Compatible with both Holding (from file) and HoldingWithPnL (from snapshot).
 */
interface HoldingCheckData {
  symbol: string;
  name: string;
  quantity: number;
  avg_cost: number;
  current_price?: number;
  market_value?: number;
  pnl_pct?: number;
  pnl_amount?: number;
  stop_loss?: number | null;
}

enum CheckStatus {
  Triggered = "triggered",
  Warning = "warning",
  Safe = "safe",
  NoStopLoss = "no_stop_loss",
}

interface TriggeredPosition {
  symbol: string;
  name: string;
  currentPrice: number;
  avgCost: number;
  stopLoss: number;
  stopLossSource: "explicit" | "default";
  pnlPct: number;
  quantity: number;
  marketValue: number;
  lossAmount: number;
}

interface WarningPosition {
  symbol: string;
  name: string;
  currentPrice: number;
  avgCost: number;
  stopLoss: number;
  stopLossSource: "explicit" | "default";
  pnlPct: number;
  distanceToStopLoss: number;
  quantity: number;
  marketValue: number;
}

interface SafePosition {
  symbol: string;
  name: string;
  currentPrice: number;
  avgCost: number;
  stopLoss: number;
  stopLossSource: "explicit" | "default";
  pnlPct: number;
  distanceToStopLoss: number;
  quantity: number;
  marketValue: number;
}

interface NoStopLossPosition {
  symbol: string;
  name: string;
  currentPrice: number;
  avgCost: number;
  pnlPct: number;
  quantity: number;
  marketValue: number;
}

interface CheckDetail {
  totalHoldings: number;
  triggered: TriggeredPosition[];
  warnings: WarningPosition[];
  safe: SafePosition[];
  noStopLossConfigured: NoStopLossPosition[];
}

// ── Constants ──────────────────────────────────────────────────────────────

const WARNING_DISTANCE_PCT = 3; // Warn when price is within 3% of stop-loss

// ── Helpers ────────────────────────────────────────────────────────────────

function fmtPrice(v: number): string {
  return `¥${v.toFixed(2)}`;
}

function fmtPct(v: number): string {
  return `${v >= 0 ? "+" : ""}${v.toFixed(2)}%`;
}

function fmtAmount(v: number): string {
  const abs = Math.abs(v);
  if (abs >= 1e8) return `${(v / 1e8).toFixed(2)}亿`;
  if (abs >= 1e4) return `${(v / 1e4).toFixed(2)}万`;
  return v.toFixed(0);
}

function gaugeBar(filled: number, total = 10): string {
  const active = Math.max(0, Math.min(total, filled));
  const empty = total - active;
  return "█".repeat(active) + "░".repeat(empty);
}

// ── Core check logic (pure function) ──────────────────────────────────────

type CheckResult =
  | { status: CheckStatus.Triggered; position: TriggeredPosition }
  | { status: CheckStatus.Warning; position: WarningPosition }
  | { status: CheckStatus.Safe; position: SafePosition }
  | { status: CheckStatus.NoStopLoss; position: NoStopLossPosition };

function checkHolding(
  holding: HoldingCheckData,
  allHoldings: HoldingCheckData[],
  defaultStopLossPct: number,
): CheckResult {
  const holdingData = allHoldings.find(
    (h) => h.symbol === holding.symbol,
  );

  const currentPrice = holding.current_price ?? 0;

  // Determine stop-loss price: prefer holding's own stop_loss, then global default
  let stopLoss: number;
  let stopLossSource: "explicit" | "default";

  const ownStopLoss = holdingData?.stop_loss;
  if (ownStopLoss && Number(ownStopLoss) > 0) {
    stopLoss = Number(ownStopLoss);
    stopLossSource = "explicit";
  } else if (defaultStopLossPct < 0) {
    stopLoss = holding.avg_cost * (1 + defaultStopLossPct / 100);
    stopLossSource = "default";
  } else {
    return {
      status: CheckStatus.NoStopLoss,
      position: {
        symbol: holding.symbol,
        name: holding.name,
        currentPrice,
        avgCost: holding.avg_cost,
        pnlPct: holding.pnl_pct ?? 0,
        quantity: holding.quantity,
        marketValue: holding.market_value ?? 0,
      },
    };
  }

  if (currentPrice <= stopLoss) {
    return {
      status: CheckStatus.Triggered,
      position: {
        symbol: holding.symbol,
        name: holding.name,
        currentPrice,
        avgCost: holding.avg_cost,
        stopLoss,
        stopLossSource,
        pnlPct: holding.pnl_pct ?? 0,
        quantity: holding.quantity,
        marketValue: holding.market_value ?? 0,
        lossAmount: (currentPrice - holding.avg_cost) * holding.quantity,
      },
    };
  }

  const distancePct = ((currentPrice - stopLoss) / stopLoss) * 100;

  if (distancePct < WARNING_DISTANCE_PCT) {
    return {
      status: CheckStatus.Warning,
      position: {
        symbol: holding.symbol,
        name: holding.name,
        currentPrice,
        avgCost: holding.avg_cost,
        stopLoss,
        stopLossSource,
        pnlPct: holding.pnl_pct ?? 0,
        distanceToStopLoss: distancePct,
        quantity: holding.quantity,
        marketValue: holding.market_value ?? 0,
      },
    };
  }

  return {
    status: CheckStatus.Safe,
    position: {
      symbol: holding.symbol,
      name: holding.name,
      currentPrice,
      avgCost: holding.avg_cost,
      stopLoss,
      stopLossSource,
      pnlPct: holding.pnl_pct ?? 0,
      distanceToStopLoss: distancePct,
      quantity: holding.quantity,
      marketValue: holding.market_value ?? 0,
    },
  };
}

function buildOutput(
  results: CheckResult[],
  defaultStopLossPct: number,
): { text: string; details: CheckDetail } {
  const triggered = results
    .filter((r): r is CheckResult & { status: CheckStatus.Triggered } => r.status === CheckStatus.Triggered)
    .map((r) => r.position);
  const warnings = results
    .filter((r): r is CheckResult & { status: CheckStatus.Warning } => r.status === CheckStatus.Warning)
    .map((r) => r.position);
  const safe = results
    .filter((r): r is CheckResult & { status: CheckStatus.Safe } => r.status === CheckStatus.Safe)
    .map((r) => r.position);
  const noStopLoss = results
    .filter((r): r is CheckResult & { status: CheckStatus.NoStopLoss } => r.status === CheckStatus.NoStopLoss)
    .map((r) => r.position);

  const totalChecked = results.length;
  const triggeredCount = triggered.length;
  const warningCount = warnings.length;
  const safeCount = safe.length;
  const noSlCount = noStopLoss.length;

  const summaryBars = [
    `🔴 已触发=${triggeredCount}`,
    `🟡 接近=${warningCount}`,
    `🟢 安全=${safeCount}`,
    ...(noSlCount > 0 ? [`⚪ 未配置=${noSlCount}`] : []),
  ];

  let output = `# 止损检查报告\n\n`;
  output += `📊 共检查 ${totalChecked} 个持仓 · ${summaryBars.join(" · ")}\n\n`;

  if (defaultStopLossPct < 0) {
    output += `ℹ️  未设置止损价的持仓将使用默认 ${defaultStopLossPct}% 回撤止损\n\n`;
  }

  if (triggeredCount > 0) {
    output += `## 🔴 已触发止损 (${triggeredCount})\n\n`;
    triggered.forEach((t) => {
      const bar = gaugeBar(Math.min(10, Math.round((Math.abs(t.pnlPct) / 20) * 10)));
      output += `### ${t.name} (${t.symbol})\n`;
      output += `- 当前价: ${fmtPrice(t.currentPrice)} | 成本: ${fmtPrice(t.avgCost)} | **止损: ${fmtPrice(t.stopLoss)}** ${t.stopLossSource === "explicit" ? "🔧" : "⚙️"}\n`;
      output += `- 亏损: ${fmtPct(t.pnlPct)} | 账面亏损: ${fmtAmount(t.lossAmount)}\n`;
      output += `- 持仓: ${t.quantity}股 (市值${fmtAmount(t.marketValue)})\n`;
      output += `- 危险等级: ${bar} ${Math.round(Math.abs(t.pnlPct))}%\n`;
      output += `- **❗ 建议: 立即执行止损**\n\n`;
    });
  }

  if (warningCount > 0) {
    output += `## 🟡 接近止损 (${warningCount})\n\n`;
    warnings.forEach((w) => {
      output += `### ${w.name} (${w.symbol})\n`;
      output += `- 当前价: ${fmtPrice(w.currentPrice)} | 成本: ${fmtPrice(w.avgCost)}\n`;
      output += `- 止损价: ${fmtPrice(w.stopLoss)} (距止损 ${w.distanceToStopLoss.toFixed(2)}%)\n`;
      output += `- 盈亏: ${fmtPct(w.pnlPct)}\n`;
      output += `- **⚡ 建议: 密切关注，可考虑提前减仓**\n\n`;
    });
  }

  if (safeCount > 0) {
    output += `## 🟢 安全持仓 (${safeCount})\n\n`;
    output += `| # | 名称 | 当前价 | 成本 | 止损 | 距止损 | 盈亏 |\n`;
    output += `|---|------|--------|------|------|--------|------|\n`;
    safe.forEach((s, i) => {
      output += `| ${i + 1} | ${s.name} | ${fmtPrice(s.currentPrice)} | ${fmtPrice(s.avgCost)} | ${fmtPrice(s.stopLoss)} | ${s.distanceToStopLoss.toFixed(1)}% | ${fmtPct(s.pnlPct)} |\n`;
    });
    output += "\n";
  }

  if (noSlCount > 0) {
    output += `## ⚪ 未设置止损 (${noSlCount})\n\n`;
    output += `以下持仓${defaultStopLossPct >= 0 ? "未设置止损价且默认止损已关闭" : `使用默认 ${defaultStopLossPct}% 止损`}:\n`;
    noStopLoss.forEach((n) => {
      output += `- ${n.name} (${n.symbol}): 当前 ${fmtPrice(n.currentPrice)} | 成本 ${fmtPrice(n.avgCost)} | 盈亏 ${fmtPct(n.pnlPct)}\n`;
    });
    output += "\n";
  }

  output += `## 💡 总体建议\n\n`;
  if (triggeredCount > 0 && warningCount > 0) {
    output += `存在已触发和接近止损的持仓，建议优先处理触发止损的持仓，同时关注接近止损品种。\n`;
  } else if (triggeredCount > 0) {
    output += `存在已触发止损的持仓，建议立即执行止损操作，控制损失扩大。\n`;
  } else if (warningCount > 0) {
    output += `存在接近止损的持仓，建议密切关注，可考虑适当减仓或放宽止损。\n`;
  } else {
    output += `✅ 所有持仓运行正常，止损空间充裕。\n`;
  }

  if (noSlCount > 0 && defaultStopLossPct >= 0) {
    output += `\n💡 可通过 portfolio.json 的 stop_loss 字段为每只持仓设置止损价，或设置 default_stop_loss_pct 参数开启自动止损。\n`;
  }

  return {
    text: output,
    details: {
      totalHoldings: totalChecked,
      triggered,
      warnings,
      safe,
      noStopLossConfigured: noStopLoss,
    },
  };
}

// ── Tool Definition ────────────────────────────────────────────────────────

export const checkStopLossTriggerTool: ToolDefinition = {
  name: "check_stop_loss_trigger",
  label: "检查止损触发",
  description:
    "Check if any portfolio holdings have triggered stop-loss conditions. " +
    "Compares current prices against configured stop-loss thresholds for each position. " +
    "If a holding has no explicit stop_loss in portfolio.json, a default percentage " +
    "(configurable, default -8%) is applied based on average cost. " +
    "Returns list of positions that need stop-loss action, helping improve risk management execution. " +
    "Use this regularly to avoid letting losses expand.",
  parameters: Type.Object({
    default_stop_loss_pct: Type.Optional(
      Type.Number({
        description:
          "Default stop-loss percentage applied to positions without an explicit stop_loss " +
          "in portfolio.json. Negative value represents max allowed drawdown from avg cost. " +
          "Default: -8 (meaning -8% from average cost). Set to -5 for tighter risk, " +
          "-10 for looser, or 0 to skip auto-calculated stop-loss entirely.",
      }),
    ),
  }),
  execute: async (_toolCallId, params: any) => {
    try {
      const defaultStopLossPct = params.default_stop_loss_pct ?? -8;
      const piDir = ".pi-invest";

      // Dynamically import to allow ESM test mocking
      const { PortfolioService } = await import(
        "../../../services/portfolio/portfolio-service.js"
      );

      const portfolioService = new PortfolioService(piDir);

      // Get current portfolio snapshot with real-time prices
      const snapshot = await portfolioService.getWithPnL();

      if (snapshot.holdings.length === 0) {
        return {
          content: [{ type: "text" as const, text: "当前无持仓" }],
          details: {
            totalHoldings: 0,
            triggered: [],
            warnings: [],
            safe: [],
            noStopLossConfigured: [],
          },
        };
      }

      // Load raw portfolio data to get explicit stop_loss values
      const portfolioData = portfolioService.load();

      // Check each holding
      const results: CheckResult[] = snapshot.holdings.map(
        (holding: HoldingCheckData) =>
          checkHolding(holding, portfolioData.holdings, defaultStopLossPct),
      );

      const { text, details } = buildOutput(results, defaultStopLossPct);

      return {
        content: [{ type: "text" as const, text }],
        details,
      };
    } catch (e) {
      return {
        content: [
          {
            type: "text" as const,
            text: `止损检查失败: ${e instanceof Error ? e.message : String(e)}`,
          },
        ],
        details: undefined,
      };
    }
  },
};

// Exported for testing: pure logic functions
export { checkHolding, buildOutput, CheckStatus };
export type { CheckResult, CheckDetail, HoldingCheckData };
