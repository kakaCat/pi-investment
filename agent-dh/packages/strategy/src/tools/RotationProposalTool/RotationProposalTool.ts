/**
 * RotationProposalTool - 轮动方案建议工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { rotationProposalPrompt, RotationProposalParams, RotationProposalResult } from './prompt';

export class RotationProposalTool extends BaseTool<RotationProposalParams, RotationProposalResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'rotation_proposal',
    category: 'strategy',
    version: '2.0.0',
    timeoutMs: 30000,
  };

  protected readonly prompt = rotationProposalPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  protected validate(args: RotationProposalParams): ValidationResult {
    if (args.mode) {
      const validModes = ['conservative', 'balanced', 'aggressive'];
      if (!validModes.includes(args.mode)) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'mode',
          issue: 'mode 必须是 conservative/balanced/aggressive',
          received: args.mode,
          expected: 'conservative | balanced | aggressive',
        };
      }
    }

    if (args.max_positions !== undefined && (!Number.isInteger(args.max_positions) || args.max_positions <= 0)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'max_positions',
        issue: 'max_positions 必须是正整数',
        received: args.max_positions,
        expected: '正整数',
      };
    }

    return { success: true };
  }

  protected async execute(
    args: RotationProposalParams,
    _context: ToolContext
  ): Promise<RotationProposalResult> {
    // 2026-09-01 契约对齐（investor w-8366e526）：后端 GET /api/agent/rotation/proposal
    // 返回 {market_style, proposal: {needs_rotation, trigger, actions, summary, expected_impact},
    // constraints, next_steps}，其中 actions 是策略级动作（activate/deactivate/adjust_weight +
    // strategy_id/strategy_name）。此前工具 as any 透传整个后端对象，与声明的
    // proposals 个股语义（symbol/buy/sell）不符——此处规范化为契约结构并保留 meta。
    const raw: any = await this.qv2.generateRotationProposal({
      account_name: args.account_name || 'default',
      mode: args.mode || 'balanced',
      max_positions: args.max_positions || 10,
    });

    const proposal: any = raw?.proposal ?? raw ?? {};
    const actions: any[] = Array.isArray(proposal.actions) ? proposal.actions : [];
    const proposals = actions.map((a: any, i: number) => ({
      action: a.action as 'activate' | 'deactivate' | 'adjust_weight',
      strategy_id: a.strategy_id,
      strategy_name: a.strategy_name,
      reason: a.reason,
      suggested_weight: a.new_weight ?? a.weight,
      priority: i + 1,
    }));

    const s: any = typeof proposal.summary === 'object' ? (proposal.summary ?? {}) : {};
    return {
      proposals,
      summary: {
        total_buy: s.total_buy ?? actions.filter((a) => a.action === 'activate').length,
        total_sell: s.total_sell ?? actions.filter((a) => a.action === 'deactivate').length,
        expected_turnover: s.expected_turnover ?? 0,
      },
      meta: {
        market_style: raw.market_style,
        style_confidence: raw.style_confidence,
        style_duration_days: raw.style_duration_days,
        needs_rotation: proposal.needs_rotation,
        trigger: proposal.trigger,
        expected_impact: proposal.expected_impact,
        constraints: raw.constraints,
        next_steps: raw.next_steps,
        active_strategies: raw.active_strategies,
      },
    };
  }

  protected wrap(data: RotationProposalResult): ToolResponse<RotationProposalResult> {
    return { success: true, data };
  }
}
