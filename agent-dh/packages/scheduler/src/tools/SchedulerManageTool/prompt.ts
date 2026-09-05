/**
 * SchedulerManageTool - 提示词定义
 *
 * 工具描述：管理 Agent OS 定时任务（调度器）
 */

import type { ToolPrompt } from '@pi-investment/core-tool';

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
  cron?: string;
  command?: string;
  description?: string;
  enabled?: boolean;
  max_retries?: number;
  retry_delay?: number;
  retry_count?: number;
  /** 任务负载（create/update 可选）：agent-webhook 任务经 payload.prompt 携带完整指令；quantsys 内部任务经 payload.job_type 指定作业类型 */
  payload?: Record<string, any>;
  /** Webhook 回调地址（create/update 可选）：设置后任务触发改走 HTTP POST，command 不再执行 */
  webhook_url?: string;
}

export interface SchedulerManageResult {
  success: boolean;
  action: string;
  tasks?: any[];
  task?: any;
  count?: number;
  task_id?: string;
  message?: string;
}

/** 任务类型标签（渲染用）：Agent任务(webhook+prompt) / 内部任务(job_type) / Webhook / 脚本命令 */
export function taskKind(task: any): string {
  if (!task) return '—';
  const p = task.payload || {};
  if (task.webhook_url && p.prompt) return '🧠 Agent任务';
  if (p.job_type) return '⚙️ 内部任务';
  if (task.webhook_url) return '🔗 Webhook';
  if (task.command) return '📜 脚本/命令';
  return '—';
}

