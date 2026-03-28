/**
 * BackgroundTaskManager - 异步工具调用管理器
 *
 * 参考 s08_background_tasks.py，但专注于工具调用而非 shell 命令
 */
import { Worker } from "worker_threads";
import { randomUUID } from "crypto";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

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
   * 异步执行工具调用
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

    // 使用 Worker 线程执行工具
    this._executeInWorker(id, toolName, params);

    return `Background task ${id} started for task #${taskId}: ${toolName}`;
  }

  private _executeInWorker(id: string, toolName: string, params: any): void {
    // 使用编译后的 JS 文件路径
    const workerPath = join(__dirname, "tool-worker.js");

    const worker = new Worker(workerPath, {
      workerData: {
        toolName,
        params,
        timeout: this.timeout
      }
    });

    worker.on("message", (result: { output?: any; error?: string }) => {
      const task = this.tasks.get(id);
      if (!task) return;

      const duration = Date.now() - task.startTime;

      if (result.error) {
        task.status = "error";
        task.error = result.error;
        this.notificationQueue.push({
          taskId: task.taskId,
          backgroundId: id,
          status: "error",
          result: result.error,
          duration,
        });

        // 记录错误事件
        this.logEvent("background_task.error", {
          background_id: id,
          task_id: task.taskId,
          tool_name: task.toolName,
          error: result.error,
          duration_ms: duration
        });
      } else {
        task.status = "completed";
        task.result = result.output;
        this.notificationQueue.push({
          taskId: task.taskId,
          backgroundId: id,
          status: "completed",
          result: result.output,
          duration,
        });

        // 记录完成事件
        this.logEvent("background_task.completed", {
          background_id: id,
          task_id: task.taskId,
          tool_name: task.toolName,
          duration_ms: duration,
          result_preview: JSON.stringify(result.output).slice(0, 200)
        });
      }
    });

    worker.on("error", (error) => {
      const task = this.tasks.get(id);
      if (!task) return;

      task.status = "error";
      task.error = error.message;
      this.notificationQueue.push({
        taskId: task.taskId,
        backgroundId: id,
        status: "error",
        result: `Worker error: ${error.message}`,
        duration: Date.now() - task.startTime,
      });
    });
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
}
