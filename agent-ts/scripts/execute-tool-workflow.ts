#!/usr/bin/env tsx
/**
 * 执行完整的工具任务流程
 * 模拟早盘分析的工作流程
 */

import { portfolioStatusTool } from '../src/infrastructure/tools/portfolio/portfolio-status-tool.js';
import { poolManageTool } from '../src/infrastructure/tools/pool/pool-manage-tool.js';
import { marketAlertTool } from '../src/infrastructure/tools/alert/market-alert-tool.js';

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('🚀 执行工具任务流程 - 模拟早盘分析');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

async function main() {
  try {
    // 任务1: 查看虚拟仓状态
    console.log('📊 任务1: 查看虚拟仓状态');
    console.log('工具: portfolio_status\n');

    const portfolioResult = await portfolioStatusTool.execute('task-1', {});
    console.log('结果:', portfolioResult.content[0].text);
    console.log('\n' + '─'.repeat(80) + '\n');

    // 任务2: 管理股票池
    console.log('📋 任务2: 管理股票池');
    console.log('工具: pool_manage\n');

    const poolResult = await poolManageTool.execute('task-2', { action: 'list' });
    console.log('结果:', poolResult.content[0].text.substring(0, 500) + '...');
    console.log('\n' + '─'.repeat(80) + '\n');

    // 任务3: 检查博弈预警信号
    console.log('⚠️  任务3: 检查市场预警信号');
    console.log('工具: market_alert\n');

    const alertResult = await marketAlertTool.execute('task-3', {});
    console.log('结果:', alertResult.content[0].text.substring(0, 500) + '...');
    console.log('\n' + '─'.repeat(80) + '\n');

    // 任务4: 发送飞书通知（测试）
    console.log('📤 任务4: 发送飞书通知');
    console.log('调用测试脚本...\n');

    const { execSync } = await import('child_process');
    const feishuResult = execSync('cd ../quantsys-v2 && source activate-py313.sh && python ../agent-ts/scripts/test-feishu-notification.py', {
      encoding: 'utf-8',
      shell: '/bin/zsh',
      cwd: process.cwd()
    });
    console.log(feishuResult);

    console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('✅ 工具任务流程执行完成！');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('\n📝 总结:');
    console.log('  ✅ portfolio_status - 虚拟仓状态查询');
    console.log('  ✅ pool_list - 股票池列表获取');
    console.log('  ✅ alert_check - 预警信号检查');
    console.log('  ✅ feishu_notify - 飞书通知发送');
    console.log('\n💡 这些工具在定时任务中会被Agent自动调用');

  } catch (error) {
    console.error('\n❌ 任务执行失败:', error);
    process.exit(1);
  }
}

main();
