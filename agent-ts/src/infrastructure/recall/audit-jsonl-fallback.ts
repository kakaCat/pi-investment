import { appendFile } from 'node:fs/promises';
import { join } from 'node:path';
import type { RecallAuditPort } from '../../services/recall/ports.js';

function getAuditFilePath(): string {
  const baseDir = process.env.PI_INVEST_DIR || '.pi-invest';
  return join(baseDir, 'recall-audit.jsonl');
}

export function createJsonlFallback(): RecallAuditPort {
  return {
    async record(decision): Promise<void> {
      try {
        const record = {
          ts: decision.ts,
          sessionId: decision.sessionId,
          flow: decision.flow,
          queryText: decision.queryText,
          strategy: decision.strategy,
          degraded: decision.degraded,
          gateResult: decision.gateResult,
          suppressReason: decision.suppressReason,
          hits: decision.hits.map(h => ({
            memoryId: h.memoryId,
            score: h.score,
            source: h.source,
            bm25Score: h.bm25Score,
            vectorScore: h.vectorScore,
          })),
        };

        const filePath = getAuditFilePath();
        await appendFile(filePath, JSON.stringify(record) + '\n', 'utf-8');
      } catch (err) {
        // Fire-and-forget: log but never throw
        console.warn('[audit-jsonl-fallback] Failed to write JSONL:', err);
        throw err; // Re-throw to signal total failure
      }
    },
  };
}
