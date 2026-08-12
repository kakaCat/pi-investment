/**
 * Session Factory - 带 logger 的 AgentSession 工厂
 *
 * 使用 session.subscribe() 监听 SDK 原生事件，而不是包装 prompt 方法。
 * 这样能可靠捕获所有 LLM 调用、工具调用，无论调用路径如何。
 *
 * SDK 事件类型:
 * - agent_start / agent_end
 * - turn_start / turn_end
 * - message_start / message_end (role: user | assistant | toolResult)
 * - tool_execution_start / tool_execution_end
 * - auto_retry_start / auto_retry_end (SDK 内置 LLM 错误重试)
 *
 * T3b 接线: prompt 包装层捕获溢出错误，触发压缩后重试一次。
 */
import { createAgentSession, resetToolExecutionCounters, incrementTurnCount, estimateTokens } from "../../sdk-facade.js";
import type { AgentSession } from "../../sdk-facade.js";
import type { PromptOptions } from "@mariozechner/pi-coding-agent";
import * as logger from "../logging/observable-logger.js";
import { rewritePromptWithSkill } from "../../services/intelligence/skill-router.js";
import { getActiveModelId } from "../../config/config.js";
import { getExplicitSkillFromPrompt, withForcedSkillScope } from "../tools/skill-guard.js";
import { isOverflowError, formatOverflowError } from "../../services/compaction/overflow-patterns.js";
import { compactConversationHistory } from "../../services/compaction/compaction-service.js";
import { getMessages } from "../../core/agent/session-adapter.js";

export type AgentType = 'main' | 'subagent' | 'plan';

/**
 * 扩展 SDK PromptOptions：skipSkillRouting=true 时跳过技能路由与 skill-guard 作用域。
 * 用于调度任务/系统事件等机器消息——它们自带完整工作流 prompt，
 * 强制注入 skill 会让 agent 把 skill 正文误当成第二个用户请求。
 */
export type PromptOptionsWithRouting = PromptOptions & { skipSkillRouting?: boolean };

export function normalizeUsage(usage: any): any {
  if (!usage) {
    return {
      input: 0,
      output: 0,
      cacheRead: 0,
      cacheWrite: 0,
      totalTokens: 0,
      cost: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, total: 0 },
    };
  }

  const input = (usage as any).input ?? (usage as any).input_tokens ?? 0;
  const output = (usage as any).output ?? (usage as any).output_tokens ?? 0;
  const cacheRead = (usage as any).cacheRead ?? (usage as any).cache_read ?? 0;
  const cacheWrite = (usage as any).cacheWrite ?? (usage as any).cache_write ?? 0;
  const totalTokens = usage.totalTokens ?? usage.total_tokens ?? input + output + cacheRead + cacheWrite;
  const cost = usage.cost ?? {};

  return {
    ...usage,
    input,
    output,
    cacheRead,
    cacheWrite,
    totalTokens,
    cost: {
      input: cost.input ?? 0,
      output: cost.output ?? 0,
      cacheRead: cost.cacheRead ?? cost.cache_read ?? 0,
      cacheWrite: cost.cacheWrite ?? cost.cache_write ?? 0,
      total: cost.total ?? 0,
    },
  };
}

function extractTextContent(content: unknown): string {
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) return content.map((c: any) => c?.text ?? '').join('');
  return String(content);
}

export interface CreateTrackedSessionOptions {
  agentType: AgentType;
  createOptions: any;
}

/**
 * 给 session 注入 logger 订阅，监听 SDK 原生事件
 */
