import { BaseTool, ErrorType, sanitizeLossless } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { QuantsysV2Client } from '@pi-investment/quantsys-v2-client';
import { poolBattlefieldPrompt, PoolBattlefieldParams, PoolBattlefieldResult } from './prompt';

/**
 * Pool Battlefield Tool（M2-3）
 *
 * 评估股票池的竞争战场格局：调用后端
 * GET /api/game/pools/{pool_id}/battlefield-assessment，
 * 返回战场评分、三方对手强度、博弈阶段与攻防建议。
 */
export class PoolBattlefieldTool extends BaseTool<
  PoolBattlefieldParams,
  PoolBattlefieldResult
> {
  protected readonly metadata: ToolMetadata = {
    name: 'pool_battlefield',
    category: 'competition',
    version: '1.0.0',
    timeoutMs: 30000,
  };

  protected readonly prompt = poolBattlefieldPrompt;

  constructor(private qv2: QuantsysV2Client) {
    super();
  }

  /**
   * Phase 1: 校验参数（pool_id / pool_name 至少一个）
   */
  protected validate(args: PoolBattlefieldParams): ValidationResult {
    const hasId = args.pool_id != null && Number.isFinite(args.pool_id);
    const hasName = typeof args.pool_name === 'string' && args.pool_name.trim().length > 0;
    if (!hasId && !hasName) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'pool_id',
        issue: 'pool_id 与 pool_name 至少传一个',
        expected: 'pool_id: number | pool_name: string',
      };
    }
    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(
    args: PoolBattlefieldParams,
    _context: ToolContext
  ): Promise<PoolBattlefieldResult> {
    // pool_name → pool_id 解析（模糊匹配池子名称）
    let poolId = args.pool_id;
    let poolName = args.pool_name?.trim() ?? '';
    if (poolId == null && poolName) {
      const pools = await this.qv2.listPools();
      const matched = (pools as any[]).filter((p) =>
        typeof p?.name === 'string' && p.name.includes(poolName)
      );
      if (matched.length === 0) {
        throw new Error(`未找到名称包含 "${poolName}" 的股票池，可用 pool_list 工具查看全部池子`);
      }
      if (matched.length > 1) {
        const names = matched.map((p) => `${p.id}:${p.name}`).join('、');
        throw new Error(`"${poolName}" 匹配到 ${matched.length} 个池子（${names}），请用 pool_id 指定`);
      }
      poolId = matched[0].id;
      poolName = matched[0].name;
    }

    const response: any = await this.qv2.getPoolBattlefield({ pool_id: poolId! });
    const d = response?.data ?? response ?? {};
    const strength = d.opponent_strength ?? {};

    // 若只传了 pool_id，补池子名称（失败不阻塞主流程）
    if (!poolName) {
      try {
        const pools = await this.qv2.listPools();
        const hit = (pools as any[]).find((p) => p?.id === poolId);
        poolName = hit?.name ?? '';
      } catch { /* 名称补充失败不影响主结果 */ }
    }

    return sanitizeLossless({
      pool_id: d.pool_id ?? poolId,
      pool_name: poolName,
      battlefield_score: d.battlefield_score ?? 0,
      opponent_strength: {
        retail_pressure: strength.retail_pressure ?? 'unknown',
        institution_interest: strength.institution_interest ?? 'unknown',
        hot_money_risk: strength.hot_money_risk ?? 'unknown',
      },
      game_phase: d.game_phase ?? 'unknown',
      advantages: Array.isArray(d.advantages) ? d.advantages : [],
      disadvantages: Array.isArray(d.disadvantages) ? d.disadvantages : [],
      recommendation: d.recommendation ?? 'hold',
      urgency: d.urgency ?? 'low',
      confidence: d.confidence ?? 0,
      data_quality: d.data_quality ?? 'unknown',
    });
  }

  /**
   * Phase 3: 包装结果
   */
  protected wrap(
    data: PoolBattlefieldResult,
    _context: ToolContext
  ): ToolResponse<PoolBattlefieldResult> {
    const s = data.opponent_strength;
    const message =
      `池子 ${data.pool_name || data.pool_id}：战场评分 ${data.battlefield_score.toFixed(1)}/100，` +
      `阶段 ${data.game_phase}，对手（散户 ${s.retail_pressure}/机构 ${s.institution_interest}/游资 ${s.hot_money_risk}），` +
      `建议 ${data.recommendation}（${data.urgency}）`;

    return {
      success: true,
      data,
      message,
      metadata: {
        pool_id: data.pool_id,
        battlefield_score: data.battlefield_score,
        game_phase: data.game_phase,
        recommendation: data.recommendation,
      },
    };
  }
}
