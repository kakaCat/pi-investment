#!/usr/bin/env tsx
/**
 * Evolution 流程测试脚本
 *
 * 测试：
 * 1. 数据检查逻辑
 * 2. 参数解析
 * 3. 报告生成
 */

import { runWeeklyEvolution, type EvolutionConfig } from "../services/intelligence/evolution-service.js";
import { readFileSync, existsSync } from "fs";
import { join } from "path";

const piDir = join(process.cwd(), ".pi-invest");

async function testEvolution() {
  console.log("🧪 测试 Evolution 流程\n");
  console.log("=" .repeat(60));

  // 测试 1: 检查数据（通过 CLI → PostgreSQL）
  console.log("\n📋 测试 1: 检查数据");
  console.log("-".repeat(60));

  const { TradeCliAdapter } = await import("../infrastructure/adapters/cli/trade-cli-adapter.js");
  const { PositionCliAdapter } = await import("../infrastructure/adapters/cli/position-cli-adapter.js");

  const tradeAdapter = new TradeCliAdapter();
  const trades = await tradeAdapter.list();
  console.log(`✅ 交易记录: ${trades.length} 笔（PostgreSQL）`);

  // 统计买入/卖出
  const buyCount = trades.filter(t => t.action === "buy").length;
  const sellCount = trades.filter(t => t.action === "sell").length;
  console.log(`   - 买入: ${buyCount} 笔`);
  console.log(`   - 卖出: ${sellCount} 笔`);

  if (buyCount === 0 && sellCount > 0) {
    console.log(`   ⚠️  只有卖出没有买入，无法计算已实现盈亏`);
  }

  const positionAdapter = new PositionCliAdapter();
  const positions = await positionAdapter.list({ status: 'open' });
  console.log(`✅ 持仓数据: ${positions.length} 个（PostgreSQL）`);

  // 测试 2: 运行进化分析（捕获错误）
  console.log("\n📋 测试 2: 运行进化分析");
  console.log("-".repeat(60));

  try {
    const config: EvolutionConfig = {
      tradeWindowDays: undefined, // 全部交易
      targetReturn: 10,
    };

    console.log("开始运行...\n");
    const result = await runWeeklyEvolution(config);

    console.log("\n✅ 进化分析完成！");
    console.log(`   - 报告路径: ${result.reportPath}`);
    console.log(`   - 目标收益: ${result.summary.targetReturn}%`);
    console.log(`   - 实际收益: ${result.summary.realizedReturn}%`);
    console.log(`   - 胜率: ${result.summary.winRate}%`);
    console.log(`   - 交易次数: ${result.summary.totalTrades}`);
    console.log(`   - 优化建议: ${result.summary.suggestionCount} 条`);
    console.log(`   - 已应用: ${result.summary.appliedCount} 条`);

  } catch (error: any) {
    console.log("\n❌ 进化分析失败:");
    console.log(`   ${error.message}`);

    if (error.message.includes("没有交易数据")) {
      console.log("\n💡 建议: 添加交易记录（通过 manage_portfolio 工具）");
    } else if (error.message.includes("时间窗口内没有交易")) {
      console.log("\n💡 建议: 使用 --all 分析全部交易");
    }
  }

  console.log("\n" + "=".repeat(60));
  console.log("🧪 测试完成\n");
}

// 运行测试
testEvolution().catch(error => {
  console.error("未捕获的错误:", error);
  process.exit(1);
});
