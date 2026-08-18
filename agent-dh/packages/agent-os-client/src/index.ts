import axios from 'axios';
import { RegistryClient } from './registry-client.js';
import { LocalRegistry } from './local-registry.js';
import {
  MemoryClient,
  NotificationClient,
  SchedulerClient,
  EvolutionClient,
} from './namespaces.js';
import type { RegistryClientConfig, AgentOSClientConfig } from './types.js';

/**
 * Agent OS Client - main entry point
 * Supports both remote (HTTP) and local (in-memory) modes
 */
export class AgentOSClient {
  public registry: RegistryClient | LocalRegistry;
  public memory: MemoryClient;
  public notification: NotificationClient;
  public scheduler: SchedulerClient;
  public evolution: EvolutionClient;
  public readonly agentId?: string;

  constructor(config?: AgentOSClientConfig) {
    this.agentId = config?.agentId;
    if (config && config.baseURL && config.baseURL !== 'local') {
      // Remote mode: connect to Agent OS backend
      this.registry = new RegistryClient(config as RegistryClientConfig);
      const http = axios.create({
        baseURL: config.baseURL,
        timeout: config.timeout || 30000,
        headers: {
          'Content-Type': 'application/json',
          ...config.headers,
        },
      });
      this.memory = new MemoryClient(http);
      this.notification = new NotificationClient(http);
      this.scheduler = new SchedulerClient(http);
      this.evolution = new EvolutionClient(http);
    } else {
      // Local mode: in-memory registry, no backend needed
      this.registry = new LocalRegistry();
      this.memory = new MemoryClient(null);
      this.notification = new NotificationClient(null);
      this.scheduler = new SchedulerClient(null);
      this.evolution = new EvolutionClient(null);
    }
  }
}

// Re-export types
export * from './types.js';
export * from './namespaces.js';
export { RegistryClient } from './registry-client.js';
export { LocalRegistry } from './local-registry.js';
