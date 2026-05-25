/**
 * Trade Manage Orders Tool (L5 执行引擎层)
 *
 * 包装 manage_orders 工具，统一命名规范为 trade_manage_orders
 * 保持现有功能不变，仅更新工具名称和描述
 */
import type { ToolDefinition } from "../index.js";
import { manageOrdersTool } from "../trading/order-tools.js";

export const tradeManageOrdersTool: ToolDefinition = {
  name: "trade_manage_orders",
  label: "管理交易订单",
  description: manageOrdersTool.description
    .replace(/manage_orders/g, "trade_manage_orders")
    .replace(/挂单管理一站式工具/g, "交易订单管理工具"),
  parameters: manageOrdersTool.parameters,
  execute: manageOrdersTool.execute
};
