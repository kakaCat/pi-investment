import { AxiosInstance } from 'axios';
import { createHttpClient } from './http.js';
import type {
  RegisterTaskParams,
  SchedulerTask,
  SchedulerTasksResponse,
  RegistryClientConfig,
  TriggerTaskParams,
  TriggerTaskResponse,
} from './types.js';

/**
 * SchedulerClient — Agent OS scheduler APIs.
 *
 * Server contract (verified live):
 *   GET  /api/v1/scheduler/tasks
 *   POST /api/v1/scheduler/tasks                 (CreateTaskRequest)
 *   POST /api/v1/scheduler/tasks/{id}/trigger
 *   GET  /api/v1/scheduler/tasks/{id}
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
}

/**
 * Normalize a 5-field cron expression (min hour dom mon dow) to the
 * 6-field format (sec min hour dom mon dow) required by the server.
 */
function normalizeCron(cron: string): string {
  const parts = cron.trim().split(/\s+/);
  return parts.length === 5 ? `0 ${cron.trim()}` : cron.trim();
}
