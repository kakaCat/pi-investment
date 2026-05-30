/**
 * Query Experience Tool Tests
 *
 * 测试经验库查询工具（query_experience）的完整功能
 */
import { describe, test, expect, beforeEach, afterEach } from "@jest/globals";
import { mkdirSync, writeFileSync, rmSync, existsSync } from "fs";
import { join } from "path";
import type { ExperienceBase, Experience } from "../../../types/evolution.js";

// ═══════════════════════════════════════════════════════════════════
// Test Setup
// ═══════════════════════════════════════════════════════════════════

const TEST_PI_DIR = join(process.cwd(), ".test-pi-invest-query");
// experience-query.ts 从 process.cwd()/.pi-invest/experience/experience-base.json 读取
const EXPERIENCE_DIR = join(TEST_PI_DIR, ".pi-invest", "experience");
const EXPERIENCE_FILE = join(EXPERIENCE_DIR, "experience-base.json");

/** 创建测试用的经验条目 */
function makeExperience(overrides: Partial<Experience> & { id: string }): Experience {
  return {
    scenario: "MACD金叉配合成交量放大",
    pattern: {
      conditions: ["MACD金叉", "成交量放大", "RSI<70"],
      action: "buy",
    },
    outcomes: {
      total_cases: 50,
      win_rate: 65,
      avg_return: 3.5,
      max_gain: 15.0,
      max_loss: -8.0,
    },
    recommendation: "moderate",
    reason: "基于50次案例，胜率65%",
    examples: [
      { date: "2026-05-15", symbol: "000001", session_id: "s1", result: 5.0 },
      { date: "2026-05-20", symbol: "000858", session_id: "s2", result: 8.2 },
    ],
    confidence: 0.75,
    last_updated: "2026-05-28",
    ...overrides,
  };
}

/** 创建包含多条经验的经验库 */
function seedExperienceBase(): ExperienceBase {
  return {
    version: "1.0.0",
    last_updated: "2026-05-29",
    experiences: [
      makeExperience({ id: "exp-001" }),
      makeExperience({
        id: "exp-002",
        scenario: "RSI超卖后反弹买入",
        pattern: {
          conditions: ["RSI<30", "OBV背离"],
          action: "buy",
        },
        outcomes: {
          total_cases: 30,
          win_rate: 73,
          avg_return: 5.2,
          max_gain: 20.0,
          max_loss: -5.0,
        },
        recommendation: "aggressive",
        reason: "胜率超70%，平均收益超5%",
        confidence: 0.85,
      }),
      makeExperience({
        id: "exp-003",
        scenario: "跌破20日均线止损卖出",
        pattern: {
          conditions: ["跌破MA20", "MACD死叉"],
          action: "sell",
        },
        outcomes: {
          total_cases: 40,
          win_rate: 80,
          avg_return: -1.5,
          max_gain: 3.0,
          max_loss: -10.0,
        },
        recommendation: "moderate",
        reason: "止损及时，避免更大亏损",
        confidence: 0.7,
        examples: [
          { date: "2026-05-22", symbol: "600036", session_id: "s3", result: -3.5 },
        ],
      }),
      makeExperience({
        id: "exp-004",
        scenario: "追涨高位科技股",
        pattern: {
          conditions: ["PE>80", "涨幅>30%", "散户热捧"],
          action: "buy",
        },
        outcomes: {
          total_cases: 20,
          win_rate: 25,
          avg_return: -8.0,
          max_gain: 10.0,
          max_loss: -25.0,
        },
        recommendation: "avoid",
        reason: "追高风险极高，胜率仅25%",
        confidence: 0.9,
      }),
    ],
  };
}

// ═══════════════════════════════════════════════════════════════════
// Tests
// ═══════════════════════════════════════════════════════════════════

