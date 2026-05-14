/**
 * Session Analyzer - Session 分析器
 *
 * 解析 session 日志,提取决策链路和工具调用信息
 */

import type { DecisionChain, ToolCall } from '../../types/evolution.js';

interface SessionEvent {
  ts: number;
  event: string;
  data?: any;
}

/**
 * 解析 session events
 */
export function parseSessionEvents(
  sessionId: string,
  events: SessionEvent[]
): DecisionChain {
  let userQuery = '';
  const toolCalls: ToolCall[] = [];
  let decision = { action: '', symbol: '', reason: '' };
  let totalTokens = 0;
  let totalCost = 0;

  const startTime = events[0]?.ts || 0;
  const endTime = events[events.length - 1]?.ts || 0;

  for (const event of events) {
    switch (event.event) {
      case 'user_message':
        if (!userQuery) {
          userQuery = event.data?.content || '';
        }
        break;

      case 'tool_call':
        toolCalls.push({
          tool_name: event.data?.tool || '',
          arguments: event.data?.args || {},
          timestamp: new Date(event.ts * 1000).toISOString()
        });
        break;

      case 'assistant_message':
        const content = event.data?.content || '';
        if (content.includes('买入')) {
          decision.action = 'buy';
        } else if (content.includes('卖出')) {
          decision.action = 'sell';
        } else if (content.includes('持有')) {
          decision.action = 'hold';
        }
        decision.reason = content;
        break;

      case 'llm_call':
        totalTokens += event.data?.tokens || 0;
        totalCost += event.data?.cost || 0;
        break;
    }
  }

  return {
    session_id: sessionId,
    timestamp: new Date(startTime * 1000).toISOString(),
    user_query: userQuery,
    tool_calls: toolCalls,
    decision,
    resources: {
      tokens: totalTokens,
      cost: totalCost,
      duration_ms: (endTime - startTime) * 1000
    }
  };
}
