#!/usr/bin/env tsx
/**
 * 手动补发今天错过的早盘分析任务
 */
import { getSchedulerRuntime } from '../src/services/scheduler/scheduler-runtime.js';
import { createSession } from '../src/session-facade.js';

console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
console.log('🔄 补发今日早盘分析任务');
console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

async function main() {
  try {
    const runtime = await getSchedulerRuntime();
    const tasks = await runtime.store.listTasks();

    const morningTask = tasks.find(t => t.name === 'morning_ai_analysis' && !t.deletedAt);

    if (!morningTask) {
      console.error('❌ 未找到早盘分析任务');
      process.exit(1);
    }

    console.log('📋 任务信息:');
    console.log(`  名称: ${morningTask.name}`);
    console.log(`  调度: ${morningTask.scheduleExpr}`);
    console.log(`  状态: ${morningTask.enabled ? '✅ 启用' : '⏸️  禁用'}`);
    console.log('');

    // 获取任务消息
    const message = (morningTask.payload as any).message as string;

    console.log('🚀 开始执行补偿任务...\n');
    console.log('─'.repeat(80));

    // 创建新会话并执行
    const { session } = await createSession({
      cwd: process.cwd()
    });

    await session.prompt(message);

    console.log('\n─'.repeat(80));
    console.log('\n✅ 补偿任务执行完成！');
    console.log('📱 如果配置了飞书通知，应该已经发送到群里');

  } catch (error) {
    console.error('\n❌ 补偿任务执行失败:', error);
    process.exit(1);
  }
}

main();
