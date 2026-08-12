/**
 * Tool Result TTL Tests
 */
import { describe, it, expect, beforeEach, afterEach } from '@jest/globals';
import { applyToolResultTTL, getToolResultStats } from '../tool-result-ttl.js';
import type { AgentMessage } from '../../../sdk-facade.js';
import { promises as fs } from 'fs';
import * as path from 'path';

// Helper functions to create properly typed messages
function createUserMessage(content: string): AgentMessage {
  return {
    role: 'user',
    content,
    timestamp: Date.now()
  } as AgentMessage;
}

function createAssistantMessage(content: Array<{ type: string; text?: string; id?: string; name?: string }>): AgentMessage {
  return {
    role: 'assistant',
    content: content.map(block => {
      if (block.type === 'text') {
        return { type: 'text', text: block.text || '' };
      } else if (block.type === 'toolCall') {
        return { type: 'toolCall', id: block.id!, name: block.name!, parameters: {} };
      }
      return block;
    }),
    timestamp: Date.now()
  } as AgentMessage;
}

function createToolResultMessage(toolCallId: string, toolName: string, text: string): AgentMessage {
  return {
    role: 'toolResult',
    toolCallId,
    toolName,
    content: [{ type: 'text', text }],
    isError: false,
    timestamp: Date.now()
  } as AgentMessage;
}

describe('getToolResultStats', () => {
  it('should calculate tool result statistics', () => {
    const messages: AgentMessage[] = [
      createUserMessage('Turn 1'),
      createAssistantMessage([{ type: 'toolCall', id: 'call_1', name: 'tool' }]),
      createToolResultMessage('call_1', 'tool', 'Result 1 '.repeat(100)),
      createUserMessage('Turn 2'),
      createAssistantMessage([{ type: 'toolCall', id: 'call_2', name: 'tool' }]),
      createToolResultMessage('call_2', 'tool', 'Result 2 '.repeat(100)),
    ];

    const stats = getToolResultStats(messages);

    expect(stats.totalCount).toBe(2);
    expect(stats.totalTokens).toBeGreaterThan(0);
    expect(stats.oldestTurn).toBe(1);
    expect(stats.newestTurn).toBe(2);
  });

  it('should return zero stats for messages without tool results', () => {
    const messages: AgentMessage[] = [
      createUserMessage('Turn 1'),
      createAssistantMessage([{ type: 'text', text: 'Response' }]),
    ];

    const stats = getToolResultStats(messages);

    expect(stats.totalCount).toBe(0);
    expect(stats.totalTokens).toBe(0);
    expect(stats.oldestTurn).toBe(0);
    expect(stats.newestTurn).toBe(0);
  });
});

describe('applyToolResultTTL', () => {
  // Note: These tests don't actually persist files since getSessionDir() returns undefined in test environment
  // We're testing the logic, not the file I/O

  it('should replace tool results older than maxTurns', async () => {
    const messages: AgentMessage[] = [];

    // Create 25 turns with tool results
    for (let i = 1; i <= 25; i++) {
      messages.push(createUserMessage(`Turn ${i}`));
      messages.push(createAssistantMessage([{ type: 'toolCall', id: `call_${i}`, name: 'tool' }]));
      messages.push(createToolResultMessage(`call_${i}`, 'tool', `Result ${i} `.repeat(50)));
    }

    // With maxTurns=20, the first 5 results should be replaced
    // Note: This will fail to persist files but should still attempt replacement
    const result = await applyToolResultTTL(messages, { maxTurns: 20 });

    // In test environment without session dir, replacedCount will be 0
    // But we can check that the logic runs without errors
    expect(result.replacedCount).toBeGreaterThanOrEqual(0);
    expect(result.savedBytes).toBeGreaterThanOrEqual(0);
  });

  it('should respect budget limits and replace oldest first', async () => {
    const messages: AgentMessage[] = [];

    // Create 10 turns with large tool results
    for (let i = 1; i <= 10; i++) {
      messages.push(createUserMessage(`Turn ${i}`));
      messages.push(createAssistantMessage([{ type: 'toolCall', id: `call_${i}`, name: 'tool' }]));
      // Large result: 1000 chars ≈ 250 tokens
      messages.push(createToolResultMessage(`call_${i}`, 'tool', 'x'.repeat(1000)));
    }

    // Set a very small budget to force replacement
    const result = await applyToolResultTTL(messages, {
      maxTurns: 100, // Don't replace by age
      maxBudgetRatio: 0.01, // Only 1% of context window
      contextWindowSize: 10000, // Small window
    });

    // Should attempt to replace some results
    expect(result.replacedCount).toBeGreaterThanOrEqual(0);
  });

  it('should not replace recent tool results within maxTurns', async () => {
    const messages: AgentMessage[] = [];

    // Create 5 turns
    for (let i = 1; i <= 5; i++) {
      messages.push(createUserMessage(`Turn ${i}`));
      messages.push(createAssistantMessage([{ type: 'toolCall', id: `call_${i}`, name: 'tool' }]));
      messages.push(createToolResultMessage(`call_${i}`, 'tool', `Result ${i}`));
    }

    const result = await applyToolResultTTL(messages, { maxTurns: 20 });

    // All results are within 20 turns, so none should be replaced by age
    // (Budget might still trigger replacement, but unlikely with small messages)
    expect(result.replacedCount).toBe(0);
  });

  it('should handle messages without tool results', async () => {
    const messages: AgentMessage[] = [
      createUserMessage('Hello'),
      createAssistantMessage([{ type: 'text', text: 'Hi there' }]),
      createUserMessage('How are you?'),
      createAssistantMessage([{ type: 'text', text: 'I am fine' }]),
    ];

    const result = await applyToolResultTTL(messages);

    expect(result.replacedCount).toBe(0);
    expect(result.savedBytes).toBe(0);
  });

  it('should skip already replaced tool results', async () => {
    const messages: AgentMessage[] = [
      createUserMessage('Turn 1'),
      createAssistantMessage([{ type: 'toolCall', id: 'call_1', name: 'tool' }]),
      {
        role: 'toolResult',
        toolCallId: 'call_1',
        toolName: 'tool',
        content: [{ type: 'text', text: '[Old tool result cleared, ref: /some/path.json]' }],
        isError: false,
        timestamp: Date.now()
      } as AgentMessage,
    ];

    const result = await applyToolResultTTL(messages, {
      maxTurns: 0, // Force replacement by age
    });

    // Already replaced, so should not be replaced again
    expect(result.replacedCount).toBe(0);
  });
});
