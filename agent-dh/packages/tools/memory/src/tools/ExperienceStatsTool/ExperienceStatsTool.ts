/**
 * ExperienceStatsTool - 经验库胜率统计（聚合 experience 记忆）
 */

import { BaseTool, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import { experienceStatsPrompt, ExperienceStatsParams } from './prompt';

interface ParsedExperience {
  id: string;
  symbol: string;
  outcome: 'profit' | 'loss' | 'neutral' | null;
  pnlPct: number | null;
  createdAt: string;
}

export class ExperienceStatsTool extends BaseTool<ExperienceStatsParams, any> {
  protected readonly metadata: ToolMetadata = {
    name: 'experience_stats',
    category: 'memory',
    version: '1.0.0',
    timeoutMs: 15000,
  };

  protected readonly prompt = experienceStatsPrompt;

  constructor(private agentOsBaseURL: string) {
    super();
  }

  protected validate(args: ExperienceStatsParams): ValidationResult {
    if (args.symbol !== undefined && !/^\d{6}$/.test(args.symbol)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbol',
        issue: 'symbol 必须是6位数字股票代码',
        received: args.symbol,
        expected: '6位数字',
        example: '601857',
      };
    }
    return { success: true };
  }

  protected async execute(args: ExperienceStatsParams, _context: ToolContext): Promise<any> {
    const limit = Math.min(Math.max(args.limit ?? 200, 1), 500);
    const url = `${this.agentOsBaseURL}/api/v1/memory?category=experience&limit=${limit}`;
    const resp = await fetch(url);
    if (!resp.ok) {
      throw new Error(`经验库查询失败: HTTP ${resp.status}`);
    }
    const res: any = await resp.json();
    const raw: any[] = res?.memories ?? res?.items ?? [];

    const cutoff = args.days ? Date.now() - args.days * 86400_000 : null;
    const parsed: ParsedExperience[] = [];
    for (const it of raw) {
      const content = String(it?.content ?? '');
      const title = String(it?.title ?? '');
      const createdAt = String(it?.created_at ?? it?.createdAt ?? '');

      // 标的：title 开头 6 位数字（experience_write 契约：title = `${symbol} ${outcome} ${scenario}`）
      const symbol = (title.match(/^(\d{6})/)?.[1]) ?? (content.match(/^(\d{6})/)?.[1]) ?? '';
      if (args.symbol && symbol !== args.symbol) continue;
      if (cutoff && createdAt && new Date(createdAt).getTime() < cutoff) continue;

      const outcomeRaw = content.match(/结果：(profit|loss|neutral)/)?.[1] ?? null;
      const pnlRaw = content.match(/盈亏：(-?\d+(?:\.\d+)?)%/)?.[1];
      parsed.push({
        id: String(it?.id ?? ''),
        symbol,
        outcome: outcomeRaw as ParsedExperience['outcome'],
        pnlPct: pnlRaw !== undefined ? parseFloat(pnlRaw) : null,
        createdAt,
      });
    }

    const total = parsed.length;
    const profits = parsed.filter((p) => p.outcome === 'profit');
    const losses = parsed.filter((p) => p.outcome === 'loss');
    const neutrals = parsed.filter((p) => p.outcome === 'neutral');
    const withPnl = parsed.filter((p) => p.pnlPct !== null);
    const winRate = total > 0 ? Math.round((profits.length / total) * 1000) / 10 : 0;
    const avgPnl = withPnl.length > 0
      ? Math.round((withPnl.reduce((s, p) => s + (p.pnlPct ?? 0), 0) / withPnl.length) * 100) / 100
      : null;
    const avgWin = profits.filter((p) => p.pnlPct !== null).length > 0
      ? Math.round((profits.reduce((s, p) => s + (p.pnlPct ?? 0), 0) / profits.filter((p) => p.pnlPct !== null).length) * 100) / 100
      : null;
    const avgLoss = losses.filter((p) => p.pnlPct !== null).length > 0
      ? Math.round((losses.reduce((s, p) => s + (p.pnlPct ?? 0), 0) / losses.filter((p) => p.pnlPct !== null).length) * 100) / 100
      : null;

    // 按标的分布
    const bySymbol: Record<string, { total: number; profit: number; loss: number; avg_pnl_pct: number | null }> = {};
    for (const p of parsed) {
      const key = p.symbol || 'unknown';
      if (!bySymbol[key]) bySymbol[key] = { total: 0, profit: 0, loss: 0, avg_pnl_pct: null };
      bySymbol[key].total += 1;
      if (p.outcome === 'profit') bySymbol[key].profit += 1;
      if (p.outcome === 'loss') bySymbol[key].loss += 1;
    }
    for (const key of Object.keys(bySymbol)) {
      const rows = parsed.filter((p) => (p.symbol || 'unknown') === key && p.pnlPct !== null);
      bySymbol[key].avg_pnl_pct = rows.length > 0
        ? Math.round((rows.reduce((s, p) => s + (p.pnlPct ?? 0), 0) / rows.length) * 100) / 100
        : null;
    }

    return sanitizeLossless({
      total,
      win_rate: winRate,
      avg_pnl_pct: avgPnl,
      avg_win_pct: avgWin,
      avg_loss_pct: avgLoss,
      low_confidence: total < 10,
      by_outcome: { profit: profits.length, loss: losses.length, neutral: neutrals.length, untagged: total - profits.length - losses.length - neutrals.length },
      by_symbol: bySymbol,
      filters: { symbol: args.symbol ?? null, days: args.days ?? null },
      note: total < 10 ? '样本不足 10 条，胜率仅供参考' : undefined,
    });
  }

  protected wrap(data: any, _context: ToolContext): ToolResponse<any> {
    return { success: true, data };
  }
}
