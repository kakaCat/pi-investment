import { afterEach, describe, expect, jest, test } from "@jest/globals";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "fs";
import { join } from "path";
import { tmpdir } from "os";

const originalCwd = process.cwd();
let tempDir: string | null = null;

afterEach(() => {
  process.chdir(originalCwd);
  jest.resetModules();
  if (tempDir) {
    rmSync(tempDir, { recursive: true, force: true });
    tempDir = null;
  }
});

describe("observable logger session resume", () => {
  test("does not overwrite existing conversation and metadata when resuming a session key", async () => {
    tempDir = mkdtempSync(join(tmpdir(), "pi-invest-logger-"));
    process.chdir(tempDir);

    const sessionKey = "20260521010101_abcd1234";
    const sessionDir = join(tempDir, ".pi-invest", "sessions", sessionKey);
    const conversationFile = join(sessionDir, "conversation.json");
    const metadataFile = join(sessionDir, "metadata.json");

    await import("fs").then(({ mkdirSync }) => mkdirSync(sessionDir, { recursive: true }));
    writeFileSync(conversationFile, JSON.stringify({ session_key: sessionKey, messages: [{ role: "user", content: "kept" }] }));
    writeFileSync(metadataFile, JSON.stringify({ session_key: sessionKey, total_messages: 1 }));

    const logger = await import("./observable-logger.js");
    logger.initSession(sessionKey);

    expect(JSON.parse(readFileSync(conversationFile, "utf-8")).messages).toHaveLength(1);
    expect(JSON.parse(readFileSync(metadataFile, "utf-8")).total_messages).toBe(1);

    logger.logUserInput("new message");

    const resumedConversation = JSON.parse(readFileSync(conversationFile, "utf-8"));
    expect(resumedConversation.messages.map((m: { content: string }) => m.content)).toEqual([
      "kept",
      "new message",
    ]);
  });
});
