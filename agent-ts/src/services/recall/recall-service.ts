import type { RecallContext, RecallHit, RecallMessage } from '../../domain/recall/types.js';
import { decidePolicy } from '../../domain/recall/policy.js';
import { applyQualityGate } from '../../domain/recall/quality-gate.js';
import { formatRecallMessage } from '../../domain/recall/recall-message.js';
import type { RecallSearchPort, RecallAuditPort } from './ports.js';

type AuditDecision = Parameters<RecallAuditPort['record']>[0];

/**
 * RecallService — 应用层编排，无业务规则本体。
 *
 * 控制流：decidePolicy → search → applyQualityGate → formatRecallMessage → 审计。
 * 任何一步失败（检索异常 / 审计抛错）都绝不阻塞对话。
 *
 * 注：RecallSearchPort 契约冻结为只返回 RecallHit[]，不暴露 strategy/degraded，
 * 因此审计里 strategy 按「检索是否真正发生」填默认值：发生='hybrid'，未发生/异常='none'；
 * degraded 恒为 false（端口无降级信息）。P2 接线真实检索适配器时若需细分再扩展端口。
 */
export class RecallService {
  constructor(
    private readonly searchPort: RecallSearchPort,
    private readonly auditPort: RecallAuditPort,
  ) {}

  async recall(ctx: RecallContext): Promise<RecallMessage | null> {
    const policy = decidePolicy(ctx.flow);
    if (!policy.enabled) {
      await this.audit(ctx, {
        strategy: 'none',
        degraded: false,
        gateResult: 'suppressed',
        suppressReason: policy.reason ?? 'policy-disabled',
        hits: [],
      });
      return null;
    }

    let hits: RecallHit[];
    try {
      hits = await this.searchPort.search(ctx.rawText, policy.topK);
    } catch {
      // 检索异常：审计 empty-result，返回 null（绝不向上抛）
      await this.audit(ctx, {
        strategy: 'none',
        degraded: false,
        gateResult: 'suppressed',
        suppressReason: 'empty-result',
        hits: [],
      });
      return null;
    }

    const gate = applyQualityGate(hits);
    if (gate.gate === 'suppressed') {
      await this.audit(ctx, {
        strategy: 'hybrid',
        degraded: false,
        gateResult: 'suppressed',
        suppressReason: gate.reason,
        hits: toAuditHits(hits),
      });
      return null;
    }

    const message = formatRecallMessage(ctx.flow, gate.hits, policy.charBudget);
    await this.audit(ctx, {
      strategy: 'hybrid',
      degraded: false,
      gateResult: 'passed',
      hits: toAuditHits(gate.hits),
    });
    return message;
  }

  private async audit(
    ctx: RecallContext,
    draft: {
      strategy: string;
      degraded: boolean;
      gateResult: 'passed' | 'suppressed';
      suppressReason?: string;
      hits: AuditDecision['hits'];
    },
  ): Promise<void> {
    try {
      await this.auditPort.record({
        ts: new Date().toISOString(),
        sessionId: ctx.sessionId,
        flow: ctx.flow,
        queryText: ctx.rawText,
        strategy: draft.strategy,
        degraded: draft.degraded,
        gateResult: draft.gateResult,
        suppressReason: draft.suppressReason,
        hits: draft.hits,
      });
    } catch {
      // 审计失败绝不阻塞对话（fire-and-forget 语义）
    }
  }
}

function toAuditHits(hits: RecallHit[]): AuditDecision['hits'] {
  return hits.map((h) => ({
    memoryId: h.id,
    score: h.score,
    source: h.source,
    bm25Score: h.bm25Score,
    vectorScore: h.vectorScore,
  }));
}