export const schedulerManagePrompt: ToolPrompt<SchedulerManageParams, SchedulerManageResult> = {
  description:
    '管理 Agent OS 定时任务（调度器）。支持：列出全部任务(list)、注册新任务(create)、查看任务详情(get)、更新任务(update)、立即触发一次(trigger)、启用(enable)、禁用(disable)、删除(delete)。' +
    '适用于：查看当前有哪些自动任务、新增每日盘前扫描、临时暂停某个任务、手动触发一次补跑。' +
    '⚠️ Agent 定时任务（webhook 驱动，本实例 13080/agent-os-trigger）的完整指令存在 payload.prompt：' +
    '改任务要干的事 = action=update + task_id + payload={"prompt":"<新指令>"}；改造 webhook 地址用 webhook_url。' +
    'list 会标出任务类型（Agent任务/Webhook/内部/脚本）。',

  useCases: [
    '查看当前所有定时任务',
    '新增/修改一个定时任务（如每日 09:00 盘前扫描）',
    '更新某 OS agent 定时任务的指令（payload.prompt）',
    '临时暂停或恢复某个任务',
    '手动触发一次任务补跑',
  ],

  examples: [
    {
      title: '列出所有定时任务',
      params: { action: 'list' },
      expectedResult: '返回任务列表及数量',
    },
    {
      title: '注册每日盘前扫描',
      params: {
        action: 'create',
        name: '盘前扫描',
        owner: 'agent-dh',
        cron: '0 9 * * *',
        command: 'signal_scan',
      },
      expectedResult: '返回新创建的任务ID和详情',
    },
    {
      title: '手动触发任务',
      params: {
        action: 'trigger',
        task_id: 'task_xxx',
      },
      expectedResult: '返回触发结果',
    },
    {
      title: '更新 OS agent 任务的指令（payload.prompt）',
      params: {
        action: 'update',
        task_id: 'task_xxx',
        payload: { prompt: '【新的任务指令】……' },
      },
      expectedResult: '返回更新后的任务详情（payload 已替换）',
    },
  ],

  parameters: {
    action: {
      type: 'string',
      required: true,
      description:
        '操作类型。list：列出所有任务；create：创建任务；get：获取任务详情；update：更新任务；trigger：立即触发一次；enable：启用任务；disable：禁用任务；delete：删除任务',
    },
    task_id: {
      type: 'string',
      required: false,
      description: '任务ID，get/update/trigger/enable/disable/delete 时必填',
    },
    name: {
      type: 'string',
      required: false,
      description: '任务名称，create 时必填',
    },
    owner: {
      type: 'string',
      required: false,
      description: '任务所有者，create 时可选，默认 agent-dh',
      default: 'agent-dh',
      example: 'agent-dh',
    },
    cron: {
      type: 'string',
      required: false,
      description: 'cron 表达式，create 时必填。如 "0 9 * * 1-5"（工作日9点）',
    },
    command: {
      type: 'string',
      required: false,
      description: '执行命令，create 时必填（设置了 webhook_url 则可不填）',
    },
    description: {
      type: 'string',
      required: false,
      description: '任务描述',
    },
    webhook_url: {
      type: 'string',
      required: false,
      description: 'Webhook 回调地址（create/update 可选）。设置后任务触发改走 HTTP POST 该地址（如 http://127.0.0.1:13080/agent-os-trigger），command 不再执行；配 payload.prompt 即把指令全文交给 agent',
    },
    payload: {
      type: 'object',
      required: false,
      description: '任务负载（create/update 可选，整体替换）。agent-webhook 任务：{"prompt": "<给 agent 的完整指令>"}；quantsys 内部任务：{"job_type": "..."}。update 传它即覆盖原 payload（可用 get 先查现值再改）',
      additionalProperties: true,
    },
    enabled: {
      type: 'boolean',
      required: false,
      description: '是否启用，update 时可选',
    },
  },

  output: {
    schema: {
      type: 'object',
      additionalProperties: false,
      properties: {
        success: { type: 'boolean' },
        action: { type: 'string' },
        tasks: { type: 'array', items: { type: 'object', additionalProperties: true } },
        task: { type: 'object', additionalProperties: true },
        count: { type: 'number' },
        task_id: { type: 'string' },
        message: { type: 'string' },
      },
    },
    render: (args, data) => {
      let output = '';

      switch (data.action) {
        case 'list': {
          output += `## 📋 定时任务列表\n\n`;
          output += `**任务总数**: ${data.count || 0}\n\n`;
          if (data.tasks && data.tasks.length > 0) {
            output += `| 任务ID | 名称 | 类型 | Cron | 状态 |\n`;
            output += `|--------|------|------|------|------|\n`;
            for (const task of data.tasks) {
              const status = task.enabled ? '✅ 启用' : '⏸️ 禁用';
              const kind = taskKind(task);
              const name = task.name || task.id;
              const cron = task.cron || task.schedule || '';
              output += `| ${task.id} | ${name} | ${kind} | ${cron} | ${status} |\n`;
            }
          } else {
            output += `*暂无定时任务*\n`;
          }
          break;
        }

        case 'create':
          output += `## ✅ 任务创建成功\n\n`;
          output += `- **任务ID**: ${data.task_id}\n`;
          output += `- **任务名称**: ${data.task?.name}\n`;
          output += `- **类型**: ${taskKind(data.task)}\n`;
          output += `- **Cron**: ${data.task?.cron}\n`;
          if (data.task?.command) output += `- **命令**: ${data.task.command}\n`;
          if (data.task?.webhook_url) output += `- **Webhook**: ${data.task.webhook_url}\n`;
          output += `- **状态**: ${data.task?.enabled ? '✅ 启用' : '⏸️ 禁用'}\n`;
          break;

        case 'get':
          output += `## 📄 任务详情\n\n`;
          if (data.task) {
            output += `- **任务ID**: ${data.task.id}\n`;
            output += `- **任务名称**: ${data.task.name}\n`;
            output += `- **所有者**: ${data.task.owner}\n`;
            output += `- **类型**: ${taskKind(data.task)}\n`;
            output += `- **Cron**: ${data.task.cron}\n`;
            if (data.task.command) output += `- **命令**: ${data.task.command}\n`;
            if (data.task.webhook_url) output += `- **Webhook**: ${data.task.webhook_url}\n`;
            output += `- **状态**: ${data.task.enabled ? '✅ 启用' : '⏸️ 禁用'}\n`;
            if (data.task.description) {
              output += `- **描述**: ${data.task.description}\n`;
            }
            if (data.task.payload && Object.keys(data.task.payload).length > 0) {
              const p = data.task.payload;
              const shown: string[] = [];
              if (p.prompt) shown.push(`prompt: ${String(p.prompt).slice(0, 120)}${String(p.prompt).length > 120 ? '…' : ''}`);
              if (p.job_type) shown.push(`job_type: ${String(p.job_type)}`);
              if (p.window) shown.push(`window: ${String(p.window)}`);
              if (p.executor) shown.push(`executor: ${String(p.executor)}`);
              if (shown.length) output += `- **Payload**: ${shown.join(' | ')}\n`;
            }
            if (data.task.last_run) {
              output += `- **上次运行**: ${data.task.last_run}\n`;
            }
            if (data.task.next_run) {
              output += `- **下次运行**: ${data.task.next_run}\n`;
            }
          }
          break;

        case 'trigger':
          output += `## 🚀 任务已触发\n\n`;
          output += `- **任务ID**: ${data.task_id}\n`;
          output += `- ${data.message || '任务已加入执行队列'}\n`;
          break;

        case 'enable':
        case 'disable':
        case 'update':
        case 'delete':
          output += `## ✅ 操作成功\n\n`;
          output += `- **操作**: ${data.action}\n`;
          output += `- **任务ID**: ${data.task_id}\n`;
          output += `- ${data.message || '操作完成'}\n`;
          break;

        default:
          output = JSON.stringify(data, null, 2);
      }

      return [{ type: 'text', text: output }];
    },
  },
};
