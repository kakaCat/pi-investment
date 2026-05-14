import { beforeEach, describe, expect, test } from "@jest/globals";
import { join } from "path";
import {
  assertToolAllowedForActiveSkill,
  getExplicitSkillFromPrompt,
  initSkillGuard,
  withForcedSkillScope,
} from "../../infrastructure/tools/skill-guard.js";

describe("skill-guard", () => {
  beforeEach(() => {
    initSkillGuard([
      { name: "deep-analysis", filePath: join(process.cwd(), "skills", "deep-analysis.md") },
      { name: "portfolio", filePath: join(process.cwd(), "skills", "portfolio.md") },
      { name: "test-no-tools", filePath: join(process.cwd(), "skills", "test-no-tools.md") },
    ] as any);
  });

  test("parses explicit skill command from prompt", () => {
    expect(getExplicitSkillFromPrompt("/skill:deep-analysis 分析一下中粮糖业")).toBe("deep-analysis");
  });

  test("allows tools declared in the active skill", async () => {
    await expect(withForcedSkillScope("deep-analysis", async () => {
      assertToolAllowedForActiveSkill("get_valuation");
    })).resolves.toBeUndefined();
  });

  test("blocks tools not declared in the active skill", async () => {
    await expect(withForcedSkillScope("portfolio", async () => {
      assertToolAllowedForActiveSkill("get_stock_news");
    })).rejects.toThrow("技能 portfolio 未授权调用工具 get_stock_news");
  });

  test("blocks invest tools when the skill contains no tool calls", async () => {
    await expect(withForcedSkillScope("test-no-tools", async () => {
      assertToolAllowedForActiveSkill("get_stock_price");
    })).rejects.toThrow("技能 test-no-tools 未授权调用工具 get_stock_price");
  });
});