export function attachLogger(session: AgentSession, agentType: AgentType, perfMonitor?: any): void {
  const startTimes = new Map<string, number>(); // tool_call_id -> start time
  const toolNames = new Map<string, string>(); // tool_call_id -> tool_name
  let turnStartTime = 0;

  session.subscribe((event: any) => {
    switch (event.type) {
      case 'agent_start':
        // 重置全局计数器
        resetToolExecutionCounters();
        break;

      case 'turn_start':
        turnStartTime = Date.now();
        if (agentType === 'main') {
          logger.logTurnStart();
        }
        break;

      case 'turn_end':
        // 递增全局 turn 计数
        incrementTurnCount();
        if (agentType === 'main') {
          logger.logTurnEnd();
        }
        break;

      case 'message_end': {
        const msg = event.message;
        if (!msg) break;

        if (msg.role === 'assistant') {
          const text = msg.content?.find((c: any) => c.type === 'text')?.text || '';
          const thinking = msg.content?.find((c: any) => c.type === 'thinking')?.thinking || '';
          const usage = normalizeUsage(msg.usage);
          msg.usage = usage;
          const duration = turnStartTime ? Date.now() - turnStartTime : 0;

          if (agentType === 'main') {
            const llmRunId = logger.logLLMStart(getActiveModelId(), 1);
            logger.logLLMEnd(llmRunId, usage, text, duration, thinking);
            logger.logAgentEnd(msg.stopReason || 'stop', usage, text);
            perfMonitor?.endLLMCall?.(undefined, usage, duration);
          } else {
            const llmRunId = logger.logLLMStart(getActiveModelId(), 1);
            logger.logLLMEnd(llmRunId, usage, text, duration, thinking);
          }
        }

        if (msg.role === 'toolResult') {
          const toolName = toolNames.get(msg.toolCallId) || msg.toolName || msg.toolCallId;
          const startTime = startTimes.get(msg.toolCallId);
          const duration = startTime ? Date.now() - startTime : undefined;

          const errorFromContent = msg.isError ? new Error(extractTextContent(msg.content)) : undefined;

          if (agentType === 'main') {
            logger.logToolResult(toolName, msg.toolCallId, msg.content, errorFromContent, duration);
            perfMonitor?.endToolCall?.(msg.toolCallId, toolName, !msg.isError);
          } else {
            logger.logToolResult(toolName, msg.toolCallId, msg.content, errorFromContent, duration);
          }

          startTimes.delete(msg.toolCallId);
          toolNames.delete(msg.toolCallId);
        }
        break;
      }

      case 'tool_execution_start': {
        startTimes.set(event.toolCallId, Date.now());
        toolNames.set(event.toolCallId, event.toolName);

        // Try multiple sources for input params (SDK may use different field names)
        const toolInput = event.input || event.toolInput || event.params;
        logger.logToolCall(event.toolName, event.toolCallId, toolInput);

        // Debug logging for bash commands to help diagnose failures
        if (event.toolName === 'bash' && toolInput) {
          const cmd = toolInput.command || toolInput.cmd;
          if (cmd) {
            const preview = typeof cmd === 'string' ? cmd.substring(0, 150) : JSON.stringify(cmd).substring(0, 150);
            console.log(`🐚 Bash command: ${preview}${cmd.length > 150 ? '...' : ''}`);
          }
        }

        if (agentType === 'main') {
          perfMonitor?.startToolCall?.(event.toolName);
        }
        break;
      }

      case 'agent_start':
        // 重置全局计数器
        resetToolExecutionCounters();
        if (agentType !== 'main') {
          // subagent/plan 用 logSubagentStart 记录
        }
        break;

      case 'agent_end':
        if (agentType !== 'main') {
          const msgs = event.messages || [];
          const lastAssistant = [...msgs].reverse().find((m: any) => m.role === 'assistant');
          const text = lastAssistant?.content?.find((c: any) => c.type === 'text')?.text || '';
          const llmCalls = msgs.filter((m: any) => m.role === 'assistant').length;
          const toolCalls = msgs.filter((m: any) => m.role === 'toolResult').length;
          const duration = turnStartTime ? Date.now() - turnStartTime : 0;
          logger.logSubagentEnd(agentType as 'subagent' | 'plan', text, llmCalls, toolCalls, duration);
        }
        break;

      case 'auto_retry_start': {
        const delaySec = Math.round((event.delayMs ?? 0) / 1000);
        console.log(`🔄 LLM 连接中断，${delaySec}s 后重试 (${event.attempt}/${event.maxAttempts}): ${event.errorMessage}`);
        logger.logLLMRetry({
          phase: 'start',
          attempt: event.attempt,
          maxAttempts: event.maxAttempts,
          delayMs: event.delayMs,
          errorMessage: event.errorMessage,
        });
        break;
      }

      case 'auto_retry_end': {
        if (event.success) {
          console.log(`✅ LLM 重试成功（第 ${event.attempt} 次）`);
        } else {
          console.error(`❌ LLM 重试耗尽（${event.attempt} 次）: ${event.finalError ?? 'unknown'}`);
        }
        logger.logLLMRetry({
          phase: 'end',
          attempt: event.attempt,
          success: event.success,
          finalError: event.finalError,
        });
        break;
      }
    }
  });
}

/**
 * 包装已有 session，注入 logger + 性能监控（主 agent 用）
 * 同时保留 prompt 包装以记录 user.input / agent.start
 * T3b: 溢出错误捕获 + 压缩重试
 */
