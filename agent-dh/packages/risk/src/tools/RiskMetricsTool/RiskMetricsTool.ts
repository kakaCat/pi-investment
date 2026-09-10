/**
 * RiskMetricsTool - 风险指标工具
 */

import { BaseTool } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { riskMetricsPrompt, RiskMetricsParams, RiskMetricsResult } from './prompt';

/**
 * 风险指标工具类
 */
export class RiskMetricsTool extends BaseTool<RiskMetricsParams, RiskMetricsResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'risk_metrics',
    category: 'risk',
    version: '1.0.0',
    timeoutMs: 15000,
  };

  protected readonly prompt = riskMetricsPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(_args: RiskMetricsParams): ValidationResult {
    // 所有参数都是可选的，直接通过
    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(args: RiskMetricsParams, _context: ToolContext): Promise<RiskMetricsResult> {
    const days = args.days || 60;
    const account = args.account_name || 'agent_virtual';

    // 1) 账户口径基础指标（拿到 navPoints / returnsSource，用于基准对齐）
    const base: any = await this.qv2.getRiskMetrics({ account_name: account, days });

    // 2) 2026-09-11 新增（REQ-342799 P1 基准与归因）：
    //    后端 /api/risk/metrics 支持 benchmark_returns（empyrical 计算 alpha/beta/informationRatio），
    //    但需要与账户收益序列**等长对齐**——实测传 6 点基准配 55 点净值会得到 beta=0 的假值。
    //    此处拉沪深300 日收益，按长度尾部对齐后回传，使 beta/alpha 从『恒 0』变为真实值。
    const attribution = await this.buildAttribution(base, days);
    const enriched: any = attribution?.benchmark_returns?.length
      ? await this.qv2.getRiskMetrics({
          account_name: account,
          days,
          benchmark_returns: attribution.benchmark_returns,
        } as any)
      : base;

    const betaRaw = enriched?.beta ?? null;
    const alphaRaw = enriched?.alpha ?? null;
    const pct = (v: any) => {
      const n = Number(v ?? 0);
      return Math.abs(n) <= 1 ? +(n * 100).toFixed(2) : n;
    };
    return {
      volatility: pct(enriched?.annualVolatility ?? enriched?.volatility ?? 0),
      max_drawdown: pct(enriched?.maxDrawdown ?? enriched?.max_drawdown ?? 0),
      sharpe_ratio: Number(enriched?.sharpeRatio ?? 0),
      beta: Number(betaRaw ?? 0),
      alpha: Number(alphaRaw ?? 0),
      var_95: pct(enriched?.var95 ?? enriched?.var_95 ?? 0),
      sortino_ratio: Number(enriched?.sortinoRatio ?? 0),
      information_ratio: enriched?.informationRatio ?? null,
      beta_note: betaRaw === null
        ? '后端未计算 beta（未提供基准或基准未对齐）——此处 0 表示未计算，不代表无市场相关性'
        : 'backend_provided（基准=' + (attribution?.benchmark_name ?? '-') + '，' + (attribution?.alignment ?? '-') + '）',
      alpha_note: alphaRaw === null
        ? '后端未计算 alpha（无基准输入）——此处 0 表示未计算，不代表无超额收益'
        : 'backend_provided（年化口径，empyrical）',
      days_requested: days,
      window_note: '账户口径为净值序列日收益（returnsSource=' + String(enriched?.returnsSource ?? '?') +
        '，navPoints=' + String(enriched?.navPoints ?? '?') + '）；后端 days 实际用于取净值快照条数上限',
      attribution: attribution
        ? {
            benchmark_symbol: attribution.benchmark_symbol,
            benchmark_name: attribution.benchmark_name,
            benchmark_return_pct: attribution.benchmark_return_pct,
            portfolio_return_pct: pct(enriched?.cumulativeReturn),
            excess_return_pct:
              attribution.benchmark_return_pct === null || enriched?.cumulativeReturn === undefined
                ? null
                : +(pct(enriched.cumulativeReturn) - attribution.benchmark_return_pct).toFixed(2),
            beta: Number(betaRaw ?? 0),
            alpha_annual_pct: pct(alphaRaw),
            information_ratio: enriched?.informationRatio ?? null,
            nav_points: enriched?.navPoints ?? null,
            alignment: attribution.alignment,
            note: '超额=组合窗口收益-基准窗口收益；alpha 为年化扣β超额（empyrical）；样本点少时结论仅供参考',
          }
        : null,
    };
  }

  /**
   * 构建基准收益序列并做尾部对齐（2026-09-11，REQ-342799 P1）。
   * 返回 { benchmark_returns, benchmark_return_pct, alignment, ... }；任一步失败返回 null（不阻塞主指标）。
   */
  private async buildAttribution(base: any, days: number): Promise<any | null> {
    try {
      const navPoints = Number(base?.navPoints ?? 0);
      if (!Number.isFinite(navPoints) || navPoints < 5) return null;
      const end = new Date().toISOString().slice(0, 10);
      const start = new Date(Date.now() - Math.max(90, days * 2 + 40) * 86400000).toISOString().slice(0, 10);
      const raw: any = await (this.qv2 as any).getKlines('000300', start, end, 'daily');
      const rows: any[] = Array.isArray(raw) ? raw : (raw?.klines ?? []);
      const closes = rows.map((r) => Number(r.close)).filter((n) => Number.isFinite(n) && n > 0);
      if (closes.length < navPoints + 1) return null;
      const rets: number[] = [];
      for (let i = 1; i < closes.length; i++) rets.push(closes[i] / closes[i - 1] - 1);
      const tail = rets.slice(-navPoints);
      const tailCloses = closes.slice(-(navPoints + 1));
      const benchReturn =
        tailCloses.length >= 2 ? +((tailCloses[tailCloses.length - 1] / tailCloses[0] - 1) * 100).toFixed(2) : null;
      return {
        benchmark_returns: tail,
        benchmark_symbol: '000300',
        benchmark_name: '沪深300',
        benchmark_return_pct: benchReturn,
        alignment: 'tail-aligned by length(navPoints=' + navPoints + ', 基准点数=' + tail.length + ')',
      };
    } catch {
      return null;
    }
  }
  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: RiskMetricsResult, _context: ToolContext): ToolResponse<RiskMetricsResult> {
    return {
      success: true,
      data: result,
    };
  }
}
