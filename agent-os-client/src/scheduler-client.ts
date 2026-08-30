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
