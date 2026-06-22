import { describe, expect, test } from "@jest/globals";
import { mkdtempSync, readFileSync, rmSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import { formatMaybeLargeJsonToolOutput, formatMaybeLargeToolOutput } from "./large-tool-output.js";
import { setSessionDataDir } from "./session-utils.js";

describe("large tool output formatter", () => {
  test("returns small output inline", () => {
    const result = formatMaybeLargeToolOutput("small", {
      label: "测试工具",
      filePrefix: "test-tool",
      maxInlineChars: 10,
    });

    expect(result.stored).toBe(false);
    expect(result.filePath).toBeUndefined();
    expect(result.text).toBe("small");
  });

  test("stores large output under the current session data directory", () => {
    const dir = mkdtempSync(join(tmpdir(), "pi-large-output-"));
    setSessionDataDir(dir);

    try {
      const result = formatMaybeLargeToolOutput("x".repeat(50), {
        label: "测试工具",
        filePrefix: "test/tool output",
        maxInlineChars: 10,
        previewChars: 8,
        metadata: { command: "demo.run" },
      });

      expect(result.stored).toBe(true);
      expect(result.filePath).toContain(join(dir, "tool-results"));
      expect(result.filePath).toMatch(/test-tool-output-\d+\.txt$/);
      expect(result.text).toContain("完整结果已保存到");
      expect(result.text).toContain("- command: demo.run");
      expect(result.text).toContain("内容预览 (前8字符)");
      expect(result.text).toContain("使用 read 工具查看完整内容");
      expect(readFileSync(result.filePath!, "utf-8")).toBe("x".repeat(50));
    } finally {
      rmSync(dir, { recursive: true, force: true });
      setSessionDataDir("/tmp");
    }
  });

  test("stores JSON output with json extension", () => {
    const dir = mkdtempSync(join(tmpdir(), "pi-large-json-output-"));
    setSessionDataDir(dir);

    try {
      const result = formatMaybeLargeJsonToolOutput({ data: "x".repeat(50) }, {
        label: "JSON工具",
        filePrefix: "json-tool",
        maxInlineChars: 10,
      });

      expect(result.filePath).toMatch(/json-tool-\d+\.json$/);
      expect(JSON.parse(readFileSync(result.filePath!, "utf-8"))).toEqual({ data: "x".repeat(50) });
    } finally {
      rmSync(dir, { recursive: true, force: true });
      setSessionDataDir("/tmp");
    }
  });
});
