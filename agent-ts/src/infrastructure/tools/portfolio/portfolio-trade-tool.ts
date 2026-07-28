/**
 * Portfolio Trade Tool - Agent执行交易
 *
 * 让Agent操作虚拟仓，执行买入/卖出决策
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { wrapToolExecution } from "../shared/error-handler.js";
import { executeAccountTrade } from "../../adapters/quant/quant-v2-client.js";

interface PortfolioTradeInput {
  action: 'buy' | 'sell';
  symbol: string;
  account: string;
  reason: string;
  amount?: number;
  shares?: number;
  price_limit?: number;
  strategy?: string;
  execute_at?: 'market_open';
}

export async function executePortfolioTrade(input: PortfolioTradeInput) {
  // 验证：必须指定代管账户
  if (!input.account) {
    return {
      success: false,
      error: '缺少必填参数 account（代管账户名）',
      hint: '先用 portfolio_status({ action: "list" }) 查看可用账户'
    };
  }

  // 验证：必须有交易理由
  if (!input.reason || input.reason.trim().length < 10) {
    return {
      success: false,
      error: '必须提供详细的交易理由（至少10字）',
      hint: '例如：技术面突破+机构增持+RSI超卖反弹'
    };
  }

  // 调用quantsys-v2的多账户交易API
  try {
    const data = await executeAccountTrade(input.account, {
      action: input.action,
      symbol: input.symbol,
      amount: input.amount,
      shares: input.shares,
      price_limit: input.price_limit,
      reason: `${input.reason}${input.strategy ? ` [策略:${input.strategy}]` : ''}`,
      execute_at: input.execute_at,
    });

    // 条件委托挂单：非交易时段 + execute_at='market_open'
    if (data.status === 'pending') {
      return {
        success: true,
        pending: true,
        pending_order_id: data.pending_order_id,
        message: `已挂单：开盘 9:31 起自动撮合（${input.action === 'buy' ? '买入' : '卖出'} ${input.symbol}）`,
        details: {
          account: input.account,
          symbol: input.symbol,
          action: input.action,
          reason: input.reason,
        },
        note: '挂单会在开盘后经完整风控护栏撮合；撮合失败（如资金不足、价格超限）会标记失败，盘中检查时可用 portfolio_status 核对',
      };
    }

    return {
      success: true,
      order_id: data.order_id,
      message: `${input.action === 'buy' ? '买入' : '卖出'}订单已成交`,
      details: {
        account: input.account,
        symbol: input.symbol,
        action: input.action,
        price: data.price,
        shares: data.shares,
        amount: data.amount,
        commission: data.commission,
        realized_pnl: data.realized_pnl ?? undefined,
        reason: input.reason
      },
      note: input.action === 'buy'
        ? 'T+1规则：今日买入，明日才能卖出'
        : '卖出已成交，已实现盈亏见 realized_pnl'
    };

  } catch (error) {
    return {
      success: false,
      error: `交易执行失败: ${error instanceof Error ? error.message : String(error)}`,
      hint: '账户名错误或风控拦截；先用 portfolio_status({ action: "list" }) 确认账户'
    };
  }
}

export const portfolioTradeTool: ToolDefinition = {
  name: "portfolio_trade",
  label: "虚拟仓交易",
  description:
    "Agent执行模拟账户交易 - 买入或卖出股票。Agent 是策略账户的操盘手：" +
    "每笔交易必须指定 account（代管账户名）和 reason（交易理由）。" +
    "不确定账户时先用 portfolio_status({ action: 'list' })。" +
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
    "\n  • 盘前（9:30前）决策用 execute_at: 'market_open' 挂单，开盘自动撮合，不要等开盘再下单" +
    "\n  • 这是虚拟仓，用于验证Agent智能",

  parameters: Type.Object({
    action: Type.Union([
      Type.Literal('buy'),
      Type.Literal('sell')
    ], {
      description: "交易动作：buy=买入, sell=卖出"
    }),

    account: Type.String({
      description: "代管账户名（必填），如 v13_simulation。不确定时先 portfolio_status({ action: 'list' })"
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
    })),

    execute_at: Type.Optional(Type.Literal('market_open', {
      description: "条件委托：非交易时段（如早盘9:00分析时）传 'market_open'，委托先挂单，开盘 9:31 起由后端自动撮合。" +
        "这样分析完工作即结束，不依赖 agent 在线等待。交易时段内传此参数则立即成交。"
    }))
  }),

  execute: async (toolCallId: string, input: PortfolioTradeInput) => {
    return wrapToolExecution(
      async () => await executePortfolioTrade(input),
      { toolName: "portfolio_trade" }
    );
  }
};
