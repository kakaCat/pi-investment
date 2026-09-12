/**
 * RegimePositionLimitTool - 市场状态仓位限制工具
 */

import { BaseTool, assessBreakerTrigger, BREAKER_THRESHOLD_PCT } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { regimePositionLimitPrompt, RegimePositionLimitParams, RegimePositionLimitResult } from './prompt';

interface OsMemoryStore {
  searchMemory(params: { q?: string; kind?: string; scope?: string; limit?: number }): Promise<{ items: any[] }>;
  createMemory(entry: { kind: string; scope: string; title: string; content: string; payload?: any; status?: string; confidence?: number; source?: string; provenance?: any }): Promise<{ id: string }>;
}

/**
 * 市场状态仓位限制工具类
 */
export class RegimePositionLimitTool extends BaseTool<RegimePositionLimitParams, RegimePositionLimitResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'regime_position_limit',
    category: 'risk',
    version: '1.0.0',
    timeoutMs: 20000,
  };

  /**
   * 取账户净值序列（total_value）供回撤可信度复算。与 risk_metrics 的 account_nav 同源
   * （/api/simulation/performance），失败返回空数组（闸门会因此判定不可信 → 不触发熔断，方向安全）。
   */
  private async fetchNavValues(accountName: string): Promise<number[]> {
    try {
      const base = process.env.QUANTSYS_V2_API_URL || 'http://127.0.0.1:5001';
      const url = base + '/api/simulation/performance?account_name=' + encodeURIComponent(accountName);
      const res = await fetch(url);
      if (!res.ok) return [];
      const body: any = await res.json();
      const curve: any[] = body?.data?.equity_curve ?? [];
      return curve
        .map((r) => Number(r?.total_value))
        .filter((n) => Number.isFinite(n) && (n as number) > 0) as number[];
    } catch {
      return [];
    }
  }

  protected readonly prompt = regimePositionLimitPrompt;

  constructor(private qv2: QuantsysV2Client, private memoryClient: OsMemoryStore) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(_args: RegimePositionLimitParams): ValidationResult {
    // 所有参数都是可选的，直接通过
    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(args: RegimePositionLimitParams, _context: ToolContext): Promise<RegimePositionLimitResult> {
    const accountName = args.account_name || 'agent_brain';

    // 1. 读最新 regime 记录（忽略已弃用）
    const res = await this.memoryClient.searchMemory({ q: 'regime', scope: 'market:regime', limit: 10 });
    const latest = (res?.items || [])
      .filter((it: any) => it.status !== 'deprecated' && it.payload?.date)
      .sort((a: any, b: any) => String(b.payload.date).localeCompare(String(a.payload.date)))[0];

    const regime = latest?.payload?.regime ?? 'sideways';
    const dataQuality = latest?.payload?.evidence?.data_quality ?? 'unknown';
    const conflicts = latest?.payload?.evidence?.conflicts ?? null;
    const regimeDate = latest?.payload?.date ?? ''; // 无 regime 记录时用空串兜底（schema 要求 string，null 会崩）

    // 2. 映射表（RFC 004 M4-1）；数据降级时收紧到震荡档（保守原则）
    const CAPS: Record<string, number> = { panic: 100, risk_on: 80, sideways: 60, risk_off: 40, euphoria: 30 };
    const rawCap = CAPS[regime] ?? 60;
    let cap = rawCap;
    let capNote = '';
    if (dataQuality === 'degraded' || (Array.isArray(conflicts) && conflicts.length > 0)) {
      cap = Math.min(cap, 60);
      // 只有实际收紧了才提示（如 euphoria 本身 30% 已低于震荡档，不算收紧）
      if (cap < rawCap) {
        capNote = `数据降级/指标矛盾，上限由 ${rawCap}% 收紧至 ${cap}%（保守）`;
      }
    }

    // 3. 当前仓位
    const summary: any = await this.qv2.getPortfolioSummary(accountName);
    const totalValue = Number(summary?.totalValue ?? 0);
    const marketValue = Number(summary?.totalMarketValue ?? 0);
    const currentPct = totalValue > 0 ? +(marketValue / totalValue * 100).toFixed(1) : 0;
    const headroom = +(cap - currentPct).toFixed(1);

    // 4. 回撤熔断（60 日最大回撤超 8% → 减仓一半）
    // 2026-08-21 E2E 修正：后端真实字段是 maxDrawdown（camelCase）且为小数比率
    // （-0.0716 = -7.16%），不是 max_drawdown 百分数——E2E 前读的是错的
    let circuit: any = { triggered: false };
    let verdict: 'compliant' | 'reduce_required' | 'circuit_breaker' = headroom >= 0 ? 'compliant' : 'reduce_required';
    // 2026-09-11 修复（w-f4aa1f6a，agent_brain 假熔断事故驱动）：
    // 原实现直接采信 risk_metrics.maxDrawdown 作为"账户回撤"，**不校验口径与样本量**。
    // 实证：agent_brain 只有 2 条净值快照 → 主口径 account_nav 不可用，服务静默回退到
    // holdings_proxy（当前持仓等权、忽略现金权重、接口自述"会高估风险"），算出 -8.88%，
    // 于是本工具报 triggered=true；而同一账户用原始净值序列复算只有 -0.13%、
    // 总盈亏 -0.53%、现金占比 75.6%——三者都不支持触发。
    // 现改为：口径必须是账户净值 + 样本足够 + 回撤可由净值序列复现，任一不满足一律不触发。
    // 闸门来自 core-tool 共享模块（与 M4 熔断工具同一套逻辑，避免两处漂移）。
    try {
      const metrics: any = await this.qv2.getRiskMetrics({ account_name: accountName, days: 60 });
      const raw = Number(metrics?.maxDrawdown ?? metrics?.max_drawdown ?? 0);
      const mdd = Math.abs(raw) <= 1 ? +(raw * 100).toFixed(2) : raw;  // 小数比率→百分比
      const caliber = String(metrics?.returnsSource ?? metrics?.returns_source ?? '').trim();
      const navs = await this.fetchNavValues(accountName);
      const assessment = assessBreakerTrigger(mdd, caliber, navs);
      circuit = {
        triggered: assessment.triggered,
        max_drawdown: mdd,
        threshold: BREAKER_THRESHOLD_PCT,
        caliber: assessment.caliber,
        untrusted: assessment.untrusted,
        note: assessment.reason,
        trust_detail: assessment.detail,
      };
      if (assessment.triggered) {
        circuit.action = '组合回撤熔断触发：强制减仓一半（权益仓位降至当前 50%），禁止新开仓直到回撤修复';
        verdict = 'circuit_breaker';
      }
    } catch (e: any) {
      circuit = { triggered: false, note: "回撤指标不可用，熔断未评估: " + String(e?.message || e).slice(0, 80) };
    }

    return {
      regime,
      regime_date: regimeDate,
      data_quality: dataQuality,
      max_position_pct: cap,
      current_position_pct: currentPct,
      headroom_pct: headroom,
      verdict,
      cap_note: capNote || null,
      reduce_to_pct: verdict === 'reduce_required' ? cap : null,
      circuit_breaker: circuit,
      mapping_table: CAPS,
    };
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: RegimePositionLimitResult, _context: ToolContext): ToolResponse<RegimePositionLimitResult> {
    return {
      success: true,
      data: result,
    };
  }
}
