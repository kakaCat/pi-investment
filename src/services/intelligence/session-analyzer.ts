/**
 * Session Analyzer - Session 分析器
 *
 * 解析 session 日志,提取决策链路和工具调用信息
 *
 * 功能：
 * 1. 解析 .pi-invest/sessions/ 目录下的 Session 日志
 * 2. 提取工具调用记录
 * 3. 关联工具调用与交易结果
 * 4. 计算每个工具的 ROI、胜率、Token 消耗
 * 5. 生成 ToolEfficiency 数据供进化系统使用
 */

import { readdirSync, readFileSync, existsSync } from 'fs';
import { join } from 'path';
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

// ─── Session 日志加载 ────────────────────────────────────────────────────────

/**
 * 从文件系统加载 Session 日志
 */
export function loadSessionLogs(piDir: string, windowDays?: number): DecisionChain[] {
  const sessionsDir = join(piDir, 'sessions');

  if (!existsSync(sessionsDir)) {
    console.log('[Session分析] sessions 目录不存在');
    return [];
  }

  const files = readdirSync(sessionsDir)
    .filter(f => f.endsWith('.jsonl') || f.endsWith('.log') || f.endsWith('.json'))
    .sort();

  // 时间窗口过滤
  let filteredFiles = files;
  if (windowDays) {
    const cutoffDate = new Date();
    cutoffDate.setDate(cutoffDate.getDate() - windowDays);
    const cutoffStr = cutoffDate.toISOString().split('T')[0];

    filteredFiles = files.filter(f => {
      const dateMatch = f.match(/(\d{4}-\d{2}-\d{2})/);
      if (dateMatch) {
        return dateMatch[1] >= cutoffStr;
      }
      return true;
    });
  }

  console.log(`[Session分析] 加载 ${filteredFiles.length} 个 Session 日志文件`);

  const sessions: DecisionChain[] = [];
  for (const file of filteredFiles) {
    const filePath = join(sessionsDir, file);
    try {
      const content = readFileSync(filePath, 'utf-8');
      const events = parseSessionFile(content);
      if (events.length > 0) {
        const sessionId = file.replace(/\.(jsonl|log|json)$/, '');
        const session = parseSessionEvents(sessionId, events);
        sessions.push(session);
      }
    } catch (e) {
      console.error(`[Session分析] 读取文件失败: ${file}`, e);
    }
  }

  return sessions;
}

/**
 * 解析 Session 文件内容
 */
function parseSessionFile(content: string): SessionEvent[] {
  const events: SessionEvent[] = [];
  const lines = content.split('\n').filter(l => l.trim());

  for (const line of lines) {
    try {
      const entry = JSON.parse(line);

      // 兼容不同的日志格式
      if (entry.event) {
        events.push({
          ts: entry.ts || entry.timestamp || Date.now() / 1000,
          event: entry.event,
          data: entry.data || entry
        });
      } else if (entry.type) {
        // 兼容 type 字段
        events.push({
          ts: entry.timestamp || Date.now() / 1000,
          event: entry.type,
          data: entry
        });
      }
    } catch {
      // 跳过无法解析的行
    }
  }

  return events;
}

/**
 * 从交易记录构建 TradeResult
 */
export function buildTradeResults(trades: Array<{
  date: string;
  action: 'buy' | 'sell';
  symbol: string;
  price: number;
  quantity: number;
}>): TradeResult[] {
  // 简化版：假设每笔卖出都有对应的买入
  const results: TradeResult[] = [];
  const buyMap = new Map<string, { price: number; date: string }>();

  for (const trade of trades) {
    if (trade.action === 'buy') {
      buyMap.set(trade.symbol, { price: trade.price, date: trade.date });
    } else if (trade.action === 'sell') {
      const buy = buyMap.get(trade.symbol);
      if (buy) {
        const returnPct = ((trade.price - buy.price) / buy.price) * 100;
        results.push({
          session_id: `${buy.date}_${trade.symbol}`, // 简化的 session_id
          symbol: trade.symbol,
          return: returnPct
        });
      }
    }
  }

  return results;
}

/**
 * 主入口：分析 Session 并计算工具效能
 */
export function analyzeSessionsAndCalculateEfficiency(
  piDir: string,
  trades: Array<{
    date: string;
    action: 'buy' | 'sell';
    symbol: string;
    price: number;
    quantity: number;
  }>,
  windowDays?: number
): ToolEfficiency[] {
  const sessions = loadSessionLogs(piDir, windowDays);

  if (sessions.length === 0) {
    console.log('[Session分析] 没有找到 Session 日志，返回空结果');
    return [];
  }

  const tradeResults = buildTradeResults(trades);
  return evaluateToolEfficiency(sessions, tradeResults);
}
