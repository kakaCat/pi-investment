/**
 * RegimePositionLimitTool - 市场状态仓位限制工具
 */

import { BaseTool } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import type { OsMemoryStore } from '@pi-investment/os-memory';
import { regimePositionLimitPrompt, RegimePositionLimitParams, RegimePositionLimitResult } from './prompt';

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

  protected readonly prompt = regimePositionLimitPrompt;

  constructor(private qv2: QuantsysV2Client, private osMemory: OsMemoryStore) {
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
    const accountName = args.account_name || 'agent_virtual';

    // 1. 读最新 regime 记录（忽略已弃用）
    const res = await this.osMemory.searchMemory({ q: 'regime', scope: 'market:regime', limit: 10 });
    const latest = (res?.items || [])
      .filter((it: any) => it.status !== 'deprecated' && it.payload?.date)
      .sort((a: any, b: any) => String(b.payload.date).localeCompare(String(a.payload.date)))[0];

    const regime = latest?.payload?.regime ?? 'sideways';
    const dataQuality = latest?.payload?.evidence?.data_quality ?? 'unknown';
    const conflicts = latest?.payload?.evidence?.conflicts ?? null;

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
    try {
      const metrics: any = await this.qv2.getRiskMetrics({ account_name: accountName, days: 60 });
      const raw = Number(metrics?.maxDrawdown ?? metrics?.max_drawdown ?? 0);
      const mdd = Math.abs(raw) <= 1 ? +(raw * 100).toFixed(2) : raw;  // 小数比率→百分比
      if (mdd <= -8) {
        circuit = {
          triggered: true,
          max_drawdown: mdd,
          action: '组合回撤熔断触发：强制减仓一半（权益仓位降至当前 50%），禁止新开仓直到回撤修复',
        };
        verdict = 'circuit_breaker';
      } else {
        circuit = { triggered: false, max_drawdown: mdd, threshold: -8 };
      }
    } catch {
      circuit = { triggered: false, note: '回撤指标不可用，熔断未评估' };
    }

    return {
      regime,
      regime_date: latest?.payload?.date ?? null,
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
