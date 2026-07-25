/**
 * 飞书消息规范化（纯函数，无外部依赖，便于测试）
 */
import type { InboundEvent } from "../types.js";

/** 飞书消息 → InboundEvent（不可规范化的返回 null） */
export function normalizeFeishuMessage(message: any): InboundEvent | null {
  if (!message || message.message_type !== "text") return null;
  const text = parseTextMessage(message.content);
  if (!text || !message.chat_id) return null;
  return {
    channel: "feishu",
    peerId: message.chat_id,
    messageId: message.message_id,
    text,
  };
}

export function parseTextMessage(content: string): string | null {
  try {
    const parsed = JSON.parse(content);
    return typeof parsed.text === "string" ? parsed.text.trim() || null : null;
  } catch {
    return null;
  }
}
