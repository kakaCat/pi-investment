import { AxiosInstance } from 'axios';
import { createHttpClient } from './http.js';
import type {
  RegisterTaskParams,
  SchedulerTask,
  SchedulerTasksResponse,
  RegistryClientConfig,
  TaskActionResult,
  TriggerTaskParams,
  TriggerTaskResponse,
  UpdateTaskParams,
} from './types.js';

/**
 * SchedulerClient — Agent OS scheduler APIs.
 *
 * Server contract (verified live):
 *   GET    /api/v1/scheduler/tasks
 *   POST   /api/v1/scheduler/tasks                 (CreateTaskRequest)
 *   GET    /api/v1/scheduler/tasks/{id}
 *   PUT    /api/v1/scheduler/tasks/{id}            (UpdateTaskRequest)
 *   DELETE /api/v1/scheduler/tasks/{id}
 *   POST   /api/v1/scheduler/tasks/{id}/trigger
 *   POST   /api/v1/scheduler/tasks/{id}/pause        (= disable)
 *   POST   /api/v1/scheduler/tasks/{id}/resume       (= enable)
 *   GET    /api/v1/scheduler/tasks/stats             (含 total_runs/last_run_status/success_rate)
 *   GET    /api/v1/scheduler/executions?task_id=     (执行明细，含 error)
 */
export class SchedulerClient {
  private client: AxiosInstance;

  constructor(config: RegistryClientConfig) {
    this.client = createHttpClient(config);
  }

  /**
   * List all scheduled tasks.
   */
  async listTasks(): Promise<SchedulerTasksResponse> {
    const response = await this.client.get<SchedulerTasksResponse>(
      '/api/v1/scheduler/tasks'
    );
    return response.data;
  }

  /**
   * List tasks WITH execution statistics.
   * GET /api/v1/scheduler/tasks/stats
   *
   * 2026-09-13（w-a9ec14d7）：这个接口一直在服务端存在，客户端却从没调过 ——
   * 于是"任务到底跑没跑/上次成功没有"在 agent 侧完全不可见（实测因此漏看
   * pre-market-routine 2026-09-11 09:25 的 failed）。返回每任务
   * total_runs / last_run_at / last_run_status / success_rate / avg_duration_ms。
   */
  async listTasksWithStats(): Promise<{ count: number; tasks: any[] }> {
    const response = await this.client.get<{ count: number; tasks: any[] }>(
      '/api/v1/scheduler/tasks/stats'
    );
    return response.data;
  }

  /**
   * List executions (task runs) of one task.
   * GET /api/v1/scheduler/executions?task_id=&limit=
   */
  async listExecutions(params: {
    task_id: string;
    limit?: number;
  }): Promise<{ count: number; executions: any[] }> {
    if (!params?.task_id) {
      throw new Error('task_id is required');
    }
    const response = await this.client.get<{ count: number; executions: any[] }>(
      '/api/v1/scheduler/executions',
      { params: { task_id: params.task_id, limit: params.limit ?? 20 } }
    );
    return response.data;
  }

  /**
   * Register a new scheduled task.
   */
  async registerTask(params: RegisterTaskParams): Promise<SchedulerTask> {
    if (!params.name || params.name.trim() === '') {
      throw new Error('name is required');
    }
    if (!params.owner || params.owner.trim() === '') {
      throw new Error('owner is required');
    }
    const response = await this.client.post<SchedulerTask>(
      '/api/v1/scheduler/tasks',
      {
        ...params,
        // The server requires a 6-field cron (sec min hour dom mon dow);
        // normalize 5-field cron expressions by prepending the seconds field.
        cron: params.cron ? normalizeCron(params.cron) : undefined,
        // The server DTO requires timeout >= 1; default when omitted.
        timeout: params.timeout ?? 60,
        // New tasks should be active by default (server DTO defaults to disabled).
        enabled: params.enabled ?? true,
      }
    );
    return response.data;
  }

  /**
   * Trigger a task immediately.
   */
  async triggerTask(params: TriggerTaskParams): Promise<TriggerTaskResponse> {
    if (!params.task_id || params.task_id.trim() === '') {
      throw new Error('task_id is required');
    }
    const response = await this.client.post<TriggerTaskResponse>(
      `/api/v1/scheduler/tasks/${encodeURIComponent(params.task_id)}/trigger`
    );
    return response.data;
  }

  /**
   * Fetch a single task by id.
   */
  async getTask(taskId: string): Promise<SchedulerTask> {
    const response = await this.client.get<SchedulerTask>(
      `/api/v1/scheduler/tasks/${encodeURIComponent(taskId)}`
    );
    return response.data;
  }

  /**
   * Update a task (partial update, all fields optional).
   */
  async updateTask(taskId: string, params: UpdateTaskParams): Promise<SchedulerTask> {
    if (!taskId || taskId.trim() === '') {
      throw new Error('task_id is required');
    }
    const response = await this.client.put<SchedulerTask>(
      `/api/v1/scheduler/tasks/${encodeURIComponent(taskId)}`,
      params
    );
    return response.data;
  }

  /**
   * Enable a task (resume).
   */
  async resumeTask(taskId: string): Promise<TaskActionResult> {
    if (!taskId || taskId.trim() === '') {
      throw new Error('task_id is required');
    }
    const response = await this.client.post<TaskActionResult>(
      `/api/v1/scheduler/tasks/${encodeURIComponent(taskId)}/resume`
    );
    return response.data;
  }

  /**
   * Disable a task (pause).
   */
  async pauseTask(taskId: string): Promise<TaskActionResult> {
    if (!taskId || taskId.trim() === '') {
      throw new Error('task_id is required');
    }
    const response = await this.client.post<TaskActionResult>(
      `/api/v1/scheduler/tasks/${encodeURIComponent(taskId)}/pause`
    );
    return response.data;
  }

  /**
   * Delete a task.
   */
  async deleteTask(taskId: string): Promise<TaskActionResult> {
    if (!taskId || taskId.trim() === '') {
      throw new Error('task_id is required');
    }
    const response = await this.client.delete<TaskActionResult>(
      `/api/v1/scheduler/tasks/${encodeURIComponent(taskId)}`
    );
    return response.data;
  }
}

/**
 * Normalize a 5-field cron expression (min hour dom mon dow) to the
 * 6-field format (sec min hour dom mon dow) required by the server.
 */
function normalizeCron(cron: string): string {
  const parts = cron.trim().split(/\s+/);
  return parts.length === 5 ? `0 ${cron.trim()}` : cron.trim();
}