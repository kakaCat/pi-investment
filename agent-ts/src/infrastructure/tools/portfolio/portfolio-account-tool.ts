/**
 * Portfolio Account Tool - 账户管理（开户）
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { wrapToolExecution } from "../shared/error-handler.js";
import { createAccount } from "../../adapters/quant/quant-v2-client.js";

interface PortfolioAccountInput {
  action: "create";
  account_name: string;
  initial_capital: number;
  display_name?: string;
  strategy_name?: string;
}

export async function manageAccount(input: PortfolioAccountInput) {
  if (input.account_name === "default") {
    return { success: false, error: "禁止使用账户名 default（历史公共账户，已废弃）" };
  }
  try {
    const data = await createAccount({
      account_name: input.account_name,
      initial_capital: input.initial_capital,
      display_name: input.display_name,
      strategy_name: input.strategy_name,
    });
    return {
      success: true,
      account_name: data.account_name,
      message: `账户 ${data.account_name} 开户成功，初始资金 ¥${input.initial_capital.toLocaleString("zh-CN")}`,
    };
  } catch (error) {
    return {
      success: false,
      error: `开户失败: ${error instanceof Error ? error.message : String(error)}`,
    };
  }
}

export const portfolioAccountTool: ToolDefinition = {
  name: "portfolio_account",
  label: "账户管理",
  description:
    "开立新的模拟账户（agent 代管账户体系）。账户名规范：策略账户 {策略}_simulation，" +
    "其他用途自由命名（禁止 default）。开户后可用 portfolio_trade 指定该账户交易。",
  parameters: Type.Object({
    action: Type.Literal("create", { description: "create=开户" }),
    account_name: Type.String({ description: "账户名（禁止 default）" }),
    initial_capital: Type.Number({ description: "初始资金（元）", minimum: 1000 }),
    display_name: Type.Optional(Type.String({ description: "显示名" })),
    strategy_name: Type.Optional(Type.String({ description: "绑定策略名（可选）" })),
  }),
  execute: async (toolCallId: string, input: PortfolioAccountInput) => {
    return wrapToolExecution(async () => await manageAccount(input), { toolName: "portfolio_account" });
  },
};
