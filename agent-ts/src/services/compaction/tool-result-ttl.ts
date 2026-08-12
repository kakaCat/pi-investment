/**
 * Tool Result TTL Manager
 *
 * 管理工具结果的生命周期和上下文预算：
 * - 超过 N 轮的结果替换为占位符
 * - 单会话工具结果总量 ≤ 0.5×上下文窗口
 * - 超出从最旧开始降级
 */

import type { AgentMessage } from "../../sdk-facade.js";
import { promises as fs } from 'fs';
import * as path from 'path';
import { getSessionDir } from '../../infrastructure/logging/observable-logger.js';

export interface ToolResultTTLOptions {
  /** 工具结果保留轮次（默认 20 轮） */
  maxTurns?: number;
  /** 工具结果占上下文窗口比例（默认 0.5） */
  maxBudgetRatio?: number;
  /** 上下文窗口大小（tokens） */
  contextWindowSize?: number;
}

/**
 * 计算消息所处的轮次（从用户消息计数）
 */
function calculateTurnIndex(messages: AgentMessage[], messageIndex: number): number {
  let turnCount = 0;
  for (let i = 0; i <= messageIndex; i++) {
    if (messages[i].role === 'user') {
      turnCount++;
    }
  }
  return turnCount;
}

/**
 * 估算消息的 token 数（简单估算：字符数 / 4）
 */
function estimateMessageTokens(msg: AgentMessage): number {
  if (msg.role === 'toolResult' && Array.isArray((msg as any).content)) {
    return (msg as any).content.reduce((sum: number, block: any) => {
      if (block.type === 'text') {
        return sum + (block.text?.length || 0) / 4;
      }
      return sum;
    }, 0);
  }
  return 0;
}

/**
 * 持久化工具结果到文件
 */
async function persistToolResult(
  toolCallId: string,
  toolName: string,
  content: any[]
): Promise<string> {
  const sessionDir = getSessionDir();
  if (!sessionDir) {
    throw new Error('No active session directory');
  }

  const ttlDir = path.join(sessionDir, 'tool-results-ttl');
  await fs.mkdir(ttlDir, { recursive: true });

  const fileName = `${toolName}_${toolCallId}.json`;
  const filePath = path.join(ttlDir, fileName);

  await fs.writeFile(
    filePath,
    JSON.stringify({ toolCallId, toolName, content, timestamp: Date.now() }, null, 2),
    'utf-8'
  );

  return filePath;
}

/**
 * 应用工具结果 TTL 策略
 *
 * 规则：
 * 1. 超过 maxTurns 轮的结果替换为占位符
 * 2. 工具结果总量超过预算时，从最旧开始降级
 *
 * @param messages - 消息数组（会被就地修改）
 * @param options - TTL 选项
 */
