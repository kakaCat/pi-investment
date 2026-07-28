/**
 * Data Fetch North Flow Tool - L1 数据管道层
 *
 * 获取北向资金流向数据（沪股通 + 深股通）。
 *
 * 【数据说明】
 * - 北向资金：境外资金通过沪港通、深港通买入A股的资金
 * - 正值：净流入（外资买入 > 卖出）
 * - 负值：净流出（外资卖出 > 买入）
 * - 数据更新：交易日盘后更新
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { wrapToolExecution } from "../shared/error-handler.js";
import { handleToolResponse, snakeize } from "../utils/index.js";

interface NorthFlowParams {
  start_date?: string;
  end_date?: string;
}

interface FlowDataPoint {
  trade_date: string;
  net_flow: number;        // 估算净买入（元）
  sh_net_flow?: number;
  sz_net_flow?: number;
  [key: string]: any;
}

interface HoldingChange {
  symbol: string;
  name?: string;
  delta_shares?: number;
  close?: number;
  estimated_value?: number;  // 元
}

interface NorthFlowData {
  data?: FlowDataPoint[];
  summary?: {
    total_net_flow?: number;   // 元
    latest_date?: string;
    prev_date?: string;
    method?: string;
    disclosure_frequency?: string;
    estimated?: boolean;
    note?: string;
    coverage?: number;
    top_inflows?: HoldingChange[];
    top_outflows?: HoldingChange[];
  };
  stale?: boolean;
  [key: string]: any;
}

/**
 * 北向资金兜底数据源（供 browser 工具抓取）。
 * 注意：2024 年 8 月起官方已停止披露北向资金实时/每日净流入明细，
 * 以下页面提供持股变动、成交活跃股等可用替代数据。
 */
const BROWSER_FALLBACK_SOURCES: Array<{ name: string; url: string; note: string }> = [
  {
    name: "东方财富 沪深港通",
    url: "https://data.eastmoney.com/hsgt/index.html",
    note: "沪深港通资金/持股总览，含北向持股市值与变动",
  },
  {
    name: "东方财富 北向持股明细",
    url: "https://data.eastmoney.com/hsgtcg/list.html",
    note: "北向资金个股持股变动明细",
  },
  {
    name: "同花顺 沪深港通",
    url: "https://data.10jqka.com.cn/hgt/",
    note: "沪深港通资金流向与成交活跃股",
  },
];

/**
 * 构造 browser 兜底指引（API 失败时返回给 agent）。
 * 遵循 SOUL.md「数据工具失败 = 先 browser 兜底，再停止」策略。
 */
function buildBrowserFallbackText(errorMsg: string): string {
  let out = `⚠️ 北向资金 API 获取失败：${errorMsg}\n\n`;
  out += "**请按 SOUL.md 兜底策略，用 `browser` 工具抓取数据**：\n\n";
  out += "1. 调用 `browser` action=navigate，url 选用下方任一数据源；\n";
  out += "2. 再调用 `browser` action=getText 读取页面文本，提取北向资金数据；\n";
  out += "3. 结论中标注 `（browser兜底，可信度较低）`。\n\n";
  out += "**推荐数据源**（按优先级）：\n";
  for (const src of BROWSER_FALLBACK_SOURCES) {
    out += `- ${src.name}：${src.url}\n  ${src.note}\n`;
  }
  out += "\n💡 提示：2024-08 起官方已停止披露北向资金每日净流入明细，";
  out += "若只需持股变动/成交活跃股，以上页面即可满足；若必须每日净额，browser 也无法获取时应如实说明。\n";
  return out;
}

