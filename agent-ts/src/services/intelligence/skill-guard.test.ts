import { beforeEach, describe, expect, test } from "@jest/globals";
import { dirname, join } from "path";
import { fileURLToPath } from "url";
import {
  assertToolAllowedForActiveSkill,
  getExplicitSkillFromPrompt,
  initSkillGuard,
  withForcedSkillScope,
} from "../../infrastructure/tools/skill-guard.js";

const __dirname = dirname(fileURLToPath(import.meta.url));

describe("skill-guard", () => {
  beforeEach(() => {
    initSkillGuard([
      { name: "deep-analysis", filePath: join(process.cwd(), "skills", "deep-analysis.md") },
      { name: "portfolio", filePath: join(process.cwd(), "skills", "portfolio.md") },
      { name: "test-no-tools", filePath: join(__dirname, "__fixtures__", "test-no-tools.md") },
      { name: "declared-tools", filePath: join(__dirname, "__fixtures__", "declared-tools.md") },
    ] as any);
  });

  test("parses explicit skill command from prompt", () => {
    expect(getExplicitSkillFromPrompt("/skill:deep-analysis 分析一下中粮糖业")).toBe("deep-analysis");
  });

  test("allows tools declared in the active skill", async () => {
    await expect(withForcedSkillScope("deep-analysis", async () => {
      assertToolAllowedForActiveSkill("data_fetch_quote");  // data_fetch_stock 已在工具清理中移除，skill 现行声明为 data_fetch_quote
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

  test("allows every tool listed in the 允许的工具 section even without backtick formatting", async () => {
    // 2026-08-12 审计发现：声明区写 `- tool_name()`（无反引号）时旧提取逻辑漏提，
    // 强制路由后 skill 自己的流程被拦（portfolio-review 7 个声明工具漏 6 个）。
    await expect(withForcedSkillScope("declared-tools", async () => {
      assertToolAllowedForActiveSkill("data_fetch_quote");
      assertToolAllowedForActiveSkill("risk_controller");
    })).resolves.toBeUndefined();
  });

  test("still blocks undeclared tools for section-based skills", async () => {
    await expect(withForcedSkillScope("declared-tools", async () => {
      assertToolAllowedForActiveSkill("pool_manage");
    })).rejects.toThrow("技能 declared-tools 未授权调用工具 pool_manage");
  });
});
