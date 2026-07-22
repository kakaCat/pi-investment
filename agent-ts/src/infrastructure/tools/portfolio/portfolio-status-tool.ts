/**
 * Portfolio Status Tool - 查看虚拟仓状态
 *
 * Agent查看当前持仓、资金、盈亏情况
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { wrapToolExecution } from "../shared/error-handler.js";
import { listAccounts, getAccount } from "../../adapters/quant/quant-v2-client.js";

interface PortfolioStatusInput {
  action?: "list" | "get";
  account?: string;
  detailed?: boolean;
}

export interface PortfolioHolding {
  symbol: string;
  shares: number;
  cost_price: number;
  current_price: number;
  market_value: number;
  pnl: number;
  pnl_pct: number;
  days_held: number;
}

export interface PortfolioView {
  success: true;
  cash: number;
  holdings: PortfolioHolding[];
  holdings_count: number;
  total_market_value: number;
  total_assets: number;
  total_pnl: number;
  total_pnl_pct: number;
  cumulative_return?: number;
  last_updated?: string;
  summary: string;
}

/**
 * 将 simulation API 的账户数据换算为视图模型。
 *
 * API 语义（已核实）：`total_value` = 总资产（含现金），
 * `cash` = 可用资金。因此：
 *   总资产   = total_value
 *   持仓市值 = total_value - cash
 * 禁止再把 cash + total_value 相加（会导致资产翻倍的历史 bug）。
 */
export function computePortfolioView(portfolio: any): PortfolioView {
  const cash = Number(portfolio.cash_available ?? portfolio.cash) || 0;
  const apiTotalValue = Number(portfolio.total_value ?? portfolio.totalValue);

  // 格式化持仓信息 (simulation API返回positions而不是holdings)
  const positions = portfolio.positions || portfolio.holdings || [];
  let totalPnl = 0;
  let positionsValue = 0;

  const holdings: PortfolioHolding[] = positions.map((h: any) => {
    const profit = Number(h.profit_total ?? h.profit ?? h.pnl) || 0;
    const marketValue = Number(h.market_value) || 0;
    totalPnl += profit;
    positionsValue += marketValue;

    return {
      symbol: h.symbol,
      shares: Number(h.shares_total ?? h.shares) || 0,
      cost_price: Number(h.avg_cost ?? h.avg_price ?? h.cost_price ?? h.cost) || 0,
      current_price: Number(h.current_price) || 0,
      market_value: marketValue,
      pnl: profit,
      pnl_pct: Number(h.profit_total_rate ?? h.profit_rate ?? h.pnl_pct) || 0,
      days_held: Number(h.days_held) || 0
    };
  });

  // 总资产：优先采用 API 的 total_value；缺失时回退为 现金+持仓市值
  const totalAssets = Number.isFinite(apiTotalValue) && apiTotalValue > 0
    ? apiTotalValue
    : cash + positionsValue;
  // 持仓市值：优先 API 的 position_value；缺失时恒等式推导，保证 总资产 = 现金 + 持仓市值
  const apiPositionValue = Number(portfolio.position_value);
  const totalMarketValue = Number.isFinite(apiPositionValue) && apiPositionValue >= 0
    ? apiPositionValue
    : Math.max(totalAssets - cash, 0);

  const totalPnlPct = totalAssets > 0 ? (totalPnl / (totalAssets - totalPnl)) * 100 : 0;
  const cumulativeReturn = Number(portfolio.cumulative_return);

  return {
    success: true,
    cash,
    holdings,
    holdings_count: holdings.length,
    total_market_value: totalMarketValue,
    total_assets: totalAssets,
    total_pnl: totalPnl,
    total_pnl_pct: totalPnlPct,
    cumulative_return: Number.isFinite(cumulativeReturn) ? cumulativeReturn : undefined,
    last_updated: portfolio.last_updated || portfolio.lastUpdated || portfolio.last_rebalance_date,
    summary: `
持仓概况：
  可用资金：¥${cash.toFixed(2)}
  持仓数量：${holdings.length}只
  持仓市值：¥${totalMarketValue.toFixed(2)}
  总资产：¥${totalAssets.toFixed(2)}
  总盈亏：¥${totalPnl.toFixed(2)} (${totalPnlPct.toFixed(2)}%)${Number.isFinite(cumulativeReturn) ? `\n  累计收益率：${(cumulativeReturn * 100).toFixed(2)}%` : ""}
    `.trim()
  };
}

export async function getPortfolioStatus(input: PortfolioStatusInput) {
  const action = input.action ?? "get";
  try {
    if (action === "list") {
      const { accounts, total } = await listAccounts();
      return {
        success: true,
        accounts,
        total,
        summary: accounts.length === 0
          ? "当前没有任何账户"
          : `共 ${total} 个账户：\n` + accounts.map(a =>
              `  - ${a.account_name}（${a.display_name ?? ""}）` +
              `${a.strategy_name ? ` [策略:${a.strategy_name}]` : ""}` +
              ` 总资产 ¥${a.total_value.toLocaleString("zh-CN")}` +
              ` 收益率 ${(a.cumulative_return * 100).toFixed(2)}%`).join("\n"),
        hint: "使用 portfolio_status({ action: 'get', account: '<账户名>' }) 查看指定账户",
      };
    }
    // action=get：account 必填
    if (!input.account) {
      return {
        success: false,
        error: "缺少必填参数 account（代管账户名）",
        hint: "先用 portfolio_status({ action: 'list' }) 查看可用账户",
      };
    }
    const data = await getAccount(input.account);
    return computePortfolioView(data);
  } catch (error) {
    return {
      success: false,
      error: `API调用失败: ${error instanceof Error ? error.message : String(error)}`,
      hint: "请检查quantsys-v2服务是否运行，或先用 action=list 确认账户名",
    };
  }
}

export const portfolioStatusTool: ToolDefinition = {
  name: "portfolio_status",
  label: "查看虚拟仓",
  description:
    "查看模拟账户状态。Agent 是策略账户的操盘手，禁止臆测账户名——" +
    "查仓/交易前必须先 action=list 确认目标账户。" +
    "\n\n两种用法：" +
    "\n  • action=list：账户发现，列出所有代管账户（名称/策略/总资产/收益率）" +
    "\n  • action=get：查看指定账户详情（资金两态/持仓/盈亏），account 必填" +
    "\n\n典型用法：" +
    "\n  portfolio_status({ action: 'list' }) - 列出所有账户" +
    "\n  portfolio_status({ action: 'get', account: 'v13_simulation' }) - 查看指定账户",

  parameters: Type.Object({
    action: Type.Optional(Type.Union([Type.Literal("list"), Type.Literal("get")], {
      description: "list=账户发现；get=查看指定账户（默认）",
      default: "get",
    })),
    account: Type.Optional(Type.String({
      description: "账户名（action=get 时必填），如 v13_simulation。不确定时先用 action=list",
    })),
    detailed: Type.Optional(Type.Boolean({
      description: "是否返回详细信息（默认false）",
      default: false
    }))
  }),

  execute: async (toolCallId: string, input: PortfolioStatusInput) => {
    return wrapToolExecution(
      async () => await getPortfolioStatus(input),
      { toolName: "portfolio_status" }
    );
  }
};
