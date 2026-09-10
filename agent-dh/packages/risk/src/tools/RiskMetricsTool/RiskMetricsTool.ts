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
    const betaRaw = result?.beta ?? result?.betaCoefficient ?? null;
    const alphaRaw = result?.alpha ?? result?.alphaAnnual ?? null;
    return {
      volatility: pct(result?.annualVolatility ?? result?.volatility ?? result?.annualizedVolatility ?? 0),
      max_drawdown: pct(result?.maxDrawdown ?? result?.max_drawdown ?? 0),
      sharpe_ratio: Number(result?.sharpeRatio ?? result?.sharpe_ratio ?? 0),
      beta: Number(betaRaw ?? 0),
      alpha: Number(alphaRaw ?? 0),
      var_95: pct(result?.var95 ?? result?.var_95 ?? result?.VaR ?? 0),
      sortino_ratio: Number(result?.sortinoRatio ?? result?.sortino_ratio ?? 0),
      // 2026-09-11（REQ-342799 数据真实性护栏）：把『未计算』与『真的是 0』区分开，
      // 避免 0 被当成『无市场相关性 / 无超额收益』这类中性结论使用。
      beta_note: betaRaw === null ? '后端未计算 beta（无基准输入）——此处 0 表示未计算，不代表无市场相关性' : 'backend_provided',
      alpha_note: alphaRaw === null ? '后端未计算 alpha（无基准输入）——此处 0 表示未计算，不代表无超额收益' : 'backend_provided',
      days_requested: args.days || 60,
      window_note: '2026-09-11 实测：后端 /api/risk/metrics 对 days=30/60/250 返回完全相同的数值（窗口参数未生效），勿假设多窗口可比',
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
