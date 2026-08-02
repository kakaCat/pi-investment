/**
 * Verify Judgments Tool - 判断自校验工具（学习闭环层）
 *
 * 调用 quantsys-v2 /api/market/heatmap，把 agent 自己的判断痕迹
 * （个股信号 / 池调入调出 / 行业态度）与验证窗内实际涨跌对照，
 * 返回"判断对/错"的结论、胜率统计与学习提示——而非原始数据堆。
 *
 * 【判断规则】（与 web-frontend StockHeatmap/verdict.ts 一致）
 * - 买入信号 & 涨 / 卖出信号 & 跌 → 对；反向 → 错
 * - 池调入 & 涨 / 池调出 & 跌 → 对；反向 → 错
 * - 行业看好 & 行业涨 / 行业回避 & 行业跌 → 对；反向 → 错
 *
 * 【适用场景】每日复盘、周期学习、验证某次判断、回答"我最近的判断准不准"
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";
import { handleToolResponse, snakeize } from "../utils/index.js";

interface HeatmapSignal { type: 'buy' | 'sell'; date: string; strategy?: string }
interface HeatmapPoolEvent { action: 'add' | 'remove'; pool: string; date: string }
interface HeatmapStock {
  symbol: string; name: string; change_pct: number; in_scope: boolean;
  signals?: HeatmapSignal[]; pool_events?: HeatmapPoolEvent[];
}
interface HeatmapIndustry {
  name: string; change_pct: number; agent_stance: 'bullish' | 'bearish' | 'neutral';
  stocks: HeatmapStock[];
}
interface HeatmapData {
  date: string; window: number; actual_end_date: string | null;
  partial: boolean; scope_degraded: boolean; excluded_count: number;
  industries: HeatmapIndustry[]; message?: string;
}

type Verdict = 'right' | 'wrong' | 'none';

function judgeSignal(type: 'buy' | 'sell', changePct: number): Verdict {
  if (changePct === 0) return 'none';
  return (type === 'buy') === changePct > 0 ? 'right' : 'wrong';
}
function judgePoolEvent(action: 'add' | 'remove', changePct: number): Verdict {
  if (changePct === 0) return 'none';
  return (action === 'add') === changePct > 0 ? 'right' : 'wrong';
}
function judgeStance(stance: string, changePct: number): Verdict {
  if (stance === 'neutral' || changePct === 0) return 'none';
  return (stance === 'bullish') === changePct > 0 ? 'right' : 'wrong';
}

const VALID_WINDOWS = [1, 5, 20];

interface JudgmentLine { verdict: Verdict; text: string }

function collectJudgments(data: HeatmapData): { lines: JudgmentLine[]; right: number; wrong: number } {
  const lines: JudgmentLine[] = [];
  let right = 0, wrong = 0;
  const push = (verdict: Verdict, text: string) => {
    if (verdict === 'none') return;
    lines.push({ verdict, text });
    if (verdict === 'right') right++; else wrong++;
  };

  for (const ind of data.industries) {
    const stanceLabel = ind.agent_stance === 'bullish' ? '看好' : ind.agent_stance === 'bearish' ? '回避' : '中性';
    push(judgeStance(ind.agent_stance, ind.change_pct),
      `行业「${ind.name}」${stanceLabel} → 行业加权 ${fmtPct(ind.change_pct)}`);

    for (const s of ind.stocks) {
      if (!s.in_scope) continue;
      if (s.signals?.length) {
        const sig = s.signals[s.signals.length - 1];
        push(judgeSignal(sig.type, s.change_pct),
          `${s.name}(${s.symbol}) ${sig.type === 'buy' ? '买入' : '卖出'}信号 @${sig.date}${sig.strategy ? `（${sig.strategy}）` : ''} → ${fmtPct(s.change_pct)}`);
      }
      if (s.pool_events?.length) {
        const evt = s.pool_events[s.pool_events.length - 1];
        push(judgePoolEvent(evt.action, s.change_pct),
          `${s.name}(${s.symbol}) ${evt.action === 'add' ? '调入' : '调出'}「${evt.pool}」@${evt.date} → ${fmtPct(s.change_pct)}`);
      }
    }
  }
  return { lines, right, wrong };
}

function fmtPct(pct: number): string {
  return `${pct > 0 ? '+' : ''}${pct}%`;
}

function formatOutput(data: HeatmapData): string {
  const out: string[] = [];
  out.push(`📊 判断自校验（${data.date} → ${data.actual_end_date ?? '无数据'}，${data.window} 日验证窗）`);

  if (data.partial) {
    out.push(`⚠️ 验证窗未满：实际数据到 ${data.actual_end_date}，以下结论为阶段性结果`);
  }
  if (data.scope_degraded) {
    out.push(`ℹ️ 池成员历史无法回放，校验口径已退化为「信号+持仓」`);
  }

  const { lines, right, wrong } = collectJudgments(data);

  if (lines.length === 0) {
    const stockCount = data.industries.reduce((n, i) => n + i.stocks.filter(s => s.in_scope).length, 0);
    out.push('');
    out.push(`📭 无可校验判断：该判断日前 30 天内无信号、无池操作记录（图中有 ${stockCount} 只关联股票，均为无判断痕迹状态）。`);
    out.push(`💡 学习提示：校验需要判断痕迹——先产生信号或池调整，之后才能用本工具验证对错。`);
    return out.join('\n');
  }

  out.push('');
  for (const l of lines) {
    out.push(`${l.verdict === 'right' ? '✅' : '❌'} ${l.text}，判断${l.verdict === 'right' ? '正确' : '错误'}`);
  }

  const total = right + wrong;
  const winRate = total > 0 ? Math.round((right / total) * 100) : 0;
  out.push('');
  out.push(`📈 统计：判断对 ${right} / 判断错 ${wrong}（胜率 ${winRate}%）`);

  if (wrong > right) {
    out.push(`💡 学习提示：错误多于正确，建议复盘错误判断的共同特征（行业集中度/信号策略来源/入场时点），必要时降低相关策略的信号置信度。`);
  } else if (wrong > 0) {
    out.push(`💡 学习提示：整体向好，重点关注 ${wrong} 个错误判断的共性，作为下一轮规则优化的输入。`);
  } else {
    out.push(`💡 学习提示：全部正确，但样本量 ${total} 偏小，继续积累判断记录以提高统计显著性。`);
  }
  return out.join('\n');
}

export const verifyJudgmentsTool: ToolDefinition = {
  name: "verify_judgments",
  label: "判断自校验",
  description:
    "校验 agent 自己过去的投资判断是否正确。把指定判断日的信号/池操作/行业态度与其后 1/5/20 个交易日的实际涨跌对照，" +
    "输出每条判断的对错、胜率统计和学习提示。适用场景：每日复盘、周期学习、回答「我最近的判断准不准」、验证某次具体判断。",

  parameters: Type.Object({
    date: Type.Optional(Type.String({ description: "判断日 YYYY-MM-DD，默认=最近一个已走完验证窗的起点" })),
    window: Type.Optional(Type.Number({ description: "验证窗（交易日）：1/5/20，默认 5" })),
  }),

  execute: async (_toolCallId, params: { date?: string; window?: number }) => {
    try {
      const window = params.window ?? 5;
      if (!VALID_WINDOWS.includes(window)) {
        return {
          content: [{ type: "text" as const, text: `判断自校验失败: window 必须是 ${VALID_WINDOWS.join('/')} 之一` }],
          details: null,
        };
      }

      const result = await runQuantV2("market.heatmap", {
        date: params.date,
        window,
      });

      if (!result.ok) {
        throw new Error((result as any).error || "获取热力图数据失败");
      }

      const data = snakeize<HeatmapData>((result as any).data);
      const formattedOutput = formatOutput(data);

      return handleToolResponse({
        toolName: 'verify_judgments',
        data: { formattedText: formattedOutput, rawData: (result as any).data },
        formatter: (d) => d.formattedText,
        metadata: { timestamp: new Date().toISOString() },
        threshold: 10 * 1024,
      });
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{ type: "text" as const, text: `判断自校验失败: ${errorMsg}` }],
        details: null,
      };
    }
  },
};
