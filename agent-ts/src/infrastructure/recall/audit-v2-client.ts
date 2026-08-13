import type { RecallAuditPort } from '../../services/recall/ports.js';
import { createJsonlFallback } from './audit-jsonl-fallback.js';

/**
 * Creates a composite audit port: tries V2 API first (3s timeout), falls back to JSONL on failure.
 * Never throws — both failures only console.warn.
 */
export function createRecallAuditPort(): RecallAuditPort {
  const jsonlFallback = createJsonlFallback();

  return {
    async record(decision): Promise<void> {
      // Try V2 API first
      try {
        const apiUrl = process.env.QUANTSYS_V2_API_URL || 'http://127.0.0.1:5001';

        const body = {
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
        };

        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 3000);

        const response = await fetch(`${apiUrl}/api/memory/recall-audit`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(body),
          signal: controller.signal,
        });

        clearTimeout(timeoutId);

        if (!response.ok) {
          throw new Error(`V2 API responded ${response.status}`);
        }

        // Success — return early
        return;
      } catch (err) {
        console.warn('[audit-v2-client] V2 API failed, falling back to JSONL:', err);
      }

      // Fallback to JSONL
      try {
        await jsonlFallback.record(decision);
      } catch (err) {
        // Both failed — only warn, never throw (fire-and-forget contract)
        console.warn('[audit-v2-client] JSONL fallback also failed:', err);
      }
    },
  };
}
