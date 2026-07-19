#!/usr/bin/env tsx
/**
 * 执行工具任务 - 测试核心投资工具
 */

import { portfolioStatusTool } from '../src/infrastructure/tools/portfolio/portfolio-status-tool.js';

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('🔧 执行工具任务测试');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

async function main() {
  try {
    // 工具1: 查看虚拟仓状态
    console.log('📊 工具1: portfolio_status - 查看虚拟仓状态');
    const startTime1 = Date.now();
    const result1 = await portfolioStatusTool.execute('test-1', {});
    const duration1 = Date.now() - startTime1;

    console.log(`✅ 执行成功 (${duration1}ms)`);
    console.log('返回数据:');
    console.log(result1.content[0].text);
    console.log('\n' + '─'.repeat(80) + '\n');

    // 工具2: 测试API连接
    console.log('🔌 工具2: 测试quantsys-v2后端连接');
    const startTime2 = Date.now();

    const response = await fetch('http://127.0.0.1:5001/api/health');
    const health = await response.json();
    const duration2 = Date.now() - startTime2;

    console.log(`✅ 后端连接正常 (${duration2}ms)`);
    console.log('健康检查:', JSON.stringify(health, null, 2));
    console.log('\n' + '─'.repeat(80) + '\n');

    // 工具3: 测试飞书通知
    console.log('📤 工具3: feishu_notify - 发送飞书通知');
    const startTime3 = Date.now();

    const { execSync } = await import('child_process');
    const feishuOutput = execSync('cd ../quantsys-v2 && source activate-py313.sh && python ../agent-ts/scripts/test-feishu-notification.py', {
      encoding: 'utf-8',
      shell: '/bin/zsh',
      cwd: process.cwd()
    });
    const duration3 = Date.now() - startTime3;

    console.log(`✅ 飞书通知发送成功 (${duration3}ms)`);
    console.log(feishuOutput);

    console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('✅ 所有工具任务执行完成！');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');

    console.log('\n📝 执行总结:');
    console.log(`  ✅ portfolio_status - ${duration1}ms`);
    console.log(`  ✅ 后端API健康检查 - ${duration2}ms`);
    console.log(`  ✅ feishu_notify - ${duration3}ms`);
    console.log(`  ⏱️  总耗时: ${duration1 + duration2 + duration3}ms`);

    console.log('\n💡 这些工具在自动化任务中的作用:');
    console.log('  • 早盘分析 (09:00): 检查持仓 → 分析市场 → 交易决策 → 发送通知');
    console.log('  • 盘中检查 (每30分钟): 监控预警 → 持仓状态 → 异常处理');
    console.log('  • 每日复盘 (18:00): 绩效评估 → 学习沉淀 → 发送报告');

  } catch (error) {
    console.error('\n❌ 任务执行失败:', error);
    if (error instanceof Error) {
      console.error('错误详情:', error.message);
    }
    process.exit(1);
  }
}

main();
