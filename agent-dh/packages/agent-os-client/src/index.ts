import { RegistryClient } from './registry-client.js';
import { LocalRegistry } from './local-registry.js';
import type { RegistryClientConfig } from './types.js';

/**
 * Agent OS Client - main entry point
 * Supports both remote (HTTP) and local (in-memory) modes
 */
export class AgentOSClient {
  public registry: RegistryClient | LocalRegistry;

  constructor(config?: RegistryClientConfig) {
    if (config && config.baseURL && config.baseURL !== 'local') {
      // Remote mode: connect to Agent OS backend
      this.registry = new RegistryClient(config);
    } else {
      // Local mode: in-memory registry, no backend needed
      this.registry = new LocalRegistry();
    }
  }
}

// Re-export types
export * from './types.js';
export { RegistryClient } from './registry-client.js';
export { LocalRegistry } from './local-registry.js';
