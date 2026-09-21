import { BaseTool, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { opponentBehaviorPrompt, OpponentBehaviorParams, OpponentBehaviorResult } from './prompt';

/**
 * Opponent Behavior Tool
 *
 * 分析市场对手行为（散户/机构/游资），识别博弈机会（M7-1）
 */
export class OpponentBehaviorTool extends BaseTool<
  OpponentBehaviorParams,
  OpponentBehaviorResult
> {
  protected readonly metadata: ToolMetadata = {
    name: 'opponent_behavior',
    category: 'data',
    version: '1.0.0',
    timeoutMs: 15000,
  };

  protected readonly prompt = opponentBehaviorPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(args: OpponentBehaviorParams): ValidationResult {
    if (args.focus != null && !['retail', 'institution', 'hot_money'].includes(args.focus)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'focus',
        issue: 'focus 必须是 retail/institution/hot_money 之一',
        received: args.focus,
        expected: 'retail | institution | hot_money',
      };
    }
    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(
    args: OpponentBehaviorParams,
    _context: ToolContext
  ): Promise<OpponentBehaviorResult> {
    try {
      const response: any = await this.qv2.getOpponentBehavior({
        ...(args.focus ? { focus: args.focus } : {}),
      });

      // 后端返回 camelCase 结构（retail/institution/hot_money/market_phase/...），
      // 与输出 schema 字段一致，但需显式给默认值防 undefined 键
      const retail = response?.retail ?? {};
      const institution = response?.institution ?? {};
      const hotMoney = response?.hot_money ?? {};
      return sanitizeLossless({
        retail: {
          behavior: retail.behavior ?? 'unknown',
          net_flow: retail.net_flow ?? null,
          emotion_index: retail.emotion_index ?? null,
          common_mistakes: retail.common_mistakes ?? [],
          degraded: retail.degraded ?? true,
          description: retail.description ?? '数据不可用',
        },
        institution: {
          behavior: institution.behavior ?? 'unknown',
          net_flow: institution.net_flow ?? null,
          target_sectors: institution.target_sectors ?? [],
          position_change: institution.position_change ?? 'unknown',
          degraded: institution.degraded ?? true,
          description: institution.description ?? '数据不可用',
        },
        hot_money: {
          behavior: hotMoney.behavior ?? 'inactive',
          target_stocks: hotMoney.target_stocks ?? [],
          stage: hotMoney.stage ?? null,
          activity_level: hotMoney.activity_level ?? 'low',
          estimated: hotMoney.estimated ?? true,
          description: hotMoney.description ?? '估算值',
        },
        market_phase: response?.market_phase ?? 'unknown',
        risk_appetite: response?.risk_appetite ?? 'unknown',
        opportunity_map: response?.opportunity_map ?? {},
        degraded: response?.degraded ?? true,
        timestamp: response?.timestamp ?? new Date().toISOString(),
      });
    } catch (e: any) {
      throw new Error(
        `对手行为分析失败: ${e?.message ?? e}`,
        { cause: e }
      );
    }
  }
}
