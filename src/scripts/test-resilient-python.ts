#!/usr/bin/env node
/**
 * 测试弹性 Python 调用
 */
import { callPythonResilient, getCacheStats, clearAllCaches } from "../infrastructure/tools/shared/python-caller-resilient-adapter.js";

async function testFunction(name: string, func: string, args: Record<string, unknown> = {}) {
  console.log(`\n${"=".repeat(60)}`);
  console.log(`测试: ${name}`);
  console.log(`${"=".repeat(60)}`);

  const start = Date.now();
  try {
    const result = await callPythonResilient(func, args);
    const elapsed = Date.now() - start;

    const parsed = JSON.parse(result);

    if (parsed.error) {
      console.log(`❌ 失败: ${parsed.error}`);
      if (parsed._from_fallback_cache) {
        console.log(`📦 使用降级缓存 (${parsed._cache_age_minutes}分钟前)`);
      }
    } else {
      console.log(`✅ 成功`);
      if (parsed._via_python_fallback) {
        console.log(`🔄 通过 Python 降级`);
      }
      if (parsed._from_fallback_cache) {
        console.log(`📦 使用降级缓存 (${parsed._cache_age_minutes}分钟前)`);
      }
    }

    console.log(`⏱️  耗时: ${elapsed}ms`);

    // 显示部分数据
    const keys = Object.keys(parsed).filter(k => !k.startsWith("_"));
    if (keys.length > 0) {
      console.log(`📊 数据字段: ${keys.slice(0, 5).join(", ")}${keys.length > 5 ? "..." : ""}`);
    }

    return { name, success: !parsed.error, elapsed, fromCache: !!parsed._from_fallback_cache };
  } catch (error) {
    const elapsed = Date.now() - start;
    console.log(`💥 异常: ${error instanceof Error ? error.message : String(error)}`);
    console.log(`⏱️  耗时: ${elapsed}ms`);
    return { name, success: false, elapsed, error: String(error) };
  }
}

async function main() {
  console.log("弹性 Python 调用测试");
  console.log("=".repeat(60));

  // 清除缓存，从头开始
  clearAllCaches();
  console.log("✅ 已清除所有缓存\n");

  const results = [];

  // 测试 1: 快速接口（10秒超时）
  results.push(await testFunction(
    "实时行情 (10s超时)",
    "get_stock_realtime_price",
    { symbol: "600519" }
  ));

  // 测试 2: 中速接口（30秒超时）
  results.push(await testFunction(
    "北向资金 (30s超时)",
    "get_north_flow",
    { days: 10 }
  ));

  // 测试 3: 慢速接口（60秒超时）- 已知会慢
  results.push(await testFunction(
    "宏观数据 (60s超时)",
    "get_macro_data",
    {}
  ));

  // 测试 4: 市场新闻（可能超时）
  results.push(await testFunction(
    "市场新闻 (60s超时)",
    "get_market_news",
    { limit: 10 }
  ));

  // 汇总报告
  console.log(`\n\n${"=".repeat(60)}`);
  console.log("测试报告汇总");
  console.log(`${"=".repeat(60)}\n`);

  const successCount = results.filter(r => r.success).length;
  const failCount = results.filter(r => !r.success).length;
  const cacheCount = results.filter(r => r.fromCache).length;
  const avgTime = results.reduce((sum, r) => sum + r.elapsed, 0) / results.length;

  console.log(`总测试数: ${results.length}`);
  console.log(`✅ 成功: ${successCount}`);
  console.log(`❌ 失败: ${failCount}`);
  console.log(`📦 使用降级缓存: ${cacheCount}`);
  console.log(`⏱️  平均耗时: ${avgTime.toFixed(0)}ms\n`);

  console.log("详细结果:");
  for (const r of results) {
    const icon = r.success ? "✅" : "❌";
    const cacheIcon = r.fromCache ? "📦" : "";
    console.log(`  ${icon} ${cacheIcon} ${r.name.padEnd(30)} ${r.elapsed}ms`);
  }

  // 缓存统计
  const stats = await getCacheStats();
  console.log(`\n缓存统计:`);
  console.log(`  - 活跃缓存: ${stats.cache_size} 条`);
  console.log(`  - 按命名空间: ${JSON.stringify(stats.by_namespace)}`);

  process.exit(failCount > 0 ? 1 : 0);
}

main().catch(err => {
  console.error("测试失败:", err);
  process.exit(1);
});
