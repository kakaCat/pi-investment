#!/usr/bin/env ts-node
/**
 * 手动测试脚本 - 验证 watch_manage 修复
 * 
 * 使用方法:
 *   cd /Users/yunpeng/pi-investment/quantsys-v2-client
 *   npx ts-node test/manual-test-watch-manage.ts
 */

import { QuantsysV2Client } from '../src/client';

async function testParseCondition() {
  console.log('\n=== 测试 parseCondition 方法 ===\n');
  
  const client = new QuantsysV2Client({
    baseURL: 'http://localhost:5001',
    timeout: 10000,
  });

  // 通过反射访问私有方法
  const parseCondition = (client as any).parseCondition.bind(client);

  const testCases = [
    { input: 'price>100', desc: '基本价格条件' },
    { input: 'price > 100', desc: '带空格的价格条件' },
    { input: 'change_pct>=5', desc: '涨跌幅条件' },
    { input: 'volume<1000000', desc: '成交量条件' },
    { input: 'price>99.5', desc: '小数值' },
    { input: 'change_pct>-5', desc: '负数值' },
    { input: '  price  <=  200  ', desc: '前后有空格' },
  ];

  let passed = 0;
  let failed = 0;

  for (const testCase of testCases) {
    try {
      const result = parseCondition(testCase.input);
      console.log(`✓ ${testCase.desc}`);
      console.log(`  输入: "${testCase.input}"`);
      console.log(`  输出: ${JSON.stringify(result, null, 2)}`);
      passed++;
    } catch (error) {
      console.log(`✗ ${testCase.desc}`);
      console.log(`  输入: "${testCase.input}"`);
      console.log(`  错误: ${(error as Error).message}`);
      failed++;
    }
    console.log('');
  }

  // 测试错误情况
  console.log('\n=== 测试错误处理 ===\n');
  
  const invalidCases = [
    { input: 'price', desc: '缺少操作符和值' },
    { input: 'price>', desc: '缺少值' },
    { input: '>100', desc: '缺少字段' },
    { input: 'invalid>100', desc: '不支持的字段' },
    { input: 'price>abc', desc: '值不是数字' },
  ];

  for (const testCase of invalidCases) {
    try {
      parseCondition(testCase.input);
      console.log(`✗ ${testCase.desc} - 应该抛出错误但没有`);
      failed++;
    } catch (error) {
      console.log(`✓ ${testCase.desc}`);
      console.log(`  输入: "${testCase.input}"`);
      console.log(`  错误: ${(error as Error).message}`);
      passed++;
    }
    console.log('');
  }

  console.log(`\n测试总结: ${passed} 通过, ${failed} 失败\n`);
  return { passed, failed };
}

async function testWatchManageCreate() {
  console.log('\n=== 测试 watch_manage 创建规则（需要后端运行） ===\n');
  
  const client = new QuantsysV2Client({
    baseURL: process.env.QUANTSYS_V2_BASE_URL || 'http://localhost:5001',
    timeout: 10000,
  });

  try {
    console.log('尝试创建盯盘规则...');
    const result = await client.manageWatchRule({
      action: 'create',
      name: 'TEST_茅台价格突破2000',
      symbol: '600519',
      condition: 'price>2000'
    });

    console.log('✓ 创建成功！');
    console.log('返回结果:', JSON.stringify(result, null, 2));
    
    // 如果创建成功，尝试删除测试规则
    if (result.success && result.rule_id) {
      console.log(`\n清理测试数据（删除规则 ${result.rule_id}）...`);
      await client.manageWatchRule({
        action: 'delete',
        rule_id: result.rule_id
      });
      console.log('✓ 测试规则已删除');
    }
    
    return true;
  } catch (error: any) {
    if (error.code === 'ECONNREFUSED') {
      console.log('⚠ 后端未运行，跳过集成测试');
      console.log('  提示: 启动后端后再运行此测试');
      return null;
    } else {
      console.log('✗ 创建失败');
      console.log('错误:', error.message);
      if (error.response) {
        console.log('响应状态:', error.response.status);
        console.log('响应数据:', JSON.stringify(error.response.data, null, 2));
      }
      return false;
    }
  }
}

async function main() {
  console.log('\n' + '='.repeat(60));
  console.log('watch_manage 修复验证测试');
  console.log('='.repeat(60));

  // 测试 parseCondition
  const { passed, failed } = await testParseCondition();

  // 测试 watch_manage 集成（如果后端可用）
  const integrationResult = await testWatchManageCreate();

  console.log('\n' + '='.repeat(60));
  console.log('总结');
  console.log('='.repeat(60));
  console.log(`单元测试: ${passed} 通过, ${failed} 失败`);
  if (integrationResult === true) {
    console.log('集成测试: ✓ 通过');
  } else if (integrationResult === false) {
    console.log('集成测试: ✗ 失败');
  } else {
    console.log('集成测试: ⚠ 跳过（后端未运行）');
  }
  console.log('='.repeat(60) + '\n');

  process.exit(failed > 0 || integrationResult === false ? 1 : 0);
}

main().catch((error) => {
  console.error('测试脚本执行失败:', error);
  process.exit(1);
});
