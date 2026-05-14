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
 * Message structure from SDK (using any to avoid type conflicts)
 */
export type SessionMessage = any;

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
  return message.content
    .filter((block: any) => block.type === "text" && typeof block.text === "string")
    .map((block: any) => block.text ?? "")
    .join("\n")
    .trim();
}
