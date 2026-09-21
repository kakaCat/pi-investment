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
    const validActions = ['list', 'create', 'get', 'update', 'trigger', 'enable', 'disable', 'delete', 'runs', 'failures'];
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
      case 'runs':
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
        // 2026-09-13（w-a9ec14d7）：把**执行统计**并进任务清单。
        // 之前 list 只返回任务定义（没有 total_runs/last_run_at/last_run_status），
        // 于是"任务没跑 / 上次跑失败了"在 agent 侧完全不可见 —— 实测因此漏看了
        // pre-market-routine 2026-09-11 09:25 的 failed（webhook 不可达）。
        // 服务端早有 GET /api/v1/scheduler/tasks/stats，这里只是没用它。
        try {
          const stats = await s.listTasksWithStats();
          const byId = new Map<string, any>(
            (stats?.tasks || []).map((x: any) => [String(x.id), x])
          );
          result.tasks = (result.tasks || []).map((task: any) => {
            const st = byId.get(String(task.id));
            if (!st) return task;
            return {
              ...task,
              total_runs: st.total_runs,
              last_run_at: st.last_run_at,
              last_run_status: st.last_run_status,
              success_rate: st.success_rate,
              avg_duration_ms: st.avg_duration_ms,
            };
          });
          result.stats_available = true;
        } catch (e: any) {
          // 统计拿不到**不让 list 整体失败**，但必须显式标注：静默降级会让人以为"一切都好"
          result.stats_available = false;
          result.stats_error = String(e?.message || e).slice(0, 160);
        }
        break;
      }
      case 'runs': {
        const res = await s.listExecutions({ task_id: args.task_id!, limit: args.limit ?? 20 });
        result.executions = res.executions;
        result.count = res.count;
        result.task_id = args.task_id!;
        break;
      }
      case 'failures': {
        // 跨任务扫一遍"最近跑失败"的任务并带出 error 文本 —— 这正是上午漏掉的那类信息。
        const stats = await s.listTasksWithStats();
        const bad = (stats?.tasks || []).filter(
          (x: any) => Number(x.total_runs || 0) > 0 &&
                      String(x.last_run_status || '').toLowerCase() !== 'success'
        );
        const out: any[] = [];
        for (const x of bad.slice(0, args.limit ?? 10)) {
          let err = '';
          try {
            const r = await s.listExecutions({ task_id: String(x.id), limit: 5 });
            const failed = (r.executions || []).find(
              (y: any) => String(y.status || '').toLowerCase() !== 'success'
            );
            err = String(failed?.error || '').slice(0, 240);
          } catch {
            // 单个任务取明细失败不影响整体扫描（下面 error 字段留空即代表"取不到"）
          }
          out.push({
            name: x.name, id: x.id, last_run_at: x.last_run_at,
            last_run_status: x.last_run_status, success_rate: x.success_rate,
            total_runs: x.total_runs, error: err,
          });
        }
        result.failures = out;
        result.count = out.length;
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
          agent_line: args.agent_line,
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
          agent_line: args.agent_line,
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