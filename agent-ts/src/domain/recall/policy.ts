// policy.ts — 策略表（声明式，唯一事实源）
import type { PolicyDecision, RecallFlow } from './types.js';

const POLICY_TABLE: Record<RecallFlow, { enabled: boolean; topK: number; charBudget: number }> = {
  'interactive-chat': { enabled: true, topK: 3, charBudget: 2000 },
  'skill-invocation': { enabled: true, topK: 2, charBudget: 1000 },
  'scheduled-task':   { enabled: true, topK: 3, charBudget: 2000 },
  'wake-event':       { enabled: true, topK: 2, charBudget: 1000 },
};

export function decidePolicy(flow: RecallFlow): PolicyDecision {
  const row = POLICY_TABLE[flow];
  if (!row) return { enabled: false, topK: 0, charBudget: 0, reason: 'unknown-flow' };
  return row.enabled
    ? { enabled: true, topK: row.topK, charBudget: row.charBudget }
    : { enabled: false, topK: 0, charBudget: 0, reason: 'policy-disabled' };
}
