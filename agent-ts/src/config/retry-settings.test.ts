import { describe, expect, test } from "@jest/globals";
import { mkdtempSync, rmSync } from "fs";
import { join } from "path";
import { tmpdir } from "os";
import { SettingsManager } from "@mariozechner/pi-coding-agent";

// npm test 的工作目录即 agent-ts 根目录，process.cwd()/.pi/settings.json 即项目 settings
describe("LLM retry project settings", () => {
  test("SDK reads retry policy from agent-ts/.pi/settings.json", () => {
    const tmpAgentDir = mkdtempSync(join(tmpdir(), "pi-agent-dir-"));
    try {
      const sm = SettingsManager.create(process.cwd(), tmpAgentDir);
      expect(sm.getRetrySettings()).toEqual({
        enabled: true,
        maxRetries: 5,
        baseDelayMs: 3000,
      });
    } finally {
      rmSync(tmpAgentDir, { recursive: true, force: true });
    }
  });
});
