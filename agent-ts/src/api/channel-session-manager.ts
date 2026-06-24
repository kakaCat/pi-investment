/**
 * Channel Session Manager - 通用的渠道会话管理器
 *
 * 用于管理不同渠道（飞书、Wake API、CLI等）的 Agent Session
 * 每个渠道可以有多个独立的会话，每个会话维护自己的上下文和消息队列
 */
import { appendFileSync, mkdirSync, writeFileSync } from "fs";
import { join } from "path";

export interface ChannelAgentSession {
  prompt(text: string): Promise<void>;
  abort(): Promise<void>;
  dispose(): void;
  agent?: {
    state?: {
      messages?: Array<{
        role: string;
        content?: Array<{ type: string; text?: string }> | string;
      }>;
    };
  };
}

export interface ChannelSessionManagerOptions {
  channelName: string;
  sessionsRootDir: string;
  createSession(sessionId: string, sessionDir: string): Promise<ChannelAgentSession>;
  extractReply?: (session: ChannelAgentSession, sessionId: string) => string;
  beforePrompt?: (session: ChannelAgentSession, sessionId: string, text: string, sessionDir: string) => Promise<void>;
  now?: () => Date;
}

interface QueueItem {
  messageId: string;
  text: string;
  resolve: (reply: string) => void;
  reject: (error: Error) => void;
}

interface SessionState {
  sessionId: string;
  session: ChannelAgentSession;
  sessionDir: string;
  logFile: string;
  contextFile: string;
  queue: QueueItem[];
  processing: boolean;
  lastActiveAt: string;
}

function defaultExtractReply(session: ChannelAgentSession): string {
  const messages = session.agent?.state?.messages ?? [];
  const lastAssistant = [...messages].reverse().find((message) => message.role === "assistant");
  if (!lastAssistant?.content) {
    return "";
  }

  if (typeof lastAssistant.content === 'string') {
    return lastAssistant.content.trim();
  }

  return lastAssistant.content
    .filter((block) => block.type === "text" && typeof (block as any).text === "string")
    .map((block) => (block as any).text ?? "")
    .join("\n")
    .trim();
}

/**
 * 通用渠道会话管理器
 *
 * 职责：
 * 1. 管理多个独立的 Agent Session（按 sessionId 隔离）
 * 2. 为每个 session 维护消息队列，确保顺序处理
 * 3. 记录消息历史和会话日志
 * 4. 支持消息去重和会话中断
 */
export class ChannelSessionManager {
  private sessions = new Map<string, SessionState>();
  private messageIds = new Set<string>();
  private now: () => Date;
  private extractReply: (session: ChannelAgentSession, sessionId: string) => string;
  private beforePrompt?: (session: ChannelAgentSession, sessionId: string, text: string, sessionDir: string) => Promise<void>;

  constructor(private options: ChannelSessionManagerOptions) {
    this.now = options.now ?? (() => new Date());
    this.extractReply = options.extractReply ?? ((session) => defaultExtractReply(session));
    this.beforePrompt = options.beforePrompt;
  }

  isDuplicate(messageId: string): boolean {
    if (this.messageIds.has(messageId)) {
      console.log(`⚠️ [${this.options.channelName}] 检测到重复消息: ${messageId}`);
      return true;
    }

    this.messageIds.add(messageId);
    return false;
  }

  isProcessing(sessionId: string): boolean {
    return this.sessions.get(sessionId)?.processing ?? false;
  }

  async processMessage(sessionId: string, messageId: string, text: string): Promise<string> {
    const state = await this.getOrCreateSession(sessionId);

    return new Promise((resolve, reject) => {
      state.queue.push({ messageId, text, resolve, reject });
      if (!state.processing) {
        void this.drainQueue(state);
      }
    });
  }

  async abort(sessionId: string): Promise<boolean> {
    const state = this.sessions.get(sessionId);
    if (!state?.processing) {
      return false;
    }

    try {
      await state.session.abort();
      state.queue.length = 0;
      state.processing = false;
      return true;
    } catch (error) {
      console.error(`❌ [${this.options.channelName}] 中断会话失败:`, error);
      return false;
    }
  }

  private async getOrCreateSession(sessionId: string): Promise<SessionState> {
    let state = this.sessions.get(sessionId);
    if (state) {
      state.lastActiveAt = this.now().toISOString();
      return state;
    }

    const sessionDir = join(this.options.sessionsRootDir, sessionId);
    mkdirSync(sessionDir, { recursive: true });

    const logFile = join(sessionDir, "conversation.log");
    const contextFile = join(sessionDir, "context.json");

    const session = await this.options.createSession(sessionId, sessionDir);

    state = {
      sessionId,
      session,
      sessionDir,
      logFile,
      contextFile,
      queue: [],
      processing: false,
      lastActiveAt: this.now().toISOString(),
    };

    this.sessions.set(sessionId, state);
    this.logConversation(state, `[Session Created] ${this.now().toISOString()}\n`);

    return state;
  }

  private async drainQueue(state: SessionState): Promise<void> {
    if (state.processing || state.queue.length === 0) {
      return;
    }

    state.processing = true;

    while (state.queue.length > 0) {
      const item = state.queue.shift()!;

      try {
        this.logConversation(state, `\n[User ${this.now().toISOString()}] ${item.text}\n`);

        if (this.beforePrompt) {
          await this.beforePrompt(state.session, state.sessionId, item.text, state.sessionDir);
        }

        await state.session.prompt(item.text);

        const reply = this.extractReply(state.session, state.sessionId);
        this.logConversation(state, `\n[Agent ${this.now().toISOString()}] ${reply}\n`);

        item.resolve(reply);
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        console.error(`❌ [${this.options.channelName}] 消息处理失败:`, errorMessage);
        this.logConversation(state, `\n[Error ${this.now().toISOString()}] ${errorMessage}\n`);
        item.reject(error instanceof Error ? error : new Error(errorMessage));
      }
    }

    state.processing = false;
    state.lastActiveAt = this.now().toISOString();

    this.saveContext(state);
  }

  private logConversation(state: SessionState, content: string): void {
    try {
      appendFileSync(state.logFile, content, "utf-8");
    } catch (error) {
      console.error(`❌ [${this.options.channelName}] 写入日志失败:`, error);
    }
  }

  private saveContext(state: SessionState): void {
    try {
      const context = {
        sessionId: state.sessionId,
        lastActiveAt: state.lastActiveAt,
        queueLength: state.queue.length,
        processing: state.processing,
      };
      writeFileSync(state.contextFile, JSON.stringify(context, null, 2), "utf-8");
    } catch (error) {
      console.error(`❌ [${this.options.channelName}] 保存上下文失败:`, error);
    }
  }

  /**
   * 清理空闲会话（可选，用于资源管理）
   */
  async cleanupIdleSessions(maxIdleMs: number = 30 * 60 * 1000): Promise<void> {
    const now = this.now().getTime();
    const toRemove: string[] = [];

    for (const [sessionId, state] of this.sessions) {
      const lastActive = new Date(state.lastActiveAt).getTime();
      if (now - lastActive > maxIdleMs && !state.processing && state.queue.length === 0) {
        toRemove.push(sessionId);
      }
    }

    for (const sessionId of toRemove) {
      const state = this.sessions.get(sessionId);
      if (state) {
        try {
          state.session.dispose();
          this.sessions.delete(sessionId);
          console.log(`🧹 [${this.options.channelName}] 清理空闲会话: ${sessionId}`);
        } catch (error) {
          console.error(`❌ [${this.options.channelName}] 清理会话失败:`, error);
        }
      }
    }
  }
}
