/**
 * RiskMetricsTool - 风险指标工具
 */

import { BaseTool, DEFAULT_AGENT_ACCOUNT } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { riskMetricsPrompt, RiskMetricsParams, RiskMetricsResult } from './prompt';
import { alignByTradingDate } from './attributionAlignment';

/**
 * 净值序列覆盖口径（消费 v2 的 data.nav_coverage）。
 *
 * v2（REQ-261006190953-fc43 卡 D）在 `GET /api/simulation/performance` 与
 * `POST /api/risk/metrics` 的 data 段返回该块，缺口**只按交易日**算：
 * 周末与法定节假日（如国庆 2026-10-01~10-07 整段）不计入缺口；
 * 交易日历不可得时 `verified=false` 且 `missing_count=0`（**不是**"全缺失"）。
 * 本工具只做透出，不再自己判星期/节假日。
 */
export interface NavCoverage {
  /** 是否做过交易日校验（false = 本轮未做，缺口数未知，不代表序列连续） */
  verified: boolean;
  /** 窗口内交易日点数（v2 口径；缺 nav_coverage 时为 null） */
  points: number | null;
  from: string | null;
  to: string | null;
  /** 缺失的**交易日**（v2 最多给 20 条） */
  missing_trading_days: string[];
  missing_count: number;
  /** v2 的口径说明（原样透出） */
  basis: string;
  /** trading-calendar / unavailable（原样透出） */
  trading_day_source: string;
  /** 供解读用的影响说明（本工具附加，非 v2 字段） */
  impact: string;
}

/** v2 未返回 nav_coverage 时的口径说明（不得据此建议补跑：缺口数未知 ≠ 无缺口） */
export const NAV_COVERAGE_UNAVAILABLE_BASIS = 'v2 未提供 nav_coverage：本轮未做交易日校验';

/** 降级对象：verified=false 的「未做交易日校验」——**不回退 weekday 自算** */
function unavailableNavCoverage(basis: string): NavCoverage {
  return {
    verified: false,
    points: null,
    from: null,
    to: null,
    missing_trading_days: [],
    missing_count: 0,
    basis,
    trading_day_source: 'unavailable',
    impact: '未做交易日校验 → 缺口数未知（0 不代表序列连续），日收益/波动率/alpha/IR 解读须保守',
  };
}

/**
 * 从 v2 响应体取 `data.nav_coverage`（兼容已解包的 data 段）并**原样透出**：
 * `basis` / `trading_day_source` / `missing_trading_days` / `missing_count` / `verified` 一律取自 v2。
 * 缺该字段时返回 `{verified:false, basis:'v2 未提供 nav_coverage：本轮未做交易日校验'}`。
 * **绝不**用「相邻快照间隔 + 跳过周末」自算缺口（那会把国庆整段误报为缺口）。
 */
export function buildNavCoverage(payload: any): NavCoverage {
  const nc = payload?.data?.nav_coverage ?? payload?.nav_coverage;
  if (!nc || typeof nc !== 'object' || Array.isArray(nc)) {
    return unavailableNavCoverage(NAV_COVERAGE_UNAVAILABLE_BASIS);
  }
  const rawDays = (nc as any).missing_trading_days;
  const missingDays: string[] = Array.isArray(rawDays)
    ? rawDays.map((d: any) => String(d)).slice(0, 20)
    : [];
  const count = Number((nc as any).missing_count);
  const missingCount = Number.isFinite(count) ? count : missingDays.length;
  const verified = (nc as any).verified === true;
  const impact = !verified
    ? 'v2 未做交易日校验（verified=false）→ 缺口数未知，日收益/波动率/alpha/IR 解读须保守'
    : missingCount > 0
      ? '存在缺口 → 日收益口径失真，波动率/alpha/IR 解读须保守'
      : '序列连续，日收益口径可用';
  const basis = (nc as any).basis;
  const source = (nc as any).trading_day_source;
  return {
    ...(nc as any),
    verified,
    points: (nc as any).points ?? null,
    from: (nc as any).from ?? null,
    to: (nc as any).to ?? null,
    missing_trading_days: missingDays,
    missing_count: missingCount,
    basis: typeof basis === 'string' && basis ? basis : 'v2 已给 nav_coverage 但未附 basis',
    trading_day_source: typeof source === 'string' && source ? source : 'unavailable',
    impact,
  };
}

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
    const account = args.account_name || DEFAULT_AGENT_ACCOUNT;

    // 1) 账户口径基础指标（拿到 navPoints / returnsSource，用于基准对齐）
    const base: any = await this.qv2.getRiskMetrics({ account_name: account, days });

    // 2) 2026-09-11 新增（REQ-342799 P1 基准与归因）：
    //    后端 /api/risk/metrics 支持 benchmark_returns（empyrical 计算 alpha/beta/informationRatio），
    //    但需要与账户收益序列**等长对齐**——实测传 6 点基准配 55 点净值会得到 beta=0 的假值。
    //    此处拉沪深300 日收益，按长度尾部对齐后回传，使 beta/alpha 从『恒 0』变为真实值。
    const attribution = await this.buildAttribution(base, days, account);
    const navCoverage = await this.probeNavCoverage(account);
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
          ? '；[缺口] 净值序列缺 ' + navCoverage.missing_count + ' 个交易日（不扣周末与法定节假日）→ 日收益口径失真'
          : '') +
        (navCoverage && navCoverage.verified === false
          ? '；[交易日覆盖率] ' + navCoverage.basis
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
   * 净值序列缺口探测（2026-09-11，REQ-342799 P3；2026-10-06 改为**消费 v2 口径**）。
   *
   * 波动率/alpha/IR 由相邻快照差分的日收益算出；缺交易日会把跨日涨跌当成单日收益，
   * 因此需要可见化。判据**不在本工具**：v2 的 `data.nav_coverage` 已按交易日历逐日核对
   * （REQ-261006190953-fc43 卡 D，唯一实现 `application/services/nav_series.nav_coverage`），
   * 这里只取字段透出——旧实现在本地按「相邻快照间隔 + 跳过周末」自算，
   * 会把国庆 2026-10-01~10-07 整段误报成缺口，且自认「未扣法定节假日」。
   * 取不到 nav_coverage 时如实标 `verified:false`（未做交易日校验），**不回退自算、不建议补跑**。
   */
  private async probeNavCoverage(account: string): Promise<NavCoverage> {
    try {
      const base = process.env.QUANTSYS_V2_API_URL || 'http://127.0.0.1:5001';
      const url = base + '/api/simulation/performance?account_name=' + encodeURIComponent(account);
      const res = await fetch(url);
      if (!res.ok) {
        return unavailableNavCoverage(
          'v2 /api/simulation/performance 返回非 2xx（HTTP ' + res.status + '）：本轮未做交易日校验',
        );
      }
      return buildNavCoverage(await res.json());
    } catch {
      return unavailableNavCoverage('未能取到 v2 nav_coverage（请求失败）：本轮未做交易日校验');
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
