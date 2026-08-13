// types.ts
export type RecallFlow =
  | 'interactive-chat'
  | 'skill-invocation'
  | 'scheduled-task'
  | 'wake-event';

export interface RecallContext {
  flow: RecallFlow;
  rawText: string;        // 用户原文（skill 展开前）
  sessionId?: string;
}

export interface PolicyDecision {
  enabled: boolean;
  topK: number;
  charBudget: number;
  reason?: string;        // enabled=false 时必填
}

export interface RecallHit {
  id: number;
  score: number;
  source: 'bm25' | 'vector' | 'both';
  bm25Score?: number;
  vectorScore?: number;
  title?: string;
  content: string;
}

export type GateResult =
  | { gate: 'passed'; hits: RecallHit[] }
  | { gate: 'suppressed'; reason: 'policy-disabled' | 'empty-result' | 'below-floor' };

export interface RecallMessage {
  customType: 'recalled-memory';
  content: string;        // XML
  display: false;
  details: { flow: RecallFlow; count: number };
}
