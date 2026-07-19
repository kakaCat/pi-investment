/**
 * Scheduler Management Tool - 调度器管理工具
 *
 * 完整的定时任务管理功能：
 * - 任务CRUD（创建、查询、更新、删除）
 * - 任务启用/禁用
 * - 手动触发任务
 * - 查询执行历史
 * - 失败任务监控
 * - 补偿执行
 *
 * 应用场景：
 * - 数据自动更新（每日收盘后更新数据）
 * - 组合再平衡（每周一调整仓位）
 * - 策略执行（每日开盘前生成交易信号）
 * - 风险监控（每小时检查风险指标）
 */
import type { ToolDefinition } from "../index.js";
import { Type } from "@sinclair/typebox";
import { runQuantV2 } from "../../adapters/quant/quant-v2-client.js";

interface SchedulerParams {
  action: "list" | "create" | "update" | "enable" | "disable" | "delete" | "trigger" | "runs" | "failed";
  task_id?: string;
  name?: string;
  cron?: string;
  command?: string;
  params?: Record<string, any>;
  enabled?: boolean;
  limit?: number;
}

interface SchedulerTask {
  id: number | string;
  name: string;
  cron: string;
  command: string;
  enabled: boolean;
  last_run_at?: string | null;
  last_run_status?: string | null;
  next_run?: string | null;
  today_triggered?: boolean;
  [key: string]: any;
}

/**
 * 归一化 v2 调度器任务响应。
 *
 * v2 enterprise API 返回 camelCase（scheduleExpr/nextRunAt/lastRun/
 * payload.command），老接口返回 snake_case（cron/next_run）——
 * 两种都接受，缺失字段回退为空字符串/null，绝不产生 undefined。
 */
export function normalizeSchedulerTask(raw: any): SchedulerTask {
  const lastRun = raw?.lastRun ?? null;
  return {
    id: raw?.id ?? "",
    name: raw?.name ?? "",
    cron: raw?.cron ?? raw?.scheduleExpr ?? raw?.cron_expression ?? "",
    command: raw?.command ?? raw?.payload?.command ?? "",
    enabled: Boolean(raw?.enabled ?? raw?.is_enabled),
    last_run_at: raw?.last_run_at ?? lastRun?.finishedAt ?? null,
    last_run_status: raw?.last_run_status ?? lastRun?.status ?? null,
    next_run: raw?.next_run ?? raw?.nextRunAt ?? raw?.next_run_at ?? null,
    today_triggered: raw?.today_triggered ?? raw?.todayTriggered ?? undefined,
  };
}

interface SchedulerResult {
  tasks?: SchedulerTask[];
  task?: SchedulerTask;
  runs?: Array<{
    id: number;
    task_id: number;
    start_time: string;
    end_time?: string;
    status: string;
    result?: any;
    error?: string;
  }>;
  total?: number;
  [key: string]: any;
}