export async function applyToolResultTTL(
  messages: AgentMessage[],
  options: ToolResultTTLOptions = {}
): Promise<{ replacedCount: number; savedBytes: number }> {
  const maxTurns = options.maxTurns ?? 20;
  const maxBudgetRatio = options.maxBudgetRatio ?? 0.5;
  const contextWindowSize = options.contextWindowSize ?? 128000; // DeepSeek v4 默认

  const maxToolResultTokens = contextWindowSize * maxBudgetRatio;

  // 计算当前轮次（最后一条用户消息的轮次）
  let currentTurn = 0;
  for (const msg of messages) {
    if (msg.role === 'user') {
      currentTurn++;
    }
  }

  // 第一遍：按轮次 TTL 替换
  const toolResultIndices: Array<{ index: number; turn: number; tokens: number }> = [];
  let replacedCount = 0;
  let savedBytes = 0;

  for (let i = 0; i < messages.length; i++) {
    const msg = messages[i];
    if (msg.role !== 'toolResult') continue;

    const turnIndex = calculateTurnIndex(messages, i);
    const age = currentTurn - turnIndex;
    const tokens = estimateMessageTokens(msg);

    toolResultIndices.push({ index: i, turn: turnIndex, tokens });

    // 超过 maxTurns 轮的结果替换为占位符
    if (age > maxTurns) {
      const toolCallId = (msg as any).toolCallId;
      const toolName = (msg as any).toolName || 'unknown';
      const content = (msg as any).content;

      try {
        // 持久化原始结果
        const filePath = await persistToolResult(toolCallId, toolName, content);

        // 计算节省的字节数
        const originalSize = JSON.stringify(content).length;
        savedBytes += originalSize;

        // 替换为占位符
        (msg as any).content = [{
          type: 'text',
          text: `[Old tool result cleared, ref: ${filePath}]\n\n💡 Use Read tool to access the original result if needed.`
        }];

        replacedCount++;
      } catch (err) {
        console.warn(`⚠️ Failed to persist tool result for TTL: ${err instanceof Error ? err.message : String(err)}`);
      }
    }
  }

  // 第二遍：按预算降级（从最旧开始）
  let totalToolResultTokens = toolResultIndices.reduce((sum, item) => {
    const msg = messages[item.index];
    return sum + estimateMessageTokens(msg); // 重新计算（可能已被占位符替换）
  }, 0);

  if (totalToolResultTokens > maxToolResultTokens) {
    // 按轮次排序（从旧到新）
    const sortedIndices = [...toolResultIndices].sort((a, b) => a.turn - b.turn);

    for (const item of sortedIndices) {
      if (totalToolResultTokens <= maxToolResultTokens) break;

      const msg = messages[item.index];
      const content = (msg as any).content;

      // 跳过已经是占位符的结果
      if (
        Array.isArray(content) &&
        content.length === 1 &&
        content[0].type === 'text' &&
        content[0].text.startsWith('[Old tool result cleared')
      ) {
        continue;
      }

      const toolCallId = (msg as any).toolCallId;
      const toolName = (msg as any).toolName || 'unknown';

      try {
        // 持久化原始结果
        const filePath = await persistToolResult(toolCallId, toolName, content);

        // 计算节省的 tokens
        const originalTokens = estimateMessageTokens(msg);
        const originalSize = JSON.stringify(content).length;
        savedBytes += originalSize;

        // 替换为占位符
        (msg as any).content = [{
          type: 'text',
          text: `[Tool result offloaded due to budget, ref: ${filePath}]\n\n💡 Use Read tool to access the original result if needed.`
        }];

        totalToolResultTokens -= originalTokens;
        totalToolResultTokens += 50; // 占位符的 token 估算
        replacedCount++;
      } catch (err) {
        console.warn(`⚠️ Failed to persist tool result for budget: ${err instanceof Error ? err.message : String(err)}`);
      }
    }
  }

  if (replacedCount > 0) {
    console.log(
      `🗜️  Tool result TTL: 替换了 ${replacedCount} 个工具结果，` +
      `节省约 ${(savedBytes / 1024).toFixed(1)} KB`
    );
  }

  return { replacedCount, savedBytes };
}

/**
 * 获取工具结果统计信息
 */
export function getToolResultStats(messages: AgentMessage[]): {
  totalCount: number;
  totalTokens: number;
  oldestTurn: number;
  newestTurn: number;
} {
  let totalCount = 0;
  let totalTokens = 0;
  let oldestTurn = Infinity;
  let newestTurn = 0;

  for (let i = 0; i < messages.length; i++) {
    const msg = messages[i];
    if (msg.role !== 'toolResult') continue;

    totalCount++;
    totalTokens += estimateMessageTokens(msg);

    const turn = calculateTurnIndex(messages, i);
    oldestTurn = Math.min(oldestTurn, turn);
    newestTurn = Math.max(newestTurn, turn);
  }

  return {
    totalCount,
    totalTokens,
    oldestTurn: oldestTurn === Infinity ? 0 : oldestTurn,
    newestTurn,
  };
}
