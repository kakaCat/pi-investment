/**
 * Agent OS Client Initialization
 *
 * Provides a singleton AgentOSClient instance for agent-ts to communicate
 * with Agent OS services (Scheduler, Memory, Decision, Notification, Resource).
 *
 * Architecture:
 * - agent-ts is a pure reasoning application
 * - All business logic goes through Agent OS via HTTP SDK
 * - This module manages the client lifecycle and configuration
 */

import { AgentOSClient, AgentOSConfig } from '@pi-investment/agent-os-client';
import { logger } from '../logging/index.js';

let clientInstance: AgentOSClient | null = null;

/**
 * Get or create the AgentOSClient singleton instance
 */
export function getAgentOSClient(): AgentOSClient {
  if (!clientInstance) {
    const config: AgentOSConfig = {
      baseURL: process.env.AGENT_OS_API_URL || 'http://localhost:8080',
      agentId: process.env.AGENT_ID || 'fin-agent',
      apiKey: process.env.AGENT_OS_API_KEY,
      timeout: parseInt(process.env.AGENT_OS_TIMEOUT || '30000', 10),
    };

    logger.info('[AgentOS] Initializing client', {
      baseURL: config.baseURL,
      agentId: config.agentId,
      hasApiKey: !!config.apiKey,
    });

    clientInstance = new AgentOSClient(config);
  }

  return clientInstance;
}

/**
 * Reset the client instance (for testing)
 */
export function resetAgentOSClient(): void {
  clientInstance = null;
}

/**
 * Check Agent OS health
 */
export async function checkAgentOSHealth(): Promise<boolean> {
  try {
    const client = getAgentOSClient();
    const health = await client.health();

    logger.info('[AgentOS] Health check passed', health);
    // Agent OS returns { status: "ok" } not "healthy"
    return health.status === 'ok' || health.status === 'healthy';
  } catch (error) {
    logger.error('[AgentOS] Health check failed', { error });
    return false;
  }
}

/**
 * Initialize Agent OS connection on startup
 */
export async function initializeAgentOS(): Promise<void> {
  logger.info('[AgentOS] Starting initialization...');

  const isHealthy = await checkAgentOSHealth();

  if (!isHealthy) {
    logger.warn('[AgentOS] Health check failed, but continuing (Agent OS may not be running)');
    // Don't throw - allow agent to start even if OS is not available
    // Tools will fail gracefully when called
  }

  logger.info('[AgentOS] Initialization complete');
}