export const schedulerManageTool: ToolDefinition = {
  name: "scheduler_manage",
  label: "调度器管理",
  description:
    "定时任务管理工具，支持任务CRUD、启用/禁用、手动触发、执行历史查询。" +
    "使用Cron表达式定义执行时间。" +
    "适用场景：数据自动更新、组合再平衡、策略执行、风险监控。",

  parameters: Type.Object({
    action: Type.Union([
      Type.Literal("list"),
      Type.Literal("create"),
      Type.Literal("update"),
      Type.Literal("enable"),
      Type.Literal("disable"),
      Type.Literal("delete"),
      Type.Literal("trigger"),
      Type.Literal("runs"),
      Type.Literal("failed")
    ], {
      description:
        "操作类型。" +
        "list: 列出所有任务；" +
        "create: 创建新任务；" +
        "update: 更新任务；" +
        "enable: 启用任务；" +
        "disable: 禁用任务；" +
        "delete: 删除任务；" +
        "trigger: 手动触发任务；" +
        "runs: 查询执行历史；" +
        "failed: 查询失败的执行"
    }),
    task_id: Type.Optional(Type.String({
      description: "任务ID（update/enable/disable/delete/trigger/runs时必需）"
    })),
    name: Type.Optional(Type.String({
      description: "任务名称（create/update时使用）"
    })),
    cron: Type.Optional(Type.String({
      description: "Cron表达式。例如：'0 9 * * 1-5'（工作日9点），'0 */4 * * *'（每4小时）"
    })),
    command: Type.Optional(Type.String({
      description: "要执行的命令。例如：'data.update', 'strategy.execute', 'portfolio.rebalance'"
    })),
    params: Type.Optional(Type.Any({
      description: "命令参数（JSON对象）"
    })),
    enabled: Type.Optional(Type.Boolean({
      description: "是否启用（create/update时使用）"
    })),
    limit: Type.Optional(Type.Integer({
      description: "返回记录数量。默认：20",
      minimum: 1,
      maximum: 100
    }))
  }),

  execute: async (_toolCallId: string, params: SchedulerParams) => {
    try {
      const { action, ...otherParams } = params;

      // 构建API命令和参数
      let command: string;
      let apiParams: any;

      switch (action) {
        case "list":
          command = "scheduler.tasks.list";
          apiParams = { limit: otherParams.limit || 20 };
          break;

        case "create":
          if (!otherParams.name || !otherParams.cron || !otherParams.command) {
            throw new Error("创建任务需要提供 name、cron、command");
          }
          command = "scheduler.tasks.create";
          apiParams = {
            name: otherParams.name,
            schedule_kind: "cron",
            schedule_expr: otherParams.cron,
            command: otherParams.command,
            params: otherParams.params,
            enabled: otherParams.enabled !== false
          };
          break;

        case "update":
          if (!otherParams.task_id) {
            throw new Error("更新任务需要提供 task_id");
          }
          command = "scheduler.tasks.update";
          apiParams = {
            task_id: otherParams.task_id,
            name: otherParams.name,
            schedule_expr: otherParams.cron,
            command: otherParams.command,
            params: otherParams.params,
            enabled: otherParams.enabled
          };
          break;

        case "enable":
          if (!otherParams.task_id) {
            throw new Error("启用任务需要提供 task_id");
          }
          command = "scheduler.tasks.enable";
          apiParams = { task_id: otherParams.task_id };
          break;

        case "disable":
          if (!otherParams.task_id) {
            throw new Error("禁用任务需要提供 task_id");
          }
          command = "scheduler.tasks.disable";
          apiParams = { task_id: otherParams.task_id };
          break;

        case "delete":
          if (!otherParams.task_id) {
            throw new Error("删除任务需要提供 task_id");
          }
          command = "scheduler.tasks.delete";
          apiParams = { task_id: otherParams.task_id };
          break;

        case "trigger":
          if (!otherParams.task_id) {
            throw new Error("触发任务需要提供 task_id");
          }
          command = "scheduler.tasks.trigger";
          apiParams = { task_id: otherParams.task_id };
          break;

        case "runs":
          if (!otherParams.task_id) {
            throw new Error("查询执行历史需要提供 task_id");
          }
          command = "scheduler.tasks.runs";
          apiParams = {
            task_id: otherParams.task_id,
            limit: otherParams.limit || 20
          };
          break;

        case "failed":
          command = "scheduler.runs.failed";
          apiParams = { limit: otherParams.limit || 20 };
          break;

        default:
          throw new Error(`未知的操作类型: ${action}`);
      }

      // 调用 quantsys-v2 API
      const result = await runQuantV2(command, apiParams);

      if (!result.ok) {
        const errorMsg = typeof (result as any).error === 'string'
          ? (result as any).error
          : (result as any).error?.message || "调度器操作失败";
        throw new Error(errorMsg);
      }

      // 格式化输出
      const formattedOutput = formatSchedulerResult(
        action,
        (result as any).data as SchedulerResult,
        params
      );

      return {
        content: [{
          type: "text" as const,
          text: formattedOutput
        }],
        details: (result as any).data
      };
    } catch (error) {
      const errorMsg = error instanceof Error ? error.message : String(error);
      return {
        content: [{
          type: "text" as const,
          text: `❌ 调度器操作失败: ${errorMsg}`
        }],
        details: null
      };
    }
  }
};

