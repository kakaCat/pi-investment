#!/usr/bin/env tsx
/**
 * HK Holdings Migration Script
 *
 * Migrates existing HK stock holdings by adding missing FX rate fields:
 * - avg_cost_hkd: HKD cost per share (reverse-calculated from CNY cost)
 * - purchase_fx_rate: FX rate at purchase time (estimated from current rate)
 *
 * Usage:
 *   npm run migrate:hk-holdings           # Dry-run (shows changes without applying)
 *   npm run migrate:hk-holdings -- --apply  # Apply changes
 */

import { PortfolioService } from "../services/portfolio/portfolio-service.js";
import { FxRateService } from "../services/fx-rate-service.js";
import { copyFileSync } from "fs";
import { join } from "path";

const PI_DIR = join(process.cwd(), ".pi-invest");

interface MigrationResult {
  symbol: string;
  name: string;
  quantity: number;
  oldAvgCost: number;
  newAvgCostHKD: number;
  newPurchaseFxRate: number;
}

async function migrateHKHoldings(dryRun: boolean = true) {
  console.log("🔄 港股持仓数据迁移工具\n");
  console.log(`模式: ${dryRun ? "🔍 预览模式（不会修改文件）" : "✍️  应用模式（将修改文件）"}\n`);

  const portfolioService = new PortfolioService(PI_DIR);
  const fxRateService = new FxRateService(PI_DIR);

  // 1. Load current portfolio
  const originalData = portfolioService.load();
  const hkHoldings = originalData.holdings.filter(h => h.market === "HK");

  if (hkHoldings.length === 0) {
    console.log("ℹ️  未找到港股持仓，无需迁移");
    return;
  }

  console.log(`📊 找到 ${hkHoldings.length} 只港股持仓\n`);

  // 2. Get current FX rate
  console.log("🌐 获取当前汇率...");
  const currentFxRate = await fxRateService.getRate("HKDCNY");
  console.log(`✅ 当前汇率: 1 HKD = ${currentFxRate.toFixed(4)} CNY\n`);

  // 3. Check which holdings need migration
  const needsMigration = hkHoldings.filter(h => !h.avg_cost_hkd || !h.purchase_fx_rate);

  if (needsMigration.length === 0) {
    console.log("✅ 所有港股持仓已包含汇率信息，无需迁移");
    return;
  }

  console.log(`🔧 需要迁移 ${needsMigration.length} 只港股:\n`);

  // 4. Calculate migration changes
  const migrations: MigrationResult[] = [];

  for (const holding of needsMigration) {
    // Reverse calculate HKD cost from CNY cost
    const avgCostHKD = holding.avg_cost / currentFxRate;

    migrations.push({
      symbol: holding.symbol,
      name: holding.name,
      quantity: holding.quantity,
      oldAvgCost: holding.avg_cost,
      newAvgCostHKD: Math.round(avgCostHKD * 100) / 100,
      newPurchaseFxRate: currentFxRate,
    });
  }

  // 5. Display changes
  console.log("📋 迁移详情:\n");
  console.log("─".repeat(80));

  for (const m of migrations) {
    console.log(`\n股票: ${m.symbol} ${m.name}`);
    console.log(`持仓: ${m.quantity} 股`);
    console.log(`\n  当前数据:`);
    console.log(`    avg_cost (CNY):        ${m.oldAvgCost.toFixed(2)} 元`);
    console.log(`    avg_cost_hkd:          (缺失)`);
    console.log(`    purchase_fx_rate:      (缺失)`);
    console.log(`\n  迁移后数据:`);
    console.log(`    avg_cost (CNY):        ${m.oldAvgCost.toFixed(2)} 元 (不变)`);
    console.log(`    avg_cost_hkd:          ${m.newAvgCostHKD.toFixed(2)} 港元 (反推)`);
    console.log(`    purchase_fx_rate:      ${m.newPurchaseFxRate.toFixed(4)} (当前汇率)`);
    console.log(`\n  市值计算:`);
    console.log(`    总成本 (CNY):          ${(m.oldAvgCost * m.quantity).toFixed(2)} 元`);
    console.log(`    总成本 (HKD):          ${(m.newAvgCostHKD * m.quantity).toFixed(2)} 港元`);
  }

  console.log("\n" + "─".repeat(80));
  console.log("\n⚠️  重要提示:");
  console.log("   • avg_cost_hkd 是根据当前汇率反推的，不是真实买入价");
  console.log("   • purchase_fx_rate 使用当前汇率估算，不是实际买入时汇率");
  console.log("   • 如果你记得真实买入价，可以在迁移后手动修正 portfolio.json");
  console.log("   • 迁移前会自动创建备份文件\n");

  // 6. Apply changes if not dry-run
  if (!dryRun) {
    console.log("💾 应用迁移...\n");

    // Create backup
    const portfolioPath = join(PI_DIR, "portfolio.json");
    const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
    const backupPath = join(PI_DIR, `portfolio.backup.${timestamp}.json`);

    copyFileSync(portfolioPath, backupPath);
    console.log(`✅ 已备份到: ${backupPath}`);

    // Update holdings
    const updatedHoldings = originalData.holdings.map(h => {
      if (h.market === "HK" && (!h.avg_cost_hkd || !h.purchase_fx_rate)) {
        const avgCostHKD = Math.round((h.avg_cost / currentFxRate) * 100) / 100;
        return {
          ...h,
          avg_cost_hkd: avgCostHKD,
          purchase_fx_rate: currentFxRate,
        };
      }
      return h;
    });

    // Save updated portfolio
    const result = portfolioService.replaceHoldings(updatedHoldings);

    if (result.success) {
      console.log(`✅ ${result.message}`);
      console.log(`\n🎉 迁移完成！共更新 ${migrations.length} 只港股持仓`);
      console.log(`\n💡 提示: 如需修正真实买入价，请编辑 ${portfolioPath}`);
    } else {
      console.error(`❌ 迁移失败: ${result.message}`);
      process.exit(1);
    }
  } else {
    console.log("🔍 预览模式 - 未修改任何文件");
    console.log("\n要应用这些更改，请运行:");
    console.log("  npm run migrate:hk-holdings -- --apply\n");
  }
}

// Parse command line arguments
const args = process.argv.slice(2);
const applyMode = args.includes("--apply");

migrateHKHoldings(!applyMode).catch((error) => {
  console.error("\n❌ 迁移失败:", error);
  process.exit(1);
});
