#!/usr/bin/env tsx
/**
 * 执行核心投资工具任务
 */

import { portfolioStatusTool } from '../src/infrastructure/tools/portfolio/portfolio-status-tool.js';
import { portfolioAnalyzeTool } from '../src/infrastructure/tools/portfolio/portfolio-analyze-tool.js';
import { poolManageTool } from '../src/infrastructure/tools/pool/pool-manage-tool.js';
import { marketAlertTool } from '../src/infrastructure/tools/alert/market-alert-tool.js';

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('🔧 执行核心投资工具任务');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

async function main() {
  try {
    // 任务1: 查看虚拟仓状态
    console.log('📊 任务1: portfolio_status - 查看虚拟仓状态');
    const startTime1 = Date.now();
    const result1 = await portfolioStatusTool.execute('task-1', {});
    const duration1 = Date.now() - startTime1;

    console.log(`✅ 执行成功 (${duration1}ms)\n`);
    const data1 = JSON.parse(result1.content[0].text);
    console.log('持仓概况：');
    console.log(`  💰 可用资金：¥${data1.cash.toFixed(2)}`);
    console.log(`  📈 持仓数量：${data1.holdings_count}只`);
    console.log(`  💼 持仓市值：¥${data1.total_market_value.toFixed(2)}`);
    console.log(`  💎 总资产：¥${data1.total_assets.toFixed(2)}`);
    console.log(`  📊 总盈亏：¥${data1.total_pnl.toFixed(2)} (${data1.total_pnl_pct.toFixed(2)}%)`);

    if (data1.holdings.length > 0) {
      console.log('\n持仓明细：');
      data1.holdings.forEach((h: any) => {
        const pnlSign = h.pnl >= 0 ? '+' : '';
        console.log(`  • ${h.symbol}: ${h.shares}股 @ ¥${h.cost_price}`);
        console.log(`    当前价：¥${h.current_price} | 盈亏：${pnlSign}¥${h.pnl.toFixed(2)} (${pnlSign}${(h.pnl_pct * 100).toFixed(2)}%)`);
      });
    }
    console.log('\n' + '─'.repeat(80) + '\n');

    // 任务2: 持仓分析
    console.log('🔍 任务2: portfolio_analyze - 持仓分析与交易建议');
    const startTime2 = Date.now();
    const result2 = await portfolioAnalyzeTool.execute('task-2', {});
    const duration2 = Date.now() - startTime2;

    console.log(`✅ 执行成功 (${duration2}ms)\n`);
    console.log(result2.content[0].text);
    console.log('\n' + '─'.repeat(80) + '\n');

    // 任务3: 股票池管理
    console.log('📋 任务3: pool_manage - 股票池列表');
    const startTime3 = Date.now();
    const result3 = await poolManageTool.execute('task-3', {
      action: 'list'
    });
    const duration3 = Date.now() - startTime3;

    console.log(`✅ 执行成功 (${duration3}ms)\n`);
    console.log(result3.content[0].text.substring(0, 500) + '...');
    console.log('\n' + '─'.repeat(80) + '\n');

    // 任务4: 预警检查
    console.log('⚠️  任务4: market_alert - 检查市场预警信号');
    const startTime4 = Date.now();
    const result4 = await marketAlertTool.execute('task-4', {});
    const duration4 = Date.now() - startTime4;

    console.log(`✅ 执行成功 (${duration4}ms)\n`);
    console.log(result4.content[0].text);
    console.log('\n' + '─'.repeat(80) + '\n');

    console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('✅ 核心投资工具任务执行完成！');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

    console.log('\n📝 执行总结:');
    console.log(`  ✅ portfolio_status - ${duration1}ms`);
    console.log(`  ✅ portfolio_analyze - ${duration2}ms`);
    console.log(`  ✅ pool_manage - ${duration3}ms`);
    console.log(`  ✅ market_alert - ${duration4}ms`);
    console.log(`  ⏱️  总耗时: ${duration1 + duration2 + duration3 + duration4}ms`);

  } catch (error) {
    console.error('\n❌ 任务执行失败:', error);
    if (error instanceof Error) {
      console.error('错误详情:', error.message);
      console.error('堆栈:', error.stack);
    }
    process.exit(1);
  }
}

main();
