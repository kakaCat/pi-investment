import { describe, it, expect } from '@jest/globals';
import { applyQualityGate } from '../quality-gate.js';
import type { RecallHit } from '../types.js';

describe('applyQualityGate', () => {
  it('should suppress empty results', () => {
    const result = applyQualityGate([]);
    expect(result).toEqual({
      gate: 'suppressed',
      reason: 'empty-result',
    });
  });

  it('should pass non-empty results with hits unchanged', () => {
    const hits: RecallHit[] = [
      {
        id: 1,
        score: 0.85,
        source: 'both',
        bm25Score: 12.5,
        vectorScore: 0.85,
        title: 'Test Memory',
        content: 'This is a test memory',
      },
      {
        id: 2,
        score: 0.72,
        source: 'vector',
        vectorScore: 0.72,
        content: 'Another memory',
      },
    ];

    const result = applyQualityGate(hits);
    expect(result).toEqual({
      gate: 'passed',
      hits,
    });
  });

  it('should pass single hit result', () => {
    const hits: RecallHit[] = [
      {
        id: 42,
        score: 0.95,
        source: 'bm25',
        bm25Score: 18.2,
        content: 'Single memory',
      },
    ];

    const result = applyQualityGate(hits);
    expect(result).toEqual({
      gate: 'passed',
      hits,
    });
  });
});
