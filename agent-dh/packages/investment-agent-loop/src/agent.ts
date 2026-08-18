import type { Context } from '@deepseek-ai/cordis';
import type { AgentStatus } from './types.js';
import { RegistryClient } from './registry-client.js';

/**
 * Agent options
 */
export interface AgentOptions {
  agentId?: string;
  type?: string;
  capabilities?: string[];
}

/**
 * Investment Agent with Registry integration
 */
export class InvestmentAgent {
  public readonly agentId: string;
  public readonly sessionId: string;
  private status: AgentStatus = 'idle';
  private heartbeatInterval?: NodeJS.Timeout;
  private heartbeatFailures = 0;
  private readonly maxHeartbeatFailures = 3;
  private isStopping = false;

  constructor(
    private ctx: Context,
    private session: any, // DSH Session type
    private options: AgentOptions,
    private registryClient: RegistryClient
  ) {
    this.agentId = options.agentId || `agent-${session.id}`;
    this.sessionId = session.id;
  }

  /**
   * Start the agent
   */
  async start(): Promise<void> {
    console.log(`[InvestmentAgent] Starting agent: ${this.agentId}`);
    
    // Start heartbeat
    this.startHeartbeat();
    
    // Update status to idle
    await this.updateStatus('idle');
  }

  /**
   * Stop the agent
   */
  async stop(): Promise<void> {
    // Prevent multiple stop calls
    if (this.isStopping) {
      return;
    }
    this.isStopping = true;

    console.log(`[InvestmentAgent] Stopping agent: ${this.agentId}`);
    
    // Stop heartbeat
    this.stopHeartbeat();
    
    // Update status to offline
    try {
      await this.updateStatus('offline');
    } catch (error) {
      console.error(`[InvestmentAgent] Failed to update status to offline:`, error);
    }
    
    // Unregister
    try {
      await this.registryClient.unregister(this.agentId);
    } catch (error) {
      console.error(`[InvestmentAgent] Failed to unregister:`, error);
    }
  }

  /**
   * Execute a task
   */
  async executeTask(taskId: string, taskData: any): Promise<any> {
    console.log(`[InvestmentAgent] Executing task: ${taskId}`);
    
    try {
      // Update status to busy
      await this.updateStatus('busy');
      
      // Execute task logic here
      // For now, just simulate some work
      await new Promise(resolve => setTimeout(resolve, 100));
      
      // Update status to idle
      await this.updateStatus('idle');
      
      return { success: true, taskId };
    } catch (error) {
      console.error(`[InvestmentAgent] Task execution failed:`, error);
      await this.updateStatus('error');
      throw error;
    }
  }

  /**
   * Update agent status
   */
  private async updateStatus(status: AgentStatus): Promise<void> {
    this.status = status;
    await this.registryClient.updateStatus(this.agentId, status);
  }

  /**
   * Start heartbeat
   */
  private startHeartbeat(): void {
    if (this.heartbeatInterval) {
      return;
    }

    this.heartbeatInterval = setInterval(async () => {
      try {
        await this.registryClient.heartbeat(this.agentId, this.status);
        this.heartbeatFailures = 0; // Reset on success
      } catch (error) {
        this.heartbeatFailures++;
        console.error(
          `[InvestmentAgent] Heartbeat failed for ${this.agentId} (${this.heartbeatFailures}/${this.maxHeartbeatFailures}):`,
          error instanceof Error ? error.message : error
        );

        // Stop agent if too many consecutive failures
        if (this.heartbeatFailures >= this.maxHeartbeatFailures) {
          console.error(
            `[InvestmentAgent] Too many heartbeat failures for ${this.agentId}, stopping agent`
          );
          await this.stop();
        }
      }
    }, 30000); // 30 seconds
  }

  /**
   * Stop heartbeat
   */
  private stopHeartbeat(): void {
    if (this.heartbeatInterval) {
      clearInterval(this.heartbeatInterval);
      this.heartbeatInterval = undefined;
    }
  }

  /**
   * Get agent info
   */
  getInfo() {
    return {
      agentId: this.agentId,
      sessionId: this.sessionId,
      status: this.status,
      type: this.options.type,
      capabilities: this.options.capabilities,
    };
  }
}
