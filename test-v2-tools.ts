/**
 * Test script for v2 migrated tools
 * Tests factor_calculate and trade_algo_execute end-to-end
 */

import { factorCalculateTool } from './src/infrastructure/tools/factor/calculate-tool.js';
import { algoExecuteTool } from './src/infrastructure/tools/trade/algo-execute-tool.js';

async function testFactorCalculate() {
  console.log('\n=== Testing factor_calculate ===\n');

  try {
    const result = await factorCalculateTool.execute('test-1', {
      symbol: '600519',
      factors: ['rsi']
    });

    console.log('✅ Factor Calculate Success');
    console.log('Response type:', result.content[0].type);
    console.log('Response length:', result.content[0].text.length, 'chars');
    console.log('\nFormatted output:\n');
    console.log(result.content[0].text);

    return true;
  } catch (error) {
    console.error('❌ Factor Calculate Failed:', error);
    return false;
  }
}

async function testAlgoExecute() {
  console.log('\n=== Testing trade_algo_execute ===\n');

  try {
    const result = await algoExecuteTool.execute('test-2', {
      symbol: '600519',
      side: 'buy',
      quantity: 1000,
      algo: 'TWAP',
      durationMinutes: 30,
      startTime: '09:30:00'
    });

    console.log('✅ Algo Execute Success');
    console.log('Response type:', result.content[0].type);
    console.log('Response length:', result.content[0].text.length, 'chars');
    console.log('\nFormatted output:\n');
    console.log(result.content[0].text);

    return true;
  } catch (error) {
    console.error('❌ Algo Execute Failed:', error);
    return false;
  }
}

async function main() {
  console.log('🧪 Testing v2 Migrated Tools\n');
  console.log('Target: quantsys-v2 API at http://127.0.0.1:5001\n');

  const results = {
    factorCalculate: await testFactorCalculate(),
    algoExecute: await testAlgoExecute()
  };

  console.log('\n=== Test Summary ===\n');
  console.log('factor_calculate:', results.factorCalculate ? '✅ PASS' : '❌ FAIL');
  console.log('trade_algo_execute:', results.algoExecute ? '✅ PASS' : '❌ FAIL');

  const allPassed = Object.values(results).every(r => r);
  console.log('\nOverall:', allPassed ? '✅ ALL TESTS PASSED' : '❌ SOME TESTS FAILED');

  process.exit(allPassed ? 0 : 1);
}

main();
