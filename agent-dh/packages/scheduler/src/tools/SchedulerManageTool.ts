/**
 * SchedulerManageTool - 定时任务管理工具（Agent OS Scheduler）
 *
 * 通过共享 AgentOSClient.scheduler (SchedulerClient) 进行：
 *   list   列出所有定时任务
 *   create 注册新任务
 *   get    获取单个任务详情
 *   update 更新任务（部分字段）
 *   trigger 立即触发一次
 *   enable 启用（resume）
 *   disable 禁用（pause）
 *   delete 删除任务
 */

import { BaseTool, ErrorType } from '@pi-investment/core-tool';
import type {
  ToolMetadata,
  ToolContext,
  ToolResponse,
  ValidationResult,
} from '@pi-investment/core-tool';
import type { AgentOSClient } from '@pi-investment/agent-os-client';

export type SchedulerAction =
  | 'list'
  | 'create'
  | 'get'
  | 'update'
  | 'trigger'
  | 'enable'
  | 'disable'
  | 'delete';

export interface SchedulerManageParams {
  action: SchedulerAction;
  task_id?: string;
  name?: string;
  owner?: string;
  description?: string;
  cron?: string;
  command?: string;
  webhook_url?: string;
  payload?: Record<string, any>;
  timeout?: number;
  retry_count?: number;
  enabled?: boolean;
}

export interface SchedulerManageResult {
  action: string;
  success: boolean;
  tasks?: any[];
  task?: any;
  message?: string;
}

const SCHEDULER_ACTIONS: SchedulerAction[] = [
  'list',
  'create',
  'get',
  'update',
  'trigger',
  'enable',
  'disable',
  'delete',
];

const TASK_ID_REQUIRED: SchedulerAction[] = [
  'get',
  'update',
  'trigger',
  'enable',
  'disable',
  'delete',
];

export const schedulerManagePrompt = {
  description:
    '管理 Agent OS 定时任务（调度器）。支持：列出全部任务(list)、注册新任务(create)、查看任务详情(get)、更新任务(update)、立即触发一次(trigger)、启用(enable)、禁用(disable)、删除(delete)。适用于：查看当前有哪些自动任务、新增每日盘前扫描、临时暂停某个任务、手动触发一次补跑。',

  useCases: [
    '查看当前所有定时任务',
    '新增/修改一个定时任务（如每日 09:00 盘前扫描）',
    '临时暂停或恢复某个任务',
    '手动触发一次任务补跑',
  ],

  examples: [
    {
      title: '列出所有定时任务',
      params: { action: 'list' } as SchedulerManageParams,
      expectedResult: '返回任务列表及数量',
    },
    {
      title: '注册每日盘前扫描',
      params: {
        action: 'create',
        name: '盘前扫描',
        owner: 'agent-dh',
        cron: '0 9 * * *',
        command: 'scan_preopen',
      } as SchedulerManageParams,
      expectedResult: '返回新建的任务详情',
    },
  ],

  notes: [
    '💡 cron 使用 5 字段（分 时 日 月 周），服务端会自动补齐秒字段',
    '💡 create 必须提供 name 与 owner',
    '💡 get/update/trigger/enable/disable/delete 必须提供 task_id',
  ],

  relatedTools: ['notification_send', 'window_create'],

  parameters: {
    action: {
      type: 'string',
      description: '操作类型：list/create/get/update/trigger/enable/disable/delete',
      required: true,
      enum: SCHEDULER_ACTIONS,
    },
    task_id: {
      type: 'string',
      description: '任务 ID（get/update/trigger/enable/disable/delete 必填）',
    },
    name: {
      type: 'string',
      description: '任务名称（create 必填；update 可选）',
    },
    owner: {
      type: 'string',
      description: '任务归属（create 必填），如 agent-dh',
    },
    description: {
      type: 'string',
      description: '任务描述',
    },
    cron: {
      type: 'string',
      description: 'Cron 表达式（5 字段：分 时 日 月 周），如 "0 9 * * *"',
      example: '0 9 * * *',
    },
    command: {
      type: 'string',
      description: '任务执行的命令/动作名',
    },
    webhook_url: {
      type: 'string',
      description: '任务触发的回调 URL',
    },
    payload: {
      type: 'object',
      description: '任务附加参数（JSON 对象）',
    },
    timeout: {
      type: 'number',
      description: '超时时间（秒），默认 60',
    },
    retry_count: {
      type: 'number',
      description: '失败重试次数',
    },
    enabled: {
      type: 'boolean',
      description: '是否启用（create 默认 true；update 可改）',
    },
  },

  output: {
    schema: {
      type: 'object',
      properties: {
        action: { type: 'string', description: '执行的操作' },
        success: { type: 'boolean', description: '是否成功' },
        tasks: {
          type: 'array',
          items: { type: 'object', additionalProperties: true },
          description: '任务列表（list 操作返回）',
        },
        task: {
          type: 'object',
          additionalProperties: true,
          description: '任务详情（get/create/update 操作返回）',
        },
        message: { type: 'string', description: '结果说明' },
      },
      additionalProperties: true,
    },
    render: (_args: SchedulerManageParams, value: SchedulerManageResult) => {
      if (!value.success) {
        return [{ type: 'text', text: `❌ ${value.action} 失败：${value.message ?? '未知错误'}` }];
      }
      switch (value.action) {
        case 'list': {
          const tasks = value.tasks ?? [];
          const lines = [`✅ 共 ${tasks.length} 个定时任务\n`];
          for (const t of tasks) {
            lines.push(
              `- **${t.name}** (\`${t.id}\`) ${t.enabled ? '🟢启用' : '⚪禁用'} | ${t.cron ?? t.schedule ?? '-'}`
            );
          }
          return [{ type: 'text', text: lines.join('\n') }];
        }
        case 'get':
        case 'create':
        case 'update': {
          const t = value.task ?? {};
          return [
            {
              type: 'text',
              text: `✅ ${value.action} 成功\n\n- **名称**: ${t.name}\n- **ID**: ${t.id}\n- **状态**: ${t.enabled ? '启用' : '禁用'}\n- **Cron**: ${t.cron ?? t.schedule ?? '-'}\n- **Owner**: ${t.owner ?? '-'}`,
            },
          ];
        }
        default:
          return [{ type: 'text', text: `✅ ${value.action} 成功：${value.message ?? ''}` }];
      }
    },
  },
};

