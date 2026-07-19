#!/usr/bin/env tsx
/**
 * 检查调度器状态
 */
import { getSchedulerRuntime } from '../src/services/scheduler/scheduler-runtime.js';

async function main() {
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('📊 调度器状态检查');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  try {
    const runtime = await getSchedulerRuntime();

    // 1. 检查调度器是否运行
    const isRunning = (runtime.service as any).ticker !== null;
    console.log(`🔍 调度器运行状态: ${isRunning ? '✅ 运行中' : '❌ 未运行'}\n`);

    // 2. 获取所有任务
    const tasks = await runtime.store.listTasks({ includeDeleted: false });
    console.log(`📋 任务总数: ${tasks.length}\n`);

    // 3. 获取任务摘要
    const summaries = await runtime.service.listTaskSummaries();

    console.log('📊 任务详情:\n');
    for (const summary of summaries) {
      if ((summary as any).deletedAt) continue;

      console.log(`  • ${summary.name}`);
      console.log(`    状态: ${summary.enabled ? '✅ 启用' : '⏸️  禁用'}`);
      console.log(`    调度: ${summary.scheduleExpr || '无'}`);
      console.log(`    下次运行: ${summary.nextRunAt ? new Date(summary.nextRunAt).toLocaleString('zh-CN') : '无'}`);

      if (summary.lastRun) {
        console.log(`    上次运行: ${new Date(summary.lastRun.startedAt || summary.lastRun.triggeredAt || '').toLocaleString('zh-CN')}`);
        console.log(`    运行状态: ${summary.lastRun.status}`);
      } else {
        console.log(`    上次运行: 从未运行`);
      }

      console.log('');
    }

    // 4. 查询最近的执行记录
    const recentRuns = await runtime.store.listRuns({ limit: 10 });
    console.log(`📜 最近执行记录 (共 ${recentRuns.length} 条):\n`);

    for (const run of recentRuns) {
      console.log(`  • ${run.taskName}`);
      console.log(`    调度时间: ${new Date(run.scheduledFor).toLocaleString('zh-CN')}`);
      console.log(`    状态: ${run.status}`);
      if (run.startedAt) {
        console.log(`    开始时间: ${new Date(run.startedAt).toLocaleString('zh-CN')}`);
      }
      if (run.finishedAt) {
        console.log(`    结束时间: ${new Date(run.finishedAt).toLocaleString('zh-CN')}`);
        console.log(`    耗时: ${run.durationMs}ms`);
      }
      if (run.error) {
        console.log(`    错误: ${run.error}`);
      }
      console.log('');
    }

    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('✅ 检查完成');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  } catch (error) {
    console.error('❌ 检查失败:', error);
    process.exit(1);
  }
}

main();
