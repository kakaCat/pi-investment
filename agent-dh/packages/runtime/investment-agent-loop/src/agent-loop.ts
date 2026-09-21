import type { Context } from '@deepseek-ai/cordis';
import { InvestmentAgent, type AgentOptions } from './agent.js';
import { RegistryClient } from './registry-client.js';
import type { AgentOSClient, AgentInfo } from './types.js';

/**
 * Agent Loop configuration
 */
export interface AgentLoopConfig {
  /** Agent OS client */
  osClient: AgentOSClient;
  /** Agent type (e.g., 'worker', 'scheduler') */
  agentType: string;
  /** Agent capabilities */
  capabilities: string[];
  /** Heartbeat interval in milliseconds (default: 30000) */
  heartbeatInterval?: number;
}

/**
 * Investment Agent Loop
 * Custom agent loop with Registry integration
 */
export class InvestmentAgentLoop {
  private registryClient: RegistryClient;
  private agents: Map<string, InvestmentAgent> = new Map();

  constructor(
    private ctx: Context,
    private config: AgentLoopConfig
  ) {
    this.registryClient = new RegistryClient(config.osClient);
  }

  /**
   * Create a new agent
   */
  async create(sessionId: string, options?: AgentOptions): Promise<InvestmentAgent> {
    console.log(`[InvestmentAgentLoop] Creating agent for session: ${sessionId}`);

    try {
      // Create session (placeholder - in real implementation, use DSH session manager)
      const session = { id: sessionId };

      // Merge options with config defaults
      const mergedOptions: AgentOptions = {
        agentId: options?.agentId || `agent-${sessionId}`,
        type: options?.type || this.config.agentType,
        capabilities: options?.capabilities || this.config.capabilities,
      };

      // Register agent with Registry
      const agentInfo: AgentInfo = {
        agent_id: mergedOptions.agentId!,
        session_id: sessionId,
        type: mergedOptions.type!,
        capabilities: mergedOptions.capabilities!,
        status: 'idle',
      };

      await this.registryClient.register(agentInfo);

      // Create agent
      const agent = new InvestmentAgent(this.ctx, session, mergedOptions, this.registryClient);

      // Start agent
      await agent.start();

      // Store agent
      this.agents.set(agent.agentId, agent);

      console.log(`[InvestmentAgentLoop] Agent created: ${agent.agentId}`);

      return agent;
    } catch (error) {
      console.error('[InvestmentAgentLoop] Failed to create agent:', error);
      throw error;
    }
  }

  /**
   * Resume an existing agent
   */
  async resume(sessionId: string, options?: AgentOptions): Promise<InvestmentAgent> {
    console.log(`[InvestmentAgentLoop] Resuming agent for session: ${sessionId}`);
    
    // For now, just create a new agent
    // In real implementation, restore from persisted state
    return this.create(sessionId, options);
  }

  /**
   * Get an agent by ID
   */
  getAgent(agentId: string): InvestmentAgent | undefined {
    return this.agents.get(agentId);
  }

  /**
   * Stop an agent
   */
  async stopAgent(agentId: string): Promise<void> {
    const agent = this.agents.get(agentId);
    if (!agent) {
      console.warn(`[InvestmentAgentLoop] Agent not found: ${agentId}`);
      return;
    }

    await agent.stop();
    this.agents.delete(agentId);
  }

  /**
   * Stop all agents
   */
  async stopAll(): Promise<void> {
    console.log('[InvestmentAgentLoop] Stopping all agents...');
    
    const stopPromises = Array.from(this.agents.values()).map(agent => agent.stop());
    await Promise.all(stopPromises);
    
    this.agents.clear();
  }

  /**
   * Get all agents
   */
  getAllAgents(): InvestmentAgent[] {
    return Array.from(this.agents.values());
  }
}
