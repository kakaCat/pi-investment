import { describe, it, expect } from '@jest/globals';
import { formatRecallMessage } from '../recall-message.js';
import type { RecallHit } from '../types.js';

describe('formatRecallMessage', () => {
  it('should format recall message with correct XML structure', () => {
    const hits: RecallHit[] = [
      {
        id: 1,
        score: 0.85,
        source: 'both',
        bm25Score: 12.5,
        vectorScore: 0.85,
        title: 'Test Memory',
        content: 'First memory content',
      },
      {
        id: 2,
        score: 0.72,
        source: 'vector',
        vectorScore: 0.72,
        content: 'Second memory content',
      },
    ];

    const result = formatRecallMessage('interactive-chat', hits, 5000);

    expect(result.customType).toBe('recalled-memory');
    expect(result.display).toBe(false);
    expect(result.details).toEqual({
      flow: 'interactive-chat',
      count: 2,
    });

    // Check XML structure
    expect(result.content).toContain('<recalled_memory');
    expect(result.content).toContain('source="auto-prefetch"');
    expect(result.content).toContain('flow="interactive-chat"');
    expect(result.content).toContain('count="2"');
    expect(result.content).toContain('gate="passed"');
    expect(result.content).toContain('<memory id="1"');
    expect(result.content).toContain('relevance="0.85"');
    expect(result.content).toContain('source="both"');
    expect(result.content).toContain('First memory content');
    expect(result.content).toContain('<memory id="2"');
    expect(result.content).toContain('relevance="0.72"');
    expect(result.content).toContain('source="vector"');
    expect(result.content).toContain('Second memory content');
    expect(result.content).toContain('</recalled_memory>');
  });

  it('should escape XML special characters', () => {
    const hits: RecallHit[] = [
      {
        id: 1,
        score: 0.90,
        source: 'bm25',
        bm25Score: 15.0,
        content: '<买卖> & "止损"',
      },
    ];

    const result = formatRecallMessage('skill-invocation', hits, 5000);

    // Should not contain unescaped special characters
    expect(result.content).not.toContain('<买卖>');
    expect(result.content).toContain('&lt;买卖&gt;');
    expect(result.content).toContain('&amp;');
    expect(result.content).toContain('&quot;止损&quot;');
  });

  it('should truncate content when exceeding charBudget', () => {
    const hits: RecallHit[] = [
      {
        id: 1,
        score: 0.90,
        source: 'bm25',
        bm25Score: 15.0,
        content: 'First memory',
      },
      {
        id: 2,
        score: 0.85,
        source: 'vector',
        vectorScore: 0.85,
        content: 'Second memory',
      },
    ];

    const result = formatRecallMessage('wake-event', hits, 50);

    // With such a small budget, should only include structure and possibly first hit
    expect(result.details.count).toBeLessThan(2);
    expect(result.content).toContain('<recalled_memory');
    expect(result.content).toContain('</recalled_memory>');
  });

  it('should handle empty hits list gracefully', () => {
    const result = formatRecallMessage('scheduled-task', [], 5000);

    expect(result.customType).toBe('recalled-memory');
    expect(result.display).toBe(false);
    expect(result.details).toEqual({
      flow: 'scheduled-task',
      count: 0,
    });
    expect(result.content).toContain('count="0"');
  });
});
