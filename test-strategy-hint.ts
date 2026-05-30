#!/usr/bin/env tsx
/**
 * Manual integration test for strategy_id hint functionality
 * Tests that missing strategy_id parameter triggers helpful error with strategy list
 */

import { quantCliTool } from './src/infrastructure/tools/core/quant-cli-tool';

// Test cases: commands that require strategy_id
const testCases = [
  {
    name: 'strategy.backtest',
    input: { command: 'strategy.backtest' }, // missing strategy_id
  },
  {
    name: 'strategy.execute',
    input: { command: 'strategy.execute' }, // missing strategy_id
  },
  {
    name: 'strategy.optimize',
    input: { command: 'strategy.optimize' }, // missing strategy_id
  },
  {
    name: 'signal.generate',
    input: { command: 'signal.generate' }, // missing strategy_id
  },
  {
    name: 'signal.track',
    input: { command: 'signal.track' }, // missing strategy_id
  },
  {
    name: 'signal.history',
    input: { command: 'signal.history' }, // missing strategy_id
  },
];

async function runTests() {
  console.log('🧪 Testing strategy_id hint functionality\n');
  console.log('=' .repeat(80));

  let passCount = 0;
  let failCount = 0;

  for (const testCase of testCases) {
    console.log(`\n📋 Test: ${testCase.name}`);
    console.log('-'.repeat(80));

    try {
      const result = await quantCliTool.execute('test-call-id', testCase.input);

      // Check if error message contains strategy list
      const hasStrategyList = result.includes('可用策略列表') || result.includes('strategy_');
      const hasMissingParam = result.includes('缺少必填参数: strategy_id');

      if (hasMissingParam && hasStrategyList) {
        console.log('✅ PASS: Error message includes strategy list hint');
        console.log(`\nError message preview:\n${result.substring(0, 200)}...`);
        passCount++;
      } else {
        console.log('❌ FAIL: Error message missing expected content');
        console.log(`  - Has "缺少必填参数: strategy_id": ${hasMissingParam}`);
        console.log(`  - Has strategy list: ${hasStrategyList}`);
        console.log(`\nActual message:\n${result}`);
        failCount++;
      }
    } catch (error) {
      console.log('❌ FAIL: Unexpected error');
      console.error(error);
      failCount++;
    }
  }

  console.log('\n' + '='.repeat(80));
  console.log(`\n📊 Test Results: ${passCount} passed, ${failCount} failed`);

  if (failCount === 0) {
    console.log('✅ All tests passed!');
    process.exit(0);
  } else {
    console.log('❌ Some tests failed');
    process.exit(1);
  }
}

runTests().catch(console.error);
