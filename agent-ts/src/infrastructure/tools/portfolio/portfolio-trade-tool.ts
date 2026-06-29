/**
 * Portfolio Trade Tool - Agent执行交易
 *
 * 让Agent操作虚拟仓，执行买入/卖出决策
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { wrapToolExecution } from "../shared/error-handler.js";

interface PortfolioTradeInput {
  action: 'buy' | 'sell';
  symbol: string;
  reason: string;
  amount?: number;
  shares?: number;
  price_limit?: number;
  strategy?: string;
}

async function executePortfolioTrade(input: PortfolioTradeInput) {
  // 验证：必须有交易理由
  if (!input.reason || input.reason.trim().length < 10) {
    return {
      success: false,
      error: '必须提供详细的交易理由（至少10字）',
      hint: '例如：技术面突破+机构增持+RSI超卖反弹'
    };
  }

  // 调用quantsys-v2的虚拟仓API
  try {
    const response = await fetch('http://127.0.0.1:5001/api/portfolio/trade', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        action: input.action,
        symbol: input.symbol,
        amount: input.amount,
        shares: input.shares,
        price_limit: input.price_limit,
        metadata: {
          agent_reason: input.reason,
          strategy: input.strategy,
          timestamp: new Date().toISOString(),
          source: 'agent_ai'
        }
      })
    });

    const result = await response.json() as any;

    if (result.success) {
      const data = result.data;

      return {
        success: true,
        order_id: data.order_id,
        message: `${input.action === 'buy' ? '买入' : '卖出'}订单已提交`,
        details: {
          symbol: input.symbol,
          action: input.action,
          price: data.price,
          shares: data.shares,
          amount: data.amount,
          reason: input.reason
        },
        note: input.action === 'buy'
          ? 'T+1规则：今日买入，明日才能卖出'
          : '卖出订单已提交'
      };
    } else {
      return {
        success: false,
        error: result.error || '交易执行失败',
        details: result
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

export const portfolioTradeTool: ToolDefinition = {
  name: "portfolio_trade",
  label: "虚拟仓交易",
  description:
    "Agent执行虚拟仓交易 - 买入或卖出股票。" +
    "\n\n功能：" +
    "\n  • 买入股票（需要有可用资金）" +
    "\n  • 卖出股票（需要有持仓且T+1可卖）" +
    "\n  • 记录交易理由（必填）" +
    "\n\n风控规则：" +
    "\n  • 单只股票最大30%仓位" +
    "\n  • 最多持有3只股票" +
    "\n  • 总仓位不超过80%" +
    "\n\n使用场景：" +
    "\n  • 发现买入机会时执行买入" +
    "\n  • 持仓达到止盈/止损条件时卖出" +
    "\n  • 必须说明理由：为什么买/卖？" +
    "\n\n注意：" +
    "\n  • T+1规则：今日买入明日才能卖" +
    "\n  • 交易理由至少10字" +
    "\n  • 这是虚拟仓，用于验证Agent智能",

  parameters: Type.Object({
    action: Type.Union([
      Type.Literal('buy'),
      Type.Literal('sell')
    ], {
      description: "交易动作：buy=买入, sell=卖出"
    }),

    symbol: Type.String({
      description: "股票代码，如：600809, 688111",
      pattern: "^\\d{6}$"
    }),

    reason: Type.String({
      description: "交易理由（必填，至少10字）- 说明为什么买入或卖出。例如：技术面MACD金叉+机构增持+板块轮动机会",
      minLength: 10
    }),

    amount: Type.Optional(Type.Number({
      description: "买入金额（元），与shares二选一。建议：不超过总资产的30%",
      minimum: 1000
    })),

    shares: Type.Optional(Type.Number({
      description: "股票数量（股），与amount二选一",
      minimum: 100
    })),

    price_limit: Type.Optional(Type.Number({
      description: "限价（可选）- 不填则市价",
      minimum: 0
    })),

    strategy: Type.Optional(Type.String({
      description: "使用的策略名称（可选）"
    }))
  }),

  execute: async (toolCallId: string, input: PortfolioTradeInput) => {
    return wrapToolExecution(
      async () => await executePortfolioTrade(input),
      { toolName: "portfolio_trade" }
    );
  }
};
