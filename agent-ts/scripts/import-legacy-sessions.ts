#!/usr/bin/env node
/**
 * Legacy session 导入：旧 sessions/ 与 wake-sessions/ → agent-sessions/ 新事件模型
 * 用法: npx tsx scripts/import-legacy-sessions.ts
 */
import { existsSync, readFileSync, readdirSync } from "fs";
import { join } from "path";
import { paths } from "../src/config/config.js";
import { emitSessionEvent, initSessionEvents, getAgentSessionsRootDir } from "../src/api/gateway/session-events.js";

function importFeishuSessions(): number {
  const root = join(paths.piDir, "sessions");
  if (!existsSync(root)) return 0;
  let count = 0;

  for (const entry of readdirSync(root, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const logFile = join(root, entry.name, "log.jsonl");
    if (!existsSync(logFile)) continue;

    const sessionKey = `agent:main:feishu:${entry.name.replace(/[^A-Za-z0-9_-]/g, "_")}`;
    emitSessionEvent(sessionKey, { type: "session_start", channel: "feishu", peerId: entry.name, agentId: "main", legacy: true });

    for (const line of readFileSync(logFile, "utf-8").split("\n")) {
      if (!line.trim()) continue;
      try {
        const rec = JSON.parse(line);
        if (rec.role === "user") {
          emitSessionEvent(sessionKey, { type: "user_message", messageId: rec.message_id ?? `legacy-${Date.now()}`, text: rec.content ?? "" });
        } else if (rec.role === "assistant") {
          emitSessionEvent(sessionKey, { type: "assistant_reply", text: rec.content ?? "", replyLength: (rec.content ?? "").length });
        }
      } catch { /* 跳过坏行 */ }
    }
    count++;
  }
  return count;
}

function importWakeSessions(): number {
  const root = join(paths.piDir, "wake-sessions");
  if (!existsSync(root)) return 0;
  let count = 0;

  for (const entry of readdirSync(root, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const logFile = join(root, entry.name, "conversation.log");
    if (!existsSync(logFile)) continue;

    const sessionKey = `agent:main:wake:${entry.name.replace(/[^A-Za-z0-9_-]/g, "_")}`;
    emitSessionEvent(sessionKey, { type: "session_start", channel: "wake", peerId: entry.name, agentId: "main", legacy: true });
    const raw = readFileSync(logFile, "utf-8");
    emitSessionEvent(sessionKey, { type: "legacy_note", note: raw.slice(0, 4000) });
    count++;
  }
  return count;
}

initSessionEvents(join(paths.piDir, "agent-sessions"));
const feishu = importFeishuSessions();
const wake = importWakeSessions();
console.log(`✅ 导入完成: feishu ${feishu} 个会话, wake ${wake} 个会话`);
console.log(`📁 输出目录: ${getAgentSessionsRootDir()}`);
