#!/usr/bin/env node
/**
 * 测试备选方案提示
 */
import { callPythonResilient } from "../infrastructure/tools/shared/python-caller-resilient-adapter.js";

async function testAlternatives() {
  console.log("测试备选方案提示功能\n");
  console.log("=".repeat(60));

  // 测试一个会失败的调用（使用错误的参数）
  console.log("\n测试 1: 调用失败时的备选方案");
  console.log("-".repeat(60));

  try {
    const result = await callPythonResilient("get_north_flow", { invalid_param: true });
    const parsed = JSON.parse(result);

    if (parsed.error) {
      console.log("❌ 调用失败（预期）");
      console.log(`错误信息: ${parsed.error}`);

      if (parsed._alternatives) {
        console.log("\n💡 备选方案:");
        parsed._alternatives.forEach((alt: string, i: number) => {
          console.log(`   ${i + 1}. ${alt}`);
        });
      } else {
        console.log("\n⚠️  警告: 没有返回备选方案！");
      }
    }
  } catch (error) {
    console.log("💥 异常:", error);
  }

  // 测试降级缓存时的备选方案
  console.log("\n\n测试 2: 使用降级缓存时的备选方案");
  console.log("-".repeat(60));

  // 先成功调用一次，建立缓存
  console.log("步骤 1: 建立缓存...");
  try {
    const result1 = await callPythonResilient("get_stock_realtime_price", { symbol: "600519" });
    const parsed1 = JSON.parse(result1);
    if (!parsed1.error) {
      console.log("✅ 缓存已建立");
    }
  } catch (error) {
    console.log("建立缓存失败:", error);
  }

  // 模拟：如果之后数据源失败，会使用降级缓存
  console.log("\n步骤 2: 模拟数据源失败场景");
  console.log("（实际场景中，当 Python 调用超时或失败时，会自动使用降级缓存）");
  console.log("降级缓存的返回数据会包含 _alternatives 字段");

  // 测试不存在的函数
  console.log("\n\n测试 3: 未知函数的通用备选方案");
  console.log("-".repeat(60));

  try {
    const result = await callPythonResilient("unknown_function", {});
    const parsed = JSON.parse(result);

    if (parsed.error) {
      console.log("❌ 调用失败（预期）");
      console.log(`错误信息: ${parsed.error}`);

      if (parsed._alternatives) {
        console.log("\n💡 通用备选方案:");
        parsed._alternatives.forEach((alt: string, i: number) => {
          console.log(`   ${i + 1}. ${alt}`);
        });
      }
    }
  } catch (error) {
    console.log("💥 异常:", error);
  }

  // 展示所有已配置的备选方案
  console.log("\n\n" + "=".repeat(60));
  console.log("已配置备选方案的函数列表");
  console.log("=".repeat(60));

  const functionsWithAlternatives = [
    "get_stock_realtime_price",
    "get_north_flow",
    "get_sector_fund_flow",
    "test_market_sentiment",
    "get_market_news",
    "get_macro_data",
    "get_lhb",
    "get_financial_indicators",
    "calculate_buy_range"
  ];

  console.log("\n以下函数在失败时会提供备选方案:");
  functionsWithAlternatives.forEach((func, i) => {
    console.log(`  ${i + 1}. ${func}`);
  });

  console.log("\n✅ 测试完成");
}

testAlternatives().catch(err => {
  console.error("测试失败:", err);
  process.exit(1);
});
