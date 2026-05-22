/**
 * Trade Log Tools — 交易日志管理工具
 *
 * 单一工具 `trade_log`，通过 action 参数区分操作：
 *
 *   list              → 列出所有交易日志
 *   get               → 读取指定股票的日志内容
 *   create            → 创建新的交易日志
 *   update            → 更新日志的建仓逻辑或操作计划
 *   append_execution  → 追加执行记录（买入/卖出操作）
 *   append_tracking   → 追加日度追踪记录
 *
 * 供 agent 直接调用，管理 .pi-invest/trade-log/ 目录下的 Markdown 文件。
 * 存储依赖 TradeLogService (src/services/trade-log-service.ts)。
 */

import type { ToolDefinition } from "./index.js";
import { Type } from "@sinclair/typebox";
import { TradeLogService } from "../../services/trade-log-service.js";

const PI_DIR = process.env.PI_DIR || ".pi-invest";

export const tradeLogTool: ToolDefinition = {
  name: "trade_log",
  label: "交易日志管理",
  description:
    "管理股票交易日志（Markdown 格式），记录建仓逻辑、操作计划、执行记录和日度追踪。\n\n" +
    "**何时使用：**\n" +
    "1. 建仓后：创建日志记录买入逻辑和操作计划\n" +
    "2. 执行交易后：追加买卖操作记录\n" +
    "3. 每日盘后：追加收盘价和浮盈追踪\n" +
    "4. 策略调整时：更新操作计划（如调整止盈止损）\n\n" +
    "**操作类型：**\n" +
    "- list: 列出所有交易日志\n" +
    "- get: 读取指定股票的日志内容（只需 symbol）\n" +
    "- create: 创建新日志（需 symbol + name + 建仓信息）\n" +
    "- update: 更新建仓逻辑或操作计划（只需 symbol）\n" +
    "- append_execution: 追加执行记录（只需 symbol + 交易信息）\n" +
    "- append_tracking: 追加日度追踪（只需 symbol + 价格/持仓/盈亏）",
  promptSnippet: '需要记录或查询交易日志时',
  promptGuidelines: [
    '所有交易操作必须记录日志',
    '支持按时间范围、股票代码查询',
    '日志包含决策依据和执行结果'
  ],

  parameters: Type.Object({
    action: Type.String({
      minLength: 1,
      description:
        "【必需】操作类型:\n" +
        '  "list"              — 列出所有交易日志\n' +
        '  "get"               — 读取指定股票的日志\n' +
        '  "create"            — 创建新的交易日志\n' +
        '  "update"            — 更新建仓逻辑或操作计划\n' +
        '  "append_execution"  — 追加执行记录\n' +
        '  "append_tracking"   — 追加日度追踪',
    }),

    // 通用参数
    symbol: Type.Optional(Type.String({ description: "股票代码，如 '600519'（除 list 外都需要，工具会自动查找对应的股票名称）" })),

    // create 参数（创建时需要提供 name）
    name: Type.Optional(Type.String({ description: "股票名称（仅 create 时需要）" })),
    initial_position: Type.Optional(Type.Number({ description: "初始持仓数量（create 时使用）" })),
    avg_cost: Type.Optional(Type.Number({ description: "持仓均价（create 时使用）" })),
    entry_logic: Type.Optional(Type.String({ description: "建仓逻辑（create 时使用）" })),
    technical_analysis: Type.Optional(Type.String({ description: "技术分析（create 时使用，可选）" })),
    operation_plan: Type.Optional(Type.String({ description: "操作计划（create 时使用，可选）" })),

    // update 参数
    update_entry_logic: Type.Optional(Type.String({ description: "更新建仓逻辑（update 时使用）" })),
    update_technical_analysis: Type.Optional(Type.String({ description: "更新技术分析（update 时使用）" })),
    update_operation_plan: Type.Optional(Type.String({ description: "更新操作计划（update 时使用）" })),

    // append_execution 参数
    execution_date: Type.Optional(Type.String({ description: "执行日期，格式 YYYY-MM-DD（append_execution 时使用）" })),
    execution_action: Type.Optional(Type.String({ description: "操作类型: 'buy' 或 'sell'（append_execution 时使用）" })),
    execution_price: Type.Optional(Type.Number({ description: "成交价格（append_execution 时使用）" })),
    execution_quantity: Type.Optional(Type.Number({ description: "成交数量（append_execution 时使用）" })),
    execution_reason: Type.Optional(Type.String({ description: "操作原因（append_execution 时使用）" })),

    // append_tracking 参数
    tracking_date: Type.Optional(Type.String({ description: "追踪日期，格式 YYYY-MM-DD（append_tracking 时使用）" })),
    tracking_close_price: Type.Optional(Type.Number({ description: "收盘价（append_tracking 时使用）" })),
    tracking_position: Type.Optional(Type.Number({ description: "当前持仓（append_tracking 时使用）" })),
    tracking_pnl: Type.Optional(Type.Number({ description: "浮动盈亏（append_tracking 时使用）" })),
    tracking_notes: Type.Optional(Type.String({ description: "备注（append_tracking 时使用，可选）" })),
  }),

  execute: async (_toolCallId, params: any) => {
    try {
      const service = new TradeLogService(PI_DIR);
      const action = params?.action;

      // 验证 action 参数
      if (!action) {
        return {
          content: [{ type: "text" as const, text: "❌ 缺少必需参数: action。支持的操作: list, get, create, update, append_execution, append_tracking" }],
          details: { error: "missing action parameter" },
        };
      }

      // 辅助函数：根据 symbol 查找对应的 name
      const findNameBySymbol = (symbol: string): string | null => {
        const logs = service.list();
        const found = logs.find(log => log.symbol === symbol);
        return found ? found.name : null;
      };

      switch (action) {
        case "list": {
          const logs = await service.list();
          if (logs.length === 0) {
            return {
              content: [{ type: "text" as const, text: "📋 暂无交易日志" }],
              details: { count: 0 },
            };
          }

          const text = `📋 交易日志列表（共 ${logs.length} 个）\n\n` +
            logs.map(log => `• ${log.symbol} - ${log.name}`).join("\n");

          return {
            content: [{ type: "text" as const, text }],
            details: { count: logs.length, logs },
          };
        }

        case "get": {
          if (!params.symbol) {
            return {
              content: [{ type: "text" as const, text: "❌ 缺少参数: symbol" }],
              details: { error: "missing symbol" },
            };
          }

          const name = findNameBySymbol(params.symbol);
          if (!name) {
            return {
              content: [{ type: "text" as const, text: `❌ 未找到 ${params.symbol} 的交易日志` }],
              details: { error: "log not found" },
            };
          }

          const content = service.read(params.symbol, name);
          if (!content) {
            return {
              content: [{ type: "text" as const, text: `❌ 读取 ${params.symbol}-${name} 的交易日志失败` }],
              details: { error: "read failed" },
            };
          }

          return {
            content: [{ type: "text" as const, text: `📄 ${params.symbol} - ${name}\n\n${content}` }],
            details: { symbol: params.symbol, name },
          };
        }

        case "create": {
          const required = ["symbol", "name", "initial_position", "avg_cost", "entry_logic"];
          const missing = required.filter(key => !params[key]);
          if (missing.length > 0) {
            return {
              content: [{ type: "text" as const, text: `❌ 缺少参数: ${missing.join(", ")}` }],
              details: { error: "missing parameters", missing },
            };
          }

          const data = {
            metadata: {
              symbol: params.symbol,
              name: params.name,
              market: "A" as const,
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            },
            holdings_summary: {
              total_shares: params.initial_position,
              avg_cost: params.avg_cost,
              total_investment: params.initial_position * params.avg_cost,
            },
            entry_logic: params.entry_logic,
            operation_plan: params.operation_plan || "",
            execution_records: [],
            tracking_records: [],
            follow_up_items: [],
          };

          service.create(data);

          return {
            content: [{ type: "text" as const, text: `✅ 已创建 ${params.symbol} - ${params.name} 的交易日志` }],
            details: { symbol: params.symbol, name: params.name },
          };
        }

        case "update": {
          if (!params.symbol) {
            return {
              content: [{ type: "text" as const, text: "❌ 缺少参数: symbol" }],
              details: { error: "missing symbol" },
            };
          }

          const name = findNameBySymbol(params.symbol);
          if (!name) {
            return {
              content: [{ type: "text" as const, text: `❌ 未找到 ${params.symbol} 的交易日志` }],
              details: { error: "log not found" },
            };
          }

          const updates: any = {};
          if (params.update_entry_logic) updates.entry_logic = params.update_entry_logic;
          if (params.update_technical_analysis) updates.technical_analysis = params.update_technical_analysis;
          if (params.update_operation_plan) updates.operation_plan = params.update_operation_plan;

          if (Object.keys(updates).length === 0) {
            return {
              content: [{ type: "text" as const, text: "❌ 没有提供要更新的内容" }],
              details: { error: "no updates provided" },
            };
          }

          service.update(params.symbol, name, updates);

          return {
            content: [{ type: "text" as const, text: `✅ 已更新 ${params.symbol} 的交易日志` }],
            details: { symbol: params.symbol, updates: Object.keys(updates) },
          };
        }

        case "append_execution": {
          const required = ["symbol", "execution_date", "execution_action", "execution_price", "execution_quantity", "execution_reason"];
          const missing = required.filter(key => !params[key]);
          if (missing.length > 0) {
            return {
              content: [{ type: "text" as const, text: `❌ 缺少参数: ${missing.join(", ")}` }],
              details: { error: "missing parameters", missing },
            };
          }

          const name = findNameBySymbol(params.symbol);
          if (!name) {
            return {
              content: [{ type: "text" as const, text: `❌ 未找到 ${params.symbol} 的交易日志` }],
              details: { error: "log not found" },
            };
          }

          service.appendExecution(params.symbol, name, {
            date: params.execution_date,
            operation: params.execution_action === "buy" ? "买入" : "卖出",
            quantity: params.execution_quantity,
            price: params.execution_price,
            amount: params.execution_price * params.execution_quantity,
            notes: params.execution_reason,
          });

          return {
            content: [{ type: "text" as const, text: `✅ 已追加 ${params.symbol} 的执行记录` }],
            details: { symbol: params.symbol, action: params.execution_action },
          };
        }

        case "append_tracking": {
          const required = ["symbol", "tracking_date", "tracking_close_price", "tracking_position", "tracking_pnl"];
          const missing = required.filter(key => !params[key]);
          if (missing.length > 0) {
            return {
              content: [{ type: "text" as const, text: `❌ 缺少参数: ${missing.join(", ")}` }],
              details: { error: "missing parameters", missing },
            };
          }

          const name = findNameBySymbol(params.symbol);
          if (!name) {
            return {
              content: [{ type: "text" as const, text: `❌ 未找到 ${params.symbol} 的交易日志` }],
              details: { error: "log not found" },
            };
          }

          service.appendTracking(params.symbol, name, {
            date: params.tracking_date,
            close_price: params.tracking_close_price,
            change_pct: 0, // 需要计算
            float_pnl_pct: params.tracking_pnl,
            position: params.tracking_position,
            notes: params.tracking_notes,
          });

          return {
            content: [{ type: "text" as const, text: `✅ 已追加 ${params.symbol} 的日度追踪` }],
            details: { symbol: params.symbol, date: params.tracking_date },
          };
        }

        default:
          return {
            content: [{ type: "text" as const, text: `❌ 未知操作: ${action}。支持: list, get, create, update, append_execution, append_tracking` }],
            details: { action, error: `unknown action: ${action}` },
          };
      }
    } catch (e) {
      return {
        content: [
          {
            type: "text" as const,
            text: `交易日志操作失败: ${e instanceof Error ? e.message : String(e)}`,
          },
        ],
        details: { action: params?.action, error: e instanceof Error ? e.message : String(e) },
      };
    }
  },
};
