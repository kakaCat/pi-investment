/**
 * 初始化 Agent AI 决策任务
 */
import { getSchedulerRuntime } from './scheduler-runtime.js';
import { createAgentDecisionTasks } from './tasks/agent-decision-tasks.js';

export async function initAgentDecisionTasks() {
  console.log('\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
  console.log('🤖 初始化 Agent AI 决策任务');
  console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

  try {
    const { service, store } = await getSchedulerRuntime();

    // 创建 AI 决策任务
    const tasks = createAgentDecisionTasks();
    const now = new Date().toISOString();

    console.log(`📋 创建 ${tasks.length} 个 Agent AI 决策任务...\n`);

    for (const taskTemplate of tasks) {
      // 检查是否已存在
      const existingTasks = await store.listTasks();
      const exists = existingTasks.find((t: any) => t.name === taskTemplate.name && !t.deletedAt);

      if (exists) {
        console.log(`  ⊙ 任务已存在: ${taskTemplate.name}`);
        continue;
      }

      // 创建任务
      const task = await store.createTask({
        id: `task-${taskTemplate.name}-${Date.now()}`,
        ...taskTemplate,
        createdAt: now,
        updatedAt: now
      });

      console.log(`  ✅ 已创建: ${task.name}`);
      console.log(`     调度: ${task.scheduleExpr}`);
      console.log(`     类型: agent_turn (AI 决策)`);
      console.log('');
    }

    // 重新加载任务
    await service.reloadTasks();
    console.log('✅ 任务已加载到调度器\n');

    // 显示任务摘要
    const summaries = await service.listTaskSummaries();
    const agentTasks = summaries.filter(s =>
      ['morning_ai_analysis', 'realtime_quick_check', 'daily_ai_review', 'weekly_evolution', 'weekly_memory_distill'].includes(s.name)
    );

    console.log('📊 Agent AI 决策任务摘要:\n');
    for (const summary of agentTasks) {
      if ((summary as any).deletedAt) continue;

      console.log(`  • ${summary.name}`);
      console.log(`    状态: ${summary.enabled ? '✅ 启用' : '⏸️  禁用'}`);
      console.log(`    调度: ${summary.scheduleExpr}`);
      console.log(`    下次运行: ${summary.nextRunAt ? new Date(summary.nextRunAt).toLocaleString('zh-CN') : '无'}`);
      console.log('');
    }

    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━');
    console.log('✅ Agent AI 决策任务初始化完成');
    console.log('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n');

    console.log('💡 提示:');
    console.log('  - 这些任务会唤醒 Agent AI 自主决策');
    console.log('  - Agent 会使用工具获取数据并做出判断');
    console.log('  - 数据更新由 quantsys-v2 调度器负责');
    console.log('  - 任务执行日志会记录 Agent 的决策过程\n');

  } catch (error) {
    console.error('\n❌ Agent AI 决策任务初始化失败:', error);
    throw error;
  }
}