export function wrapSessionWithLogger(session: AgentSession, perfMonitor?: any): AgentSession {
  attachLogger(session, 'main', perfMonitor);

  const originalPrompt = session.prompt.bind(session);
  session.prompt = async function(userMessage: string, options?: PromptOptionsWithRouting) {
    logger.logUserInput(userMessage);
    logger.logAgentStart(userMessage);
    perfMonitor?.startLLMCall?.();

    // W1.4: 记忆召回注入——按用户消息 prefetch top-3，以附注形式注入（不进系统提示词，保住 prompt cache 前缀）
    // 失败静默降级为空，绝不阻塞对话。
    let messageToSend = userMessage;
    try {
      const { getMemoryProvider } = await import('../../services/memory/index.js');
      const provider = getMemoryProvider();
      const recalled = await provider.prefetch(userMessage.slice(0, 500), undefined, 3, 2000);
      if (recalled && recalled.trim()) {
        messageToSend = `${userMessage}\n\n<recalled_memory source="auto-prefetch">\n${recalled}\n</recalled_memory>`;
      }
    } catch {
      // provider 未初始化或检索失败——静默跳过
    }

    // T3b 接线：溢出错误触发压缩重试（仅一次）
    let overflowRetryUsed = false;

    const executePrompt = async (msg: string, opts?: PromptOptionsWithRouting) => {
      // skipSkillRouting：调度任务/系统事件等机器消息跳过技能路由——
      // 它们自带完整工作流 prompt，强制注入 skill 会让 agent 把 skill 正文
      // 误当成第二个用户请求（2026-08-12 审计：早盘/盘中/复盘三个任务在
      // gateway 路径下全部被误路由到 portfolio-entry）。
      if (opts?.skipSkillRouting) {
        return await originalPrompt(msg, opts);
      }
      const routed = rewritePromptWithSkill(msg);
      if (routed.forcedSkill) {
        console.log(`🎯 强制技能路由: ${routed.forcedSkill}`);
      }
      const activeSkill = routed.forcedSkill ?? getExplicitSkillFromPrompt(routed.prompt);
      return await withForcedSkillScope(activeSkill, () => originalPrompt(routed.prompt, opts));
    };

    try {
      return await executePrompt(messageToSend, options);
    } catch (error) {
      // T3b: 检测溢出错误，触发压缩后重试一次
      if (!overflowRetryUsed && isOverflowError(error)) {
        console.log(formatOverflowError(error, 1));
        overflowRetryUsed = true;

        try {
          const messages = getMessages(session as any);
          const result = compactConversationHistory(
            messages as any,
            (m: unknown) => estimateTokens(m as any),
            {
              keepTurns: 3,
              tokenThreshold: 0, // 立即压缩，不检查阈值
            }
          );

          if (result.compacted) {
            console.log('🗜️  上下文已压缩，重试 prompt');
            return await executePrompt(messageToSend, options);
          } else {
            console.warn('⚠️ 压缩未生效（可能已是最小状态），无法重试');
          }
        } catch (compactErr) {
          console.warn(`⚠️ 压缩失败: ${compactErr instanceof Error ? compactErr.message : String(compactErr)}`);
        }
      }
      throw error;
    }
  };

  return session;
}

/**
 * 创建带 logger 追踪的 AgentSession（subagent / plan 用）
 * T3b: 溢出错误捕获 + 压缩重试
 */
export async function createTrackedSession(opts: CreateTrackedSessionOptions): Promise<AgentSession> {
  const { agentType, createOptions } = opts;
  const { session } = await createAgentSession(createOptions as any);

  attachLogger(session, agentType);

  const originalPrompt = session.prompt.bind(session);
  session.prompt = async function(userMessage: string, options?: any) {
    logger.logSubagentStart(agentType as 'subagent' | 'plan', userMessage);

    // T3b 接线：溢出错误触发压缩重试（仅一次）
    let overflowRetryUsed = false;

    const executePrompt = async (msg: string, opts?: any) => {
      const routed = rewritePromptWithSkill(msg);
      const activeSkill = routed.forcedSkill ?? getExplicitSkillFromPrompt(routed.prompt);
      return await withForcedSkillScope(activeSkill, () => originalPrompt(routed.prompt, opts));
    };

    try {
      return await executePrompt(userMessage, options);
    } catch (error) {
      // T3b: 检测溢出错误，触发压缩后重试一次
      if (!overflowRetryUsed && isOverflowError(error)) {
        console.log(formatOverflowError(error, 1));
        overflowRetryUsed = true;

        try {
          const messages = getMessages(session as any);
          const result = compactConversationHistory(
            messages as any,
            (m: unknown) => estimateTokens(m as any),
            {
              keepTurns: 3,
              tokenThreshold: 0, // 立即压缩，不检查阈值
            }
          );

          if (result.compacted) {
            console.log('🗜️  上下文已压缩，重试 prompt');
            return await executePrompt(userMessage, options);
          } else {
            console.warn('⚠️ 压缩未生效（可能已是最小状态），无法重试');
          }
        } catch (compactErr) {
          console.warn(`⚠️ 压缩失败: ${compactErr instanceof Error ? compactErr.message : String(compactErr)}`);
        }
      }
      throw error;
    }
  };

  return session;
}
