/**
 * 批量回测脚本
 *
 * 遍历所有启用量化策略，跳过不支持指标的策略，
 * 使用沪深300 proxy（市值 top 300）作为股票池，
 * 回测6个月（2025-11-17 至 2026-05-17）。
 */

import { QuantService } from '../services/quant/quant-service.js';
import { BacktestEngine } from '../services/quant/backtest-engine.js';
import { StockDBService } from '../services/data/stock-db-service.js';
import path from 'path';
import fs from 'fs';

// ===== 不支持的回测指标列表 =====
const UNSUPPORTED_INDICATORS = new Set([
  'price_support',
  'price_resistance',
  'price_breakout',
  'price_ma',
]);

interface StrategyResult {
  name: string;
  id: string;
  status: 'ok' | 'skipped' | 'error';
  total_return: number;
  annual_return: number;
  max_drawdown: number;
  sharpe_ratio: number;
  win_rate: number;
  total_trades: number;
  profit_loss_ratio: number;
  error?: string;
}

/**
 * 检查策略是否使用了不支持的指标
 */
function hasUnsupportedIndicators(strategy: any): string | null {
  const allConditions = [
    ...(strategy.entry?.conditions || []),
    ...(strategy.exit?.conditions || []),
  ];
  for (const c of allConditions) {
    if (UNSUPPORTED_INDICATORS.has(c.indicator)) {
      return `${c.indicator}`;
    }
  }
  // 也检查筛查过滤器
  if (strategy.screening?.filters?.symbols) {
    return null; // 单股策略可以跑，但用其指定标的
  }
  return null;
}

/**
 * 获取策略应有的回测股票池
 */
function getStrategySymbols(strategy: any, top300: string[]): string[] {
  const customSymbols = strategy.screening?.filters?.symbols;
  if (customSymbols && Array.isArray(customSymbols) && customSymbols.length > 0) {
    return customSymbols; // 单股策略用其指定标的
  }
  return top300; // 全市场策略用沪深300 proxy
}

