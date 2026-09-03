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
    const result: any = await this.qv2.getRiskMetrics({
      account_name: args.account_name || 'agent_virtual',
      days: args.days || 60,
    });

    // 映射后端字段到标准格式
    // 2026-09-04 修复：schema 契约 最大回撤（%），后端返回小数比率（maxDrawdown: -0.0772=-7.72%），
    // 需 ×100 转百分数，口径统一到 regime_position_limit(-7.72)/m4 熔断(-8 阈值)
    const rawMdd = Number(result?.maxDrawdown ?? result?.max_drawdown ?? 0);
    const mdd = Math.abs(rawMdd) <= 1 ? +(rawMdd * 100).toFixed(2) : rawMdd;
    return {
      volatility: result?.volatility ?? result?.annualizedVolatility ?? 0,
      max_drawdown: mdd,
      sharpe_ratio: result?.sharpe_ratio ?? result?.sharpeRatio ?? 0,
      beta: result?.beta ?? 0,
      alpha: result?.alpha ?? 0,
      var_95: result?.var_95 ?? result?.var95 ?? result?.VaR ?? 0,
      sortino_ratio: result?.sortino_ratio ?? result?.sortinoRatio ?? 0,
      ...result,
    };
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