export class SchedulerManageTool extends BaseTool<SchedulerManageParams, SchedulerManageResult> {
  protected readonly metadata: ToolMetadata = {
    name: 'scheduler_manage',
    category: 'scheduler',
    version: '1.0.0',
    timeoutMs: 15000,
  };

  protected readonly prompt = schedulerManagePrompt;

  constructor(private aos: AgentOSClient) {
    super();
  }

  protected validate(args: SchedulerManageParams): ValidationResult {
    if (!args.action || !SCHEDULER_ACTIONS.includes(args.action)) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'action',
        issue: 'action 必须是受支持的操作',
        expected: SCHEDULER_ACTIONS.join(' | '),
        guide: '请选择 list/create/get/update/trigger/enable/disable/delete 之一',
      };
    }

    if (TASK_ID_REQUIRED.includes(args.action) && !args.task_id) {
      return {
        success: false,
        errorType: ErrorType.INPUT_ERROR,
        field: 'task_id',
        issue: `${args.action} 操作必须提供 task_id`,
        expected: '已存在的任务 ID',
        guide: '先用 scheduler_manage(action: list) 获取任务 ID',
      };
    }

    if (args.action === 'create') {
      if (!args.name) {
        return {
          success: false,
          errorType: ErrorType.INPUT_ERROR,
          field: 'name',
          issue: 'create 操作必须提供 name',
          expected: '任务名称字符串',
        };
      }
      if (!args.owner) {
        return {
          success: false,
          errorType: ErrorType.INPUT_EMPTY,
          field: 'owner',
          issue: 'create 操作必须提供 owner',
          expected: '任务归属，如 agent-dh',
        };
      }
    }

    return { success: true };
  }

  protected async execute(
    args: SchedulerManageParams,
    _context: ToolContext
  ): Promise<SchedulerManageResult> {
    const s = this.aos.scheduler;
    const result: SchedulerManageResult = { action: args.action, success: true };

    switch (args.action) {
      case 'list': {
        const res = await s.listTasks();
        result.tasks = res.tasks;
        result.message = `共 ${res.count} 个任务`;
        break;
      }
      case 'create': {
        const task = await s.registerTask({
          name: args.name!,
          owner: args.owner!,
          description: args.description,
          cron: args.cron,
          command: args.command,
          webhook_url: args.webhook_url,
          payload: args.payload,
          timeout: args.timeout,
          retry_count: args.retry_count,
          enabled: args.enabled,
        });
        result.task = task;
        break;
      }
      case 'get': {
        result.task = await s.getTask(args.task_id!);
        break;
      }
      case 'update': {
        const task = await s.updateTask(args.task_id!, {
          name: args.name,
          description: args.description,
          cron: args.cron,
          webhook_url: args.webhook_url,
          payload: args.payload,
          timeout: args.timeout,
          retry_count: args.retry_count,
          enabled: args.enabled,
        });
        result.task = task;
        break;
      }
      case 'trigger': {
        const res = await s.triggerTask({ task_id: args.task_id! });
        result.task = res;
        result.message = '已触发';
        break;
      }
      case 'enable': {
        const res = await s.resumeTask(args.task_id!);
        result.message = res.message;
        break;
      }
      case 'disable': {
        const res = await s.pauseTask(args.task_id!);
        result.message = res.message;
        break;
      }
      case 'delete': {
        const res = await s.deleteTask(args.task_id!);
        result.message = res.message;
        break;
      }
    }

    return result;
  }

  protected wrap(data: SchedulerManageResult): ToolResponse<SchedulerManageResult> {
    return { success: true, data };
  }
}
