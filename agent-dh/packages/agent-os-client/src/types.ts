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
}
