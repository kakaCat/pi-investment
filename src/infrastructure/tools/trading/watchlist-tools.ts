/**
 * Watchlist Tool — 关注列表管理
 *
 * 管理"想买的股票"备选池，独立于已持仓管理。
 * 数据存储在 .pi-invest/watchlist.json
 *
 * 三个池子：
 *   A池=核心建仓（确定性高，随时准备出手）
 *   B池=候选观察（需要等买点或更多确认）
 *   C池=研究关注（初步了解，待深度分析）
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { WatchlistService } from "../../../services/portfolio/watchlist-service.js";
import { join } from "path";

const PI_DIR = join(process.cwd(), ".pi-invest");
const _watchlistSvc = new WatchlistService(PI_DIR);

const poolLabel: Record<string, string> = { A: "核心建仓", B: "候选观察", C: "研究关注" };
const statusLabel: Record<string, string> = {
  watching: "关注中",
  ready: "待买入",
  bought: "已买入",
  discarded: "已放弃",
};

export const manageWatchlistTool: ToolDefinition = {
  name: "manage_watchlist",
  label: "管理关注列表",
  description: [
    "管理关注/自选股票列表（备选池），存储在 .pi-invest/watchlist.json。",
    "Actions:",
    "  'list' — 列出全部关注，按 A/B/C 池分组展示",
    "  'get' — 查看某只股票的关注详情（symbol）",
    "  'add' — 添加关注 【必需: symbol, name, market, reason, buy_range_low】",
    "  'update' — 更新关注项信息",
    "  'remove' — 移除关注项",
    "  'ready' — 列出价格已到买入区的关注项",
    "  'summary' — 文本摘要",
    "",
    "优先级: 1(最高)~5(最低)。池子: A=核心建仓 B=候选观察 C=研究关注。",
    "买入后 → update status='bought'。放弃 → update status='discarded'。",
  ].join("\n"),
  promptSnippet: '需要管理自选股列表时',
  promptGuidelines: [
    '支持添加、删除、查询自选股',
    '可以为每只股票添加备注和标签',
    '自选股会在每日分析中优先关注'
  ],
  parameters: Type.Object({
    action: Type.Union(
      [
        Type.Literal("list"),
        Type.Literal("get"),
        Type.Literal("add"),
        Type.Literal("update"),
        Type.Literal("remove"),
        Type.Literal("ready"),
        Type.Literal("summary"),
      ],
      { description: "操作类型" }
    ),
    symbol: Type.Optional(
      Type.String({
        description: "股票代码（6位A股或HK代码），get/add/update/remove 时需要",
      })
    ),
    name: Type.Optional(Type.String({ description: "股票名称（add 时需要）" })),
    market: Type.Optional(
      Type.Union([Type.Literal("A"), Type.Literal("HK")], {
        description: "市场: A=A股, HK=港股（add 时需要）",
      })
    ),
    reason: Type.Optional(Type.String({ description: "关注理由（add 时需要）" })),
    buy_range_low: Type.Optional(
      Type.Number({ description: "买入区间下限（add 时需要）" })
    ),
    buy_range_high: Type.Optional(
      Type.Number({ description: "买入区间上限，0=市价（默认0）" })
    ),
    target_price: Type.Optional(Type.Number({ description: "目标价（可选）" })),
    stop_loss: Type.Optional(Type.Number({ description: "止损价（可选）" })),
    priority: Type.Optional(
      Type.Integer({ description: "优先级 1~5，1最高（默认3）" })
    ),
    pool: Type.Optional(
      Type.Union([Type.Literal("A"), Type.Literal("B"), Type.Literal("C")], {
        description: "池子: A=核心建仓, B=候选观察, C=研究关注（默认C）",
      })
    ),
    status: Type.Optional(
      Type.Union(
        [
          Type.Literal("watching"),
          Type.Literal("ready"),
          Type.Literal("bought"),
          Type.Literal("discarded"),
        ],
        { description: "状态（update 时使用）" }
      )
    ),
    notes: Type.Optional(Type.String({ description: "备注" })),
  }),
  execute: async (_toolCallId: string, params: any) => {
    const {
      action,
      symbol,
      name,
      market,
      reason,
      buy_range_low,
      buy_range_high,
      target_price,
      stop_loss,
      priority,
      pool,
      status,
      notes,
    } = params;

    try {
      // ── list ──────────────────────────────────────────────────────────────
      if (action === "list") {
        const summary = _watchlistSvc.getSummary();
        const pools = ["A", "B", "C"];
        const sections = pools
          .map((p) => {
            const items = summary[`${p}_pool`] ?? [];
            if (items.length === 0) return "";
            const itemLines = items.map(
              (item: any, i: number) =>
                `${i + 1}. **${item.name}**（\`${item.symbol}\`）` +
                (item.buy_range_low
                  ? `买入 ¥${item.buy_range_low}~${item.buy_range_high || "市价"}`
                  : "") +
                (item.target_price ? ` → 目标 ¥${item.target_price}` : "") +
                (item.stop_loss ? ` ⛔ ${item.stop_loss}` : "") +
                ` | ${item.reason ?? ""}` +
                (item.notes ? `\n   > ${item.notes}` : "")
            );
            return `## ${poolLabel[p]}（${items.length} 只）\n${itemLines.join("\n\n")}`;
          })
          .filter(Boolean);

        return {
          content: [
            {
              type: "text" as const,
              text: `📋 关注列表总览（共 ${summary.total ?? 0} 只，含已买/已弃）\n\n${sections.join("\n\n")}`,
            },
          ],
          details: undefined,
        };
      }

      // ── get ───────────────────────────────────────────────────────────────
      if (action === "get") {
        if (!symbol)
          return {
            content: [
              {
                type: "text" as const,
                text: "⚠️ 查看关注项需要提供 symbol（股票代码）",
              },
            ],
            details: undefined,
          };
        const item = _watchlistSvc.get(symbol);
        if (!item)
          return {
            content: [
              { type: "text" as const, text: `未在关注列表中找到: ${symbol}` },
            ],
            details: undefined,
          };

        return {
          content: [
            {
              type: "text" as const,
              text: [
                `📋 **${item.name}**（\`${item.symbol}\`）关注详情`,
                `• 池子: ${poolLabel[item.pool] ?? item.pool}`,
                `• 优先级: ${"⭐".repeat(item.priority ?? 3)}`,
                `• 状态: ${statusLabel[item.status] ?? item.status}`,
                `• 买入区间: ¥${item.buy_range_low ?? "-"} ~ ¥${item.buy_range_high || "市价"}`,
                item.target_price ? `• 目标价: ¥${item.target_price}` : "",
                item.stop_loss ? `• 止损价: ¥${item.stop_loss}` : "",
                `• 理由: ${item.reason ?? "-"}`,
                item.notes ? `• 备注: ${item.notes}` : "",
              ]
                .filter(Boolean)
                .join("\n"),
            },
          ],
          details: undefined,
        };
      }

      // ── add ───────────────────────────────────────────────────────────────
      if (action === "add") {
        if (!symbol || !name || !market || !reason || buy_range_low == null) {
          return {
            content: [
              {
                type: "text" as const,
                text: "⚠️ 添加关注需要提供：\n• symbol（股票代码）\n• name（股票名称）\n• market（市场: A或HK）\n• reason（关注理由）\n• buy_range_low（买入区间下限）",
              },
            ],
            details: undefined,
          };
        }
        const res = _watchlistSvc.add(
          symbol,
          name,
          market,
          reason,
          buy_range_low,
          buy_range_high ?? 0,
          target_price ?? 0,
          stop_loss ?? 0,
          priority ?? 3,
          pool ?? "C",
          notes ?? ""
        );
        return {
          content: [
            {
              type: "text" as const,
              text: res.success
                ? `✅ 已添加 **${name}**（\`${symbol}\`）到关注列表\n  • 池子: ${poolLabel[pool ?? "C"]}\n  • 买入区间: ¥${buy_range_low} ~ ¥${buy_range_high || "市价"}\n  • 理由: ${reason}`
                : `❌ 添加失败: ${res.message ?? res.error ?? "未知错误"}`,
            },
          ],
          details: undefined,
        };
      }

      // ── update ────────────────────────────────────────────────────────────
      if (action === "update") {
        if (!symbol)
          return {
            content: [
              {
                type: "text" as const,
                text: "⚠️ 更新关注项需要提供 symbol（股票代码）",
              },
            ],
            details: undefined,
          };
        const updates: Record<string, any> = {};
        if (name !== undefined) updates.name = name;
        if (buy_range_low !== undefined) updates.buy_range_low = buy_range_low;
        if (buy_range_high !== undefined) updates.buy_range_high = buy_range_high;
        if (target_price !== undefined) updates.target_price = target_price;
        if (stop_loss !== undefined) updates.stop_loss = stop_loss;
        if (priority !== undefined) updates.priority = priority;
        if (pool !== undefined) updates.pool = pool;
        if (status !== undefined) updates.status = status;
        if (reason !== undefined) updates.reason = reason;
        if (notes !== undefined) updates.notes = notes;

        const res = _watchlistSvc.update(symbol, updates);
        const updatedFields = Object.keys(updates).join(", ");
        return {
          content: [
            {
              type: "text" as const,
              text: res.success
                ? `✅ 已更新 \`${symbol}\` 的关注信息：${updatedFields}`
                : `❌ 更新失败: ${res.message ?? res.error ?? "未知错误"}`,
            },
          ],
          details: undefined,
        };
      }

      // ── remove ────────────────────────────────────────────────────────────
      if (action === "remove") {
        if (!symbol)
          return {
            content: [
              {
                type: "text" as const,
                text: "⚠️ 移除关注项需要提供 symbol（股票代码）",
              },
            ],
            details: undefined,
          };
        const res = _watchlistSvc.remove(symbol);
        return {
          content: [
            {
              type: "text" as const,
              text: res.success
                ? `✅ 已将 \`${symbol}\` 从关注列表中移除`
                : `❌ 移除失败: ${res.message ?? res.error ?? "未知错误"}`,
            },
          ],
          details: undefined,
        };
      }

      // ── ready ─────────────────────────────────────────────────────────────
      if (action === "ready") {
        const ready = _watchlistSvc.getReadyToBuy();
        if (ready.length === 0) {
          return {
            content: [
              {
                type: "text" as const,
                text: "📋 当前没有价格已到买入区的关注项",
              },
            ],
            details: undefined,
          };
        }
        const lines = ready.map(
          (item: any, i: number) =>
            `${i + 1}. **${item.name}**（\`${item.symbol}\`）— 已到买入区间 ¥${item.buy_range_low ?? "-"}`
        );
        return {
          content: [
            {
              type: "text" as const,
              text: `📋 以下 ${ready.length} 只关注项已到买入区间\n\n${lines.join("\n")}`,
            },
          ],
          details: undefined,
        };
      }

      // ── summary ───────────────────────────────────────────────────────────
      if (action === "summary") {
        const text = _watchlistSvc.summaryText();
        return { content: [{ type: "text" as const, text: text }], details: undefined };
      }

      return {
        content: [
          {
            type: "text" as const,
            text: `⚠️ 未知操作: "${action}"，有效操作: list / get / add / update / remove / ready / summary`,
          },
        ],
        details: undefined,
      };
    } catch (e) {
      return {
        content: [
          { type: "text" as const, text: `❌ 操作失败: ${String(e)}` },
        ],
        details: undefined,
      };
    }
  },
};
