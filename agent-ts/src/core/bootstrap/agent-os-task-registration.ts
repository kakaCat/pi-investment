/**
 * Agent OS Task Registration
 * 启动时将所有定时任务注册到 Agent OS
 */
import { getAgentOSClient } from '../../infrastructure/agent-os/client.js';
import { createAgentDecisionTasks } from '../../services/scheduler/tasks/agent-decision-tasks.js';
import { logger } from '../../infrastructure/logging/index.js';

/**
 * Convert standard 5-field cron to Agent OS 6-field cron (adds seconds field)
 * Standard: MIN HOUR DOM MON DOW
 * Agent OS: SEC MIN HOUR DOM MON DOW
 */
function convertCronTo6Field(cron5: string): string {
  const trimmed = cron5.trim();
  const fields = trimmed.split(/\s+/);

  if (fields.length === 5) {
    // Standard 5-field cron, prepend "0" for seconds
    return `0 ${trimmed}`;
  } else if (fields.length === 6) {
    // Already 6-field, return as-is
    logger.info('[TaskRegistration] Cron expression already has 6 fields', { cron: trimmed });
    return trimmed;
  } else {
    // Invalid format
    throw new Error(
      `Invalid cron expression: expected 5 or 6 fields, got ${fields.length}. ` +
      `Expression: "${trimmed}"`
    );
  }
}

interface TaskRegistrationOptions {
  webhookBaseUrl: string;  // agent-ts webhook URL
  force?: boolean;         // 是否强制重新注册
}

interface RegistrationResult {
  task: string;
  status: 'created' | 'updated' | 'skipped' | 'failed';
  id?: string;
  error?: string;
}

/**
 * 注册所有任务到 Agent OS
 */
export async function registerTasksToAgentOS(options: TaskRegistrationOptions) {
  logger.info('[TaskRegistration] Starting task registration to Agent OS', {
    webhookBaseUrl: options.webhookBaseUrl,
  });

  const client = getAgentOSClient();

  // 1. 获取任务模板
  const taskTemplates = createAgentDecisionTasks();

  // 2. 检查已存在的任务
  let existingTasks;
  try {
    const response = await client.scheduler.listTasks();
    existingTasks = response;
  } catch (error) {
    logger.error('[TaskRegistration] Failed to list existing tasks', {
      error: error instanceof Error ? error.message : String(error),
    });
    throw new Error('Failed to list existing tasks from Agent OS');
  }

  const existingTaskMap = new Map(existingTasks.map((t) => [t.name, t]));

  logger.info('[TaskRegistration] Found existing tasks', {
    count: existingTasks.length,
    tasks: existingTasks.map((t) => t.name),
  });

  // 3. 注册或更新任务
  const results: RegistrationResult[] = [];

  for (const template of taskTemplates) {
    try {
      const existingTask = existingTaskMap.get(template.name);

      if (existingTask && !options.force) {
        // 任务已存在，跳过
        logger.info('[TaskRegistration] Task already exists, skipping', {
          task_name: template.name,
        });
        results.push({ task: template.name, status: 'skipped', id: existingTask.id });
        continue;
      }

      // 构建任务请求
      const taskRequest = {
        name: template.name,
        owner: 'fin-agent',
        enabled: template.enabled,
        cron: template.scheduleKind === 'cron' ? convertCronTo6Field(template.scheduleExpr) : undefined,
        webhook_url: `${options.webhookBaseUrl}/api/webhook/agent-os/trigger`,
        payload: template.payload,
        timeout: 3600, // 1小时超时
        retry_count: 0, // Agent OS 控制重试策略
      };

      if (existingTask && options.force) {
        // 更新已存在的任务
        logger.info('[TaskRegistration] Updating existing task', {
          task_name: template.name,
          task_id: existingTask.id,
        });

        await client.scheduler.updateTask(existingTask.id, taskRequest);
        results.push({ task: template.name, status: 'updated', id: existingTask.id });
      } else {
        // 注册新任务
        logger.info('[TaskRegistration] Registering new task', {
          task_name: template.name,
          cron: taskRequest.cron,
        });

        const newTask = await client.scheduler.registerTask(taskRequest);
        results.push({ task: template.name, status: 'created', id: newTask.id });
      }

      logger.info('[TaskRegistration] Task registered successfully', {
        task_name: template.name,
        status: results[results.length - 1].status,
      });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      logger.error('[TaskRegistration] Failed to register task', {
        task_name: template.name,
        error: errorMessage,
        errorDetails: error,
      });

      results.push({
        task: template.name,
        status: 'failed',
        error: errorMessage,
      });
    }
  }

  // 4. 汇总结果
  const summary = {
    total: taskTemplates.length,
    created: results.filter((r) => r.status === 'created').length,
    updated: results.filter((r) => r.status === 'updated').length,
    skipped: results.filter((r) => r.status === 'skipped').length,
    failed: results.filter((r) => r.status === 'failed').length,
  };

  logger.info('[TaskRegistration] Task registration completed', summary);

  return {
    summary,
    results,
  };
}
