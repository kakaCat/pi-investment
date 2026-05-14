/**
 * Session Analyzer - Session 分析器
 *
 * 解析 session 日志,提取决策链路和工具调用信息
 */

import type { DecisionChain, ToolCall, ToolEfficiency } from '../../types/evolution.js';

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

interface TradeResult {
  session_id: string;
  symbol: string;
  return: number;
}

/**
 * 评估工具效能
 */
export function evaluateToolEfficiency(
  sessions: DecisionChain[],
  trades: TradeResult[]
): ToolEfficiency[] {
  // 构建 session_id -> trade 映射
  const tradeMap = new Map<string, TradeResult>();
  for (const trade of trades) {
    tradeMap.set(trade.session_id, trade);
  }

  // 统计每个工具的使用情况
  const toolStats = new Map<string, {
    calls: number;
    decisions: number;
    wins: number;
    totalReturn: number;
    totalTokens: number;
    totalCost: number;
  }>();

  for (const session of sessions) {
    const trade = tradeMap.get(session.session_id);
    const hasDecision = session.decision.action !== '';
    const isWin = trade && trade.return > 0;

    for (const toolCall of session.tool_calls) {
      const stats = toolStats.get(toolCall.tool_name) || {
        calls: 0,
        decisions: 0,
        wins: 0,
        totalReturn: 0,
        totalTokens: 0,
        totalCost: 0
      };

      stats.calls++;
      if (hasDecision) {
        stats.decisions++;
        if (isWin) stats.wins++;
        if (trade) stats.totalReturn += trade.return;
      }
      stats.totalTokens += session.resources.tokens;
      stats.totalCost += session.resources.cost;

      toolStats.set(toolCall.tool_name, stats);
    }
  }

  // 转换为 ToolEfficiency 数组
  const result: ToolEfficiency[] = [];

  for (const [toolName, stats] of toolStats.entries()) {
    const winRate = stats.decisions > 0 ? stats.wins / stats.decisions : 0;
    const avgReturn = stats.decisions > 0 ? stats.totalReturn / stats.decisions : 0;
    const avgTokens = stats.calls > 0 ? stats.totalTokens / stats.calls : 0;
    const costPerCall = stats.calls > 0 ? stats.totalCost / stats.calls : 0;
    const roi = costPerCall > 0 ? avgReturn / costPerCall : 0;

    // 评级：基于 ROI
    let rating: 1 | 2 | 3 | 4 | 5;
    if (roi >= 50) rating = 5;
    else if (roi >= 20) rating = 4;
    else if (roi >= 5) rating = 3;
    else if (roi >= 0) rating = 2;
    else rating = 1;

    result.push({
      tool_name: toolName,
      call_count: stats.calls,
      decisions_after_call: stats.decisions,
      win_rate: winRate,
      avg_return: avgReturn,
      avg_tokens: avgTokens,
      cost_per_call: costPerCall,
      roi,
      rating
    });
  }

  return result.sort((a, b) => b.roi - a.roi);
}