async function main() {
  const stockDBService = StockDBService.getInstance('.pi-invest');
  const quantService = new QuantService();
  const backtestEngine = new BacktestEngine(stockDBService);

  console.log('=== 批量回测 ===\n');
  console.log(`时间范围: 2025-11-17 至 2026-05-17\n`);

  // 获取沪深300 proxy（市值 top 300）
  console.log('📊 获取沪深300 proxy 股票池...');
  const top300Stocks = stockDBService.getTopNByMarketCap(300, true);
  const top300Symbols = top300Stocks.map(s => s.symbol);
  console.log(`   已获取 ${top300Symbols.length} 只股票\n`);

  // 获取所有策略目录下的JSON文件
  const strategiesDir = path.join('.pi-invest', 'quant', 'strategies');
  const files = fs.readdirSync(strategiesDir).filter(f => f.endsWith('.json'));

  const results: StrategyResult[] = [];
  let skipped = 0;
  let ran = 0;

  for (const file of files) {
    const filePath = path.join(strategiesDir, file);
    const strategy = JSON.parse(fs.readFileSync(filePath, 'utf-8'));

    // 只跑启用的策略
    if (!strategy.enabled) {
      console.log(`⏭️  跳过 (未启用): ${strategy.name}`);
      skipped++;
      continue;
    }

    // 检查不支持的指标
    const unsupported = hasUnsupportedIndicators(strategy);
    if (unsupported) {
      console.log(`⏭️  跳过 (不支持指标 "${unsupported}"): ${strategy.name}`);
      results.push({
        name: strategy.name,
        id: strategy.id,
        status: 'skipped',
        total_return: 0,
        annual_return: 0,
        max_drawdown: 0,
        sharpe_ratio: 0,
        win_rate: 0,
        total_trades: 0,
        profit_loss_ratio: 0,
        error: `不支持指标: ${unsupported}`,
      });
      skipped++;
      continue;
    }

    // 确定股票池
    const symbols = getStrategySymbols(strategy, top300Symbols);

    console.log(`▶️  运行: ${strategy.name} (${symbols.length}只股票)`);

    try {
      // 设置回测时间 6 个月，带 60 秒超时
      const result = await Promise.race([
        backtestEngine.runBacktest(strategy, '2025-11-17', '2026-05-17', symbols, 100000),
        new Promise<{ timeout: true }>((_, reject) =>
          setTimeout(() => reject(new Error('Timeout after 120s')), 120_000)
        ),
      ]);

      if ('timeout' in (result as any)) {
        throw new Error('Timeout');
      }

      const r = result as any;
      results.push({
        name: strategy.name,
        id: strategy.id,
        status: 'ok',
        total_return: r.total_return,
        annual_return: r.annual_return,
        max_drawdown: r.max_drawdown,
        sharpe_ratio: r.sharpe_ratio,
        win_rate: r.win_rate,
        total_trades: r.total_trades,
        profit_loss_ratio: r.profit_loss_ratio,
      });
      ran++;
      console.log(`   ✅ 完成: 收益率 ${r.total_return.toFixed(2)}%, 交易 ${r.total_trades}次\n`);
    } catch (e: any) {
      console.log(`   ❌ 失败: ${e.message}`);
      results.push({
        name: strategy.name,
        id: strategy.id,
        status: 'error',
        total_return: 0,
        annual_return: 0,
        max_drawdown: 0,
        sharpe_ratio: 0,
        win_rate: 0,
        total_trades: 0,
        profit_loss_ratio: 0,
        error: e.message,
      });
    }
  }

  // 输出结果表格
  console.log('\n' + '='.repeat(120));
  console.log('📊 批量回测结果');
  console.log('='.repeat(120));

  console.log('\n▶️ 运行成功：');
  console.log('─'.repeat(120));
  const header = `${'策略名称'.padEnd(24)} ${'收益率%'.padEnd(10)} ${'年化%'.padEnd(10)} ${'最大回撤%'.padEnd(10)} ${'夏普'.padEnd(8)} ${'胜率%'.padEnd(8)} ${'交易次数'.padEnd(8)} ${'盈亏比'.padEnd(8)}`;
  console.log(header);
  console.log('─'.repeat(120));

  for (const r of results) {
    if (r.status === 'ok') {
      const name = r.name.length > 24 ? r.name.substring(0, 21) + '...' : r.name.padEnd(24);
      console.log(
        `${name} ${r.total_return.toFixed(2).padStart(8)}% ${r.annual_return.toFixed(2).padStart(8)}% ${r.max_drawdown.toFixed(2).padStart(8)}% ${r.sharpe_ratio.toFixed(2).padStart(6)}  ${r.win_rate.toFixed(1).padStart(6)}% ${String(r.total_trades).padStart(6)}   ${r.profit_loss_ratio.toFixed(2).padStart(6)}`
      );
    }
  }

  console.log('\n⏭️ 跳过：');
  for (const r of results) {
    if (r.status === 'skipped') {
      console.log(`  ${r.name}: ${r.error}`);
    }
  }

  console.log('\n❌ 失败：');
  for (const r of results) {
    if (r.status === 'error') {
      console.log(`  ${r.name}: ${r.error}`);
    }
  }

  console.log('\n─'.repeat(120));
  console.log(`总计: ${results.length} | 成功: ${ran} | 跳过: ${skipped} | 失败: ${results.filter(r => r.status === 'error').length}`);

  // 保存结果到文件
  const resultSummary = {
    total: results.length,
    ok: results.filter(r => r.status === 'ok').length,
    skipped: results.filter(r => r.status === 'skipped').length,
    failed: results.filter(r => r.status === 'error').length,
    details: results
  };
  fs.writeFileSync('/tmp/batch-backtest-results.json', JSON.stringify(resultSummary, null, 2));

  stockDBService.close();
}

main().catch(console.error);
