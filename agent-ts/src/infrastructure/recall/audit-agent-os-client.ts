import type { RecallAuditPort } from '../../services/recall/ports.js';
import { createJsonlFallback } from './audit-jsonl-fallback.js';
import { agentOSMemoryWrite } from '../agent-os/cli.js';

/**
 * 复合审计端口：先写 agent-os 记忆库，失败则落 JSONL；**永不抛错**（fire-and-forget 契约）。
 *
 * 2026-10-05 · REQ-261004202231-bb99：原实现 POST 到 quantsys-v2 的记忆审计端点，
 * 该端点已随 v2 记忆子系统下线。现改为把每条召回决策作为一条 agent-os 记忆写入
 * （namespace=recall-audit），JSONL 回退保留 —— 审计不允许因后端不可用而丢。
 */
export function createRecallAuditPort(): RecallAuditPort {
  const jsonlFallback = createJsonlFallback();

  return {
    async record(decision): Promise<void> {
      // 先写 agent-os
      try {
        const result = await agentOSMemoryWrite({
          namespace: 'recall-audit',
          content: JSON.stringify({
            ts: decision.ts,
            session_id: decision.sessionId,
            flow: decision.flow,
            query_text: decision.queryText,
            strategy: decision.strategy,
            degraded: decision.degraded,
            gate_result: decision.gateResult,
            suppress_reason: decision.suppressReason,
            hits: decision.hits.map(h => ({
              memory_id: h.memoryId,
              score: h.score,
              source: h.source,
              bm25_score: h.bm25Score,
              vector_score: h.vectorScore,
            })),
          }),
          tags: ['recall-audit', decision.gateResult].filter(Boolean) as string[],
          metadata: {
            flow: decision.flow,
            gate_result: decision.gateResult,
            session_id: decision.sessionId,
          },
        });

        if (!result.success) {
          throw new Error(result.error ?? 'agent-os memory write failed');
        }

        // 成功即返回
        return;
      } catch (err) {
        console.warn('[audit-agent-os] agent-os 写入失败，回退 JSONL:', err);
      }

      // 回退 JSONL
      try {
        await jsonlFallback.record(decision);
      } catch (err) {
        // 两条路都失败 —— 只告警，绝不抛（fire-and-forget 契约）
        console.warn('[audit-agent-os] JSONL 回退同样失败:', err);
      }
    },
  };
}
