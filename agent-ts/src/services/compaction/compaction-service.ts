/**
 * Context Compaction - 上下文压缩
 *
 * 1. Micro-compaction: 每轮清空旧的工具调用结果
 * 2. Conversation compaction: 超过 token 阈值时压缩旧轮次对话
 * 3. Compact tool: Agent 可主动触发压缩
 * 4. Pre-compaction memory hook: 压缩前调用 memory provider 的 syncTurn
 */
import type { AgentMessage } from "../../sdk-facade.js";
import { compactionConfig } from "../../config/config.js";
import type { MemoryProvider } from "../memory/port.js";

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
        if (content.type === "text" && (content as any).text.length > minLength) {
          const originalLength = (content as any).text.length;
          (content as any).text = `[Compacted: ${toolName} result (${originalLength} chars)]`;
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
 * 查找安全的分割点：不在 assistant(tool_calls) 与其后续 tool result 之间
 *
 * 规则：split 点不得落在 assistant(tool_calls) 与其后续 toolResult 之间
 * 如果落在中间，向前移动到 assistant 消息之前
 *
 * @param messages - 消息数组
 * @param proposedSplitIndex - 提议的分割位置
 * @returns 安全的分割位置
 */
export function findSafeSplitPoint(
  messages: AgentMessage[],
  proposedSplitIndex: number
): number {
  // 向后扫描，查找是否有未配对的 tool_calls
  const pendingToolCalls = new Set<string>();

  for (let i = 0; i < proposedSplitIndex; i++) {
    const msg = messages[i];

    // 收集 assistant 的 tool_calls
    if (msg.role === "assistant" && Array.isArray(msg.content)) {
      for (const block of msg.content) {
        if (block.type === "toolCall") {
          pendingToolCalls.add(block.id);
        }
      }
    }

    // 移除已配对的 toolResult
    if (msg.role === "toolResult") {
      pendingToolCalls.delete(msg.toolCallId);
    }
  }

  // 如果有未配对的 tool_calls，说明 split 点落在工具对中间
  if (pendingToolCalls.size > 0) {
    // 向前查找最近的完整工具对边界
    for (let i = proposedSplitIndex - 1; i >= 0; i--) {
      const msg = messages[i];

      // 如果遇到 assistant 消息且包含 tool_calls，检查是否是待解决的调用
      if (msg.role === "assistant" && Array.isArray(msg.content)) {
        const hasUnmatchedCall = msg.content.some(
          block => block.type === "toolCall" && pendingToolCalls.has(block.id)
        );

        if (hasUnmatchedCall) {
          // 这是未配对的 tool_calls，返回它之前的位置
          return i;
        }
      }
    }
  }

  return proposedSplitIndex;
}

/**
 * 整体对话压缩：当上下文超过 token 阈值时，将旧轮次压缩为摘要。
 *
 * 策略：
 * - 保留最近 keepTurns 轮完整对话（包括工具调用和结果）
 * - 更早的轮次：保留用户消息原文，助手回复截断至摘要长度
 * - 旧的工具结果交由 microCompact 处理
 * - 确保 split 点不会分割 tool_calls 和其对应的 toolResult
 * - 压缩前调用 memory provider 的 syncTurn（如果提供）
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
    /** Memory provider（可选，用于压缩前同步） */
    memoryProvider?: MemoryProvider;
    /** 会话 ID（用于 memory sync） */
    sessionId?: string;
  } = {}
): { compacted: boolean; estimatedTokens: number } {
  const keepTurns = options.keepTurns ?? 3;
  const assistantSummaryChars = options.assistantSummaryChars ?? 500;
  const tokenThreshold = options.tokenThreshold ?? 40000;

  const totalTokens = messages.reduce((sum, m) => sum + estimateTokens(m), 0);
  if (totalTokens <= tokenThreshold) {
    return { compacted: false, estimatedTokens: totalTokens };
  }

  // 压缩前钩子：调用 memory provider 的 syncTurn
  if (options.memoryProvider && messages.length > 0) {
    try {
      // 提取最近的用户和助手消息用于 syncTurn
      let lastUserContent = '';
      let lastAssistantContent = '';

      for (let i = messages.length - 1; i >= 0; i--) {
        const msg = messages[i];
        if (msg.role === 'user' && !lastUserContent) {
          lastUserContent = typeof (msg as any).content === 'string'
            ? (msg as any).content
            : '';
        }
        if (msg.role === 'assistant' && !lastAssistantContent) {
          const content = (msg as any).content;
          if (Array.isArray(content)) {
            const textBlocks = content
              .filter((block: any) => block.type === 'text')
              .map((block: any) => block.text)
              .join('\n');
            lastAssistantContent = textBlocks;
          }
        }
        if (lastUserContent && lastAssistantContent) break;
      }

      // 仅记录上下文，不写库（写入由 agent 自主用 memory_write）
      if (lastUserContent || lastAssistantContent) {
        options.memoryProvider.syncTurn(
          lastUserContent,
          lastAssistantContent,
          options.sessionId
        ).catch((err: unknown) => {
          console.warn(`⚠️ Pre-compaction memory sync failed: ${err instanceof Error ? err.message : String(err)}`);
        });
      }
    } catch (err) {
      console.warn(`⚠️ Pre-compaction memory sync error: ${err instanceof Error ? err.message : String(err)}`);
    }
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

  // 保留最近 keepTurns 轮的起始位置（提议的 split 点）
  const proposedSplitIndex = userIndices[userIndices.length - keepTurns];

  // 查找安全的 split 点（不会分割工具对）
  const keepFromIndex = findSafeSplitPoint(messages, proposedSplitIndex);

  let compactedCount = 0;

  // 压缩 keepFromIndex 之前的助手消息
  for (let i = 0; i < keepFromIndex; i++) {
    const msg = messages[i];
    if (msg.role !== "assistant" || !Array.isArray(msg.content)) continue;

    for (const block of msg.content) {
      if (block.type === "text" && typeof (block as any).text === "string" && (block as any).text.length > assistantSummaryChars) {
        // 提取前几行作为摘要（通常是结论性语句）
        const lines = (block as any).text.split("\n");
        let summary = "";
        for (const line of lines) {
          if (summary!.length + line.length > assistantSummaryChars) break;
          summary += (summary ? "\n" : "") + line;
        }
        (block as any).text = summary + `\n\n[已压缩，原文 ${(block as any).text.length} 字符]`;
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
          totalSize += (content as any).text.length;
          if ((content as any).text.startsWith("[Compacted:")) {
            compactedCount++;
            compactedSize += (content as any).text.length;
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
