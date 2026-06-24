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
import { handleToolResponse } from "../utils/index.js";

interface NorthFlowParams {
  start_date?: string;
  end_date?: string;
}

interface FlowDataPoint {
  date: string;
  shanghai_flow?: number;
  shenzhen_flow?: number;
  total_flow?: number;
  [key: string]: any;
}

interface NorthFlowData {
  data?: FlowDataPoint[];
  summary?: {
    total_inflow?: number;
    total_outflow?: number;
    net_flow?: number;
    avg_daily_flow?: number;
  };
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
    "获取北向资金（沪股通+深股通）的历史流入流出数据。" +
    "北向资金是外资通过互联互通机制买入A股的资金，是重要的市场情绪指标。" +
    "正值表示净流入，负值表示净流出。" +
    "适用场景：跟踪外资动向、判断市场情绪、分析资金面。",

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

  execute: async (_toolCallId, params: NorthFlowParams) => {
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

      const nfData = (result as any).data as NorthFlowData;

      // API 成功但无数据：同样走 browser 兜底，避免 agent 拿到空结果直接停止
      if (!nfData || !nfData.data || nfData.data.length === 0) {
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
 */
function formatNorthFlowData(data: NorthFlowData): string {
  if (!data || !data.data || data.data.length === 0) {
    return "❌ 未获取到北向资金数据";
  }

  const flowData = data.data;
  let output = "💰 **北向资金流向**\n\n";

  // 1. 汇总统计
  if (data.summary) {
    output += "### 📊 汇总统计\n\n";
    const summary = data.summary;

    if (summary.net_flow !== undefined) {
      const netFlowFormatted = formatAmount(summary.net_flow);
      const flowType = summary.net_flow >= 0 ? "净流入" : "净流出";
      const emoji = summary.net_flow >= 0 ? "📈" : "📉";
      output += `- **区间净流向**：${emoji} ${flowType} ${netFlowFormatted}\n`;
    }

    if (summary.total_inflow !== undefined) {
      output += `- **累计流入**：${formatAmount(summary.total_inflow)}\n`;
    }

    if (summary.total_outflow !== undefined) {
      output += `- **累计流出**：${formatAmount(Math.abs(summary.total_outflow))}\n`;
    }

    if (summary.avg_daily_flow !== undefined) {
      output += `- **日均流向**：${formatAmount(summary.avg_daily_flow)}\n`;
    }

    output += "\n";
  }

  // 2. 最近10条数据
  output += "### 📅 最近流向记录\n\n";
  output += "| 日期 | 沪股通 | 深股通 | 合计 | 趋势 |\n";
  output += "|------|--------|--------|------|------|\n";

  const recentData = flowData.slice(-10);

  for (const item of recentData) {
    const shanghaiFlow = item.shanghai_flow || 0;
    const shenzhenFlow = item.shenzhen_flow || 0;
    const totalFlow = item.total_flow || (shanghaiFlow + shenzhenFlow);

    const shanghaiFormatted = formatAmount(shanghaiFlow, true);
    const shenzhenFormatted = formatAmount(shenzhenFlow, true);
    const totalFormatted = formatAmount(totalFlow, true);
    const trend = getTrendEmoji(totalFlow);

    output += `| ${item.date} | ${shanghaiFormatted} | ${shenzhenFormatted} | ${totalFormatted} | ${trend} |\n`;
  }

  output += "\n";

  // 3. 趋势分析
  if (flowData.length >= 5) {
    output += analyzeTrend(flowData);
  }

  return output;
}

/**
 * 格式化金额（亿元）
 */
function formatAmount(amount: number, withSign: boolean = false): string {
  const absAmount = Math.abs(amount);
  const formatted = absAmount >= 100
    ? absAmount.toFixed(0)
    : absAmount.toFixed(2);

  let result = `${formatted} 亿`;

  if (withSign) {
    if (amount > 0) {
      result = `+${result}`;
    } else if (amount < 0) {
      result = `-${result}`;
    }
  }

  return result;
}

/**
 * 获取趋势表情
 */
function getTrendEmoji(flow: number): string {
  if (flow > 50) return "🔥"; // 大幅流入
  if (flow > 10) return "📈"; // 流入
  if (flow > -10) return "➡️"; // 持平
  if (flow > -50) return "📉"; // 流出
  return "❄️"; // 大幅流出
}

/**
 * 分析趋势
 */
function analyzeTrend(data: FlowDataPoint[]): string {
  const recent5 = data.slice(-5);
  const inflowDays = recent5.filter(d => (d.total_flow || 0) > 0).length;
  const outflowDays = recent5.filter(d => (d.total_flow || 0) < 0).length;

  const totalFlow5d = recent5.reduce((sum, d) => sum + (d.total_flow || 0), 0);
  const avgFlow = totalFlow5d / 5;

  let output = "### 💡 趋势分析（近5日）\n\n";

  // 流向统计
  output += `- **流向天数**：流入 ${inflowDays} 天，流出 ${outflowDays} 天\n`;
  output += `- **日均流向**：${formatAmount(avgFlow)}\n`;

  // 趋势判断
  let trendDescription = "";
  if (inflowDays >= 4) {
    trendDescription = "🔥 **持续流入**，外资做多情绪强烈";
  } else if (inflowDays >= 3) {
    trendDescription = "📈 **净流入为主**，外资偏积极";
  } else if (outflowDays >= 4) {
    trendDescription = "❄️ **持续流出**，外资做空情绪明显";
  } else if (outflowDays >= 3) {
    trendDescription = "📉 **净流出为主**，外资偏谨慎";
  } else {
    trendDescription = "➡️ **流向分化**，外资观望为主";
  }

  output += `- **整体判断**：${trendDescription}\n`;

  // 连续性判断
  const latestFlow = recent5[recent5.length - 1].total_flow || 0;
  const previousFlow = recent5[recent5.length - 2]?.total_flow || 0;

  if (latestFlow > 0 && previousFlow > 0) {
    output += `- **连续性**：连续流入，外资持续加仓\n`;
  } else if (latestFlow < 0 && previousFlow < 0) {
    output += `- **连续性**：连续流出，外资持续减仓\n`;
  } else if (latestFlow > 0 && previousFlow < 0) {
    output += `- **连续性**：由流出转为流入，情绪改善\n`;
  } else if (latestFlow < 0 && previousFlow > 0) {
    output += `- **连续性**：由流入转为流出，情绪转弱\n`;
  }

  output += "\n";

  return output;
}
