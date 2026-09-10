/**
 * ChipAnalysisTool - 筹码分析工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { chipAnalysisPrompt, ChipAnalysisParams, ChipAnalysisResult } from './prompt';

/**
 * 筹码分析工具类
 */
export class ChipAnalysisTool extends BaseTool<ChipAnalysisParams, ChipAnalysisResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'chip_analysis',
    category: 'market',
    version: '1.0.0',
    timeoutMs: 10000,
  };

  protected readonly prompt = chipAnalysisPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(args: ChipAnalysisParams): ValidationResult {
    if (!args.symbol) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbol',
        issue: 'symbol 是必填参数',
        expected: '6位数字股票代码',
        example: '600519',
      };
    }

    if (!/^\d{6}$/.test(args.symbol)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'symbol',
        issue: 'symbol 必须是6位数字股票代码',
        received: args.symbol,
        expected: '6位数字',
        example: '600519',
      };
    }

    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(args: ChipAnalysisParams, _context: ToolContext): Promise<ChipAnalysisResult> {
    const raw: any = await this.qv2.getChipDistribution(args.symbol);

    // 2026-09-11 修复（REQ-342799 数据真实性护栏）
    // 后端真实契约（curl /api/analysis/chip-distribution/{symbol} 实测）：
    //   { symbol, asOf, close, curve:[{price,weight}], metrics:{ avgCost, profitRatio,
    //     cost70Low, cost70High, cost90Low, cost90High, peakPrice, concentration } }
    // 旧实现只读顶层 avg_cost/avgCost（并不存在）→ 静默返回全 0 假数据。
    // 现在：一律读 metrics；缺失即显式抛错，绝不用 0 冒充有效筹码。
    const payload: any = (raw && (raw.data ?? raw)) ?? {};
    const m: any = payload.metrics ?? null;
    const curve: any[] = Array.isArray(payload.curve) ? payload.curve : [];

    if (!m || typeof m !== 'object') {
      throw new Error(
        `chip_analysis 未取到有效筹码指标（symbol=${args.symbol}）：后端响应缺少 metrics 字段，` +
        `实际键=[${Object.keys(payload).join(',')}]。按数据真实性护栏拒绝返回 0 值假数据。`,
      );
    }

    const num = (v: any, field: string): number => {
      const n = Number(v);
      if (!Number.isFinite(n)) {
        throw new Error(`chip_analysis 字段 ${field} 非数值：${JSON.stringify(v)}（symbol=${args.symbol}）`);
      }
      return n;
    };
    const toPct = (v: number) => +(Math.abs(v) <= 1 ? v * 100 : v).toFixed(2);
    const levels = (...vs: any[]) =>
      vs.map((v) => Number(v)).filter((v) => Number.isFinite(v) && v > 0);

    const close = Number(payload.close ?? curve[curve.length - 1]?.price ?? 0);
    const avgCost = num(m.avgCost ?? m.avg_cost, 'metrics.avgCost');
    const profitRatio = num(m.profitRatio ?? m.profit_ratio, 'metrics.profitRatio');
    // concentration 语义（domain/chip_distribution/calculator.py:151）= (cost70High-cost70Low)/中位价
    // → 是"成本区间相对宽度"，越小=筹码越集中。此处按 % 输出并显式标注口径。
    const concentration = num(m.concentration, 'metrics.concentration');
    const cost90 = levels(m.cost90Low, m.cost90High);
    const cost70 = levels(m.cost70Low, m.cost70High);
    const peak = levels(m.peakPrice);
    const pool = [...new Set([...cost90, ...cost70, ...peak])];

    return {
      symbol: payload.symbol ?? args.symbol,
      as_of: payload.asOf ?? null,
      close,
      avg_cost: +avgCost.toFixed(4),
      profit_ratio: toPct(profitRatio),
      concentration: toPct(concentration),
      concentration_meaning: '成本区间相对宽度（%）= (cost70High-cost70Low)/中位价，数值越小=筹码越集中',
      cost_band_70: cost70,
      cost_band_90: cost90,
      peak_cost: peak[0] ?? null,
      support_levels: pool.filter((v) => v < close).sort((a, b) => b - a),
      resistance_levels: pool.filter((v) => v >= close).sort((a, b) => a - b),
      levels_basis: 'derived_from_cost_bands（由后端 cost70/cost90/peakPrice 推导，非独立算法）',
      chip_distribution: curve,
      curve_points: curve.length,
      data_source: 'backend quant.chip_distribution_state（日期见 as_of，非实时行情）',
    } as ChipAnalysisResult;
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: ChipAnalysisResult, _context: ToolContext): ToolResponse<ChipAnalysisResult> {
    return {
      success: true,
      data: result,
    };
  }
}
