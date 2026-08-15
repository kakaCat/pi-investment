/**
 * Agent OS Memory Provider Integration Test
 *
 * 验证 Memory Provider 完整功能
 */

import { describe, it, expect, beforeAll, afterAll } from '@jest/globals';
import { AgentOSMemoryProvider } from '../../../src/services/memory/agent-os-provider.js';
import type { MemoryProvider } from '../../../src/services/memory/port.js';

describe('AgentOSMemoryProvider Integration', () => {
  let provider: MemoryProvider;
  const testSessionId = 'test-session-' + Date.now();

  beforeAll(async () => {
    provider = new AgentOSMemoryProvider();

    await provider.initialize(testSessionId, {
      sessionKind: 'user',
      channel: 'terminal',
    });
  });

  afterAll(async () => {
    await provider.shutdown();
  });

  it('should check availability', () => {
    expect(provider.isAvailable()).toBe(true);
    expect(provider.name).toBe('agent-os');
  });

  it('should return system prompt block', () => {
    const block = provider.systemPromptBlock();
    expect(block).toContain('Agent OS');
    expect(block).toContain(testSessionId);
  });

  it('should write and query memory', async () => {
    // Write memory
    const writeResult = await provider.write({
      kind: 'episode',
      scope: 'global',
      title: 'Test Memory Entry',
      content: 'This is a test memory entry for integration testing',
      source: 'agent',
      confidence: 0.9,
    });

    expect(writeResult).toBeDefined();
    expect(writeResult.id).toBeDefined();

    // Query memory
    const queryResult = await provider.query('test memory entry', {
      limit: 5,
    });

    expect(queryResult).toBeDefined();
    expect(queryResult.items).toBeDefined();
    expect(Array.isArray(queryResult.items)).toBe(true);
    expect(queryResult.strategy).toBe('hybrid');
  }, 15000);

  it('should search memory (legacy interface)', async () => {
    const results = await provider.search('test memory', 5);

    expect(Array.isArray(results)).toBe(true);
    results.forEach(item => {
      expect(item).toHaveProperty('content');
      expect(item).toHaveProperty('score');
    });
  }, 10000);

  it('should write and query experience', async () => {
    const experienceResult = await provider.writeExperience({
      scenario: 'test_scenario',
      conditions: ['condition1', 'condition2'],
      action: 'buy',
      total_cases: 10,
      win_rate: 0.7,
      avg_return: 0.05,
      recommendation: 'moderate',
      reason: 'Test experience entry',
      confidence: 0.8,
    });

    expect(experienceResult.success).toBe(true);
    expect(experienceResult.id).toBeDefined();

    // Query experience
    const queryResult = await provider.queryExperience({
      scenario: 'test_scenario',
      limit: 5,
    });

    expect(typeof queryResult).toBe('string');
    expect(queryResult).not.toBe('无相关经验');
  }, 15000);

  it('should handle prefetch', async () => {
    const prefetchResult = await provider.prefetch(
      'test memory',
      testSessionId,
      3,
      2000
    );

    expect(typeof prefetchResult).toBe('string');
    // Prefetch may return empty string if no relevant memories
  }, 10000);

  it('should reject recall-sourced writes', async () => {
    const writeResult = await provider.write({
      content: 'This should be rejected',
      source: 'recall', // This should be rejected
    });

    expect(writeResult.path).toBe('rejected:recall-loop');
  });
});
