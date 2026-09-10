/**
 * RiskMetricsTool - 风险指标工具
 */

import { BaseTool } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { riskMetricsPrompt, RiskMetricsParams, RiskMetricsResult } from './prompt';
import { alignByTradingDate } from './attributionAlignment';

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
    const attribution = await this.buildAttribution(base, days, account);
    const navCoverage = await this.probeNavCoverage(account, Number(base?.navPoints ?? 0));
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
      nav_coverage: navCoverage,
      window_note: '账户口径为净值序列日收益（returnsSource=' + String(enriched?.returnsSource ?? '?') +
        '，navPoints=' + String(enriched?.navPoints ?? '?') + '）；后端 days 实际用于取净值快照条数上限' +
        (navCoverage && navCoverage.missing_count > 0
          ? '；[缺口] 净值序列缺 ' + navCoverage.missing_count + ' 个工作日 → 日收益口径失真'
          : ''),
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
   * 取账户净值序列日期（升序）。与 probeNavCoverage 同源（/api/simulation/performance），
   * 供**按交易日对齐**使用（2026-09-11，w-f4aa1f6a）。失败返回 null，不阻塞主指标。
   */
  private async fetchNavDates(account: string): Promise<string[] | null> {
    try {
      const base = process.env.QUANTSYS_V2_API_URL || 'http://127.0.0.1:5001';
      const url = base + '/api/simulation/performance?account_name=' + encodeURIComponent(account);
      const res = await fetch(url);
      if (!res.ok) return null;
      const body: any = await res.json();
      const curve: any[] = body?.data?.equity_curve ?? [];
      const dates = curve.map((r) => String(r?.date ?? '').slice(0, 10)).filter(Boolean);
      return dates.length ? Array.from(new Set(dates)).sort() : null;
    } catch {
      return null;
    }
  }
  /**
   * 净值序列缺口探测（2026-09-11，REQ-342799 P3）。
   * 波动率/alpha/IR 由相邻快照差分的日收益算出；缺交易日会把跨日涨跌当成单日收益。
   * 实测 agent_virtual：59 个交易日只有 55 条快照（缺 08-10/08-24/08-26/08-27/08-31）。
   * 只做可见化，不改写数据（该表口径由 w-8f2c4cc5 维护）。
   */
  private async probeNavCoverage(account: string, navPoints: number): Promise<any | null> {
    try {
      const base = process.env.QUANTSYS_V2_API_URL || 'http://127.0.0.1:5001';
      const url = base + '/api/simulation/performance?account_name=' + encodeURIComponent(account);
      const res = await fetch(url);
      if (!res.ok) return null;
      const body: any = await res.json();
      const curve: any[] = body?.data?.equity_curve ?? [];
      const dates = curve.map((r) => String(r?.date ?? '')).filter(Boolean);
      if (dates.length < 5) return null;
      const tail = navPoints > 0 && navPoints < dates.length ? dates.slice(-navPoints) : dates;
      const missing: string[] = [];
      for (let i = 1; i < tail.length; i++) {
        const prev = new Date(tail[i - 1] + 'T00:00:00Z');
        const cur = new Date(tail[i] + 'T00:00:00Z');
        const gapDays = Math.round((cur.getTime() - prev.getTime()) / 86400000);
        if (gapDays <= 1) continue;
        for (let d = 1; d < gapDays; d++) {
          const day = new Date(prev.getTime() + d * 86400000);
          const wd = day.getUTCDay();
          if (wd !== 0 && wd !== 6) missing.push(day.toISOString().slice(0, 10));
        }
      }
      const impact = missing.length
        ? '存在缺口 → 日收益口径失真，波动率/alpha/IR 解读须保守'
        : '序列连续，日收益口径可用';
      return {
        points: tail.length,
        from: tail[0],
        to: tail[tail.length - 1],
        missing_weekdays: missing.slice(0, 20),
        missing_count: missing.length,
        basis: '按相邻快照间隔识别缺失工作日（未扣法定节假日，数字可能略高估）',
        impact,
      };
    } catch {
      return null;
    }
  }
  /**
   * 构建基准收益序列并**按交易日对齐**（2026-09-11 修正：原为按长度尾部对齐，w-f4aa1f6a）。
   * 净值日期取自 /api/simulation/performance 的 equity_curve（与后端 returnsSource=account_nav 同源），
   * 基准日期取自沪深300 日线；在净值序列自己的日期对上取基准收益，缺端点则如实降级标注。
   * 任一步失败返回 null（不阻塞主指标）。
   */
  private async buildAttribution(base: any, days: number, account: string): Promise<any | null> {
    try {
      const navPoints = Number(base?.navPoints ?? 0);
      if (!Number.isFinite(navPoints) || navPoints < 5) return null;
      const navDates = await this.fetchNavDates(account);
      if (!navDates || navDates.length < 5) return null;
      const end = new Date().toISOString().slice(0, 10);
      const start = new Date(Date.now() - Math.max(90, days * 2 + 40) * 86400000).toISOString().slice(0, 10);
      const raw: any = await (this.qv2 as any).getKlines('000300', start, end, 'daily');
      const rows: any[] = Array.isArray(raw) ? raw : (raw?.klines ?? []);
      if (!rows.length) return null;
      const aligned = alignByTradingDate(navDates, rows, navPoints);
      if (!aligned.pairs) return null;
      return {
        benchmark_returns: aligned.benchmarkReturns,
        benchmark_symbol: '000300',
        benchmark_name: '沪深300',
        benchmark_return_pct: aligned.benchmarkReturnPct,
        alignment: aligned.note,
        alignment_ok: aligned.ok,
        alignment_pairs: aligned.pairs,
        alignment_missing_dates: aligned.missingDates,
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
