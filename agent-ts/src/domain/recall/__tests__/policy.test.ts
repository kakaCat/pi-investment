import { describe, it, expect } from '@jest/globals';
import { decidePolicy } from '../policy.js';
import type { RecallFlow } from '../types.js';

describe('decidePolicy', () => {
  it('should return correct policy for interactive-chat', () => {
    const result = decidePolicy('interactive-chat');
    expect(result).toEqual({
      enabled: true,
      topK: 3,
      charBudget: 2000,
    });
  });

  it('should return correct policy for skill-invocation', () => {
    const result = decidePolicy('skill-invocation');
    expect(result).toEqual({
      enabled: true,
      topK: 2,
      charBudget: 1000,
    });
  });

  it('should return correct policy for scheduled-task', () => {
    const result = decidePolicy('scheduled-task');
    expect(result).toEqual({
      enabled: true,
      topK: 3,
      charBudget: 2000,
    });
  });

  it('should return correct policy for wake-event', () => {
    const result = decidePolicy('wake-event');
    expect(result).toEqual({
      enabled: true,
      topK: 2,
      charBudget: 1000,
    });
  });

  it('should handle unknown flow type', () => {
    const result = decidePolicy('unknown-flow' as RecallFlow);
    expect(result).toEqual({
      enabled: false,
      topK: 0,
      charBudget: 0,
      reason: 'unknown-flow',
    });
  });
});
