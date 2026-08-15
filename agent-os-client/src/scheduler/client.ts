import { BaseHTTPClient } from '../http/client.js';
import {
  Task,
  TaskCreateRequest,
  Execution,
  ExecutionUpdateRequest,
  TaskListFilters,
  ExecutionListFilters,
} from './types.js';

/**
 * Scheduler Client - Manage tasks and executions
 */
export class SchedulerClient {
  constructor(private http: BaseHTTPClient) {}

  /**
   * List all tasks
   */
  async listTasks(filters?: TaskListFilters): Promise<Task[]> {
    const response = await this.http.get<{ count: number; tasks: Task[] | null }>(
      '/api/v1/scheduler/tasks',
      filters
    );
    return response.tasks || [];
  }

  /**
   * Register a new task
   */
  async registerTask(request: TaskCreateRequest): Promise<Task> {
    return this.http.post<Task>('/api/v1/scheduler/tasks', request);
  }

  /**
   * Get task details by ID
   */
  async getTask(taskId: string): Promise<Task> {
    return this.http.get<Task>(`/api/v1/scheduler/tasks/${taskId}`);
  }

  /**
   * Update task
   */
  async updateTask(taskId: string, updates: Partial<TaskCreateRequest>): Promise<Task> {
    return this.http.put<Task>(`/api/v1/scheduler/tasks/${taskId}`, updates);
  }

  /**
   * Delete a task
   */
  async deleteTask(taskId: string): Promise<void> {
    return this.http.delete<void>(`/api/v1/scheduler/tasks/${taskId}`);
  }

  /**
   * Manually trigger a task
   */
  async triggerTask(taskId: string, params?: any): Promise<Execution> {
    return this.http.post<Execution>(`/api/v1/scheduler/tasks/${taskId}/trigger`, {
      params,
    });
  }

  /**
   * Pause a task
   */
  async pauseTask(taskId: string): Promise<Task> {
    return this.http.post<Task>(`/api/v1/scheduler/tasks/${taskId}/pause`);
  }

  /**
   * Resume a task
   */
  async resumeTask(taskId: string): Promise<Task> {
    return this.http.post<Task>(`/api/v1/scheduler/tasks/${taskId}/resume`);
  }

  /**
   * List task executions
   */
  async listExecutions(filters?: ExecutionListFilters): Promise<Execution[]> {
    const response = await this.http.get<{ count: number; executions: Execution[] | null }>(
      '/api/v1/scheduler/executions',
      filters
    );
    return response.executions || [];
  }

  /**
   * Get execution details by ID
   */
  async getExecution(executionId: string): Promise<Execution> {
    return this.http.get<Execution>(`/api/v1/scheduler/executions/${executionId}`);
  }

  /**
   * Update execution status (called by agent after task execution)
   */
  async updateExecution(
    executionId: string,
    update: ExecutionUpdateRequest
  ): Promise<Execution> {
    return this.http.put<Execution>(`/api/v1/scheduler/executions/${executionId}`, update);
  }

  /**
   * Cancel a running execution
   */
  async cancelExecution(executionId: string): Promise<Execution> {
    return this.http.post<Execution>(`/api/v1/scheduler/executions/${executionId}/cancel`);
  }
}
