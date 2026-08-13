import { describe, it, expect, jest } from '@jest/globals';
import { RecallService } from './recall-service.js';
import type { RecallSearchPort, RecallAuditPort } from './ports.js';
import type { RecallContext, RecallFlow, RecallHit } from '../../domain/recall/types.js';

type AuditDecision = Parameters<RecallAuditPort['record']>[0];

function hit(id: number, score = 0.6): RecallHit {
  return {
    id,
    score,
    source: 'both',
    bm25Score: 2.0,
    vectorScore: score,
    content: `记忆内容${id}`,
  };
}

function ctx(flow: RecallFlow, rawText = '中国铝业股息'): RecallContext {
  return { flow, rawText, sessionId: 'sess-1' };
}

describe('RecallService.recall', () => {
  it('returns null and audits suppressed when policy is disabled', async () => {
    const search = jest.fn<RecallSearchPort['search']>();
    const audit = jest.fn<(decision: AuditDecision) => Promise<void>>();
    const svc = new RecallService({ search }, { record: audit });

    // slash-command 不在策略表，decidePolicy 返回 enabled=false / reason=unknown-flow
    const result = await svc.recall(ctx('slash-command' as RecallFlow));

    expect(result).toBeNull();
    expect(search).not.toHaveBeenCalled();
    expect(audit).toHaveBeenCalledTimes(1);
    const decision = audit.mock.calls[0][0];
    expect(decision.flow).toBe('slash-command');
    expect(decision.gateResult).toBe('suppressed');
    expect(decision.suppressReason).toBe('unknown-flow');
    expect(decision.hits).toEqual([]);
  });

  it('returns null and audits empty-result when search returns no hits', async () => {
    const search = jest.fn<RecallSearchPort['search']>().mockResolvedValue([]);
    const audit = jest.fn<(decision: AuditDecision) => Promise<void>>();
    const svc = new RecallService({ search }, { record: audit });

    const result = await svc.recall(ctx('interactive-chat'));

    expect(result).toBeNull();
    expect(search).toHaveBeenCalledWith('中国铝业股息', 3);
    expect(audit).toHaveBeenCalledTimes(1);
    const decision = audit.mock.calls[0][0];
    expect(decision.gateResult).toBe('suppressed');
    expect(decision.suppressReason).toBe('empty-result');
    expect(decision.hits).toEqual([]);
  });

  it('returns a RecallMessage and audits passed when hits exist', async () => {
    const hits = [hit(1, 0.9), hit(2, 0.5)];
    const search = jest.fn<RecallSearchPort['search']>().mockResolvedValue(hits);
    const audit = jest.fn<(decision: AuditDecision) => Promise<void>>();
    const svc = new RecallService({ search }, { record: audit });

    const result = await svc.recall(ctx('interactive-chat'));

    expect(result).not.toBeNull();
    expect(result!.customType).toBe('recalled-memory');
    expect(result!.details.count).toBe(2);
    expect(result!.content).toContain('<recalled_memory');
    expect(result!.content).toContain('<memory id="1"');
    expect(result!.content).toContain('<memory id="2"');

    expect(audit).toHaveBeenCalledTimes(1);
    const decision = audit.mock.calls[0][0];
    expect(decision.gateResult).toBe('passed');
    expect(decision.suppressReason).toBeUndefined();
    expect(decision.hits).toEqual([
      { memoryId: 1, score: 0.9, source: 'both', bm25Score: 2.0, vectorScore: 0.9 },
      { memoryId: 2, score: 0.5, source: 'both', bm25Score: 2.0, vectorScore: 0.5 },
    ]);
  });

  it('returns null and audits empty-result when search throws', async () => {
    const search = jest.fn<RecallSearchPort['search']>().mockRejectedValue(new Error('v2 down'));
    const audit = jest.fn<(decision: AuditDecision) => Promise<void>>();
    const svc = new RecallService({ search }, { record: audit });

    const result = await svc.recall(ctx('interactive-chat'));

    expect(result).toBeNull();
    expect(audit).toHaveBeenCalledTimes(1);
    const decision = audit.mock.calls[0][0];
    expect(decision.gateResult).toBe('suppressed');
    expect(decision.suppressReason).toBe('empty-result');
    expect(decision.hits).toEqual([]);
  });

  it('still returns the message when audit throws', async () => {
    const search = jest.fn<RecallSearchPort['search']>().mockResolvedValue([hit(1)]);
    const audit = jest.fn<(decision: AuditDecision) => Promise<void>>().mockRejectedValue(new Error('audit down'));
    const svc = new RecallService({ search }, { record: audit });

    const result = await svc.recall(ctx('interactive-chat'));

    expect(result).not.toBeNull();
    expect(result!.customType).toBe('recalled-memory');
  });
});
