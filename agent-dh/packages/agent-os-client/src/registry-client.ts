import axios, { AxiosInstance } from 'axios';
import axiosRetry from 'axios-retry';
import type {
  AgentInfo,
  AgentHeartbeat,
  StatusUpdate,
  UnregisterRequest,
  Agent,
  RegistryClientConfig,
} from './types.js';

/**
 * Registry client for interacting with Agent OS Registry
 */
export class RegistryClient {
  private client: AxiosInstance;

  constructor(config: RegistryClientConfig) {
    this.client = axios.create({
      baseURL: config.baseURL,
      timeout: config.timeout || 30000,
      headers: {
        'Content-Type': 'application/json',
        ...config.headers,
      },
    });

    // Configure retry mechanism
    axiosRetry(this.client, {
      retries: 3,
      retryDelay: axiosRetry.exponentialDelay,
      retryCondition: (error) => {
        // Retry on network errors or 5xx server errors
        return axiosRetry.isNetworkOrIdempotentRequestError(error) ||
               (error.response?.status ? error.response.status >= 500 : false);
      },
      onRetry: (retryCount, error, requestConfig) => {
        console.log(
          `[RegistryClient] Retrying request (${retryCount}/3): ${requestConfig.method?.toUpperCase()} ${requestConfig.url}`
        );
      },
    });
  }

  /**
   * Register an agent
   */
  async register(info: AgentInfo): Promise<Agent> {
    // Validate input
    if (!info.agent_id || info.agent_id.trim() === '') {
      throw new Error('agent_id is required and cannot be empty');
    }
    if (!info.type || info.type.trim() === '') {
      throw new Error('type is required and cannot be empty');
    }
    if (!Array.isArray(info.capabilities)) {
      throw new Error('capabilities must be an array');
    }
    if (info.capabilities.length === 0) {
      throw new Error('capabilities cannot be empty');
    }
    
    try {
      const response = await this.client.post<Agent>(
        '/api/v1/registry/agents/register',
        info
      );
      return response.data;
    } catch (error) {
      console.error('[RegistryClient] Register failed:', error);
      throw error;
    }
  }

  /**
   * Send heartbeat
   */
  async heartbeat(heartbeat: AgentHeartbeat): Promise<void> {
    // Validate input
    if (!heartbeat.agent_id || heartbeat.agent_id.trim() === '') {
      throw new Error('agent_id is required and cannot be empty');
    }
    if (!heartbeat.status) {
      throw new Error('status is required');
    }
    const validStatuses: AgentStatus[] = ['idle', 'busy', 'offline', 'error'];
    if (!validStatuses.includes(heartbeat.status)) {
      throw new Error(`Invalid status: ${heartbeat.status}. Must be one of: ${validStatuses.join(', ')}`);
    }

    try {
      await this.client.post('/api/v1/registry/agents/heartbeat', heartbeat);
    } catch (error) {
      console.error('[RegistryClient] Heartbeat failed:', error);
      throw error;
    }
  }

  /**
   * Update agent status
   */
  async updateStatus(update: StatusUpdate): Promise<void> {
    // Validate input
    if (!update.agent_id || update.agent_id.trim() === '') {
      throw new Error('agent_id is required and cannot be empty');
    }
    if (!update.status) {
      throw new Error('status is required');
    }
    const validStatuses: AgentStatus[] = ['idle', 'busy', 'offline', 'error'];
    if (!validStatuses.includes(update.status)) {
      throw new Error(`Invalid status: ${update.status}. Must be one of: ${validStatuses.join(', ')}`);
    }

    try {
      await this.client.post('/api/v1/registry/agents/update-status', update);
    } catch (error) {
      console.error('[RegistryClient] Update status failed:', error);
      throw error;
    }
  }

  /**
   * Unregister an agent
   */
  async unregister(params: UnregisterRequest): Promise<void> {
    // Validate input
    if (!params.agent_id || params.agent_id.trim() === '') {
      throw new Error('agent_id is required and cannot be empty');
    }

    try {
      await this.client.post('/api/v1/registry/agents/unregister', params);
    } catch (error) {
      console.error('[RegistryClient] Unregister failed:', error);
      throw error;
    }
  }

  /**
   * List active agents
   */
  async listActive(capability?: string): Promise<Agent[]> {
    const response = await this.client.get<Agent[]>(
      '/api/v1/registry/agents/available',
      {
        params: capability ? { capability } : undefined,
      }
    );
    return response.data;
  }

  /**
   * Get agent info
   */
  async getAgent(agentId: string): Promise<Agent> {
    const response = await this.client.get<Agent>(
      `/api/v1/registry/agents/${agentId}`
    );
    return response.data;
  }
}
