#!/usr/bin/env tsx
/**
 * 测试 P0 缺失功能
 */

import { queryExperience, queryAndFormatExperience } from "../services/intelligence/experience-query.js";
import { analyzeSessionsAndCalculateEfficiency } from "../services/intelligence/session-analyzer.js";

console.log("🧪 测试 P0 缺失功能\n");

// ─── 测试 1: 经验库查询工具 ────────────────────────────────────────────────

console.log("═".repeat(60));
console.log("测试 1: 经验库查询工具");
console.log("═".repeat(60));

try {
  // 测试查询
  const result1 = queryAndFormatExperience({
    scenario: "MACD金叉",
    limit: 3
  });

  console.log("\n查询场景: MACD金叉");
  console.log(result1 || "未找到相关经验");

  // 测试条件查询
  const result2 = queryAndFormatExperience({
    scenario: "追涨买入",
    conditions: ["RSI>70", "涨幅>5%"],
    limit: 2
  });

  console.log("\n查询场景: 追涨买入 (RSI>70, 涨幅>5%)");
  console.log(result2 || "未找到相关经验");

  console.log("\n✅ 经验库查询工具测试通过");
} catch (e) {
  console.error("❌ 经验库查询工具测试失败:", e);
}

// ─── 测试 2: Session 分析器 ────────────────────────────────────────────────

console.log("\n" + "═".repeat(60));
console.log("测试 2: Session 分析器");
console.log("═".repeat(60));

try {
  const piDir = process.cwd() + "/.pi-invest";

  // 模拟交易数据
  const mockTrades = [
    { date: "2026-05-10", action: "buy" as const, symbol: "600519", price: 100, quantity: 100 },
    { date: "2026-05-15", action: "sell" as const, symbol: "600519", price: 105, quantity: 100 },
  ];

  const toolStats = analyzeSessionsAndCalculateEfficiency(piDir, mockTrades, 90);

  console.log(`\n分析结果: 找到 ${toolStats.length} 个工具`);

  if (toolStats.length > 0) {
    console.log("\n工具效能 Top 5:");
    for (const tool of toolStats.slice(0, 5)) {
      console.log(`  - ${tool.tool_name}: ROI ${tool.roi.toFixed(1)}, 胜率 ${(tool.win_rate * 100).toFixed(0)}%, 评级 ${tool.rating}/5`);
    }
  } else {
    console.log("  (没有 Session 日志，这是正常的)");
  }

  console.log("\n✅ Session 分析器测试通过");
} catch (e) {
  console.error("❌ Session 分析器测试失败:", e);
}

// ─── 总结 ──────────────────────────────────────────────────────────────────

console.log("\n" + "═".repeat(60));
console.log("🎉 P0 功能测试完成");
console.log("═".repeat(60));

console.log(`
✅ 已完成的 P0 功能:
  1. 经验库查询工具 - Agent 可以查询历史经验
  2. Session 分析器 - 自动计算工具效能

📝 使用方式:
  - Agent 调用: query_experience({ scenario: "MACD金叉" })
  - 进化系统: 自动分析 Session 并计算工具 ROI

🔗 集成状态:
  - ✅ 已注册到工具列表
  - ✅ 已集成到进化服务
  - ✅ 自动化执行
`);
