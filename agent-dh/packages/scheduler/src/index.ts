import { Context, Service } from '@deepseek-ai/cordis';
import z from '@deepseek-ai/schemastery';
import { defineTool } from '@deepseek-ai/dsh-tools';
import { AgentOSClient } from '@pi-investment/agent-os-client';

export interface Config {
  agentOS?: {
    baseURL?: string;
    agentId?: string;
  };
}

/**
 * Scheduler Plugin for Agent-DH
 *
 * Task scheduling via Agent OS.
 */
export default class SchedulerPlugin extends Service {
  static inject = ['tools'];
  static Config = z.object({
    agentOS: z.object({
      baseURL: z.string().default('http://localhost:8080'),
      agentId: z.string().default('agent-dh'),
    }).default({} as any),
  }).default({} as any)

  private aos: AgentOSClient;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'scheduler');
    this.aos = new AgentOSClient({
      baseURL: config.agentOS?.baseURL || 'http://localhost:8080',
      agentId: config.agentOS?.agentId || 'agent-dh',
    });
    this.registerTools();
  }

  private registerTools() {
    const { ctx, aos } = this;

    // 调度器管理
    ctx.tools.register(defineTool({
      name: 'scheduler_manage',
      description: '管理定时任务：列出、创建、启用、禁用、删除、手动触发。定时任务是 Agent 自主运行的基础（如每日 02:00 刷新股票池、09:00 盘前扫描信号）。注意：当前仅 list/create/trigger 完整可用，enable/disable/delete 的后端接口尚未完全实现。',
      parameters: {
        action: {
          type: 'string',
          description: '操作类型。list：列出所有任务（只读）；create：创建任务（需同时传 name、cron、command）；trigger：立即手动触发一次（需传 task_id）；enable/disable/delete：启停/删除（需传 task_id，后端尚未完全实现）',
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
      timeoutMs: 10000,
      execute: async (args: any) => {
        switch (args.action) {
          case 'list':
            return aos.scheduler.listTasks() as any;
          case 'create':
            return aos.scheduler.registerTask({
              name: args.name,
              owner: aos['agentId'] || 'agent-dh',
              cron: args.cron,
              command: args.command,
            }) as any;
          case 'trigger':
            return aos.scheduler.triggerTask({ task_id: args.task_id }) as any;
          default:
            return { action: args.action, task_id: args.task_id, note: 'Operation not fully implemented' } as any;
        }
      },
    } as any));
  }
}