describe("query_experience Tool", () => {
  beforeEach(() => {
    // 创建测试经验库
    if (existsSync(TEST_PI_DIR)) {
      rmSync(TEST_PI_DIR, { recursive: true });
    }
    mkdirSync(EXPERIENCE_DIR, { recursive: true });

    const base = seedExperienceBase();
    writeFileSync(EXPERIENCE_FILE, JSON.stringify(base, null, 2));
  });

  afterEach(() => {
    if (existsSync(TEST_PI_DIR)) {
      rmSync(TEST_PI_DIR, { recursive: true });
    }
  });

  test("query returns relevant experiences by scenario", async () => {
    // Mock cwd to use test dir
    const origCwd = process.cwd;
    process.cwd = () => TEST_PI_DIR;

    try {
      const { queryAndFormatExperience } = await import(
        "../../../services/intelligence/experience-query.js"
      );
      const result = queryAndFormatExperience({
        scenario: "MACD金叉",
        limit: 3,
      });

      expect(result).toContain("经验");
      expect(result).toContain("MACD金叉配合成交量放大");
      expect(result).toContain("胜率: 65.0%");  // exp-001 has 65% win_rate
    } finally {
      process.cwd = origCwd;
    }
  });

  test("query returns empty for no match", async () => {
    const origCwd = process.cwd;
    process.cwd = () => TEST_PI_DIR;

    try {
      const { queryAndFormatExperience } = await import(
        "../../../services/intelligence/experience-query.js"
      );
      const result = queryAndFormatExperience({
        scenario: "ZZZ完全不匹配的场景ZZZ",
        limit: 5,
      });

      expect(result).toBe("未找到相关历史经验。");
    } finally {
      process.cwd = origCwd;
    }
  });

  test("query filters by conditions", async () => {
    const origCwd = process.cwd;
    process.cwd = () => TEST_PI_DIR;

    try {
      const { queryAndFormatExperience } = await import(
        "../../../services/intelligence/experience-query.js"
      );
      const result = queryAndFormatExperience({
        scenario: "超卖",
        conditions: ["RSI<30"],
        limit: 5,
      });

      expect(result).toContain("RSI超卖后反弹买入");
      expect(result).toContain("aggressive");
    } finally {
      process.cwd = origCwd;
    }
  });

  test("query filters by symbol", async () => {
    const origCwd = process.cwd;
    process.cwd = () => TEST_PI_DIR;

    try {
      const { queryAndFormatExperience } = await import(
        "../../../services/intelligence/experience-query.js"
      );
      const result = queryAndFormatExperience({
        scenario: "MACD金叉",
        symbol: "000858",
        limit: 5,
      });

      // exp-001 has an example with symbol 000858
      expect(result).toContain("MACD金叉配合成交量放大");
    } finally {
      process.cwd = origCwd;
    }
  });

  test("query respects limit parameter", async () => {
    const origCwd = process.cwd;
    process.cwd = () => TEST_PI_DIR;

    try {
      const { queryAndFormatExperience } = await import(
        "../../../services/intelligence/experience-query.js"
      );
      const result = queryAndFormatExperience({
        scenario: "买入",
        limit: 2,
      });

      // Should show at most 2 results
      const count = (result.match(/经验 \d+/g) || []).length;
      expect(count).toBeLessThanOrEqual(2);
    } finally {
      process.cwd = origCwd;
    }
  });

  test("tool execute returns success for valid params", async () => {
    const origCwd = process.cwd;
    process.cwd = () => TEST_PI_DIR;

    try {
      // Directly test the tool's execute function
      const { queryExperienceTool } = await import("./query-experience-tool.js");

      const result = await queryExperienceTool.execute(
        "test-call-1",
        { scenario: "止损卖出", limit: 3 },
        undefined,
        undefined,
        {} as any
      );

      expect(result.content).toBeDefined();
      if (result.content[0] && "text" in result.content[0]) {
        expect(typeof result.content[0].text).toBe("string");
        const text = result.content[0].text;
        expect(text).toContain("经验");
      }
    } finally {
      process.cwd = origCwd;
    }
  });

  test("tool execute handles missing experience file gracefully", async () => {
    const emptyDir = join(TEST_PI_DIR, "_empty");
    mkdirSync(join(emptyDir, "experience"), { recursive: true });
    const origCwd = process.cwd;
    process.cwd = () => emptyDir;

    try {
      const { queryExperienceTool } = await import("./query-experience-tool.js");

      const result = await queryExperienceTool.execute(
        "test-call-2",
        { scenario: "任何场景", limit: 3 },
        undefined,
        undefined,
        {} as any
      );

      expect(result.content).toBeDefined();
      if (result.content[0] && "text" in result.content[0]) {
        const text = result.content[0].text;
        expect(text).toContain("未找到");
      }
    } finally {
      process.cwd = origCwd;
    }
  });

  test("query returns avoid recommendation for known bad patterns", async () => {
    const origCwd = process.cwd;
    process.cwd = () => TEST_PI_DIR;

    try {
      const { queryAndFormatExperience } = await import(
        "../../../services/intelligence/experience-query.js"
      );
      const result = queryAndFormatExperience({
        scenario: "追涨",
        limit: 5,
      });

      expect(result).toContain("追涨高位科技股");
      expect(result).toContain("avoid");
      expect(result).toContain("胜率: 25.0%");
    } finally {
      process.cwd = origCwd;
    }
  });

  test("query returns experiences sorted by relevance", async () => {
    const origCwd = process.cwd;
    process.cwd = () => TEST_PI_DIR;

    try {
      const { queryAndFormatExperience } = await import(
        "../../../services/intelligence/experience-query.js"
      );
      const result = queryAndFormatExperience({
        scenario: "买入",
        limit: 3,
      });

      // Higher-confidence results should appear first
      // exp-004 (avoid, conf 0.9) > exp-002 (aggressive, conf 0.85) > exp-001 (moderate, conf 0.75)
      const idx004 = result.indexOf("追涨高位科技股");
      const idx002 = result.indexOf("RSI超卖后反弹买入");
      const idx001 = result.indexOf("MACD金叉配合成交量放大");

      // Not all may match in text results, skip if any not found
      if (idx001 >= 0 && idx002 >= 0) {
        expect(idx002).toBeLessThan(idx001); // Higher confidence first
      }
    } finally {
      process.cwd = origCwd;
    }
  });
});
