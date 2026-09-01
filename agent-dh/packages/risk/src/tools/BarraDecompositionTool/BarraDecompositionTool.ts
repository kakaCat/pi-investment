/**
 * BarraDecompositionTool - Barra风险分解工具
 */

import { BaseTool } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { barraDecompositionPrompt, BarraDecompositionParams, BarraDecompositionResult } from './prompt';

/**
 * Barra风险分解工具类
 */
export class BarraDecompositionTool extends BaseTool<BarraDecompositionParams, BarraDecompositionResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'risk_barra_decomposition',
    category: 'risk',
    version: '1.0.0',
    timeoutMs: 20000,
  };

  protected readonly prompt = barraDecompositionPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(_args: BarraDecompositionParams): ValidationResult {
    // 所有参数都是可选的，直接通过
    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(args: BarraDecompositionParams, _context: ToolContext): Promise<BarraDecompositionResult> {
    const symbols = args.symbols?.length
      ? args.symbols
      : // 2026-09-01：Barra 横截面回归需 ≥ 因子数+5 只股票（5 风格因子 → ≥10），
      // 原 5 只默认必然触发样本不足 → 全 NaN → null。扩至 10 只蓝筹。
      ['600519', '000858', '601318', '000001', '600036', '601398', '600028', '601288', '600900', '000333'];

    const result: any = await this.qv2.getBarraDecomposition({
      symbols,
      start_date: args.start_date || new Date(Date.now() - 90 * 86400000).toISOString().slice(0, 10),
      end_date: args.end_date || new Date().toISOString().slice(0, 10),
      weights: args.weights,
    });

    // 映射后端字段到标准格式
    return {
      total_risk: result?.total_risk ?? result?.totalRisk ?? 0,
      factor_risks: result?.factor_risks ?? result?.factorRisks ?? [],
      idiosyncratic_risk: result?.idiosyncratic_risk ?? result?.idiosyncraticRisk ?? 0,
      industry_concentration: result?.industry_concentration ?? result?.industryConcentration ?? 0,
      style_exposure: result?.style_exposure ?? result?.styleExposure ?? {},
      ...result,
    };
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: BarraDecompositionResult, _context: ToolContext): ToolResponse<BarraDecompositionResult> {
    return {
      success: true,
      data: result,
    };
  }
}
