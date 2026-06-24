/**
 * Session Adapter - SDK Private API Compatibility Layer
 *
 * Purpose:
 * - Encapsulates all access to SDK private APIs (e.g., agent.state, _baseSystemPrompt)
 * - Provides type-safe interfaces for internal session manipulation
 * - Isolates SDK upgrade impact to this single file
 *
 * When SDK upgrades:
 * - Only this file needs to be updated
 * - All consumers remain unchanged
 */

import type { AgentSession } from "@mariozechner/pi-coding-agent";

/**
 * Message content block types
 */
export interface TextBlock {
  type: "text";
  text: string;
}

export interface ImageBlock {
  type: "image";
  source: {
    type: "base64" | "url";
    media_type?: string;
    data?: string;
    url?: string;
  };
}

export type ContentBlock = TextBlock | ImageBlock;

/**
 * Token usage and cost information
 */
export interface CostInfo {
  input: number;
  output: number;
  cacheRead: number;
  cacheWrite: number;
  total: number;
}

export interface UsageInfo {
  input: number;
  output: number;
  cacheRead: number;
  cacheWrite: number;
  totalTokens: number;
  cost: CostInfo;
}

/**
 * Message structure from SDK with proper types
 */
export interface SessionMessage {
  role: "user" | "assistant" | "system";
  content: ContentBlock[] | string;
  usage?: Partial<UsageInfo> & {
    // SDK 可能使用的旧字段名
    input_tokens?: number;
    output_tokens?: number;
    cache_read?: number;
    cache_write?: number;
    total_tokens?: number;
  };
}

/**
 * Agent state structure (private SDK API)
 */
interface AgentState {
  messages: SessionMessage[];
  systemPrompt?: string;
  [key: string]: any;
}

/**
 * Type guard to check if session has agent state
 */
function hasAgentState(session: any): boolean {
  return session?.agent?.state !== undefined;
}

/**
 * Set the system prompt for the session
 * Replaces: (session as any).agent.state.systemPrompt = prompt
 */
export function setSystemPrompt(session: AgentSession | any, prompt: string): void {
  if (hasAgentState(session)) {
    (session as any).agent.state.systemPrompt = prompt;
  } else {
    console.warn("⚠️ Session does not have agent.state, cannot set system prompt");
  }
}

/**
 * Get the current system prompt
 */
export function getSystemPrompt(session: AgentSession | any): string | undefined {
  if (hasAgentState(session)) {
    return (session as any).agent.state.systemPrompt;
  }
  return undefined;
}

/**
 * Add a message to the session's message history
 * Replaces: (session as any).agent.state.messages.push(message)
 */
export function addMessage(session: AgentSession | any, message: SessionMessage): void {
  if (hasAgentState(session)) {
    (session as any).agent.state.messages.push(message);
  } else {
    console.warn("⚠️ Session does not have agent.state, cannot add message");
  }
}

/**
 * Get all messages from the session
 * Replaces: (session as any).agent.state.messages
 */
export function getMessages(session: AgentSession | any): SessionMessage[] {
  if (hasAgentState(session)) {
    return (session as any).agent.state.messages;
  }
  return [];
}

/**
 * Normalize assistant message usage information
 * Handles different naming conventions from various SDK versions
 */
export function normalizeAssistantUsages(session: AgentSession | any): void {
  for (const message of getMessages(session)) {
    if (message?.role !== "assistant") continue;

    const usage = message.usage ?? {};
    const input = usage.input ?? usage.input_tokens ?? 0;
    const output = usage.output ?? usage.output_tokens ?? 0;
    const cacheRead = usage.cacheRead ?? usage.cache_read ?? 0;
    const cacheWrite = usage.cacheWrite ?? usage.cache_write ?? 0;
    const cost = usage.cost ?? {};

    const normalizedUsage: UsageInfo = {
      input,
      output,
      cacheRead,
      cacheWrite,
      totalTokens: usage.totalTokens ?? usage.total_tokens ?? input + output + cacheRead + cacheWrite,
      cost: {
        input: cost.input ?? 0,
        output: cost.output ?? 0,
        cacheRead: cost.cacheRead ?? cost.cache_read ?? 0,
        cacheWrite: cost.cacheWrite ?? cost.cache_write ?? 0,
        total: cost.total ?? 0,
      },
    };

    message.usage = normalizedUsage;
  }
}

/**
 * Get the last message from the session
 */
export function getLastMessage(session: AgentSession | any): SessionMessage | undefined {
  const messages = getMessages(session);
  return messages[messages.length - 1];
}

/**
 * Get the number of messages in the session
 */
export function getMessageCount(session: AgentSession | any): number {
  return getMessages(session).length;
}

/**
 * Get the agent state (for advanced operations like compaction)
 * Replaces: session.agent.state
 */
export function getAgentState(session: AgentSession | any): AgentState | null {
  if (hasAgentState(session)) {
    return (session as any).agent.state;
  }
  return null;
}

/**
 * Get the model from the session
 * Replaces: (session as any).agent.model
 */
export function getModel(session: AgentSession | any): any {
  if (hasAgentState(session)) {
    return (session as any).agent.model;
  }
  return null;
}

/**
 * Check if session has agent state initialized
 */
export function hasState(session: AgentSession | any): boolean {
  return hasAgentState(session);
}

/**
 * Create a user message object
 */
export function createUserMessage(text: string): SessionMessage {
  return {
    role: "user",
    content: [{ type: "text", text }],
  };
}

/**
 * Create an assistant message object
 */
export function createAssistantMessage(text: string): SessionMessage {
  return {
    role: "assistant",
    content: [{ type: "text", text }],
  };
}

/**
 * Extract text content from a message
 */
export function extractTextContent(message: SessionMessage): string {
  // Handle string content (legacy format)
  if (typeof message.content === "string") {
    return message.content.trim();
  }

  // Handle array of content blocks
  if (Array.isArray(message.content)) {
    return message.content
      .filter((block): block is TextBlock => block.type === "text" && typeof (block as any).text === "string")
      .map(block => (block as any).text)
      .join("\n")
      .trim();
  }

  return "";
}
