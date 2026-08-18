import type {
  AgentInfo,
  AgentStatus,
  AgentHeartbeat,
  StatusUpdate,
  Agent,
} from './types.js';

/**
 * Local in-memory registry for standalone mode
 * Does not require Agent OS backend
 */
export class LocalRegistry {
  private agents = new Map<string, Agent>();
  private heartbeats = new Map<string, Date>();

  async register(info: AgentInfo): Promise<Agent> {
    const agent: Agent = {
      id: info.agent_id,
      agent_id: info.agent_id,
      session_id: info.session_id || null,
      agent_type: info.type,
      status: 'idle',
      capabilities: info.capabilities || [],
      host: null,
      port: null,
      pid: null,
      version: null,
      metadata: info.metadata || {},
      last_heartbeat_at: new Date().toISOString(),
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    };
    this.agents.set(info.agent_id, agent);
    this.heartbeats.set(info.agent_id, new Date());
    console.log(`[LocalRegistry] Agent registered: ${info.agent_id}`);
    return agent;
  }

  async heartbeat(heartbeat: AgentHeartbeat): Promise<void> {
    const agent = this.agents.get(heartbeat.agent_id);
    if (!agent) {
      throw new Error(`Agent not found: ${heartbeat.agent_id}`);
    }
    agent.status = heartbeat.status;
    agent.last_heartbeat_at = new Date().toISOString();
    this.heartbeats.set(heartbeat.agent_id, new Date());
    console.log(`[LocalRegistry] Heartbeat: ${heartbeat.agent_id} (${heartbeat.status})`);
  }

  async updateStatus(update: StatusUpdate): Promise<void> {
    const agent = this.agents.get(update.agent_id);
    if (!agent) {
      throw new Error(`Agent not found: ${update.agent_id}`);
    }
    agent.status = update.status;
    agent.updated_at = new Date().toISOString();
    console.log(`[LocalRegistry] Status updated: ${update.agent_id} -> ${update.status}`);
  }

  async unregister(params: { agent_id: string }): Promise<void> {
    const agent = this.agents.get(params.agent_id);
    if (agent) {
      agent.status = 'offline';
      agent.updated_at = new Date().toISOString();
    }
    console.log(`[LocalRegistry] Agent unregistered: ${params.agent_id}`);
  }

  async listActive(): Promise<Agent[]> {
    return Array.from(this.agents.values()).filter(a => a.status !== 'offline');
  }

  async getAgent(agentId: string): Promise<Agent | null> {
    return this.agents.get(agentId) || null;
  }

  getAllAgents(): Agent[] {
    return Array.from(this.agents.values());
  }
}
