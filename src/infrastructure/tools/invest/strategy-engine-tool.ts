/**
 * V2 策略代码引擎工具
 *
 * 暴露 quantsys-v2 的策略代码引擎（创建/回测/运行/列出自定义策略）
 * 这些能力在旧 quant/ 中完全不存在，是 v2 独有的。
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantV2 } from "../../quant/quant-v2-client.js";

const V2_BASE = "http://127.0.0.1:5001";

export const strategyEngineTool: ToolDefinition = {
  name: "strategy_engine",
  label: "策略引擎",
  description:
    "策略代码引擎：创建、查看、回测和运行自定义量化策略。支持两种策略类型：\n" +
    "- indicator 型：用 df['buy']/df['sell'] 定义买卖条件\n" +
    "- script 型：on_init(ctx)/on_bar(ctx, bar) 事件驱动模式\n" +
    "创建策略 → 自动验证代码安全性 → 回测验证表现 → 运行产生实时信号",
  parameters: Type.Object({
    action: Type.String({
      description: "操作: 'list'(列出策略), 'get'(查看详情), 'create'(创建策略), 'backtest'(回测), 'run'(运行产生信号)",
    }),
    strategy_id: Type.Optional(Type.String({ description: "策略ID" })),
    name: Type.Optional(Type.String({ description: "策略名称" })),
    code: Type.Optional(Type.String({ description: "策略代码" })),
    code_type: Type.Optional(Type.String({ description: "策略类型: 'indicator' 或 'script'" })),
    description: Type.Optional(Type.String({ description: "策略描述" })),
    symbol: Type.Optional(Type.String({ description: "股票代码" })),
    start: Type.Optional(Type.String({ description: "回测开始日期 YYYY-MM-DD" })),
    end: Type.Optional(Type.String({ description: "回测结束日期 YYYY-MM-DD" })),
  }),
  execute: async (_toolCallId: string, rawParams: any) => {
    const action = rawParams?.action ?? "list";

    try {
      let result: any;

      switch (action) {
        case "list": {
          result = await runQuantV2("strategy.list", {});
          break;
        }
        case "get": {
          if (!rawParams?.strategy_id) {
            return { content: [{ type: "text" as const, text: "缺少 strategy_id 参数" }], details: undefined };
          }
          result = await runQuantV2("strategy.get", { strategy_id: rawParams.strategy_id });
          break;
        }
        case "create": {
          if (!rawParams?.name || !rawParams?.code || !rawParams?.code_type) {
            return { content: [{ type: "text" as const, text: "创建策略需要 name, code, code_type 参数" }], details: undefined };
          }
          const resp = await fetch(`${V2_BASE}/api/strategies/create`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              name: rawParams.name,
              code: rawParams.code,
              type: rawParams.code_type,
              description: rawParams.description ?? "",
              params: rawParams.params ?? "{}",
            }),
            signal: AbortSignal.timeout(60_000),
          });
          result = await resp.json();
          break;
        }
        case "backtest": {
          if (!rawParams?.strategy_id || !rawParams?.symbol) {
            return { content: [{ type: "text" as const, text: "回测需要 strategy_id 和 symbol 参数" }], details: undefined };
          }
          const resp = await fetch(`${V2_BASE}/api/backtest/run`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              strategy_name: rawParams.strategy_id,
              symbol: rawParams.symbol,
              start: rawParams.start ?? "2025-01-01",
              end: rawParams.end ?? "2026-05-24",
              initial_cash: rawParams.initial_cash ?? 1_000_000,
            }),
            signal: AbortSignal.timeout(120_000),
          });
          result = await resp.json();
          break;
        }
        case "run": {
          if (!rawParams?.strategy_id || !rawParams?.symbol) {
            return { content: [{ type: "text" as const, text: "运行策略需要 strategy_id 和 symbol 参数" }], details: undefined };
          }
          const resp = await fetch(`${V2_BASE}/api/strategies/start/${rawParams.strategy_id}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            signal: AbortSignal.timeout(30_000),
          });
          result = await resp.json();
          break;
        }
        default: {
          return { content: [{ type: "text" as const, text: `不支持的操作: ${action}。支持: list, get, create, backtest, run` }], details: undefined };
        }
      }

      return {
        content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }],
        details: undefined,
      };
    } catch (error) {
      return {
        content: [{ type: "text" as const, text: `策略引擎调用失败: ${error instanceof Error ? error.message : String(error)}` }],
        details: undefined,
      };
    }
  },
};
