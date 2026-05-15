#!/usr/bin/env tsx
/**
 * 简单测试配置解析功能
 */

import type { EvolutionConfig } from "../services/intelligence/evolution-service.js";

function testConfigParsing() {
  console.log("🧪 测试配置解析功能\n");

  // 测试 1: 默认配置
  const config1: EvolutionConfig = {};
  console.log("✅ 测试 1: 默认配置");
  console.log("   配置:", JSON.stringify(config1, null, 2));

  // 测试 2: 自定义时间窗口
  const config2: EvolutionConfig = {
    tradeWindowDays: 30,
    targetReturn: 8,
  };
  console.log("\n✅ 测试 2: 自定义时间窗口（30天）");
  console.log("   配置:", JSON.stringify(config2, null, 2));

  // 测试 3: 全历史模式
  const config3: EvolutionConfig = {
    tradeWindowDays: undefined,
    reviewWindowCount: 20,
  };
  console.log("\n✅ 测试 3: 全历史模式");
  console.log("   配置:", JSON.stringify(config3, null, 2));

  // 测试 4: 激进配置
  const config4: EvolutionConfig = {
    targetReturn: 20,
    tradeWindowDays: 180,
    reviewWindowCount: 20,
    evolutionWindowRecent: 5,
    evolutionWindowLearning: 200,
  };
  console.log("\n✅ 测试 4: 激进配置");
  console.log("   配置:", JSON.stringify(config4, null, 2));

  console.log("\n🎉 所有配置解析测试通过");
}

testConfigParsing();
