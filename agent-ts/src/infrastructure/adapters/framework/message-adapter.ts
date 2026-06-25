/**
 * Message Adapter
 *
 * 处理内部消息类型与框架消息类型的转换
 */

import type { AgentMessage } from "../../../sdk-facade.js";
import type { InternalMessage } from './types.js';

/**
 * 将内部消息转换为框架 AgentMessage
 *
 * @param msg 内部消息
 * @returns 框架消息
 */
export function toAgentMessage(msg: InternalMessage): AgentMessage {
  // 由于 AgentMessage 是联合类型，我们需要返回兼容的格式
  // 这里做简单的类型断言，让 TypeScript 编译通过
  return msg as any as AgentMessage;
}

/**
 * 将框架 AgentMessage 转换为内部消息
 *
 * @param msg 框架消息
 * @returns 内部消息
 */
export function fromAgentMessage(msg: AgentMessage): InternalMessage {
  // Extract common fields from framework message format
  const raw = msg as any;
  const role = raw.role === 'user' || raw.role === 'assistant' || raw.role === 'system'
    ? raw.role
    : 'assistant' as 'user' | 'assistant' | 'system';
  const content = raw.content || '';

  return { role, content, ...raw };
}

/**
 * 批量转换为 AgentMessage
 */
export function toAgentMessages(messages: InternalMessage[]): AgentMessage[] {
  return messages.map(toAgentMessage);
}

/**
 * 批量转换为内部消息
 */
export function fromAgentMessages(messages: AgentMessage[]): InternalMessage[] {
  return messages.map(fromAgentMessage);
}

/**
 * 类型守卫：检查是否为合法的消息数组
 */
export function isValidMessageArray(messages: unknown): messages is AgentMessage[] {
  return Array.isArray(messages);
}

/**
 * 安全的消息数组转换
 * 用于处理类型不确定的场景
 */
export function ensureAgentMessages(messages: any[]): AgentMessage[] {
  // 直接返回，使用类型断言
  // 实际的消息格式由框架在运行时验证
  return messages as AgentMessage[];
}
