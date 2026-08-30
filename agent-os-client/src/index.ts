import { RegistryClient } from './registry-client.js';
import { LocalRegistry } from './local-registry.js';
import { MemoryClient } from './memory-client.js';
import { SchedulerClient } from './scheduler-client.js';
import { NotificationClient } from './notification-client.js';
import { EvolutionClient } from './evolution-client.js';
import type { RegistryClientConfig } from './types.js';

/**
 * Agent OS Client - main entry point
 * Supports both remote (HTTP) and local (in-memory) modes
 *
 * Aggregates one client per Agent OS API surface:
 *   - registry      (agent registry; remote requires server routes)
 *   - memory        (memory search / write)
 *   - scheduler     (scheduled tasks)
 *   - notification  (notifications)
 *   - evolution     (strategy evolution; server routes pending)
 */
export class AgentOSClient {
  public registry: RegistryClient | LocalRegistry;
  public memory: MemoryClient;
  public scheduler: SchedulerClient;
  public notification: NotificationClient;
  public evolution: EvolutionClient;
  public agentId: string;

  constructor(config?: RegistryClientConfig) {
    this.agentId = config?.agentId || 'agent-dh';
    if (config && config.baseURL && config.baseURL !== 'local') {
      // Remote mode: connect to Agent OS backend
      this.registry = new RegistryClient(config);
      this.memory = new MemoryClient(config);
      this.scheduler = new SchedulerClient(config);
      this.notification = new NotificationClient(config);
      this.evolution = new EvolutionClient(config);
    } else {
      // Local mode: in-memory registry, no backend needed
      this.registry = new LocalRegistry();
      this.memory = new MemoryClient({ baseURL: 'http://localhost:8080' });
      this.scheduler = new SchedulerClient({ baseURL: 'http://localhost:8080' });
      this.notification = new NotificationClient({ baseURL: 'http://localhost:8080' });
      this.evolution = new EvolutionClient({ baseURL: 'http://localhost:8080' });
    }
  }
}

// Re-export types
export * from './types.js';
export { RegistryClient } from './registry-client.js';
export { LocalRegistry } from './local-registry.js';
export { MemoryClient } from './memory-client.js';
export { SchedulerClient } from './scheduler-client.js';
export { NotificationClient } from './notification-client.js';
export { EvolutionClient } from './evolution-client.js';
