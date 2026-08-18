/**
 * Agent information for registration
 */
export interface AgentInfo {
  agent_id: string;
  session_id?: string;
  type: string;
  capabilities: string[];
  status?: string;
  host?: string;
  port?: number;
  pid?: number;
  version?: string;
  metadata?: Record<string, any>;
}

/**
 * Agent status
 */
export type AgentStatus = 'idle' | 'busy' | 'offline' | 'error';

/**
 * Agent heartbeat
 */
export interface AgentHeartbeat {
  agent_id: string;
  status: AgentStatus;
  load?: number;
  current_task_id?: string;
  metadata?: Record<string, any>;
}

/**
 * Status update
 */
export interface StatusUpdate {
  agent_id: string;
  status: AgentStatus;
  message?: string;
  metadata?: Record<string, any>;
}

/**
 * Unregister request
 */
export interface UnregisterRequest {
  agent_id: string;
}

/**
 * Agent response (from server)
 */
export interface Agent {
  id: string;
  agent_id: string;
  session_id?: string;
  agent_type: string;
  status: AgentStatus;
  host?: string;
  port?: number;
  pid?: number;
  version?: string;
  registered_at: string;
  last_heartbeat_at: string;
  capabilities?: string[];
  metadata?: Record<string, any>;
}

/**
 * Registry client configuration
 */
export interface RegistryClientConfig {
  baseURL: string;
  timeout?: number;
  headers?: Record<string, string>;
  /** Agent identity sent with registry operations (used by plugins) */
  agentId?: string;
}

// ─────────────────────────────────────────────────────────────
// Memory
// ─────────────────────────────────────────────────────────────

/**
 * A memory record as returned by Agent OS /api/v1/memory*
 */
export interface MemoryRecord {
  id: string;
  title?: string;
  content: string;
  category?: string;
  tags?: string[];
  agent_id?: string;
  created_at: string;
  updated_at: string;
}

/**
 * Memory search request (client-facing; `top_k` is mapped to server `limit`)
 */
export interface MemorySearchParams {
  query: string;
  top_k?: number;
  category?: string;
  tag?: string;
}

/**
 * Memory search response: `{ memories, total }`
 */
export interface MemorySearchResponse {
  memories: MemoryRecord[];
  total: number;
}

/**
 * Memory write request. `namespace` is a client hint mapped to the
 * server `category` (knowledge | experience | decision | data).
 */
export interface MemoryWriteParams {
  content: string;
  title?: string;
  namespace?: string;
  importance?: number;
  tags?: string[];
}

export interface MemoryWriteResponse {
  success: boolean;
  message?: string;
  memory?: MemoryRecord;
}

// ─────────────────────────────────────────────────────────────
// Scheduler
// ─────────────────────────────────────────────────────────────

/**
 * A scheduled task as returned by Agent OS /api/v1/scheduler/tasks
 */
export interface SchedulerTask {
  id: string;
  name: string;
  owner: string;
  description?: string;
  schedule?: string;
  cron?: string;
  command?: string;
  webhook_url?: string;
  payload?: Record<string, any>;
  timeout?: number;
  retry_count?: number;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface SchedulerTasksResponse {
  count: number;
  tasks: SchedulerTask[];
}

/**
 * Request body for POST /api/v1/scheduler/tasks (CreateTaskRequest)
 */
export interface RegisterTaskParams {
  name: string;
  owner: string;
  description?: string;
  cron?: string;
  command?: string;
  webhook_url?: string;
  payload?: Record<string, any>;
  timeout?: number;
  retry_count?: number;
  enabled?: boolean;
}

export interface TriggerTaskParams {
  task_id: string;
}

export interface TriggerTaskResponse {
  id?: string;
  task_id?: string;
  status?: string;
  [key: string]: any;
}

// ─────────────────────────────────────────────────────────────
// Notification
// ─────────────────────────────────────────────────────────────

/**
 * Request body for POST /api/v1/notifications/send
 */
export interface SendNotificationParams {
  channel?: string;
  title: string;
  content: string;
  /** Client-side severity hint; currently ignored by the server */
  urgency?: string;
}

export interface SendNotificationResponse {
  success: boolean;
  message?: string;
  [key: string]: any;
}

// ─────────────────────────────────────────────────────────────
// Evolution
// ─────────────────────────────────────────────────────────────

export interface EvolutionRunParams {
  strategy_id: string;
  mode?: string;
  generations?: number;
}

export interface EvolutionRunResponse {
  status?: string;
  strategy_id?: string;
  [key: string]: any;
}

export interface EvolutionLeaderboardParams {
  limit?: number;
}

export interface EvolutionLeaderboardResponse {
  entries?: any[];
  [key: string]: any;
}

/**
 * AgentOS client configuration
 */
export interface AgentOSClientConfig extends Partial<RegistryClientConfig> {
  /** Agent ID used as task owner / identity when talking to Agent OS */
  agentId?: string;
}
