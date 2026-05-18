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
import { createAgentSession } from "@mariozechner/pi-coding-agent";
import type { AgentSession } from "@mariozechner/pi-coding-agent";
import * as logger from "../logging/observable-logger.js";
import { rewritePromptWithSkill } from "../../services/intelligence/skill-router.js";
import { getExplicitSkillFromPrompt, withForcedSkillScope } from "../tools/skill-guard.js";

export type AgentType = 'main' | 'subagent' | 'plan';

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
          const usage = msg.usage;
          const duration = turnStartTime ? Date.now() - turnStartTime : 0;

          if (agentType === 'main') {
            const llmRunId = logger.logLLMStart('deepseek-chat', 1);
            logger.logLLMEnd(llmRunId, usage, text, duration, thinking);
            logger.logAgentEnd(msg.stopReason || 'stop', usage, text);
            perfMonitor?.endLLMCall?.(undefined, usage, duration);
          } else {
            const llmRunId = logger.logLLMStart('deepseek-chat', 1);
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
        logger.logToolCall(event.toolName, event.toolCallId, event.input);
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
      return await withForcedSkillScope(activeSkill, () => originalPrompt(routed.prompt, options));
    } catch (error) {
      throw error;
    }
  };

  return session;
}

/**
 * 创建带 logger 追踪的 AgentSession（subagent / plan 用）
 */
export async function createTrackedSession(opts: CreateTrackedSessionOptions): Promise<AgentSession> {
  const { agentType, createOptions } = opts;
  const { session } = await createAgentSession(createOptions as any);

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
