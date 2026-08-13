/**
 * Task Registration - Register agent tasks to Agent OS Scheduler
 *
 * Agent 启动时自动注册所有定时任务到 Agent OS
 */

import * as AgentOS from '../../infrastructure/agent-os/agent-os-cli.js';

export interface TaskDefinition {
  name: string;
  schedule: string;  // Cron 表达式
  description: string;
  prompt: string;  // Agent 执行任务时的提示词
  enabled?: boolean;
}

/**
 * Agent 的定时任务配置
 */
export const AGENT_TASKS: TaskDefinition[] = [
  {
    name: 'daily_recall_audit',
    schedule: '0 2 * * *',  // 每天 02:00
    description: 'Daily memory recall and audit',
    prompt: 'Review and audit the memory system. Check for outdated entries, validate important memories, and summarize recent learnings.',
    enabled: true,
  },
  {
    name: 'market_open_scan',
    schedule: '0 9 * * 1-5',  // 工作日 09:00
    description: 'Scan for buy signals before market opens',
    prompt: 'Scan all stock pools for buy signals. Analyze market conditions and prepare buy recommendations for today.',
    enabled: true,
  },
  {
    name: 'market_close_review',
    schedule: '30 15 * * 1-5',  // 工作日 15:30
    description: 'Analyze performance after market closes',
    prompt: 'Review today\'s market performance. Analyze portfolio changes, calculate returns, and adjust positions if needed.',
    enabled: true,
  },
  {
    name: 'weekly_pool_refresh',
    schedule: '0 20 * * 6',  // 每周六 20:00
    description: 'Weekly stock pool refresh and validation',
    prompt: 'Refresh all dynamic stock pools. Validate screening criteria, remove underperforming stocks, and add new candidates.',
    enabled: true,
  },
];

/**
 * Register all tasks to Agent OS Scheduler
 */
export async function registerTasksToOS(webhookUrl: string, agentId: string = 'fin-agent'): Promise<void> {
  console.log('[Task Registration] Starting task registration to Agent OS...');

  const results: { name: string; id?: string; error?: string }[] = [];

  for (const task of AGENT_TASKS) {
    if (!task.enabled) {
      console.log(`[Task Registration] Skipping disabled task: ${task.name}`);
      continue;
    }

    try {
      // 构造 webhook 调用命令
      const webhookPayload = {
        task: task.name,
        prompt: task.prompt,
      };

      const command = `curl -X POST "${webhookUrl}" ` +
        `-H "Content-Type: application/json" ` +
        `-d '${JSON.stringify(webhookPayload).replace(/'/g, "\\'")}'`;

      // 注册任务到 Agent OS
      const taskId = await AgentOS.Scheduler.register({
        name: task.name,
        description: task.description,
        schedule: task.schedule,
        command: command,
        enabled: true,
        owner: agentId,
      });

      console.log(`✓ Registered task: ${task.name} (ID: ${taskId})`);
      results.push({ name: task.name, id: taskId });
    } catch (error: any) {
      console.error(`✗ Failed to register task: ${task.name}`, error.message);
      results.push({ name: task.name, error: error.message });
    }
  }

  // 汇总结果
  const successful = results.filter(r => r.id).length;
  const failed = results.filter(r => r.error).length;

  console.log(`[Task Registration] Complete: ${successful} succeeded, ${failed} failed`);

  if (failed > 0) {
    console.warn('[Task Registration] Some tasks failed to register. Check logs above.');
  }
}

/**
 * Unregister all tasks from Agent OS Scheduler
 * (用于 agent 关闭或重新注册时清理)
 */
export async function unregisterTasksFromOS(): Promise<void> {
  console.log('[Task Registration] Unregistering tasks from Agent OS...');

  try {
    // 获取所有任务
    const tasks = await AgentOS.Scheduler.list({ enabledOnly: false });

    // 过滤出我们注册的任务
    const ourTasks = tasks.filter(t =>
      AGENT_TASKS.some(def => def.name === t.name)
    );

    if (ourTasks.length === 0) {
      console.log('[Task Registration] No tasks to unregister');
      return;
    }

    // 删除任务
    for (const task of ourTasks) {
      try {
        await AgentOS.Scheduler.deleteTask(task.id);
        console.log(`✓ Unregistered task: ${task.name}`);
      } catch (error: any) {
        console.error(`✗ Failed to unregister task: ${task.name}`, error.message);
      }
    }

    console.log('[Task Registration] Unregistration complete');
  } catch (error: any) {
    console.error('[Task Registration] Failed to unregister tasks:', error.message);
  }
}

/**
 * List registered tasks from Agent OS
 */
export async function listRegisteredTasks(): Promise<AgentOS.Task[]> {
  try {
    const tasks = await AgentOS.Scheduler.list({ enabledOnly: false, stats: true });

    // 过滤出我们注册的任务
    return tasks.filter(t =>
      AGENT_TASKS.some(def => def.name === t.name)
    );
  } catch (error: any) {
    console.error('[Task Registration] Failed to list tasks:', error.message);
    return [];
  }
}
