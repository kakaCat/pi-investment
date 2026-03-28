/**
 * 股票记忆查询工具
 *
 * Agent 可主动查询已知股票的静态信息，避免重复调用数据源
 */

import { stockMemoryService } from "../services/memory/stock-memory-service.js";

export const queryStockMemoryTool = {
  name: "query_stock_memory",
  description: `查询股票静态信息记忆（名称、行业、上市日期）

使用场景：
- 在调用 get_stock_info 之前，先查询记忆
- 如果记忆中有，直接使用，无需调用 get_stock_info
- 如果记忆中没有，再调用 get_stock_info 并保存到记忆

参数：
- symbol: 股票代码（如 600519）
- action: "get" 查询单个 | "list" 列出所有`,

  input_schema: {
    type: "object",
    properties: {
      symbol: {
        type: "string",
        description: "股票代码（action=get时必填）",
      },
      action: {
        type: "string",
        enum: ["get", "list"],
        description: "操作类型",
      },
    },
    required: ["action"],
  },

  execute: async (args: { symbol?: string; action: string }) => {
    if (args.action === "list") {
      const all = Array.from((stockMemoryService as any).stocks.values());
      return JSON.stringify({
        count: all.length,
        stocks: all,
      });
    }

    if (args.action === "get" && args.symbol) {
      const info = stockMemoryService.get(args.symbol);
      if (info) {
        return JSON.stringify({
          found: true,
          ...info,
          note: "来自记忆，无需调用 get_stock_info",
        });
      }
      return JSON.stringify({
        found: false,
        symbol: args.symbol,
        note: "记忆中无此股票，需调用 get_stock_info",
      });
    }

    return JSON.stringify({ error: "参数错误" });
  },
};