export const dataFetchNorthFlowTool: ToolDefinition = {
  name: "data_fetch_north_flow",
  label: "获取北向资金流向",
  description:
    "获取北向资金动向。注意：北向【每日】净买入已于2024-08停止官方披露；" +
    "本工具返回港交所CCASS季度持股变化估算（外资季度调仓方向+增减持个股榜单），" +
    "适合判断外资中长期态度，不可当作每日资金流。" +
    "适用场景：跟踪外资季度调仓方向、识别外资增减持个股。",

  parameters: Type.Object({
    start_date: Type.Optional(
      Type.String({
        description: "开始日期，格式：YYYY-MM-DD。默认：近30天",
        pattern: "^\\d{4}-\\d{2}-\\d{2}$"
      })
    ),
    end_date: Type.Optional(
      Type.String({
        description: "结束日期，格式：YYYY-MM-DD。默认：今天",
        pattern: "^\\d{4}-\\d{2}-\\d{2}$"
      })
    )
  }),

  execute: async (_toolCallId: string, params: NorthFlowParams) => {
    try {
      const { start_date, end_date } = params;

      // 调用 quantsys-v2 API（命令名须匹配 V2_ROUTES 映射键：market.north_flow）
      const result = await runQuantV2("market.north_flow", {
        start_date,
        end_date
      });

      if (!result.ok) {
        throw new Error((result as any).error?.message || "获取北向资金数据失败");
      }

      const nfData = snakeize<NorthFlowData>((result as any).data);

      // API 成功但无数据：同样走 browser 兜底，避免 agent 拿到空结果直接停止
      if (!nfData || !(nfData as any).data || (nfData as any).data.length === 0) {
        return {
          content: [{
            type: "text" as const,
            text: buildBrowserFallbackText("API 返回空数据（北向资金明细可能已停止披露）"),
          }],
          details: { fallback: "browser", reason: "empty_data" },
        };
      }

      // 格式化输出并使用统一响应处理
      const formattedOutput = formatNorthFlowData(nfData);

      return handleToolResponse({
        toolName: 'data_fetch_north_flow',
        data: { formattedText: formattedOutput, rawData: (result as any).data },
        formatter: (d) => d.formattedText,
        metadata: { start_date, end_date },
        threshold: 15 * 1024, // 15KB
      });
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      // API 失败 → 返回 browser 兜底指引（而非直接报错停止）
      return {
        content: [{
          type: "text" as const,
          text: buildBrowserFallbackText(errorMsg),
        }],
        details: { fallback: "browser", reason: "api_error", error: errorMsg }
      };
    }
  }
};

/**
 * 格式化北向资金数据输出
 *
 * 契约（2026-07-28 起）：北向每日净买入已于 2024-08 停止披露（交易所
 * 规则变更，无免费替代）。后端改用港交所 CCASS 季度持股变化估算，
 * 金额单位为元。输出必须强调「季度估算」语义，避免 agent 当成每日资金流。
 */
function formatNorthFlowData(data: NorthFlowData): string {
  if (!data || !data.data || data.data.length === 0) {
    return "❌ 未获取到北向资金数据";
  }

  const summary = data.summary || {};
  let output = "💰 **北向资金（外资季度调仓估算）**\n\n";

  // 语义警告（最重要，放最前）
  output += "⚠️ **数据性质说明**：北向【每日】净买入已于 2024-08 停止官方披露，";
  output += "以下为港交所 CCASS **季度持股变化 × 收盘价**的估算值，";
  output += "反映外资**季度级**调仓方向，不能当作每日资金流使用。\n\n";

  if (data.stale) {
    output += "⚠️ 本次返回的是过期缓存（数据源暂时不可用）\n\n";
  }

  // 汇总
  if (summary.total_net_flow !== undefined) {
    const total = summary.total_net_flow / 1e8;
    const emoji = total >= 0 ? "📈" : "📉";
    const dir = total >= 0 ? "增持" : "减持";
    output += "### 📊 季度持股变化\n\n";
    output += `- **对比区间**：${summary.prev_date} → ${summary.latest_date}\n`;
    output += `- **外资${dir}估算**：${emoji} **${total >= 0 ? '+' : ''}${total.toFixed(1)} 亿元**\n`;
    if (summary.coverage !== undefined) {
      output += `- **价格覆盖率**：${(summary.coverage * 100).toFixed(0)}%（有收盘价的持仓占比）\n`;
    }
    output += "\n";
  }

  // 增持榜
  if (summary.top_inflows?.length) {
    output += "### 🟢 外资增持 TOP\n\n";
    output += "| 股票 | 持股变化 | 估算金额 |\n|------|----------|----------|\n";
    for (const item of summary.top_inflows.slice(0, 5)) {
      output += `| ${item.name || item.symbol} (${item.symbol}) | ${formatShares(item.delta_shares)} | +${((item.estimated_value || 0) / 1e8).toFixed(1)}亿 |\n`;
    }
    output += "\n";
  }

  // 减持榜
  if (summary.top_outflows?.length) {
    output += "### 🔴 外资减持 TOP\n\n";
    output += "| 股票 | 持股变化 | 估算金额 |\n|------|----------|----------|\n";
    for (const item of summary.top_outflows.slice(0, 5)) {
      output += `| ${item.name || item.symbol} (${item.symbol}) | ${formatShares(item.delta_shares)} | ${((item.estimated_value || 0) / 1e8).toFixed(1)}亿 |\n`;
    }
    output += "\n";
  }

  if (summary.note) {
    output += `> ${summary.note}\n`;
  }

  return output;
}

/** 持股数量格式化（万股/亿股） */
function formatShares(shares?: number): string {
  if (shares === undefined || shares === null) return "-";
  const sign = shares >= 0 ? "+" : "-";
  const abs = Math.abs(shares);
  if (abs >= 1e8) return `${sign}${(abs / 1e8).toFixed(2)}亿股`;
  return `${sign}${(abs / 1e4).toFixed(0)}万股`;
}
