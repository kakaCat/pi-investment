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

    // 2026-09-11 修复（REQ-342799 数据真实性护栏）
    // curl 实测：样本不足时后端返回 {success:false, data:null, message:'Insufficient data for all symbols'}
    // 旧实现把 null 映射成 total_risk=0 / factor_risks=[] → 静默输出『零风险』假结论。
    // 现在：后端未成功或关键字段全空 → 显式抛错（BaseTool 转为 success:false 返回）。
    const payload: any = (result && (result.data ?? result)) ?? null;
    const backendFailed = result?.success === false;
    const hasAny = (v: any) => v !== null && v !== undefined && !(Array.isArray(v) && v.length === 0);
    const metricKeys = ['total_risk', 'totalRisk', 'factor_risks', 'factorRisks', 'idiosyncratic_risk', 'idiosyncraticRisk', 'style_exposure', 'styleExposure', 'factorRisk'];
    const meaningful = !!payload && metricKeys.some((k) => hasAny(payload[k]));
    if (backendFailed || !meaningful) {
      // 区分两种失败：无 payload（样本不足直接拒绝）vs 有结构但字段全 null（NaN→null 伪装）
      const keys = Object.keys(payload ?? result ?? {});
      const allNullish = !!payload && keys.length > 0 && metricKeys.every((k) => !hasAny(payload[k]));
      const reason = result?.message ?? result?.error ?? result?.error_message
        ?? (allNullish
          ? '后端返回结构中所有指标字段均为空（null/[]），典型原因：样本不足导致横截面回归不可用'
          : '后端未返回有效分解结果');
      throw new Error(
        'risk_barra_decomposition 无有效结果：' + reason +
        '；原始键=[' + Object.keys(payload ?? result ?? {}).join(',') + ']。' +
        'Barra 横截面回归需 ≥10 只标的（因子数+5）；样本不足时请改用 risk_metrics 单标的风险指标。' +
        '按数据真实性护栏，拒绝以 0 风险冒充有效分解。',
      );
    }

    // 映射后端字段到标准格式
    return {
      total_risk: payload.total_risk ?? payload.totalRisk ?? 0,
      factor_risks: payload.factor_risks ?? payload.factorRisks ?? [],
      idiosyncratic_risk: payload.idiosyncratic_risk ?? payload.idiosyncraticRisk ?? 0,
      industry_concentration: payload.industry_concentration ?? payload.industryConcentration ?? 0,
      style_exposure: payload.style_exposure ?? payload.styleExposure ?? {},
      ...payload,
    };
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: BarraDecompositionResult, _context: ToolContext): ToolResponse<BarraDecompositionResult> {
    // P1-5: 降级模式时添加警告信息
    if (result.degraded) {
      return {
        success: true,
        data: result,
        message: result.warning || '小样本模式：仅使用市值单因子，精度降低但可用',
      };
    }
    
    return {
      success: true,
      data: result,
    };
  }
}
