#!/usr/bin/env tsx
/**
 * 验证 Memory Distill Task 完整流程
 * 设计：docs/superpowers/plans/2026-08-12-execution-tickets.md T2（W1.5b）
 *
 * 用法：tsx scripts/verify-distill-task.ts
 */

import { runQuantV2 } from '../src/infrastructure/adapters/quant/quant-v2-client.js';

async function main() {
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('📚 Memory Distill Task 验证');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  // Step 1: 获取蒸馏输入
  console.log('第一步：获取蒸馏输入（过去 7 天）...');
  try {
    const inputsResult = await runQuantV2('memory_distill_inputs', { days: 7 });

    if (!inputsResult.ok) {
      console.error('❌ 获取输入失败:', inputsResult.error);
      process.exit(1);
    }

    const inputs = inputsResult.data as any;
    console.log(`✅ 成功获取输入数据:`);
    console.log(`   - Episodes: ${inputs.episodes?.length || 0} 条`);
    console.log(`   - Decisions: ${inputs.decisions?.length || 0} 条`);

    if (inputs.episodes?.length === 0 && inputs.decisions?.length === 0) {
      console.log('\n⚠️  过去 7 天无数据，跳过第二步');
      process.exit(0);
    }

    // Step 2: 模拟蒸馏候选
    console.log('\n第二步：提交蒸馏候选...');

    const candidates = [
      {
        title: '测试规则：验证蒸馏流程',
        content: '触发条件：测试场景\n行动建议：验证 API 工作正常\n预期结果：候选被保存到数据库',
        evidence_ids: inputs.episodes?.[0]?.id ? [inputs.episodes[0].id] :
                      inputs.decisions?.[0]?.id ? [inputs.decisions[0].id] : [],
      },
    ];

    // 只有有证据时才提交
    if (candidates[0].evidence_ids.length === 0) {
      console.log('⚠️  无可用证据 ID，跳过候选提交');
      process.exit(0);
    }

    const candidatesResult = await runQuantV2('memory_distill_candidates', { candidates });

    if (!candidatesResult.ok) {
      console.error('❌ 提交候选失败:', candidatesResult.error);
      process.exit(1);
    }

    const result = candidatesResult.data as any;
    console.log(`✅ 成功提交候选:`);
    console.log(`   - 已保存: ${result.saved || 0} 条`);
    console.log(`   - 已跳过: ${result.skipped || 0} 条`);

    // Step 3: 验证数据库
    console.log('\n第三步：验证数据库记录...');
    console.log('请手动执行以下 SQL 验证：');
    console.log('psql -d quant_investment -c "SELECT id,title,status,source FROM quant.memory_entries WHERE source=\'distiller\' ORDER BY id DESC LIMIT 5;"');

    console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('✅ 验证完成');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  } catch (error) {
    console.error('❌ 验证失败:', error);
    process.exit(1);
  }
}

main();
