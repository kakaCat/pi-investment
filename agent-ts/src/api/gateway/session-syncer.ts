/**
 * SessionSyncer — session 事件异步同步到 quantsys-v2
 *
 * 原则：本地 events.jsonl 是权威源；同步失败只记日志，永不阻塞消息处理。
 * 幂等：v2 端 UNIQUE(session_key, seq) 去重，重复推送安全。
 * 断点续传：.sync-state.json 记录每个 sessionKey 的 lastSyncedSeq。
 */
import { existsSync, readFileSync, readdirSync, writeFileSync } from "fs";
import { join } from "path";
import { onSessionEvent, readEvents, type StoredSessionEvent } from "./session-events.js";

export interface SessionSyncerOptions {
  apiBase: string;               // 如 http://127.0.0.1:5001
  sessionsRootDir: string;
  stateFile?: string;
  flushIntervalMs?: number;      // 默认 5000
  batchSize?: number;            // 默认 20
  fetchImpl?: typeof fetch;
}

interface QueuedEvent {
  session_key: string;
  seq: number;
  event_type: string;
  payload: Record<string, any>;
  created_at: string;
}

export class SessionSyncer {
  private queue: QueuedEvent[] = [];
  private state: Record<string, number> = {};
  private timer: NodeJS.Timeout | null = null;
  private flushing = false;
  private readonly stateFile: string;
  private readonly flushIntervalMs: number;
  private readonly batchSize: number;
  private readonly fetchImpl: typeof fetch;

  constructor(private options: SessionSyncerOptions) {
    this.stateFile = options.stateFile ?? join(options.sessionsRootDir, ".sync-state.json");
    this.flushIntervalMs = options.flushIntervalMs ?? 5000;
    this.batchSize = options.batchSize ?? 20;
    this.fetchImpl = options.fetchImpl ?? fetch;
    this.loadState();
  }

  start(): void {
    onSessionEvent((sessionKey, event) => this.enqueue(sessionKey, event));
    this.resumeUnsynced();
    this.timer = setInterval(() => { void this.flush(); }, this.flushIntervalMs);
    this.timer.unref?.();
  }

  async stop(): Promise<void> {
    if (this.timer) {
      clearInterval(this.timer);
      this.timer = null;
    }
    await this.flush();
  }

  enqueue(sessionKey: string, event: StoredSessionEvent): void {
    const { seq, timestamp, type, ...payload } = event;
    this.queue.push({
      session_key: sessionKey,
      seq,
      event_type: type,
      payload,
      created_at: timestamp,
    });
  }

  async flush(): Promise<void> {
    if (this.flushing || this.queue.length === 0) return;
    this.flushing = true;
    try {
      const batch = this.queue.slice(0, this.batchSize);
      const resp = await this.fetchImpl(`${this.options.apiBase}/api/sessions/events`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ events: batch }),
      });
      const result = (await resp.json()) as any;
      if (!resp.ok || result?.success === false) {
        throw new Error(result?.error || `HTTP ${resp.status}`);
      }
      // 成功：移出队列并推进断点
      this.queue.splice(0, batch.length);
      for (const e of batch) {
        this.state[e.session_key] = Math.max(this.state[e.session_key] ?? 0, e.seq);
      }
      this.saveState();
    } catch (err) {
      // 失败保留队列，下轮重试（本地数据不丢）
      console.warn(`⚠️ [syncer] 同步失败，${this.queue.length} 条事件待重试:`,
        err instanceof Error ? err.message : err);
    } finally {
      this.flushing = false;
    }
  }

  /** 启动时扫描磁盘，把 lastSyncedSeq 之后的事件重新入队 */
  private resumeUnsynced(): void {
    if (!existsSync(this.options.sessionsRootDir)) return;
    for (const entry of readdirSync(this.options.sessionsRootDir, { withFileTypes: true })) {
      if (!entry.isDirectory() || !entry.name.startsWith("agent:")) continue;
      const lastSynced = this.state[entry.name] ?? 0;
      const events = readEvents(join(this.options.sessionsRootDir, entry.name));
      for (const event of events) {
        if (event.seq > lastSynced) {
          this.enqueue(entry.name, event);
        }
      }
    }
  }

  private loadState(): void {
    try {
      if (existsSync(this.stateFile)) {
        this.state = JSON.parse(readFileSync(this.stateFile, "utf-8"));
      }
    } catch {
      this.state = {};
    }
  }

  private saveState(): void {
    try {
      writeFileSync(this.stateFile, JSON.stringify(this.state, null, 2), "utf-8");
    } catch (err) {
      console.warn(`⚠️ [syncer] 保存 sync state 失败:`, err instanceof Error ? err.message : err);
    }
  }
}
