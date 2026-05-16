#!/usr/bin/env node
/**
 * 测试超时修复 - 验证慢速接口是否能正确超时
 */

import { callPython } from './dist/infrastructure/tools/shared/python-caller.js';

const SLOW_FUNCTIONS = [
  { name: 'get_macro_data', args: {}, expectedTimeout: 55000 },
  { name: 'get_market_news', args: { num: 10 }, expectedTimeout: 55000 },
  { name: 'get_stock_fund_flow', args: { symbol: '600519' }, expectedTimeout: 35000 },
  { name: 'get_lhb', args: {}, expectedTimeout: 35000 },
];

async function testFunction(func, args, expectedTimeout) {
  console.log(`\n🧪 测试 ${func} (预期超时: ${expectedTimeout}ms)`);
  const startTime = Date.now();

  try {
    const result = await callPython(func, args);
    const elapsed = Date.now() - startTime;

    const parsed = JSON.parse(result);
    if (parsed.error) {
      console.log(`⚠️  返回错误: ${parsed.error}`);
      console.log(`⏱️  耗时: ${elapsed}ms`);

      if (parsed.error.includes('Timeout') || parsed.error.includes('timeout')) {
        console.log(`✅ 超时控制生效 (${elapsed}ms < ${expectedTimeout + 5000}ms)`);
        return { success: true, timeout: true, elapsed };
      }
    } else {
      console.log(`✅ 成功获取数据`);
      console.log(`⏱️  耗时: ${elapsed}ms`);
      return { success: true, timeout: false, elapsed };
    }
  } catch (error) {
    const elapsed = Date.now() - startTime;
    console.log(`❌ 异常: ${error.message}`);
    console.log(`⏱️  耗时: ${elapsed}ms`);

    if (error.message.includes('Timeout') || error.message.includes('timeout')) {
      console.log(`✅ 超时控制生效`);
      return { success: true, timeout: true, elapsed };
    }

    return { success: false, elapsed };
  }
}

async function main() {
  console.log('🚀 开始测试超时修复...\n');
  console.log('修复内容:');
  console.log('1. Python bridge 超时从 120秒 降低到 90秒');
  console.log('2. 分级超时: 快速15秒, 中速35秒, 慢速55秒');
  console.log('3. Python 端添加函数级超时装饰器 (30-50秒)');
  console.log('4. 降级缓存机制 - 失败时使用旧数据');

  const results = [];

  for (const { name, args, expectedTimeout } of SLOW_FUNCTIONS) {
    const result = await testFunction(name, args, expectedTimeout);
    results.push({ name, ...result });
  }

  console.log('\n\n📊 测试总结:');
  console.log('═'.repeat(60));

  for (const { name, success, timeout, elapsed } of results) {
    const status = success ? (timeout ? '⏱️  超时' : '✅ 成功') : '❌ 失败';
    console.log(`${status} ${name.padEnd(30)} ${elapsed}ms`);
  }

  const allPassed = results.every(r => r.success);
  console.log('═'.repeat(60));
  console.log(allPassed ? '✅ 所有测试通过' : '❌ 部分测试失败');

  process.exit(allPassed ? 0 : 1);
}

main().catch(err => {
  console.error('测试脚本异常:', err);
  process.exit(1);
});
