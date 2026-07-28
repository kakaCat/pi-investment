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
 */
import { createAgentSession } from "../../sdk-facade.js";
import type { AgentSession } from "../../sdk-facade.js";
import * as logger from "../logging/observable-logger.js";
import { rewritePromptWithSkill } from "../../services/intelligence/skill-router.js";
import { getActiveModelId } from "../../config/config.js";
import { getExplicitSkillFromPrompt, withForcedSkillScope } from "../tools/skill-guard.js";
import { promptWithDynamicTools } from "../tools/tool-groups.js";

export type AgentType = 'main' | 'subagent' | 'plan';

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
      case 'turn_start':
        turnStartTime = Date.now();
        if (agentType === 'main') {
          logger.logTurnStart();
        }
        break;

      case 'turn_end':
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
    }
  });
}

/**
 * 包装已有 session，注入 logger + 性能监控（主 agent 用）
 * 同时保留 prompt 包装以记录 user.input / agent.start
 */
export function wrapSessionWithLogger(session: AgentSession, perfMonitor?: any): AgentSession {
  attachLogger(session, 'main', perfMonitor);

  const originalPrompt = session.prompt.bind(session);
  session.prompt = async function(userMessage: string, options?: any) {
    logger.logUserInput(userMessage);
    logger.logAgentStart(userMessage);
    perfMonitor?.startLLMCall?.();
    try {
      const routed = rewritePromptWithSkill(userMessage);
      if (routed.forcedSkill) {
        console.log(`🎯 强制技能路由: ${routed.forcedSkill}`);
      }
      const activeSkill = routed.forcedSkill ?? getExplicitSkillFromPrompt(routed.prompt);
      // promptWithDynamicTools：run 前按关键词预加载工具组；
      // run 内模型调用 load_tools 后自动续跑，让新工具进入下一次 run 的快照
      return await withForcedSkillScope(activeSkill, () =>
        promptWithDynamicTools((msg) => originalPrompt(msg, options), routed.prompt));
    } catch (error) {
      throw error;
    }
  };

  return session;
}

/**
 * 创建带 logger 追踪的 AgentSession（subagent / plan 用）
 *
 * agentType='main'（如 gateway 渠道会话）走 wrapSessionWithLogger：
 * 记录 user.input / turn / llm / tool 完整轨迹，并把消息写入 conversation.json，
 * 保证 restart_agent 能恢复渠道会话历史。
 */
export async function createTrackedSession(opts: CreateTrackedSessionOptions): Promise<AgentSession> {
  const { agentType, createOptions } = opts;
  const { session } = await createAgentSession(createOptions as any);

  if (agentType === 'main') {
    return wrapSessionWithLogger(session);
  }

  attachLogger(session, agentType);

  const originalPrompt = session.prompt.bind(session);
  session.prompt = async function(userMessage: string, options?: any) {
    logger.logSubagentStart(agentType as 'subagent' | 'plan', userMessage);
    try {
      const routed = rewritePromptWithSkill(userMessage);
      const activeSkill = routed.forcedSkill ?? getExplicitSkillFromPrompt(routed.prompt);
      return await withForcedSkillScope(activeSkill, () => originalPrompt(routed.prompt, options));
    } catch (error) {
      throw error;
    }
  };

  return session;
}
