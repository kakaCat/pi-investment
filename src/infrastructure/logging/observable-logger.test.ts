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

  test("stores oversized tool results as artifacts instead of embedding them in events", async () => {
    tempDir = mkdtempSync(join(tmpdir(), "pi-invest-logger-large-"));
    process.chdir(tempDir);

    const logger = await import("./observable-logger.js");
    const sessionKey = "20260521020202_abcd5678";
    logger.initSession(sessionKey);

    const largeValue = "x".repeat(220_000);
    logger.logToolResult("quant_cli", "call-large", {
      content: [{ type: "text", text: largeValue }],
      details: { largeValue },
    });

    const eventsFile = join(tempDir, ".pi-invest", "sessions", sessionKey, "events.jsonl");
    const events = readFileSync(eventsFile, "utf-8").trim().split("\n").map((line) => JSON.parse(line));
    const resultEvent = events.find((event) => event.event === "tool.result");

    expect(JSON.stringify(resultEvent).length).toBeLessThan(20_000);
    expect(resultEvent.result.stored).toBe(true);
    expect(resultEvent.result.filePath).toContain(join(tempDir, ".pi-invest", "sessions", sessionKey, "tool-results"));
    expect(readFileSync(resultEvent.result.filePath, "utf-8")).toContain(largeValue);
  });
});
