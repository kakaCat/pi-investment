/**
 * Task definition for Agent OS Scheduler
 */
export interface Task {
  id: string;
  name: string;
  description?: string;
  owner: string;
  cron?: string;
  priority: number;
  status: 'active' | 'paused';
  tags: string[];
  webhook_url?: string;
  metadata?: any;
  created_at: string;
  updated_at: string;
}

/**
 * Task creation request
 */
export interface TaskCreateRequest {
  name: string;
  description?: string;
  owner: string;
  cron?: string;
  priority?: number;
  tags?: string[];
  webhook_url?: string;
  metadata?: any;
}

/**
 * Task execution record
 */
export interface Execution {
  id: string;
  task_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  started_at?: string;
  completed_at?: string;
  duration_ms?: number;
  result?: any;
  error?: string;
  metadata?: any;
}

/**
 * Execution update request
 */
export interface ExecutionUpdateRequest {
  status: 'running' | 'completed' | 'failed';
  result?: any;
  error?: string;
  metadata?: any;
}

/**
 * Task list filters
 */
export interface TaskListFilters {
  owner?: string;
  status?: 'active' | 'paused';
  tags?: string[];
}

/**
 * Execution list filters
 */
export interface ExecutionListFilters {
  task_id?: string;
  status?: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';
  limit?: number;
  offset?: number;
}
