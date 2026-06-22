/**
 * BackgroundTaskManager - 异步工具调用管理器
 *
 * 注意：由于 tsx + Worker 的模块解析限制，改用主线程异步执行
 * 虽然不是真正的并行（CPU密集型任务仍会阻塞），但对于 I/O 密集型工具
 * （如网络请求、数据库查询）仍能实现并发效果。
 *
 * 核心机制：实现异步工具调用
 * ==========================================
 *
 * 问题：Agent 直接调用工具是同步的（串行执行）
 * - 调用 get_stock_info → 等待 2 秒 → 返回
 * - 调用 get_quality_score → 等待 3 秒 → 返回
 * - 调用 get_financial_data → 等待 2 秒 → 返回
 * 总耗时：7 秒
 *
 * 解决：使用 Promise.all 实现并发执行
 * - background_run(1, "get_stock_info", {...}) → 立即返回
 * - background_run(2, "get_quality_score", {...}) → 立即返回
 * - background_run(3, "get_financial_data", {...}) → 立即返回
 * - 三个工具作为 Promise 并发执行（I/O 异步）
 * - 下一轮通过 drainNotifications() 获取所有完成的结果
 * 总耗时：3 秒（最慢的那个工具）
 *
 * 使用流程：
 * 1. Agent 调用 task_create 创建任务追踪
 * 2. Agent 调用 background_run 启动异步执行（立即返回）
 * 3. Agent 继续其他工作或结束当前轮次
 * 4. 下一轮 agent-loop.ts 自动调用 drainNotifications()
 * 5. 将完成的任务结果注入到 Agent 的上下文中
 *
 * 关键点：
 * - background_run 不阻塞，立即返回任务 ID
 * - 工具在主线程异步执行，I/O 操作仍能并发
 * - 多个 background_run 可以并发执行（异步 I/O）
 * - Agent 必须在系统提示词中被告知使用这个机制
 */
import { randomUUID } from "crypto";

// 动态导入 logger（避免循环依赖）
let logEvent: ((event: string, data: any) => void) | null = null;
async function getLogger() {
  if (!logEvent) {
    const logger = await import("../../infrastructure/logging/observable-logger.js");
    logEvent = logger.logEvent;
  }
  return logEvent;
}

export interface BackgroundTask {
  id: string;
  taskId: number;
  status: "running" | "completed" | "error" | "timeout";
  toolName: string;
  params: any;
  result?: any;
  error?: string;
  startTime: number;
}

export interface TaskNotification {
  taskId: number;
  backgroundId: string;
  status: "completed" | "error" | "timeout";
  result: any;
  duration: number;
}

export class BackgroundTaskManager {
  private tasks = new Map<string, BackgroundTask>();
  private notificationQueue: TaskNotification[] = [];
  private readonly timeout: number;

  constructor(timeoutMs = 300000) {
    this.timeout = timeoutMs;
  }

  /**
   * 记录事件（异步，不阻塞）
   */
  private logEvent(event: string, data: any) {
    getLogger().then(log => log?.(event, data)).catch(() => {});
  }

  /**
   * 异步执行工具调用（在主线程中，使用 Promise 异步执行）
   */
  async run(taskId: number, toolName: string, params: any): Promise<string> {
    const id = randomUUID().slice(0, 8);

    const task: BackgroundTask = {
      id,
      taskId,
      status: "running",
      toolName,
      params,
      startTime: Date.now(),
    };

    this.tasks.set(id, task);

    // 记录异步任务启动事件
    this.logEvent("background_task.start", {
      background_id: id,
      task_id: taskId,
      tool_name: toolName,
      params
    });

    // 在主线程中异步执行工具（不阻塞，立即返回）
    this._executeAsync(id, toolName, params).catch(error => {
      // 捕获未处理的错误
      console.error(`[BackgroundTask ${id}] Unhandled error:`, error);
    });

    return `Background task ${id} started for task #${taskId}: ${toolName}`;
  }

