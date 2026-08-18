import { RegistryClient } from './registry-client.js';
import type { RegistryClientConfig } from './types.js';

/**
 * Agent OS Client - main entry point
 */
export class AgentOSClient {
  public registry: RegistryClient;

  constructor(config: RegistryClientConfig) {
    this.registry = new RegistryClient(config);
  }
}

// Re-export types
export * from './types.js';
export { RegistryClient } from './registry-client.js';
