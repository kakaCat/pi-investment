/**
 * RotationSimulateTool - 轮动模拟工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { rotationSimulatePrompt, RotationSimulateParams, RotationSimulateResult } from './prompt';

export class RotationSimulateTool extends BaseTool<RotationSimulateParams, RotationSimulateResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'rotation_simulate',
    category: 'strategy',
    version: '2.0.0',
    timeoutMs: 30000,
  };

  protected readonly prompt = rotationSimulatePrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: RotationSimulateParams): ValidationResult {
    if (!Array.isArray(args.proposals) || args.proposals.length === 0) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'proposals',
        issue: 'proposals 必须是非空数组',
        received: args.proposals,
        expected: '[{ action, strategy_id?, strategy_name?, symbol?, weight? }]',
      };
    }

    // 2026-09-01：action 与后端 strategy_rotation_engine 对齐（activate/deactivate/adjust_weight）
    for (let i = 0; i < args.proposals.length; i++) {
      const p = args.proposals[i];
      if (!p.action || !['activate', 'deactivate', 'adjust_weight'].includes(p.action)) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: `proposals[${i}].action`,
          issue: 'action 必须是 activate/deactivate/adjust_weight',
          received: p.action,
          expected: 'activate | deactivate | adjust_weight',
        };
      }
    }

    return { success: true };
  }

  protected async execute(
    args: RotationSimulateParams,
    _context: ToolContext
  ): Promise<RotationSimulateResult> {
    // 2026-08-30 修复：后端引擎返回的是策略级模拟结果（simulated_trades/portfolio_after/warnings），
    // 与 DSH 输出契约（simulation.{feasible,expected_positions,...}）不一致，直接透传会导致 render 崩溃。
    // 此处做字段映射，同时保留原始明细供上层参考。
    const raw = await this.qv2.simulateRotation({
      proposals: args.proposals,
      account_name: args.account_name || 'default',
      check_constraints: args.check_constraints !== false,
    });

    const trades = Array.isArray(raw?.simulated_trades) ? raw.simulated_trades : [];
    const after = raw?.portfolio_after ?? {};
    const warnings = Array.isArray(raw?.warnings) ? raw.warnings : [];
    const expectedPositions = trades.map((t: any) => {
      const shares = Number(t.shares ?? 0);
      const price = Number(t.price ?? 0);
      const value = shares * price;
      return {
        symbol: String(t.symbol ?? ''),
        name: String(t.symbol ?? ''),
        shares,
        value,
        weight: Number(after?.total) > 0 ? value / Number(after.total) : 0,
      };
    });

    return {
      simulation: {
        feasible: true,
        expected_positions: expectedPositions,
        cash_required: 0,
        cash_available: Number(after?.cash ?? 0),
        warnings,
      },
      constraints_check: {
        passed: warnings.length === 0,
        violations: warnings,
      },
      // 保留后端原始字段，供 Agent 决策参考（schema additionalProperties 允许）
      raw: {
        simulated_trades: trades,
        portfolio_before: raw?.portfolio_before ?? null,
        portfolio_after: after,
        estimated_cost: raw?.estimated_cost ?? 0,
        risk_metrics_change: raw?.risk_metrics_change ?? null,
        next_steps: Array.isArray(raw?.next_steps) ? raw.next_steps : [],
      },
    };
  }

  protected wrap(data: RotationSimulateResult): ToolResponse<RotationSimulateResult> {
    return { success: true, data };
  }
}
