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

    // 映射后端字段到标准格式（2026-09-04 修复）
    // curl 实测 POST /api/risk/metrics 返回 camelCase 比率字段：
    //   sharpeRatio / sortinoRatio / calmarRatio / maxDrawdown / annualReturn /
    //   annualVolatility / var95 / cvar95 / cumulativeReturn
    // schema 契约 % 类指标（volatility/max_drawdown/var_95）为百分数 → 比率×100，
    // 口径统一到 regime_position_limit(-7.72)/m4 熔断(-8 阈值)；
    // 后端未计算 beta/alpha（需基准输入）→ 保持 0。不再 ...result 透传（避免 camelCase/snake_case 双写混淆）
    const pct = (v: any) => {
      const n = Number(v ?? 0);
      return Math.abs(n) <= 1 ? +(n * 100).toFixed(2) : n;
    };
    return {
      volatility: pct(result?.annualVolatility ?? result?.volatility ?? result?.annualizedVolatility ?? 0),
      max_drawdown: pct(result?.maxDrawdown ?? result?.max_drawdown ?? 0),
      sharpe_ratio: Number(result?.sharpeRatio ?? result?.sharpe_ratio ?? 0),
      beta: Number(result?.beta ?? 0),
      alpha: Number(result?.alpha ?? 0),
      var_95: pct(result?.var95 ?? result?.var_95 ?? result?.VaR ?? 0),
      sortino_ratio: Number(result?.sortinoRatio ?? result?.sortino_ratio ?? 0),
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
