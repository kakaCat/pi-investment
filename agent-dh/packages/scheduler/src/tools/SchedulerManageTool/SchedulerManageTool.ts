/**
 * SchedulerManageTool - 定时任务管理工具
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type { ToolMetadata, ToolContext, ToolResponse, ValidationResult } from '@pi-investment/core-tool';
import type { AgentOSClient } from '@pi-investment/agent-os-client';
import { schedulerManagePrompt, SchedulerManageParams, SchedulerManageResult } from './prompt';

/**
 * 定时任务管理工具类
 */
export class SchedulerManageTool extends BaseTool<SchedulerManageParams, SchedulerManageResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'scheduler_manage',
    category: 'system',
    version: '1.0.0',
    timeoutMs: 20000,
  };

  protected readonly prompt = schedulerManagePrompt;

  constructor(private osClient: AgentOSClient) {
    super();
  }

  /**
   * Phase 1: 校验参数
   */
  protected validate(args: SchedulerManageParams): ValidationResult {
    // 校验 action
    const validActions = ['list', 'create', 'get', 'update', 'trigger', 'enable', 'disable', 'delete'];
    if (!args.action || !validActions.includes(args.action)) {
      return {
        success: false,
        error: {
          success: false,
          errorType: ErrorType.VALIDATION_ERROR,
          field: 'action',
          issue: `action 必须是: ${validActions.join(', ')}`,
          expected: validActions.join(' | '),
        },
      };
    }

    // 根据不同的 action 校验必需参数
    switch (args.action) {
      case 'create':
        if (!args.name) {
          return {
            success: false,
            error: {
              success: false,
              errorType: ErrorType.VALIDATION_ERROR,
              field: 'name',
              issue: 'create 操作需要提供 name',
              expected: 'string',
            },
          };
        }
        if (!args.cron) {
          return {
            success: false,
            error: {
              success: false,
              errorType: ErrorType.VALIDATION_ERROR,
              field: 'cron',
              issue: 'create 操作需要提供 cron 表达式',
              expected: 'string (cron expression)',
            },
          };
        }
        if (!args.command && !args.webhook_url) {
          return {
            success: false,
            error: {
              success: false,
              errorType: ErrorType.VALIDATION_ERROR,
              field: 'command',
              issue: 'create 操作需要提供 command（或 webhook_url：webhook 驱动任务无需命令）',
              expected: 'string',
            },
          };
        }
        break;

      case 'get':
      case 'update':
      case 'trigger':
      case 'enable':
      case 'disable':
      case 'delete':
        if (!args.task_id) {
          return {
            success: false,
            error: {
              success: false,
              errorType: ErrorType.VALIDATION_ERROR,
              field: 'task_id',
              issue: `${args.action} 操作需要提供 task_id`,
              expected: 'string',
            },
          };
        }
        break;

      case 'list':
        // list 不需要额外参数
        break;
    }

    return { success: true };
  }

  /**
   * Phase 2: 执行任务
   */
  protected async execute(args: SchedulerManageParams, _context: ToolContext): Promise<SchedulerManageResult> {
    const s = this.osClient.scheduler;
    const result: SchedulerManageResult = {
      success: true,
      action: args.action,
    };

    switch (args.action) {
      case 'list': {
        const res = await s.listTasks();
        result.tasks = res.tasks;
        result.count = res.count;
        break;
      }
      case 'create': {
        const task = await s.registerTask({
          name: args.name!,
          owner: args.owner || 'agent-dh',
          cron: args.cron!,
          command: args.command,
          description: args.description,
          enabled: args.enabled ?? true,
          max_retries: args.max_retries,
          retry_delay: args.retry_delay,
          webhook_url: args.webhook_url,
          payload: args.payload,
        } as any);
        result.task = task;
        result.task_id = task.id;
        result.message = `任务「${task.name}」已创建`;
        break;
      }
      case 'get': {
        const task = await s.getTask(args.task_id!);
        result.task = task;
        break;
      }
      case 'update': {
        const task = await s.updateTask(args.task_id!, {
          name: args.name,
          cron: args.cron,
          command: args.command,
          description: args.description,
          enabled: args.enabled,
          max_retries: args.max_retries,
          retry_delay: args.retry_delay,
          retry_count: args.retry_count,
          webhook_url: args.webhook_url,
          payload: args.payload,
        } as any);
        result.task = task;
        result.task_id = args.task_id;
        result.message = args.payload
          ? '任务已更新（payload 已覆盖）'
          : args.webhook_url
            ? '任务已更新（webhook_url 已设置）'
            : '任务已更新';
        break;
      }
      case 'trigger': {
        const res = await s.triggerTask({ task_id: args.task_id! });
        result.task = res;
        result.task_id = args.task_id;
        result.message = '任务已触发';
        break;
      }
      case 'enable': {
        const res = await s.resumeTask(args.task_id!);
        result.task_id = args.task_id;
        result.message = res.message;
        break;
      }
      case 'disable': {
        const res = await s.pauseTask(args.task_id!);
        result.task_id = args.task_id;
        result.message = res.message;
        break;
      }
      case 'delete': {
        const res = await s.deleteTask(args.task_id!);
        result.task_id = args.task_id;
        result.message = res.message;
        break;
      }
    }

    return result;
  }

  /**
   * Phase 3: 包装返回数据
   */
  protected wrap(result: SchedulerManageResult): ToolResponse<SchedulerManageResult> {
    return { success: true, data: result };
  }
}
