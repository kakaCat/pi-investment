import { BaseHTTPClient, AgentOSConfig, AgentOSError } from './http/client.js';
import { SchedulerClient } from './scheduler/client.js';
import { MemoryClient } from './memory/client.js';
import { DecisionClient } from './decision/client.js';
import { NotificationClient } from './notification/client.js';
import { ResourceClient } from './resource/client.js';

/**
 * Agent OS Client - Main SDK entry point
 *
 * @example
 * ```typescript
 * import { AgentOSClient } from '@pi-investment/agent-os-client';
 *
 * const client = new AgentOSClient({
 *   baseURL: 'http://localhost:8080',
 *   agentId: 'fin-agent',
 * });
 *
 * // Use sub-clients
 * await client.scheduler.listTasks();
 * await client.memory.write({ namespace: 'fin-agent', content: 'test' });
 * await client.notification.send({ title: 'Test', content: 'Hello' });
 * ```
 */
export class AgentOSClient {
  private http: BaseHTTPClient;

  /** Scheduler operations (tasks, executions) */
  public scheduler: SchedulerClient;

  /** Memory operations (write, search, query) */
  public memory: MemoryClient;

  /** Decision operations (record, track, query) */
  public decision: DecisionClient;

  /** Notification operations (send, channels) */
  public notification: NotificationClient;

  /** Resource operations (quota, usage, namespaces) */
  public resource: ResourceClient;

  /**
   * Create a new Agent OS Client
   *
   * @param config - Client configuration
   */
  constructor(config: AgentOSConfig) {
    this.http = new BaseHTTPClient(config);

    // Initialize sub-clients
    this.scheduler = new SchedulerClient(this.http);
    this.memory = new MemoryClient(this.http);
    this.decision = new DecisionClient(this.http);
    this.notification = new NotificationClient(this.http);
    this.resource = new ResourceClient(this.http);
  }

  /**
   * Get the base URL
   */
  getBaseURL(): string {
    return this.http.getBaseURL();
  }

  /**
   * Get the agent ID
   */
  getAgentId(): string | undefined {
    return this.http.getAgentId();
  }

  /**
   * Health check
   */
  async health(): Promise<{ status: string; version: string }> {
    return this.http.get('/health');
  }

  /**
   * Get API version
   */
  async version(): Promise<{ version: string; build_time: string }> {
    return this.http.get('/version');
  }
}

// Re-export everything for convenience
export * from './http/client.js';
export * from './scheduler/types.js';
export * from './memory/types.js';
export * from './decision/types.js';
export * from './notification/types.js';
export * from './resource/types.js';
