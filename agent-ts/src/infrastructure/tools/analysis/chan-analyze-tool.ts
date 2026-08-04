/**
 * Chan Analyze Tool - 缠论分析工具
 *
 * 调用 quantsys-v2 POST /api/chan/analyze，返回个股缠论结构：
 * 走势类型（上涨/下跌/盘整）、笔/线段/中枢、三类买卖点（1买/2买/3买），
 * 以及每类买卖点的历史验证胜率（来自 agent_knowledge 蒸馏，可能为 null）。
 *
 * 何时使用：
 * - 分析个股技术结构、判断当前处于什么走势阶段
 * - 评估缠论买卖点信号是否值得跟进（结合历史胜率）
 *
 * 解读提示：
 * - 1买（下跌背驰）最安全、2买（回调不破中枢）次之、3买（突破前高）最激进
 * - knowledge.win_rate 是按买卖点类型统计的历史胜率，samples<10 时参考意义弱
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { handleToolResponse } from "../utils/index.js";

interface ChanBuyPoint {
  type: string; price: number; date: string | null;
  confidence: number; position_ratio: number; reason: string;
  knowledge?: { win_rate: number; samples: number; suggested_confidence: string } | null;
}

function formatChan(data: any): string {
  const lines: string[] = [
    `缠论分析 ${data.symbol}：走势类型 = ${data.trend_type}`,
    `结构：笔 ${data.bis?.length ?? 0} 个，线段 ${data.segments?.length ?? 0} 个，中枢 ${data.zhongshus?.length ?? 0} 个`,
  ];
  const bps: ChanBuyPoint[] = data.buypoints ?? [];
  if (bps.length === 0) {
    lines.push('当前无买卖点信号。');
  } else {
    lines.push(`买卖点 ${bps.length} 个：`);
    for (const bp of bps) {
      let line = `- ${bp.type} @ ${bp.price}（${bp.date ?? '未知日期'}）置信度 ${(bp.confidence * 100).toFixed(0)}%，建议仓位 ${(bp.position_ratio * 100).toFixed(0)}%，原因：${bp.reason}`;
      if (bp.knowledge) {
        line += `｜历史胜率 ${(bp.knowledge.win_rate * 100).toFixed(0)}%（${bp.knowledge.samples} 样本），建议置信度：${bp.knowledge.suggested_confidence}`;
      }
      lines.push(line);
    }
  }
  return lines.join('\n');
}

export const chanAnalyzeTool: ToolDefinition = {
  name: "chan_analyze",
  label: "缠论分析",
  description: "缠论技术分析：识别个股走势类型（上涨/下跌/盘整）、笔/线段/中枢结构和三类买卖点（1买/2买/3买），并附各类型买卖点的历史验证胜率。用于技术结构分析和买卖点信号评估。",
  parameters: Type.Object({
    symbol: Type.String({ description: "股票代码，如 600519.SH" }),
    start_date: Type.Optional(Type.String({ description: "开始日期 YYYY-MM-DD（默认最近1年）" })),
    end_date: Type.Optional(Type.String({ description: "结束日期 YYYY-MM-DD（默认今天）" })),
  }),
  execute: async (_toolCallId: string, params: any) => {
    if (!params.symbol) {
      return {
        content: [{ type: "text" as const, text: "缺少必填参数: symbol" }],
        details: { success: false, error: "MISSING_SYMBOL" }
      };
    }
    try {
      const body: Record<string, unknown> = { symbol: params.symbol };
      if (params.start_date) body.startDate = params.start_date;
      if (params.end_date) body.endDate = params.end_date;
      const response = await runQuantV2("chan.analyze", body);
      // 注意：handleToolResponse 把 data 原样传给 formatter（不解包），
      // runQuantV2 返回 {ok, command, data: <v2响应体>}，需手动取 .data
      return handleToolResponse({
        toolName: 'chan_analyze',
        data: (response as any).data ?? response,
        formatter: (data) => typeof data === 'string' ? data : formatChan(data),
        metadata: { params }
      });
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{ type: "text" as const, text: `缠论分析失败: ${errorMsg}` }],
        details: { success: false, error: errorMsg, params }
      };
    }
  }
};
