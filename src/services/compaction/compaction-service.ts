/**
 * Context Compaction - 上下文压缩
 *
 * 1. Micro-compaction: 每轮清空旧的工具调用结果
 * 2. Conversation compaction: 超过 token 阈值时压缩旧轮次对话
 * 3. Compact tool: Agent 可主动触发压缩
 */
import type { AgentMessage } from "@mariozechner/pi-agent-core";
import { compactionConfig } from "../../config/config.js";

/**
 * 压缩选项
 */
export interface CompactionOptions {
  /** 保留最近 N 个工具调用结果 */
  keepRecent?: number;
  /** 工具结果超过此长度才压缩 */
  minLength?: number;
}

/**
 * 微压缩：清空旧的 toolResult，只保留最近 N 个
 * @param messages - Agent 消息数组
 * @param options - 压缩选项
 */
export function microCompact(
  messages: AgentMessage[],
  options: CompactionOptions = {}
): void {
  const keepRecent = options.keepRecent ?? compactionConfig.keepRecentToolResults;
  const minLength = options.minLength ?? compactionConfig.minLengthToCompact;

  // 收集所有 toolResult 消息的位置
  const toolResults: Array<{ msgIdx: number; toolName: string; length: number }> = [];

  // 构建 toolCallId -> toolName 映射
  const toolNameMap = new Map<string, string>();
  for (const msg of messages) {
    if (msg.role === "assistant" && Array.isArray(msg.content)) {
      for (const block of msg.content) {
        if (block.type === "toolCall") {
          toolNameMap.set(block.id, block.name);
        }
      }
    }
  }

  // 找到所有 toolResult 消息
  for (let i = 0; i < messages.length; i++) {
    const msg = messages[i];
    if (msg.role === "toolResult") {
      const toolName = toolNameMap.get(msg.toolCallId) || msg.toolName || "unknown";
      const totalLength = msg.content.reduce((sum, c) => {
        return sum + (c.type === "text" ? c.text.length : 0);
      }, 0);
      toolResults.push({ msgIdx: i, toolName, length: totalLength });
    }
  }

  // 只清空旧的（保留最近 keepRecent 个）
  if (toolResults.length <= keepRecent) return;

  const toClear = toolResults.slice(0, -keepRecent);
  let compactedCount = 0;

  for (const { msgIdx, toolName, length } of toClear) {
    const msg = messages[msgIdx];
    if (msg.role === "toolResult") {
      // 清空 content 数组中的长文本
      for (const content of msg.content) {
        if (content.type === "text" && content.text.length > minLength) {
          const originalLength = content.text.length;
          content.text = `[Compacted: ${toolName} result (${originalLength} chars)]`;
          compactedCount++;
        }
      }
    }
  }

  if (compactedCount > 0) {
    console.log(`🗜️  压缩了 ${compactedCount} 个工具调用结果`);
  }
}

/**
 * 整体对话压缩：当上下文超过 token 阈值时，将旧轮次压缩为摘要。
 *
 * 策略：
 * - 保留最近 keepTurns 轮完整对话（包括工具调用和结果）
 * - 更早的轮次：保留用户消息原文，助手回复截断至摘要长度
 * - 旧的工具结果交由 microCompact 处理
 *
 * @returns 压缩后的总 token 估算值
 */
export function compactConversationHistory(
  messages: AgentMessage[],
  estimateTokens: (msg: AgentMessage) => number,
  options: {
    /** 保留最近 N 轮完整对话 */
    keepTurns?: number;
    /** 旧助手消息保留的最大字符数 */
    assistantSummaryChars?: number;
    /** 触发压缩的 token 阈值 */
    tokenThreshold?: number;
  } = {}
): { compacted: boolean; estimatedTokens: number } {
  const keepTurns = options.keepTurns ?? 3;
  const assistantSummaryChars = options.assistantSummaryChars ?? 500;
  const tokenThreshold = options.tokenThreshold ?? 40000;

  const totalTokens = messages.reduce((sum, m) => sum + estimateTokens(m), 0);
  if (totalTokens <= tokenThreshold) {
    return { compacted: false, estimatedTokens: totalTokens };
  }

  // 找到每个用户消息的位置（作为轮次边界）
  const userIndices: number[] = [];
  for (let i = 0; i < messages.length; i++) {
    if (messages[i].role === "user") {
      userIndices.push(i);
    }
  }

  if (userIndices.length <= keepTurns) {
    return { compacted: false, estimatedTokens: totalTokens };
  }

  // 保留最近 keepTurns 轮的起始位置
  const keepFromIndex = userIndices[userIndices.length - keepTurns];
  let compactedCount = 0;

  // 压缩 keepFromIndex 之前的助手消息
  for (let i = 0; i < keepFromIndex; i++) {
    const msg = messages[i];
    if (msg.role !== "assistant" || !Array.isArray(msg.content)) continue;

    for (const block of msg.content) {
      if (block.type === "text" && typeof block.text === "string" && block.text.length > assistantSummaryChars) {
        // 提取前几行作为摘要（通常是结论性语句）
        const lines = block.text.split("\n");
        let summary = "";
        for (const line of lines) {
          if (summary.length + line.length > assistantSummaryChars) break;
          summary += (summary ? "\n" : "") + line;
        }
        block.text = summary + `\n\n[已压缩，原文 ${block.text.length} 字符]`;
        compactedCount++;
      }
    }
  }

  if (compactedCount > 0) {
    const newTotal = messages.reduce((sum, m) => sum + estimateTokens(m), 0);
    console.log(
      `🗜️  整体对话压缩: 压缩了 ${compactedCount} 条助手消息，` +
      `tokens ${totalTokens} → ${newTotal} (保留最近 ${keepTurns} 轮)`
    );
    return { compacted: true, estimatedTokens: newTotal };
  }

  return { compacted: false, estimatedTokens: totalTokens };
}

/**
 * 获取压缩统计信息
 */
export function getCompactionStats(messages: AgentMessage[]): {
  totalMessages: number;
  toolResultCount: number;
  compactedCount: number;
  totalSize: number;
  compactedSize: number;
} {
  let toolResultCount = 0;
  let compactedCount = 0;
  let totalSize = 0;
  let compactedSize = 0;

  for (const msg of messages) {
    if (msg.role === "toolResult") {
      toolResultCount++;
      for (const content of msg.content) {
        if (content.type === "text") {
          totalSize += content.text.length;
          if (content.text.startsWith("[Compacted:")) {
            compactedCount++;
            compactedSize += content.text.length;
          }
        }
      }
    }
  }

  return {
    totalMessages: messages.length,
    toolResultCount,
    compactedCount,
    totalSize,
    compactedSize,
  };
}
