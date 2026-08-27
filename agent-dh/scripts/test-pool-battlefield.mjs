#!/usr/bin/env node
/**
 * M2-3 pool_battlefield 工具测试
 * 测试是否还存在 TypeError
 */

import { QuantsysV2Client } from '../quantsys-v2-client/src/client.js';

async function testPoolBattlefield() {
  const client = new QuantsysV2Client({
    baseURL: 'http://localhost:5001',
    timeout: 30000,
  });

  console.log('=== M2-3 pool_battlefield 测试 ===\n');

  try {
    // 测试 Pool 27（高 ROE 池）
    console.log('1. 测试 Pool 27...');
    const result27 = await client.getPoolBattlefield({ pool_id: 27 });
    console.log('✅ Pool 27 成功');
    console.log('   - battlefield_score:', result27.battlefield_score);
    console.log('   - game_phase:', result27.game_phase);
    console.log('   - data_quality:', result27.data_quality);
    console.log('');

    // 测试 Pool 35（低估值池）
    console.log('2. 测试 Pool 35...');
    const result35 = await client.getPoolBattlefield({ pool_id: 35 });
    console.log('✅ Pool 35 成功');
    console.log('   - battlefield_score:', result35.battlefield_score);
    console.log('   - game_phase:', result35.game_phase);
    console.log('   - data_quality:', result35.data_quality);
    console.log('');

    // 测试不存在的 Pool
    console.log('3. 测试不存在的 Pool 999...');
    try {
      await client.getPoolBattlefield({ pool_id: 999 });
      console.log('❌ 应该报错但没有');
    } catch (error) {
      console.log('✅ 正确报错:', error.message);
    }
    console.log('');

    console.log('=== 所有测试通过 ===');
    console.log('结论: pool_battlefield 工具正常工作，无 TypeError');

  } catch (error) {
    console.error('❌ 测试失败:', error.message);
    console.error('Stack:', error.stack);
    process.exit(1);
  }
}

testPoolBattlefield();
