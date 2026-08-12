/**
 * Compaction Service Tests
 */
import { describe, it, expect } from '@jest/globals';
import { findSafeSplitPoint, compactConversationHistory } from '../compaction-service.js';
import type { AgentMessage } from '../../../sdk-facade.js';

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

describe('findSafeSplitPoint', () => {
  it('should not split between assistant tool_calls and tool results', () => {
    const messages: AgentMessage[] = [
      createUserMessage('Turn 1'),
      createAssistantMessage([
        { type: 'text', text: 'Let me check that' },
        { type: 'toolCall', id: 'call_1', name: 'stock_info' }
      ]),
      createToolResultMessage('call_1', 'stock_info', 'Stock data here'),
      createUserMessage('Turn 2'),
      createAssistantMessage([
        { type: 'text', text: 'Analyzing' },
        { type: 'toolCall', id: 'call_2', name: 'analyze' }
      ]),
      createToolResultMessage('call_2', 'analyze', 'Analysis result'),
      createUserMessage('Turn 3'),
      createAssistantMessage([
        { type: 'text', text: 'Let me search' },
        { type: 'toolCall', id: 'call_3', name: 'search' }
      ]),
      createToolResultMessage('call_3', 'search', 'Search result'),
      createUserMessage('Turn 4'),
      createAssistantMessage([{ type: 'text', text: 'Done' }]),
    ];

    // 测试：提议的 split 点在工具对中间（index 2，在 call_1 的 toolResult 之后）
    const safeSplit = findSafeSplitPoint(messages, 2);

    // 期望：split 点应该移到 call_1 的 assistant 消息之前（index 1）
    expect(safeSplit).toBe(1);
  });

  it('should return proposed index if no tool pairs are split', () => {
    const messages: AgentMessage[] = [
      createUserMessage('Turn 1'),
      createAssistantMessage([
        { type: 'toolCall', id: 'call_1', name: 'tool' }
      ]),
      createToolResultMessage('call_1', 'tool', 'Result'),
      createUserMessage('Turn 2'),
      createAssistantMessage([{ type: 'text', text: 'Response' }]),
    ];

    // 提议的 split 点在工具对之后
    const safeSplit = findSafeSplitPoint(messages, 4);

    // 期望：返回原提议的 index
    expect(safeSplit).toBe(4);
  });

  it('should handle multiple consecutive tool pairs', () => {
    const messages: AgentMessage[] = [
      createUserMessage('Request'),
      createAssistantMessage([
        { type: 'toolCall', id: 'call_1', name: 'tool1' },
        { type: 'toolCall', id: 'call_2', name: 'tool2' }
      ]),
      createToolResultMessage('call_1', 'tool1', 'Result 1'),
      createToolResultMessage('call_2', 'tool2', 'Result 2'),
      createAssistantMessage([{ type: 'text', text: 'Summary' }]),
    ];

    // 提议的 split 点在第一个 toolResult 之后（index 3）
    const safeSplit = findSafeSplitPoint(messages, 3);

    // 期望：移到 assistant(tool_calls) 之前（index 1）
    expect(safeSplit).toBe(1);
  });

  it('should not create orphan tool results after compaction', () => {
    // 构造包含 20 轮对话的完整场景
    const messages: AgentMessage[] = [];

    for (let i = 1; i <= 20; i++) {
      messages.push(createUserMessage(`Turn ${i}`));
      messages.push(createAssistantMessage([
        { type: 'text', text: `Response ${i}` },
        { type: 'toolCall', id: `call_${i}`, name: 'tool' }
      ]));
      messages.push(createToolResultMessage(`call_${i}`, 'tool', `Result ${i}`));
    }

    // 提议保留最后 5 轮（从 user Turn 16 开始）
    const userTurn16Index = messages.findIndex(
      m => m.role === 'user' && (m as any).content.includes('Turn 16')
    );

    const safeSplit = findSafeSplitPoint(messages, userTurn16Index);

    // 验证：split 之后的所有 toolResult 都有对应的 tool_calls
    const toolCallsAfterSplit = new Set<string>();
    const toolResultsAfterSplit: string[] = [];

    for (let i = safeSplit; i < messages.length; i++) {
      const msg = messages[i];
      if (msg.role === 'assistant' && Array.isArray((msg as any).content)) {
        for (const block of (msg as any).content) {
          if (block.type === 'toolCall') {
            toolCallsAfterSplit.add(block.id);
          }
        }
      }
      if (msg.role === 'toolResult') {
        toolResultsAfterSplit.push((msg as any).toolCallId);
      }
    }

    // 所有 toolResult 都应该有对应的 tool_call
    for (const resultId of toolResultsAfterSplit) {
      expect(toolCallsAfterSplit.has(resultId)).toBe(true);
    }
  });
});

describe('compactConversationHistory', () => {
  const simpleTokenEstimator = (msg: AgentMessage): number => {
    if (msg.role === 'user' && typeof (msg as any).content === 'string') {
      return (msg as any).content.length / 4;
    }
    if ((msg.role === 'assistant' || msg.role === 'toolResult') && Array.isArray((msg as any).content)) {
      return (msg as any).content.reduce((sum: number, block: any) => {
        if (block.type === 'text') {
          return sum + (block.text?.length || 0) / 4;
        }
        return sum + 50; // toolCall/toolResult base cost
      }, 0);
    }
    return 0;
  };

  it('should use safe split point when compacting', () => {
    const messages: AgentMessage[] = [];

    // 创建足够大的对话以触发压缩
    for (let i = 1; i <= 10; i++) {
      messages.push(createUserMessage(`User message ${i}`));
      messages.push(createAssistantMessage([
        { type: 'text', text: `Assistant response ${i} `.repeat(100) }, // 长文本
        { type: 'toolCall', id: `call_${i}`, name: 'tool' }
      ]));
      messages.push(createToolResultMessage(`call_${i}`, 'tool', `Tool result ${i}`));
    }

    const result = compactConversationHistory(messages, simpleTokenEstimator, {
      keepTurns: 3,
      tokenThreshold: 1000
    });

    expect(result.compacted).toBe(true);

    // 验证：压缩后没有孤儿 tool results
    const toolCallsInMessages = new Set<string>();
    const toolResultsInMessages: string[] = [];

    for (const msg of messages) {
      if (msg.role === 'assistant' && Array.isArray((msg as any).content)) {
        for (const block of (msg as any).content) {
          if (block.type === 'toolCall') {
            toolCallsInMessages.add(block.id);
          }
        }
      }
      if (msg.role === 'toolResult') {
        toolResultsInMessages.push((msg as any).toolCallId);
      }
    }

    // 所有 toolResult 都应该有对应的 tool_call
    for (const resultId of toolResultsInMessages) {
      expect(toolCallsInMessages.has(resultId)).toBe(true);
    }
  });
});
