#!/usr/bin/env tsx
/**
 * 手动注册任务到 Agent OS 的脚本
 * 用于测试和调试任务注册流程
 */
import { registerTasksToAgentOS } from '../src/core/bootstrap/agent-os-task-registration.js';
import { initializeAgentOS } from '../src/infrastructure/agent-os/client.js';

async function main() {
  const args = process.argv.slice(2);
  const force = args.includes('--force');
  const webhookBaseUrl = process.env.AGENT_WEBHOOK_BASE_URL || 'http://localhost:3002';

  console.log('🚀 Agent OS 任务注册工具\n');
  console.log('配置:');
  console.log(`  - Webhook Base URL: ${webhookBaseUrl}`);
  console.log(`  - Force Update: ${force ? 'Yes' : 'No'}\n`);

  try {
    // 初始化 Agent OS 客户端
    console.log('🔌 正在连接 Agent OS...');
    await initializeAgentOS();
    console.log('✅ Agent OS 连接成功\n');

    // 注册任务
    console.log('📝 正在注册任务...');
    const { summary, results } = await registerTasksToAgentOS({
      webhookBaseUrl,
      force,
    });

    // 打印汇总
    console.log('\n📊 注册结果汇总:');
    console.log(`  - 总任务数: ${summary.total}`);
    console.log(`  - 创建: ${summary.created}`);
    console.log(`  - 更新: ${summary.updated}`);
    console.log(`  - 跳过: ${summary.skipped}`);
    console.log(`  - 失败: ${summary.failed}\n`);

    // 打印详细结果
    console.log('📋 详细结果:');
    results.forEach((result) => {
      const statusIcon = {
        created: '✓',
        updated: '↻',
        skipped: '⊘',
        failed: '✗',
      }[result.status];

      const statusColor = {
        created: '\x1b[32m', // green
        updated: '\x1b[33m', // yellow
        skipped: '\x1b[90m', // gray
        failed: '\x1b[31m',  // red
      }[result.status];

      const resetColor = '\x1b[0m';

      console.log(`  ${statusIcon} ${statusColor}${result.task}${resetColor} - ${result.status}`);
      if (result.id) {
        console.log(`    ID: ${result.id}`);
      }
      if (result.error) {
        console.log(`    Error: ${result.error}`);
      }
    });

    console.log('\n✅ 任务注册完成');

    if (summary.failed > 0) {
      process.exit(1);
    }
  } catch (error) {
    console.error('\n❌ 任务注册失败:', error);
    process.exit(1);
  }
}

main();
