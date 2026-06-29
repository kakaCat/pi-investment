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

async function getPortfolioStatus(input: PortfolioStatusInput) {
  try {
    const response = await fetch('http://127.0.0.1:5001/api/portfolio', {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' }
    });

    const result = await response.json() as any;

    if (result.success) {
      const portfolio = result.data;

      // 格式化持仓信息
      const holdings = portfolio.holdings?.map((h: any) => ({
        symbol: h.symbol,
        shares: h.shares,
        cost_price: h.cost_price || h.cost,
        current_price: h.current_price,
        market_value: h.market_value || (h.shares * h.current_price),
        pnl: h.pnl,
        pnl_pct: h.pnl_pct,
        days_held: h.days_held || 0
      })) || [];

      return {
        success: true,
        cash: portfolio.cash || 0,
        holdings: holdings,
        holdings_count: holdings.length,
        total_market_value: portfolio.total_market_value || portfolio.totalValue || 0,
        total_assets: portfolio.total_assets || (portfolio.cash + portfolio.totalValue) || 0,
        total_pnl: portfolio.total_pnl || portfolio.totalPnl || 0,
        total_pnl_pct: portfolio.total_pnl_pct || portfolio.totalPnlPct || 0,
        last_updated: portfolio.last_updated || portfolio.lastUpdated,
        summary: `
持仓概况：
  可用资金：¥${(portfolio.cash || 0).toFixed(2)}
  持仓数量：${holdings.length}只
  持仓市值：¥${(portfolio.total_market_value || portfolio.totalValue || 0).toFixed(2)}
  总资产：¥${(portfolio.total_assets || (portfolio.cash + portfolio.totalValue) || 0).toFixed(2)}
  总盈亏：¥${(portfolio.total_pnl || portfolio.totalPnl || 0).toFixed(2)} (${(portfolio.total_pnl_pct || portfolio.totalPnlPct || 0).toFixed(2)}%)
        `.trim()
      };
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
