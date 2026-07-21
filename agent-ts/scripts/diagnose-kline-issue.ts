#!/usr/bin/env tsx
/**
 * 诊断K线数据不足问题
 */

import { swingPointsTool } from '../src/infrastructure/tools/invest/swing-points-tool.js';

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('🔍 K线数据问题诊断');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

async function testSwingPoints(symbol: string, minChange: number = 5) {
  console.log(`\n📊 测试股票: ${symbol}`);
  console.log(`   波动阈值: ${minChange}%`);

  try {
    const startTime = Date.now();
    const result = await swingPointsTool.execute('test-swing', {
      symbol,
      min_change: minChange
    });
    const duration = Date.now() - startTime;

    const text = result.content[0].text;

    // 检查是否有错误
    if (text.includes('K线数据不足')) {
      console.log(`   ❌ K线数据不足 (${duration}ms)`);
      console.log(`   ${text.split('\n')[0]}`);
      return { success: false, error: 'insufficient_data', duration };
    } else if (text.includes('失败')) {
      console.log(`   ❌ 执行失败 (${duration}ms)`);
      console.log(`   ${text.substring(0, 200)}`);
      return { success: false, error: 'execution_failed', duration };
    } else {
      // 解析成功结果
      const klineMatch = text.match(/(\d+)\s*根K线/);
      const pointsMatch = text.match(/共\s*(\d+)\s*个/);
      const tradesMatch = text.match(/交易次数:\s*(\d+)/);

      console.log(`   ✅ 分析成功 (${duration}ms)`);
      if (klineMatch) console.log(`   K线数量: ${klineMatch[1]}根`);
      if (pointsMatch) console.log(`   拐点数量: ${pointsMatch[1]}个`);
      if (tradesMatch) console.log(`   交易次数: ${tradesMatch[1]}笔`);

      return {
        success: true,
        duration,
        klines: klineMatch ? parseInt(klineMatch[1]) : 0,
        points: pointsMatch ? parseInt(pointsMatch[1]) : 0
      };
    }
  } catch (error) {
    console.log(`   ❌ 异常: ${error instanceof Error ? error.message : String(error)}`);
    return { success: false, error: 'exception', duration: 0 };
  }
}

async function main() {
  const testCases = [
    { symbol: '600519', name: '贵州茅台', expected: 'success' },
    { symbol: '000001', name: '平安银行', expected: 'success' },
    { symbol: '600000', name: '浦发银行', expected: 'success' },
    { symbol: '000858', name: '五粮液', expected: 'success' },
    { symbol: '999999', name: '不存在的股票', expected: 'fail' },
  ];

  console.log('📋 测试计划:');
  testCases.forEach((tc, i) => {
    console.log(`  ${i + 1}. ${tc.symbol} (${tc.name}) - 预期: ${tc.expected}`);
  });

  console.log('\n' + '─'.repeat(80));
  console.log('开始测试...\n');

  const results = [];
  for (const testCase of testCases) {
    const result = await testSwingPoints(testCase.symbol);
    results.push({ ...testCase, ...result });
    await new Promise(resolve => setTimeout(resolve, 500)); // 避免请求过快
  }

  console.log('\n' + '━'.repeat(80));
  console.log('📊 测试总结\n');

  const successful = results.filter(r => r.success);
  const failed = results.filter(r => !r.success);

  console.log(`总测试数: ${results.length}`);
  console.log(`✅ 成功: ${successful.length}`);
  console.log(`❌ 失败: ${failed.length}\n`);

  if (failed.length > 0) {
    console.log('失败详情:');
    failed.forEach(r => {
      console.log(`  • ${r.symbol} (${r.name}): ${r.error || 'unknown'}`);
    });
  }

  console.log('\n💡 诊断结论:');

  if (successful.length === 0) {
    console.log('  ⚠️  所有测试都失败，可能原因:');
    console.log('     1. 后端服务连接问题');
    console.log('     2. 数据库中完全没有K线数据');
    console.log('     3. API路由配置错误');
  } else if (failed.some(r => r.expected === 'success' && !r.success)) {
    console.log('  ⚠️  部分预期成功的股票失败:');
    const unexpectedFails = failed.filter(r => r.expected === 'success');
    unexpectedFails.forEach(r => {
      console.log(`     • ${r.symbol}: 可能是K线数据缺失或日期范围不足`);
    });
  } else {
    console.log('  ✅ 测试符合预期，系统正常工作');
  }

  console.log('\n📝 优化建议:');
  console.log('  1. 在工具中添加更友好的错误提示（区分不同失败原因）');
  console.log('  2. 提供fallback机制：数据不足时自动扩大日期范围');
  console.log('  3. 返回可用的日期范围建议');
  console.log('  4. 添加数据源健康检查API');

  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
}

main().catch(console.error);
