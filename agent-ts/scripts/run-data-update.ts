#!/usr/bin/env tsx
/**
 * 执行数据更新任务
 */
import { runQuantV2 } from '../src/infrastructure/adapters/quant/quant-v2-client.js';

async function main() {
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('🔄 开始执行每日数据更新任务');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  try {
    // 执行数据更新
    console.log('🔄 执行全量数据更新...');
    console.log('   更新范围：all (全部股票)');
    console.log('   更新天数：730天（默认）\n');

    const updateResult = await runQuantV2('data.update', {
      source: 'all',
      days: 730,
      force: false,
      async: false
    });

    if (updateResult.ok) {
      console.log('✅ 数据更新成功！\n');
      console.log('更新结果：');
      const data = (updateResult as any).data;
      if (typeof data === 'string') {
        console.log(data);
      } else {
        console.log(JSON.stringify(data, null, 2));
      }
    } else {
      console.error('❌ 数据更新失败：');
      console.error((updateResult as any).error);
      process.exit(1);
    }

    console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('✅ 每日数据更新任务完成');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  } catch (error) {
    console.error('\n❌ 数据更新任务失败：', error);
    process.exit(1);
  }
}

main();
