/**
 * Evolution Leaderboard Tool - 行为进化适应度排行榜
 *
 * 调用 quantsys-v2 GET /api/evolution/leaderboard，返回全账户滚动 20 日
 * 双侧捕获适应度排名：fitness = 上涨捕获 − 下跌捕获。
 * 上涨捕获 ≥1 = 大盘涨时跟得上；下跌捕获越小 = 大盘跌时亏得越少。
 *
 * 何时使用：每日复盘评估自己在全账户中的相对表现；判断当前行为模式
 * 是「涨跟不上」还是「跌守不住」。
 *
 * 解读提示：
 * - 上涨捕获 ≥1 为跟上大盘，<1 为涨时掉队
 * - 下跌捕获 <1 为跌时少亏，>1 为跌时亏更多
 * - status 非 ok（insufficient_sample / no_trades / data_gap）不参与排名
 */
import { Type } from "@sinclair/typebox";
import type { ToolDefinition } from "../index.js";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { handleToolResponse } from "../utils/index.js";

interface FitnessRow {
  rank: number; accountName: string; fitness: number | null;
  upCapture: number | null; downCapture: number | null;
  upDays: number; downDays: number; status: string;
}

function formatBoard(data: any): string {
  const ranking: FitnessRow[] = data.ranking ?? [];
  if (ranking.length === 0) {
    return `尚无适应度数据（${data.message ?? '等待每日计算任务产出'}）。`;
  }
  const lines: string[] = [
    `行为进化适应度排行（窗口 ${data.windowEnd} 止 ${data.windowDays} 交易日）：`,
  ];
  for (const r of ranking) {
    if (r.status !== 'ok' || r.fitness == null) {
      lines.push(`#${r.rank} ${r.accountName}：${r.status}（样本不足或无交易，不参与排名）`);
      continue;
    }
    lines.push(
      `#${r.rank} ${r.accountName}：适应度 ${r.fitness.toFixed(2)}` +
      `｜上涨捕获 ${r.upCapture!.toFixed(2)}（${r.upDays} 个涨日）` +
      `｜下跌捕获 ${r.downCapture!.toFixed(2)}（${r.downDays} 个跌日）`
    );
  }
  lines.push('解读：上涨捕获≥1 为跟上大盘；下跌捕获<1 为跌时少亏；适应度越高越好。');
  return lines.join('\n');
}

export const evolutionLeaderboardTool: ToolDefinition = {
  name: "evolution_leaderboard",
  label: "进化适应度排行",
  description: "查看全账户滚动20日双侧捕获适应度排名（fitness=上涨捕获−下跌捕获）。用于每日复盘评估相对表现：涨时是否跟上、跌时是否守住。",
  parameters: Type.Object({
    window: Type.Optional(Type.Number({ description: "窗口交易日数，默认 20", default: 20 })),
  }),
  execute: async (_toolCallId: string, params: any) => {
    try {
      const response = await runQuantV2("evolution.leaderboard", { window: params.window ?? 20 });
      return handleToolResponse({
        toolName: 'evolution_leaderboard',
        data: (response as any).data ?? response,
        formatter: (data) => typeof data === 'string' ? data : formatBoard(data),
        metadata: { params },
      });
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{ type: "text" as const, text: `适应度排行查询失败: ${errorMsg}` }],
        details: { success: false, error: errorMsg, params },
      };
    }
  },
};
