/**
 * Portfolio Status Tool - 查看虚拟仓状态
 *
 * Agent查看当前持仓、资金、盈亏情况
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { wrapToolExecution } from "../shared/error-handler.js";

interface PortfolioStatusInput {
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
  const cash = Number(portfolio.cash) || 0;
  const apiTotalValue = Number(portfolio.total_value ?? portfolio.totalValue);

  // 格式化持仓信息 (simulation API返回positions而不是holdings)
  const positions = portfolio.positions || portfolio.holdings || [];
  let totalPnl = 0;
  let positionsValue = 0;

  const holdings: PortfolioHolding[] = positions.map((h: any) => {
    const profit = Number(h.profit ?? h.pnl) || 0;
    const marketValue = Number(h.market_value) || 0;
    totalPnl += profit;
    positionsValue += marketValue;

    return {
      symbol: h.symbol,
      shares: Number(h.shares) || 0,
      cost_price: Number(h.avg_price ?? h.cost_price ?? h.cost) || 0,
      current_price: Number(h.current_price) || 0,
      market_value: marketValue,
      pnl: profit,
      pnl_pct: Number(h.profit_rate ?? h.pnl_pct) || 0,
      days_held: Number(h.days_held) || 0
    };
  });

  // 总资产：优先采用 API 的 total_value；缺失时回退为 现金+持仓市值
  const totalAssets = Number.isFinite(apiTotalValue) && apiTotalValue > 0
    ? apiTotalValue
    : cash + positionsValue;
  // 持仓市值：恒等式推导，保证 总资产 = 现金 + 持仓市值 永远成立
  const totalMarketValue = Math.max(totalAssets - cash, 0);

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

async function getPortfolioStatus(input: PortfolioStatusInput) {
  try {
    const response = await fetch('http://127.0.0.1:5001/api/simulation/accounts/default', {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });

    const result = await response.json() as any;

    if (result.success) {
      return computePortfolioView(result.data);
    } else {
      return {
        success: false,
        error: result.error || '获取持仓信息失败'
      };
    }

  } catch (error) {
    return {
      success: false,
      error: `API调用失败: ${error instanceof Error ? error.message : String(error)}`,
      hint: '请检查quantsys-v2服务是否运行 (http://127.0.0.1:5001)'
    };
  }
}

export const portfolioStatusTool: ToolDefinition = {
  name: "portfolio_status",
  label: "查看虚拟仓",
  description:
    "查看Agent虚拟仓的当前状态 - 持仓、资金、盈亏。" +
    "\n\n返回信息：" +
    "\n  • 可用资金" +
    "\n  • 持仓列表（股票、数量、成本、现价、盈亏）" +
    "\n  • 总资产" +
    "\n  • 总盈亏和收益率" +
    "\n\n使用场景：" +
    "\n  • 早盘分析：先检查持仓再决策" +
    "\n  • 评估绩效：查看累计收益" +
    "\n  • 风控检查：确认仓位是否合理" +
    "\n\n典型用法：" +
    "\n  portfolio_status() - 查看当前状态" +
    "\n  portfolio_status({ detailed: true }) - 查看详细信息",

  parameters: Type.Object({
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
