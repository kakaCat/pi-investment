/**
 * Session 结构化事件流 — agent 工作质量审计的核心数据
 *
 * 本地 events.jsonl 是权威源；监听器（SessionSyncer）异步同步到 v2。
 */
import { appendFileSync, existsSync, mkdirSync, readFileSync } from "fs";
import { homedir } from "os";
import { join } from "path";

export type SessionEvent =
  | { type: 'session_start'; channel: string; peerId: string; agentId: string; legacy?: boolean }
  | { type: 'user_message'; messageId: string; text: string; event?: string; data?: Record<string, any> }
  | { type: 'tool_call'; toolName: string; params?: Record<string, any>; durationMs: number; success: boolean; error?: string; resultSummary?: string }
  | { type: 'assistant_reply'; text: string; replyLength: number }
  | { type: 'error'; stage: string; message: string }
  | { type: 'session_idle'; reason: string }
  | { type: 'legacy_note'; note: string };

export interface StoredSessionEvent {
  seq: number;
  timestamp: string;
  type: string;
  [key: string]: any;
}

type EventListener = (sessionKey: string, event: StoredSessionEvent) => void;

let _sessionsRootDir: string | null = null;
const _seqCounters = new Map<string, number>();
const _listeners: EventListener[] = [];

/** 测试用：重置内存状态并覆盖根目录 */
export function resetSessionEventState(rootDir?: string): void {
  _seqCounters.clear();
  _listeners.length = 0;
  _sessionsRootDir = rootDir ?? null;
  setSessionContext(null);
}

/** 启动引导时注入会话根目录（如 paths.piDir/agent-sessions） */
export function initSessionEvents(rootDir: string): void {
  _sessionsRootDir = rootDir;
}

export function getAgentSessionsRootDir(): string {
  return _sessionsRootDir ?? join(homedir(), ".pi-invest", "agent-sessions");
}

export function sessionDirOf(sessionKey: string): string {
  return join(getAgentSessionsRootDir(), sessionKey);
}

/** 追加事件到 events.jsonl，并通知监听器。写盘失败只告警不抛错（不阻塞主链路） */
export function emitSessionEvent(sessionKey: string, event: SessionEvent): void {
  const seq = (_seqCounters.get(sessionKey) ?? 0) + 1;
  _seqCounters.set(sessionKey, seq);

  const stored: StoredSessionEvent = {
    ...event,
    seq,
    timestamp: new Date().toISOString(),
  };

  try {
    const dir = sessionDirOf(sessionKey);
    if (!existsSync(dir)) mkdirSync(dir, { recursive: true });
    appendFileSync(join(dir, "events.jsonl"), JSON.stringify(stored) + "\n", "utf-8");
  } catch (err) {
    console.warn(`⚠️ [session-events] 写入 events.jsonl 失败:`, err instanceof Error ? err.message : err);
  }

  for (const listener of _listeners) {
    try {
      listener(sessionKey, stored);
    } catch (err) {
      console.warn(`⚠️ [session-events] 监听器异常:`, err instanceof Error ? err.message : err);
    }
  }
}

export function onSessionEvent(listener: EventListener): void {
  _listeners.push(listener);
}

/** 读取会话目录下的事件流 */
export function readEvents(sessionDir: string): StoredSessionEvent[] {
  const file = join(sessionDir, "events.jsonl");
  if (!existsSync(file)) return [];
  return readFileSync(file, "utf-8")
    .split("\n")
    .filter((line) => line.trim())
    .map((line) => JSON.parse(line) as StoredSessionEvent);
}

// ─── 当前会话上下文（工具层感知所属会话）───
let _context: { sessionKey: string; sessionDir: string } | null = null;

export function setSessionContext(sessionKey: string | null, sessionDir?: string): void {
  _context = sessionKey ? { sessionKey, sessionDir: sessionDir ?? sessionDirOf(sessionKey) } : null;
}

export function getSessionContext(): { sessionKey: string; sessionDir: string } | null {
  return _context;
}
