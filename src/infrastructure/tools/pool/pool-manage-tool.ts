/**
 * Pool management tool — CRUD, refresh, scan-and-create for stock pools.
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import {
  createPool,
  listPools,
  getPool,
  updatePool,
  deletePool,
  refreshPool,
  scanAndCreatePool,
} from "../../quant/quant-v2-client.js";

export const poolManageTool: ToolDefinition = {
  name: "pool_manage",
  label: "股票池管理",
  description:
    "管理股票池：创建静态/动态池、列出所有池、查看详情、更新、删除、刷新动态池、筛选建池。" +
    "动态池保存筛选条件(filter_template)，可定时自动刷新。" +
    "筛选建池(scan_create)：执行多因子扫描后自动创建池子。",
  parameters: Type.Object({
    action: Type.Union(
      [
        Type.Literal("create"),
        Type.Literal("list"),
        Type.Literal("get"),
        Type.Literal("update"),
        Type.Literal("delete"),
        Type.Literal("refresh"),
        Type.Literal("scan_create"),
      ],
      { description: "操作类型" },
    ),
    pool_id: Type.Optional(
      Type.Number({ description: "池子ID (get/update/delete/refresh 需要)" }),
    ),
    name: Type.Optional(
      Type.String({ description: "池子名称 (create/scan_create 需要)" }),
    ),
    pool_type: Type.Optional(
      Type.Union([Type.Literal("static"), Type.Literal("dynamic")], {
        description: "池子类型 (create/scan_create 需要)",
      }),
    ),
    symbols: Type.Optional(
      Type.Array(Type.String(), {
        description: "股票代码列表 (create static 时手动指定)",
      }),
    ),
    filter: Type.Optional(
      Type.Object(
        {
          min_score: Type.Optional(
            Type.Number({ description: "最低综合评分 (0-100)" }),
          ),
          max_risk_level: Type.Optional(
            Type.String({ description: "最大风险等级: low/medium/high" }),
          ),
          technical: Type.Optional(
            Type.Array(Type.String(), {
              description:
                "技术面条件: rsi_oversold, macd_golden_cross, bollinger_breakout, volume_surge",
            }),
          ),
          fundamental: Type.Optional(
            Type.Array(Type.String(), {
              description:
                "基本面条件: pe_low, roe_high, gross_margin_high, debt_ratio_low",
            }),
          ),
          top_n: Type.Optional(
            Type.Number({ description: "取排名前N只 (默认50)" }),
          ),
        },
        { description: "筛选条件 (scan_create/create dynamic 需要)" },
      ),
    ),
    refresh_interval: Type.Optional(
      Type.Union([Type.Literal("daily"), Type.Literal("weekly")], {
        description: "动态池刷新周期",
      }),
    ),
    description: Type.Optional(
      Type.String({ description: "池子描述" }),
    ),
  }),
  execute: async (_toolCallId: string, rawParams: any) => {
    const {
      action,
      pool_id,
      name,
      pool_type,
      symbols,
      filter,
      refresh_interval,
      description,
    } = rawParams;

    try {
      let result: any;

      switch (action) {
        case "create":
          if (!name || !pool_type) {
            return _err("create 需要 name 和 pool_type 参数");
          }
          result = await createPool({
            name,
            pool_type,
            symbols,
            filter_template: filter,
            refresh_interval,
            description,
          });
          break;

        case "list":
          result = await listPools();
          break;

        case "get":
          if (!pool_id) return _err("get 需要 pool_id 参数");
          result = await getPool(pool_id);
          break;

        case "update":
          if (!pool_id) return _err("update 需要 pool_id 参数");
          result = await updatePool(pool_id, {
            name,
            symbols,
            description,
          } as any);
          break;

        case "delete":
          if (!pool_id) return _err("delete 需要 pool_id 参数");
          result = await deletePool(pool_id);
          break;

        case "refresh":
          if (!pool_id) return _err("refresh 需要 pool_id 参数");
          result = await refreshPool(pool_id);
          break;

        case "scan_create":
          if (!name || !pool_type || !filter) {
            return _err("scan_create 需要 name, pool_type, filter 参数");
          }
          result = await scanAndCreatePool({
            name,
            pool_type,
            filter,
            refresh_interval,
            description,
          });
          break;

        default:
          return _err(`未知操作: ${action}`);
      }

      const data = result?.data ?? result;
      const text = _formatResult(action, data);
      return {
        content: [{ type: "text" as const, text }],
        details: undefined,
      };
    } catch (error) {
      return _err(
        `操作失败: ${error instanceof Error ? error.message : String(error)}`,
      );
    }
  },
};

function _err(msg: string) {
  return {
    content: [{ type: "text" as const, text: `❌ ${msg}` }],
    details: undefined,
  };
}

function _formatResult(action: string, data: any): string {
  if (!data) return "操作完成（无返回数据）";

  switch (action) {
    case "list": {
      const pools = Array.isArray(data) ? data : [];
      if (pools.length === 0) return "📋 暂无股票池";
      const lines = pools.map(
        (p: any) =>
          `  [${p.id}] ${p.name} (${p.pool_type}) — ${p.symbol_count}只股票` +
          (p.refresh_interval ? ` — 刷新: ${p.refresh_interval}` : ""),
      );
      return `📋 股票池列表 (${pools.length}个):\n${lines.join("\n")}`;
    }

    case "get": {
      const syms = data.symbols || [];
      let text = `📊 池子详情: ${data.name} (${data.pool_type})\n`;
      text += `  成员 (${syms.length}只): ${syms.slice(0, 10).join(", ")}`;
      if (syms.length > 10) text += ` ... 等${syms.length}只`;
      if (data.filter_template) {
        text += `\n  筛选条件: ${JSON.stringify(data.filter_template)}`;
      }
      if (data.last_validation?.best_strategy) {
        const best = data.last_validation.best_strategy;
        text += `\n  最优策略: ${best.name || best.id} (评分: ${best.score})`;
      }
      return text;
    }

    case "create":
    case "scan_create": {
      const syms = data.symbols || [];
      return (
        `✅ 池子已创建: [${data.id}] ${data.name} (${data.pool_type})\n` +
        `  入池 ${syms.length} 只股票: ${syms.slice(0, 10).join(", ")}` +
        (syms.length > 10 ? ` ... 等${syms.length}只` : "")
      );
    }

    case "refresh": {
      const syms = data.symbols || [];
      return `🔄 池子已刷新: ${data.name}\n  当前 ${syms.length} 只股票`;
    }

    case "delete":
      return `🗑️ 池子已删除`;

    case "update":
      return `✏️ 池子已更新: ${data.name}`;

    default:
      return JSON.stringify(data, null, 2);
  }
}