/**
 * 格式化调度器结果
 */
function formatSchedulerResult(
  action: string,
  data: SchedulerResult,
  params: SchedulerParams
): string {
  if (!data) {
    return "❌ 未获取到调度器数据";
  }

  let output = "⏰ **调度器管理**\n\n";

  // 单任务响应统一归一化（create/update/enable/disable/trigger 路径）
  if ((data as any)?.task) {
    (data as any).task = normalizeSchedulerTask((data as any).task);
  }

  switch (action) {
    case "list":
      output += formatTaskList(data);
      break;
    case "create":
      output += formatTaskCreated(data);
      break;
    case "update":
      output += formatTaskUpdated(data);
      break;
    case "enable":
      output += formatTaskEnabled(data);
      break;
    case "disable":
      output += formatTaskDisabled(data);
      break;
    case "delete":
      output += formatTaskDeleted(params);
      break;
    case "trigger":
      output += formatTaskTriggered(data);
      break;
    case "runs":
      output += formatTaskRuns(data);
      break;
    case "failed":
      output += formatFailedRuns(data);
      break;
  }

  return output;
}

/**
 * 格式化任务列表
 */
export function formatTaskList(data: SchedulerResult): string {
  let output = "### 📋 定时任务列表\n\n";

  if (!data.tasks || data.tasks.length === 0) {
    return output + "暂无定时任务\n\n";
  }

  // 幂等归一化：raw API 任务与已归一化对象都安全
  const tasks = data.tasks.map((t) => normalizeSchedulerTask(t));

  output += `**任务总数**：${data.total || tasks.length}个\n\n`;

  output += "| ID | 任务名称 | Cron表达式 | 状态 | 下次执行 | 上次执行 |\n";
  output += "|----|----------|-----------|------|----------|----------|\n";

  for (const task of tasks) {
    const statusEmoji = task.enabled ? "✅" : "⏸️";
    const status = task.enabled ? "启用" : "禁用";
    const nextRun = task.next_run ? String(task.next_run).slice(0, 16) : "—";
    let lastRun = "—";
    if (task.last_run_at) {
      const icon = task.last_run_status === "success" ? "✅" : task.last_run_status === "failed" ? "❌" : "•";
      lastRun = `${icon} ${String(task.last_run_at).slice(0, 16)}`;
    }

    output += `| ${task.id} | ${task.name} | \`${task.cron}\` | ${statusEmoji} ${status} | ${nextRun} | ${lastRun} |\n`;
  }

  output += "\n";

  // Cron 表达式说明
  output += "### 💡 Cron表达式说明\n\n";
  output += "格式：`分 时 日 月 周`\n\n";
  output += "常用示例：\n";
  output += "- `0 9 * * 1-5` - 工作日每天9点\n";
  output += "- `0 */4 * * *` - 每4小时\n";
  output += "- `0 0 * * 0` - 每周日午夜\n";
  output += "- `30 15 * * *` - 每天15:30\n\n";

  return output;
}

/**
 * 格式化任务创建结果
 */
function formatTaskCreated(data: SchedulerResult): string {
  let output = "### ✅ 任务创建成功\n\n";

  if ((data as any).task) {
    output += `**任务ID**：${data.task!.id}\n`;
    output += `**任务名称**：${data.task!.name}\n`;
    output += `**Cron表达式**：\`${data.task!.cron}\`\n`;
    output += `**执行命令**：${data.task!.command}\n`;
    output += `**状态**：${data.task!.enabled ? '✅ 已启用' : '⏸️ 已禁用'}\n`;

    if (data.task!.next_run) {
      output += `**下次执行**：${data.task!.next_run}\n`;
    }

    output += "\n";
  }

  return output;
}

