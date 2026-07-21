#!/usr/bin/env tsx
/**
 * 执行所有工具任务的综合测试
 */

import { portfolioStatusTool } from '../src/infrastructure/tools/portfolio/portfolio-status-tool.js';
import { portfolioAnalyzeTool } from '../src/infrastructure/tools/portfolio/portfolio-analyze-tool.js';
import { poolManageTool } from '../src/infrastructure/tools/pool/pool-manage-tool.js';
import { marketAlertTool } from '../src/infrastructure/tools/alert/market-alert-tool.js';
import { swingPointsTool } from '../src/infrastructure/tools/invest/swing-points-tool.js';

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('🚀 执行所有工具任务综合测试');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

interface ToolResult {
  name: string;
  success: boolean;
  duration: number;
  error?: string;
}

const results: ToolResult[] = [];

async function runTool(name: string, label: string, fn: () => Promise<any>) {
  console.log(`📊 ${label}`);
  const startTime = Date.now();

  try {
    const result = await fn();
    const duration = Date.now() - startTime;
    const text = result.content[0].text;

    // 检查是否有错误
    const hasError = text.includes('失败') || text.includes('错误') || text.includes('error');

    if (hasError) {
      console.log(`   ❌ 执行失败 (${duration}ms)`);
      console.log(`   ${text.substring(0, 100)}...`);
      results.push({ name, success: false, duration, error: 'execution_failed' });
    } else {
      console.log(`   ✅ 执行成功 (${duration}ms)`);
      // 显示简要结果
      const lines = text.split('\n').slice(0, 3);
      lines.forEach(line => {
        if (line.trim()) console.log(`   ${line.substring(0, 80)}`);
      });
      results.push({ name, success: true, duration });
    }
  } catch (error) {
    const duration = Date.now() - startTime;
    console.log(`   ❌ 异常 (${duration}ms)`);
    console.log(`   ${error instanceof Error ? error.message : String(error)}`);
    results.push({ name, success: false, duration, error: 'exception' });
  }

  console.log('');
}

async function main() {
  // 1. 持仓状态
  await runTool(
    'portfolio_status',
    '任务1: 查看虚拟仓状态',
    () => portfolioStatusTool.execute('test-1', {})
  );

  // 2. 持仓分析
  await runTool(
    'portfolio_analyze',
    '任务2: 持仓分析与建议',
    () => portfolioAnalyzeTool.execute('test-2', {})
  );

  // 3. 股票池管理
  await runTool(
    'pool_manage',
    '任务3: 股票池列表',
    () => poolManageTool.execute('test-3', { action: 'list' })
  );

  // 4. 市场预警
  await runTool(
    'market_alert',
    '任务4: 市场预警检查',
    () => marketAlertTool.execute('test-4', {})
  );

  // 5. 波段分析 - 贵州茅台
  await runTool(
    'swing_points_600519',
    '任务5: ZigZag波段分析 (600519)',
    () => swingPointsTool.execute('test-5', { symbol: '600519', min_change: 5 })
  );

  // 6. 波段分析 - 平安银行
  await runTool(
    'swing_points_000001',
    '任务6: ZigZag波段分析 (000001)',
    () => swingPointsTool.execute('test-6', { symbol: '000001', min_change: 5 })
  );

  // 7. 测试错误处理 - 不存在的股票
  await runTool(
    'swing_points_invalid',
    '任务7: 错误处理测试 (999999)',
    () => swingPointsTool.execute('test-7', { symbol: '999999', min_change: 5 })
  );

  // 总结
  console.log('━'.repeat(80));
  console.log('📊 测试总结\n');

  const successful = results.filter(r => r.success);
  const failed = results.filter(r => !r.success);

  console.log(`总任务数: ${results.length}`);
  console.log(`✅ 成功: ${successful.length}`);
  console.log(`❌ 失败: ${failed.length}`);
  console.log(`⏱️  总耗时: ${results.reduce((sum, r) => sum + r.duration, 0)}ms\n`);

  if (successful.length > 0) {
    console.log('成功的工具:');
    successful.forEach(r => {
      console.log(`  ✅ ${r.name} (${r.duration}ms)`);
    });
    console.log('');
  }

  if (failed.length > 0) {
    console.log('失败的工具:');
    failed.forEach(r => {
      console.log(`  ❌ ${r.name} (${r.error || 'unknown'})`);
    });
    console.log('');
  }

  // 性能分析
  const avgDuration = results.reduce((sum, r) => sum + r.duration, 0) / results.length;
  const slowest = results.reduce((max, r) => r.duration > max.duration ? r : max);
  const fastest = results.reduce((min, r) => r.duration < min.duration ? r : min);

  console.log('⚡ 性能分析:');
  console.log(`  平均耗时: ${avgDuration.toFixed(0)}ms`);
  console.log(`  最快工具: ${fastest.name} (${fastest.duration}ms)`);
  console.log(`  最慢工具: ${slowest.name} (${slowest.duration}ms)`);

  console.log('\n💡 这些工具在自动化任务中的作用:');
  console.log('  • 早盘分析 (09:00): 持仓状态 → 市场预警 → 交易决策');
  console.log('  • 盘中检查 (每30分钟): 预警监控 → 波段机会 → 风险控制');
  console.log('  • 每日复盘 (18:00): 持仓分析 → 池刷新 → 绩效评估');

  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
}

main().catch(console.error);
