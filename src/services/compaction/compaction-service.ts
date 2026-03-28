/**
 * Context Compaction - 上下文压缩
 *
 * 1. Micro-compaction: 每轮清空旧的工具调用结果
 * 2. Compact tool: Agent 可主动触发压缩
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
