#!/usr/bin/env tsx
/**
 * 测试进化系统配置功能
 */

import { runWeeklyEvolution, type EvolutionConfig } from "../services/intelligence/evolution-service.js";

async function testConfigs() {
  console.log("🧪 测试进化系统配置功能\n");

  // 测试 1: 默认配置
  console.log("═".repeat(60));
  console.log("测试 1: 默认配置");
  console.log("═".repeat(60));
  try {
    const result1 = await runWeeklyEvolution();
    console.log("\n✅ 默认配置测试通过");
    console.log(`   - 分析交易: ${result1.summary.totalTrades} 笔`);
    console.log(`   - 收益率: ${result1.summary.realizedReturn}%`);
    console.log(`   - 胜率: ${result1.summary.winRate}%`);
  } catch (e) {
    console.error("❌ 默认配置测试失败:", e instanceof Error ? e.message : String(e));
  }

  // 测试 2: 自定义时间窗口（30天）
  console.log("\n" + "═".repeat(60));
  console.log("测试 2: 自定义时间窗口（30天）");
  console.log("═".repeat(60));
  try {
    const config2: EvolutionConfig = {
      tradeWindowDays: 30,
      targetReturn: 8,
    };
    const result2 = await runWeeklyEvolution(config2);
    console.log("\n✅ 30天窗口测试通过");
    console.log(`   - 分析交易: ${result2.summary.totalTrades} 笔`);
    console.log(`   - 收益率: ${result2.summary.realizedReturn}%`);
  } catch (e) {
    console.error("❌ 30天窗口测试失败:", e instanceof Error ? e.message : String(e));
  }

  // 测试 3: 全历史模式
  console.log("\n" + "═".repeat(60));
  console.log("测试 3: 全历史模式");
  console.log("═".repeat(60));
  try {
    const config3: EvolutionConfig = {
      tradeWindowDays: undefined, // 全部
      reviewWindowCount: 20,
    };
    const result3 = await runWeeklyEvolution(config3);
    console.log("\n✅ 全历史模式测试通过");
    console.log(`   - 分析交易: ${result3.summary.totalTrades} 笔`);
    console.log(`   - 收益率: ${result3.summary.realizedReturn}%`);
  } catch (e) {
    console.error("❌ 全历史模式测试失败:", e instanceof Error ? e.message : String(e));
  }

  // 测试 4: 激进配置
  console.log("\n" + "═".repeat(60));
  console.log("测试 4: 激进配置");
  console.log("═".repeat(60));
  try {
    const config4: EvolutionConfig = {
      targetReturn: 20,
      tradeWindowDays: 180,
      reviewWindowCount: 20,
      evolutionWindowRecent: 5,
      evolutionWindowLearning: 200,
    };
    const result4 = await runWeeklyEvolution(config4);
    console.log("\n✅ 激进配置测试通过");
    console.log(`   - 目标收益: ${result4.summary.targetReturn}%`);
    console.log(`   - 实际收益: ${result4.summary.realizedReturn}%`);
    console.log(`   - 差距: ${result4.summary.targetReturn - result4.summary.realizedReturn}%`);
  } catch (e) {
    console.error("❌ 激进配置测试失败:", e instanceof Error ? e.message : String(e));
  }

  console.log("\n" + "═".repeat(60));
  console.log("🎉 所有测试完成");
  console.log("═".repeat(60));
}

testConfigs().catch(e => {
  console.error("测试失败:", e);
  process.exit(1);
});
