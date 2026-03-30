import { appendFileSync, mkdirSync, writeFileSync } from "fs";
import { join } from "path";

export interface FeishuAgentSession {
  prompt(text: string): Promise<void>;
  abort(): Promise<void>;
  dispose(): void;
  agent?: {
    state?: {
      messages?: Array<{
        role: string;
        content?: Array<{ type: string; text?: string }>;
      }>;
    };
  };
}

export interface FeishuSessionManagerOptions {
  sessionsRootDir: string;
  createSession(chatId: string, sessionDir: string): Promise<FeishuAgentSession>;
  extractReply?: (session: FeishuAgentSession, chatId: string) => string;
  beforePrompt?: (session: FeishuAgentSession, chatId: string, text: string, sessionDir: string) => Promise<void>;
  now?: () => Date;
}

interface QueueItem {
  messageId: string;
  text: string;
  resolve: (reply: string) => void;
  reject: (error: Error) => void;
}

interface ChatSessionState {
  chatId: string;
  session: FeishuAgentSession;
  sessionDir: string;
  logFile: string;
  contextFile: string;
  queue: QueueItem[];
  processing: boolean;
  lastActiveAt: string;
}

function defaultExtractReply(session: FeishuAgentSession): string {
  const messages = session.agent?.state?.messages ?? [];
  const lastAssistant = [...messages].reverse().find((message) => message.role === "assistant");
  if (!lastAssistant?.content) {
    return "";
  }

  return lastAssistant.content
    .filter((block) => block.type === "text" && typeof block.text === "string")
    .map((block) => block.text ?? "")
    .join("\n")
    .trim();
}

export class FeishuSessionManager {
  private sessions = new Map<string, ChatSessionState>();
  private messageIds = new Set<string>();
  private now: () => Date;
  private extractReply: (session: FeishuAgentSession, chatId: string) => string;
  private beforePrompt?: (session: FeishuAgentSession, chatId: string, text: string, sessionDir: string) => Promise<void>;

  constructor(private options: FeishuSessionManagerOptions) {
    this.now = options.now ?? (() => new Date());
    this.extractReply = options.extractReply ?? ((session) => defaultExtractReply(session));
    this.beforePrompt = options.beforePrompt;
  }

  isDuplicate(messageId: string): boolean {
    if (this.messageIds.has(messageId)) {
      console.log(`⚠️ 检测到重复消息: ${messageId}`);
      return true;
    }

    this.messageIds.add(messageId);
    return false;
  }

  isProcessing(chatId: string): boolean {
    return this.sessions.get(chatId)?.processing ?? false;
  }

  async processMessage(chatId: string, messageId: string, text: string): Promise<string> {
    const state = await this.getOrCreateSession(chatId);

    return new Promise((resolve, reject) => {
      state.queue.push({ messageId, text, resolve, reject });
      if (!state.processing) {
        void this.drainQueue(state);
      }
    });
  }

  async abort(chatId: string): Promise<boolean> {
    const state = this.sessions.get(chatId);
    if (!state?.processing) {
      return false;
    }

    const queued = state.queue.splice(0);
    const cancellationError = new Error("Task cancelled");
    for (const item of queued) {
      item.reject(cancellationError);
    }

    try {
      await state.session.abort();
      return true;
    } catch {
      return false;
    }
  }

  shutdown(): void {
    for (const state of this.sessions.values()) {
      state.session.dispose();
    }

    this.sessions.clear();
    this.messageIds.clear();
  }

  private async getOrCreateSession(chatId: string): Promise<ChatSessionState> {
    const existing = this.sessions.get(chatId);
    if (existing) {
      return existing;
    }

    const sessionDir = join(this.options.sessionsRootDir, chatId);
    mkdirSync(sessionDir, { recursive: true });

    const state: ChatSessionState = {
      chatId,
      session: await this.options.createSession(chatId, sessionDir),
      sessionDir,
      logFile: join(sessionDir, "log.jsonl"),
      contextFile: join(sessionDir, "context.json"),
      queue: [],
      processing: false,
      lastActiveAt: this.now().toISOString(),
    };

    this.sessions.set(chatId, state);
    this.writeContext(state);
    return state;
  }

  private async drainQueue(state: ChatSessionState): Promise<void> {
    state.processing = true;

    while (state.queue.length > 0) {
      const item = state.queue.shift()!;

      try {
        const reply = await this.executeItem(state, item);
        item.resolve(reply);
      } catch (error) {
        item.reject(error instanceof Error ? error : new Error(String(error)));
      }
    }

    state.processing = false;
    state.lastActiveAt = this.now().toISOString();
    this.writeContext(state);
  }

  private async executeItem(state: ChatSessionState, item: QueueItem): Promise<string> {
    this.appendLog(state.logFile, {
      role: "user",
      content: item.text,
      message_id: item.messageId,
      timestamp: this.now().toISOString(),
    });

    if (this.beforePrompt) {
      await this.beforePrompt(state.session, state.chatId, item.text, state.sessionDir);
    }

    await state.session.prompt(item.text);

    const reply = this.extractReply(state.session, state.chatId);
    if (reply) {
      this.appendLog(state.logFile, {
        role: "assistant",
        content: reply,
        timestamp: this.now().toISOString(),
      });
    }

    state.lastActiveAt = this.now().toISOString();
    this.writeContext(state);
    return reply;
  }

  private appendLog(file: string, payload: Record<string, string>): void {
    appendFileSync(file, JSON.stringify(payload) + "\n", "utf-8");
  }

  private writeContext(state: ChatSessionState): void {
    writeFileSync(
      state.contextFile,
      JSON.stringify(
        {
          chatId: state.chatId,
          sessionDir: state.sessionDir,
          processing: state.processing,
          queuedMessages: state.queue.length,
          updatedAt: state.lastActiveAt,
        },
        null,
        2
      ),
      "utf-8"
    );
  }
}
