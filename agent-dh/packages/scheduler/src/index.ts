import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';

export interface Config {
  agentOS?: {
    baseURL?: string;
    agentId?: string;
  };
}

interface TaskLike {
  id: string;
  name: string;
  [key: string]: any;
}

/**
 * Scheduler Plugin for Agent-DH
 *
 * Task scheduling via Agent OS Scheduler API (/api/v1/scheduler).
 * Self-contained: uses the global fetch API, no client dependency.
 */
export default class SchedulerPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    agentOS: z.object({
      baseURL: z.string().default('http://localhost:8080'),
      agentId: z.string().default('agent-dh'),
    }).default({} as any),
  }).default({} as any)

  private baseURL: string;
  private owner: string;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'scheduler');
    this.baseURL = config.agentOS?.baseURL || 'http://localhost:8080';
    this.owner = config.agentOS?.agentId || 'agent-dh';
    this.registerTools();
  }

  private async request<T>(method: 'GET' | 'POST' | 'PUT' | 'DELETE', path: string, body?: any): Promise<T> {
    const response = await fetch(`${this.baseURL}${path}`, {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!response.ok) {
      const text = await response.text().catch(() => '');
      throw new Error(`Agent OS scheduler ${method} ${path} -> HTTP ${response.status}: ${text.slice(0, 200)}`);
    }
    return response.json() as Promise<T>;
  }

  private registerTools() {
    const { ctx } = this;
    const api = (p: string) => `/api/v1/scheduler${p}`;

    // 调度器管理
    ctx.tools.register(defineTool({
      name: 'scheduler_manage',
      description: '管理定时任务：列出、创建、启用、禁用、删除、手动触发。定时任务是 Agent 自主运行的基础（如每日 02:00 刷新股票池、09:00 盘前扫描信号）。',
      parameters: {
        action: {
          type: 'string',
          description: '操作类型。list：列出所有任务（只读）；create：创建任务（需同时传 name、cron、command）；trigger：立即手动触发一次（需传 task_id）；enable：启用任务（需传 task_id）；disable：禁用任务（需传 task_id）；delete：删除任务（需传 task_id，不可恢复）',
          enum: ['list', 'create', 'enable', 'disable', 'delete', 'trigger'],
          required: true,
        },
        task_id: {
          type: 'string',
          description: '任务ID，trigger/enable/disable/delete 时必填，通过 action=list 获取',
        },
        name: {
          type: 'string',
          description: '任务名称，create 时必填，如 "每日早盘扫描"',
        },
        cron: {
          type: 'string',
          description: 'cron 表达式，create 时必填。如 "0 9 * * 1-5"（工作日9点）、"0 2 * * *"（每天凌晨2点）',
        },
        command: {
          type: 'string',
          description: '执行命令，create 时必填，如 pool_refresh、signal_scan、report_generate',
        },
      },
      output: {
        schema: {
          type: 'object',
          properties: {
            success: { type: 'boolean', description: '是否成功' },
            action: { type: 'string', description: '执行的操作' },
            tasks: { type: 'array', description: '任务列表（list时）' },
            task_id: { type: 'string', description: '任务ID' },
            message: { type: 'string', description: '结果消息' },
          },
          additionalProperties: true,
        },
        render: (_args: any, value: any) => [{
          type: 'text',
          text: JSON.stringify(value, null, 2),
        }],
      },
      timeoutMs: 20000,
      execute: async (args: any) => {
        switch (args.action) {
          case 'list': {
            const result = await this.request<{ tasks: TaskLike[]; count: number }>('GET', api('/tasks'));
            return { success: true, action: 'list', tasks: result.tasks, count: result.count } as any;
          }
          case 'create': {
            if (!args.name || !args.cron || !args.command) {
              return { success: false, action: 'create', message: 'create 需要同时提供 name、cron、command' } as any;
            }
            const task = await this.request<TaskLike>('POST', api('/tasks'), {
              name: args.name,
              owner: this.owner,
              // 服务端要求 6 段 cron（秒 分 时 日 月 周），5 段自动补秒
              cron: args.cron.trim().split(/\s+/).length === 5 ? `0 ${args.cron.trim()}` : args.cron.trim(),
              command: args.command,
              // 服务端 DTO 要求 timeout >= 1，缺省补 60 秒
              timeout: 60,
              enabled: true,
            });
            return { success: true, action: 'create', task_id: task.id, task, message: `任务「${task.name}」已创建` } as any;
          }
          case 'trigger': {
            if (!args.task_id) return { success: false, action: 'trigger', message: '缺少 task_id' } as any;
            const run = await this.request<any>('POST', api(`/tasks/${encodeURIComponent(args.task_id)}/trigger`));
            return { success: true, action: 'trigger', task_id: args.task_id, run, message: '任务已触发' } as any;
          }
          case 'enable': {
            if (!args.task_id) return { success: false, action: 'enable', message: '缺少 task_id' } as any;
            const result = await this.request<{ message: string }>('POST', api(`/tasks/${encodeURIComponent(args.task_id)}/resume`));
            return { success: true, action: 'enable', task_id: args.task_id, message: result.message } as any;
          }
          case 'disable': {
            if (!args.task_id) return { success: false, action: 'disable', message: '缺少 task_id' } as any;
            const result = await this.request<{ message: string }>('POST', api(`/tasks/${encodeURIComponent(args.task_id)}/pause`));
            return { success: true, action: 'disable', task_id: args.task_id, message: result.message } as any;
          }
          case 'delete': {
            if (!args.task_id) return { success: false, action: 'delete', message: '缺少 task_id' } as any;
            const result = await this.request<{ message: string }>('DELETE', api(`/tasks/${encodeURIComponent(args.task_id)}`));
            return { success: true, action: 'delete', task_id: args.task_id, message: result.message } as any;
          }
          default:
            return { success: false, action: args.action, message: `未知操作: ${args.action}` } as any;
        }
      },
    } as any));
  }
}
