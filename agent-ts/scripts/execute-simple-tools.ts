#!/usr/bin/env tsx
/**
 * 执行简化的核心投资工具任务
 */

import { portfolioStatusTool } from '../src/infrastructure/tools/portfolio/portfolio-status-tool.js';
import { poolManageTool } from '../src/infrastructure/tools/pool/pool-manage-tool.js';
import { opportunityScanTool } from '../src/infrastructure/tools/invest/opportunity-scan-tool.js';

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
    try {
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
    } catch (e) {
      console.log(result1.content[0].text);
    }
    console.log('\n' + '─'.repeat(80) + '\n');

    // 任务2: 股票池管理 - 列表
    console.log('📋 任务2: pool_manage list - 股票池列表');
    const startTime2 = Date.now();
    const result2 = await poolManageTool.execute('task-2', {
      command: 'list'
    });
    const duration2 = Date.now() - startTime2;

    console.log(`✅ 执行成功 (${duration2}ms)\n`);
    console.log(result2.content[0].text);
    console.log('\n' + '─'.repeat(80) + '\n');

    // 任务3: 机会扫描
    console.log('🔍 任务3: opportunity_scan - 扫描投资机会');
    const startTime3 = Date.now();
    const result3 = await opportunityScanTool.execute('task-3', {
      pool_id: 'all',
      min_score: 70
    });
    const duration3 = Date.now() - startTime3;

    console.log(`✅ 执行成功 (${duration3}ms)\n`);
    console.log(result3.content[0].text.substring(0, 1000));
    if (result3.content[0].text.length > 1000) {
      console.log('\n...(输出已截断，完整结果请查看日志)');
    }
    console.log('\n' + '─'.repeat(80) + '\n');

    console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('✅ 核心投资工具任务执行完成！');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

    console.log('\n📝 执行总结:');
    console.log(`  ✅ portfolio_status - ${duration1}ms`);
    console.log(`  ✅ pool_manage list - ${duration2}ms`);
    console.log(`  ✅ opportunity_scan - ${duration3}ms`);
    console.log(`  ⏱️  总耗时: ${duration1 + duration2 + duration3}ms`);

  } catch (error) {
    console.error('\n❌ 任务执行失败:', error);
    if (error instanceof Error) {
      console.error('错误详情:', error.message);
    }
    process.exit(1);
  }
}

main();
