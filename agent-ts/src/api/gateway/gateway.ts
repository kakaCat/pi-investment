/**
 * AgentGateway — 入站通道的统一汇聚点
 * 所有 adapter 把消息规范化为 InboundEvent 后交给 dispatch
 */
import { ChannelSessionManager, type ChannelAgentSession } from "./channel-session-manager.js";
import { buildSessionKey } from "./session-key.js";
import type { GatewayHandlers, InboundEvent } from "./types.js";
import type { InputSource } from "@mariozechner/pi-coding-agent";

export interface AgentGatewayOptions {
  sessionsRootDir: string;
  createSession: (sessionKey: string, sessionDir: string) => Promise<ChannelAgentSession>;
  beforePrompt?: (session: ChannelAgentSession, sessionKey: string, text: string, sessionDir: string) => Promise<void>;
  extractReply?: (session: ChannelAgentSession, sessionKey: string) => string;
}

export class AgentGateway {
  private manager: ChannelSessionManager;

  constructor(options: AgentGatewayOptions) {
    this.manager = new ChannelSessionManager({
      channelName: "Gateway",
      sessionsRootDir: options.sessionsRootDir,
      createSession: options.createSession,
      beforePrompt: options.beforePrompt,
      extractReply: options.extractReply,
    });
  }

  isDuplicate(messageId: string): boolean {
    return this.manager.isDuplicate(messageId);
  }

  isProcessing(sessionKey: string): boolean {
    return this.manager.isProcessing(sessionKey);
  }

  async dispatch(event: InboundEvent): Promise<string> {
    const sessionKey = buildSessionKey(event.channel, event.peerId);
    // P2-T3 接线：wake 通道是机器事件（v2 推送）→ source=extension → wake-event flow；
    // feishu/cli 是人工消息 → 缺省 interactive（interactive-chat / skill-invocation）。
    const source: InputSource = event.channel === "wake" ? "extension" : "interactive";
    return this.manager.processMessage(sessionKey, event.messageId, event.text, source);
  }

  async abort(sessionKey: string): Promise<boolean> {
    return this.manager.abort(sessionKey);
  }

  /** 提供给 adapter 的处理器集合 */
  handlers(): GatewayHandlers {
    return {
      dispatch: (event) => this.dispatch(event),
      isProcessing: (sessionKey) => this.isProcessing(sessionKey),
      abort: (sessionKey) => this.abort(sessionKey),
    };
  }

  shutdown(): void {
    this.manager.shutdown();
  }
}
