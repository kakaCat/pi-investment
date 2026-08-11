import { describe, expect, test } from "@jest/globals";
import { mkdtempSync, existsSync, rmSync } from "fs";
import { tmpdir } from "os";
import { join } from "path";
import {
  generateExperienceSummary,
  loadExperienceSummary,
  saveExperienceSummary,
} from "./experience-learner.js";

describe("experience-learner 经验总结持久化", () => {
  test("保存/加载使用 experience-summary.json（不带感叹号笔误）", async () => {
    const piDir = mkdtempSync(join(tmpdir(), "pi-test-"));
    try {
      const summary = await generateExperienceSummary([]);
      await saveExperienceSummary(summary, piDir);

      expect(existsSync(join(piDir, "evolution/experience-summary.json"))).toBe(true);
      expect(existsSync(join(piDir, "evolution/experience-summary!.json"))).toBe(false);

      const loaded = await loadExperienceSummary(piDir);
      expect(loaded).not.toBeNull();
      expect(loaded!.version).toBe("1.0");
      expect(loaded!.totalEvolutions).toBe(0);
    } finally {
      rmSync(piDir, { recursive: true, force: true });
    }
  });
});
