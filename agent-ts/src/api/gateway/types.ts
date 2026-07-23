/**
 * Gateway 核心类型：统一入站信封与通道适配器接口
 * 参考 OpenClaw: channel adapter 只做"翻译+传输"，agent 逻辑对传输层无感
 */
import type { ChannelName } from "./session-key.js";

export interface InboundEvent {
  channel: ChannelName;
  peerId: string;               // feishu: chatId; wake: session_id || 'default'
  messageId: string;            // 去重键
  text: string;                 // 已规范化的 prompt 文本
  event?: string;               // wake 事件类型（market_alert 等）
  data?: Record<string, any>;   // 原始载荷（审计用）
}

export interface GatewayHandlers {
  dispatch(event: InboundEvent): Promise<string>;
  isProcessing(sessionKey: string): boolean;
  abort(sessionKey: string): Promise<boolean>;
}

export interface ChannelAdapter {
  readonly name: string;
  start(handlers: GatewayHandlers): void;
  shutdown(): void;
}
