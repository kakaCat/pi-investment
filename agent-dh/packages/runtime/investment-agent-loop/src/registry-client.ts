import type { AgentOSClient } from '@pi-investment/agent-os-client';
import type {
  AgentInfo,
  AgentStatus,
  AgentHeartbeat,
  StatusUpdate,
} from './types.js';

/**
 * Registry client for Agent OS
 * Handles agent registration, heartbeat, and status updates
 */
export class RegistryClient {
  constructor(private osClient: AgentOSClient) {}

  /**
   * Register agent with Registry
   */
  async register(agentInfo: AgentInfo): Promise<void> {
    try {
      await this.osClient.registry.register(agentInfo);
      console.log(`[RegistryClient] Agent registered: ${agentInfo.agent_id}`);
    } catch (error) {
      console.error('[RegistryClient] Failed to register agent:', error);
      throw error;
    }
  }

  /**
   * Send heartbeat to Registry
   */
  async heartbeat(agentId: string, status: AgentStatus, metadata?: Record<string, any>): Promise<void> {
    try {
      const heartbeat: AgentHeartbeat = {
        agent_id: agentId,
        status,
        metadata,
      };
      await this.osClient.registry.heartbeat(heartbeat);
      console.log(`[RegistryClient] Heartbeat sent: ${agentId} (${status})`);
    } catch (error) {
      console.error('[RegistryClient] Failed to send heartbeat:', error);
      // Don't throw - heartbeat failures shouldn't crash the agent
    }
  }

  /**
   * Update agent status
   */
  async updateStatus(agentId: string, status: AgentStatus, message?: string): Promise<void> {
    try {
      const update: StatusUpdate = {
        agent_id: agentId,
        status,
        message,
      };
      await this.osClient.registry.updateStatus(update);
      console.log(`[RegistryClient] Status updated: ${agentId} -> ${status}`);
    } catch (error) {
      console.error('[RegistryClient] Failed to update status:', error);
      throw error;
    }
  }

  /**
   * Unregister agent from Registry
   */
  async unregister(agentId: string): Promise<void> {
    try {
      await this.osClient.registry.unregister({ agent_id: agentId });
      console.log(`[RegistryClient] Agent unregistered: ${agentId}`);
    } catch (error) {
      console.error('[RegistryClient] Failed to unregister agent:', error);
      // Don't throw - unregister failures shouldn't crash shutdown
    }
  }
}