/**
 * 格式化任务更新结果
 */
function formatTaskUpdated(data: SchedulerResult): string {
  let output = "### ✅ 任务更新成功\n\n";

  if ((data as any).task) {
    output += `**任务ID**：${data.task!.id}\n`;
    output += `**任务名称**：${data.task!.name}\n`;
    output += `**Cron表达式**：\`${data.task!.cron}\`\n`;
    output += `**执行命令**：${data.task!.command}\n`;
    output += `**状态**：${data.task!.enabled ? '✅ 已启用' : '⏸️ 已禁用'}\n\n`;
  }

  return output;
}

/**
 * 格式化任务启用结果
 */
function formatTaskEnabled(data: SchedulerResult): string {
  let output = "### ✅ 任务已启用\n\n";

  if ((data as any).task) {
    output += `**任务名称**：${data.task!.name}\n`;
    if (data.task!.next_run) {
      output += `**下次执行**：${data.task!.next_run}\n`;
    }
    output += "\n";
  }

  return output;
}

/**
 * 格式化任务禁用结果
 */
function formatTaskDisabled(data: SchedulerResult): string {
  let output = "### ⏸️ 任务已禁用\n\n";

  if ((data as any).task) {
    output += `**任务名称**：${data.task!.name}\n`;
    output += `任务已暂停，不会自动执行\n\n`;
  }

  return output;
}

/**
 * 格式化任务删除结果
 */
function formatTaskDeleted(params: SchedulerParams): string {
  return `### ✅ 任务已删除\n\n**任务ID**：${params.task_id}\n\n`;
}

/**
 * 格式化任务触发结果
 */
function formatTaskTriggered(data: SchedulerResult): string {
  let output = "### 🚀 任务已触发\n\n";

  if ((data as any).task) {
    output += `**任务名称**：${data.task!.name}\n`;
    output += `任务已添加到执行队列，正在运行中...\n\n`;
  }

  return output;
}

/**
 * 格式化任务执行历史
 */
function formatTaskRuns(data: SchedulerResult): string {
  let output = "### 📊 执行历史\n\n";

  if (!data.runs || data.runs.length === 0) {
    return output + "暂无执行记录\n\n";
  }

  output += `**记录数**：${data.runs.length}条\n\n`;

  output += "| ID | 开始时间 | 结束时间 | 状态 | 说明 |\n";
  output += "|----|----------|----------|------|------|\n";

  for (const run of data.runs) {
    const statusEmoji = getStatusEmoji(run.status);
    const endTime = run.end_time || '-';
    const description = run.error ? run.error.substring(0, 50) : '正常';

    output += `| ${run.id} | ${run.start_time} | ${endTime} | ${statusEmoji} ${run.status} | ${description} |\n`;
  }

  output += "\n";

  return output;
}

/**
 * 格式化失败的执行
 */
function formatFailedRuns(data: SchedulerResult): string {
  let output = "### ⚠️ 失败的执行\n\n";

  if (!data.runs || data.runs.length === 0) {
    return output + "✅ 暂无失败记录\n\n";
  }

  output += `**失败记录数**：${data.runs.length}条\n\n`;

  for (const run of data.runs) {
    output += `**执行ID**：${run.id}\n`;
    output += `**任务ID**：${run.task_id}\n`;
    output += `**开始时间**：${run.start_time}\n`;
    output += `**错误信息**：${run.error || '未知错误'}\n`;
    output += "\n";
  }

  output += "💡 **建议**：检查任务配置和命令参数，修复后可重新触发任务\n\n";

  return output;
}

/**
 * 获取状态表情
 */
function getStatusEmoji(status: string): string {
  const emojiMap: Record<string, string> = {
    "success": "✅",
    "failed": "❌",
    "running": "🔄",
    "pending": "⏳"
  };
  return emojiMap[status] || "➖";
}
