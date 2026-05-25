/**
 * Portfolio Rebalance Tool (L4 组合构建层)
 *
 * 包装 manage_portfolio 工具，统一命名规范为 portfolio_rebalance
 * 保持现有功能不变，仅更新工具名称和描述
 */
import type { ToolDefinition } from "../index.js";
import { managePortfolioTool } from "../invest/portfolio-tools.js";

export const portfolioRebalanceTool: ToolDefinition = {
  name: "portfolio_rebalance",
  label: "组合再平衡",
  description: managePortfolioTool.description
    .replace(/manage_portfolio/g, "portfolio_rebalance")
    .replace(/Manage the user's local portfolio/g, "Rebalance and manage the user's portfolio"),
  parameters: managePortfolioTool.parameters,
  execute: managePortfolioTool.execute
};
