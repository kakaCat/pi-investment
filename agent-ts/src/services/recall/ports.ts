// ports.ts
import type { GateResult, RecallContext, RecallHit, RecallMessage } from '../../domain/recall/types.js';

export interface RecallSearchPort {
  search(query: string, limit: number): Promise<RecallHit[]>;
}

export interface RecallAuditPort {
  record(decision: {
    ts: string; sessionId?: string; flow: string; queryText: string;
    strategy: string; degraded: boolean;
    gateResult: 'passed' | 'suppressed'; suppressReason?: string;
    hits: Array<{ memoryId: number; score: number; source: string; bm25Score?: number; vectorScore?: number }>;
  }): Promise<void>;  // 实现必须 fire-and-forget 友好（内部 catch，不抛）
}