  /**
   * 在主线程中异步执行工具
   */
  private async _executeAsync(id: string, toolName: string, params: any): Promise<void> {
    const task = this.tasks.get(id);
    if (!task) return;

    try {
      // 动态导入工具注册表
      const { allCustomTools } = await import("../../infrastructure/tools/index.js");
      const tool = allCustomTools.find(t => t.name === toolName);

      if (!tool) {
        throw new Error(`Tool not found: ${toolName}`);
      }

      // 创建 AbortSignal 和超时
      const abortController = new AbortController();
      const timeoutId = setTimeout(() => {
        abortController.abort();
      }, this.timeout);

      // 执行工具
      const result = await tool.execute(
        "background-call",
        params,
        abortController.signal,
        undefined, // onUpdate callback
        {} as any  // ExtensionContext (minimal mock)
      );

      clearTimeout(timeoutId);

      const duration = Date.now() - task.startTime;
      task.status = "completed";
      task.result = result;

      this.notificationQueue.push({
        taskId: task.taskId,
        backgroundId: id,
        status: "completed",
        result: result,
        duration,
      });

      // 记录完成事件
      this.logEvent("background_task.completed", {
        background_id: id,
        task_id: task.taskId,
        tool_name: task.toolName,
        duration_ms: duration,
        result_preview: JSON.stringify(result).slice(0, 200)
      });

    } catch (error) {
      const duration = Date.now() - task.startTime;
      const message = error instanceof Error ? error.message : String(error);

      task.status = error instanceof Error && error.name === "AbortError" ? "timeout" : "error";
      task.error = message;

      this.notificationQueue.push({
        taskId: task.taskId,
        backgroundId: id,
        status: task.status,
        result: message,
        duration,
      });

      // 记录错误事件
      this.logEvent("background_task.error", {
        background_id: id,
        task_id: task.taskId,
        tool_name: task.toolName,
        error: message,
        duration_ms: duration
      });
    }
  }

  /**
   * 检查任务状态
   */
  check(id?: string): string {
    if (id) {
      const task = this.tasks.get(id);
      if (!task) return `Error: Unknown task ${id}`;

      const elapsed = Math.round((Date.now() - task.startTime) / 1000);
      const resultPreview = task.result
        ? JSON.stringify(task.result).slice(0, 200)
        : task.error || "(running)";
      return `[${task.status}] Task #${task.taskId} - ${task.toolName} (${elapsed}s)\n${resultPreview}`;
    }

    const lines: string[] = [];
    for (const [id, task] of this.tasks) {
      const elapsed = Math.round((Date.now() - task.startTime) / 1000);
      lines.push(`${id}: [${task.status}] Task #${task.taskId} - ${task.toolName} (${elapsed}s)`);
    }
    return lines.length > 0 ? lines.join("\n") : "No background tasks.";
  }

  /**
   * 获取并清空通知队列
   */
  drainNotifications(): TaskNotification[] {
    const notifications = [...this.notificationQueue];
    this.notificationQueue = [];
    return notifications;
  }

  /**
   * 获取运行中的任务数量
   */
  getRunningCount(): number {
    return Array.from(this.tasks.values()).filter(t => t.status === "running").length;
  }

  /**
   * 获取运行中的任务（用于重启时收集）
   */
  getRunningTasks(): BackgroundTask[] {
    return Array.from(this.tasks.values()).filter(t => t.status === "running");
  }

  /**
   * 恢复中断的任务为失败状态（用于重启后恢复）
   */
  restoreInterruptedTasks(interrupted: Array<{
    id: string;
    taskId: number;
    toolName: string;
    params: any;
    startTime: number;
    reason: string;
  }>): void {
    for (const task of interrupted) {
      const failedTask: BackgroundTask = {
        id: task.id,
        taskId: task.taskId,
        status: "error",
        toolName: task.toolName,
        params: task.params,
        startTime: task.startTime,
        error: `Task interrupted by agent restart (reason: ${task.reason})`,
        result: undefined
      };

      this.tasks.set(task.id, failedTask);

      // 添加到通知队列，让 agent 知道这些任务失败了
      this.notificationQueue.push({
        taskId: task.taskId,
        backgroundId: task.id,
        status: "error",
        result: `Task interrupted by agent restart`,
        duration: Date.now() - task.startTime
      });

      // 记录事件
      this.logEvent("background_task.restored_as_failed", {
        background_id: task.id,
        task_id: task.taskId,
        tool_name: task.toolName,
        reason: task.reason
      });
    }
  }
}
