import { BaseHTTPClient } from '../http/client.js';
import { ResourceQuota, Namespace, ResourceUsage } from './types.js';

/**
 * Resource Client - Manage quotas and namespaces
 */
export class ResourceClient {
  constructor(private http: BaseHTTPClient) {}

  /**
   * Get quota for an agent
   */
  async getQuota(agentId?: string): Promise<ResourceQuota> {
    const id = agentId || this.http.getAgentId();
    if (!id) {
      throw new Error('Agent ID is required');
    }
    return this.http.get<ResourceQuota>(`/api/v1/resource/quota/${id}`);
  }

  /**
   * List all quotas
   */
  async listQuotas(): Promise<ResourceQuota[]> {
    return this.http.get<ResourceQuota[]>('/api/v1/resource/quota');
  }

  /**
   * Get namespace info
   */
  async getNamespace(name: string): Promise<Namespace> {
    return this.http.get<Namespace>(`/api/v1/resource/namespaces/${name}`);
  }

  /**
   * List namespaces
   */
  async listNamespaces(): Promise<Namespace[]> {
    return this.http.get<Namespace[]>('/api/v1/resource/namespaces');
  }

  /**
   * Get resource usage history
   */
  async getUsage(agentId?: string, hours?: number): Promise<ResourceUsage[]> {
    const id = agentId || this.http.getAgentId();
    if (!id) {
      throw new Error('Agent ID is required');
    }
    return this.http.get<ResourceUsage[]>(`/api/v1/resource/usage/${id}`, { hours: hours || 24 });
  }

  /**
   * Check if quota is available
   */
  async checkQuota(agentId?: string, tokensNeeded?: number): Promise<{ available: boolean; remaining: number }> {
    const id = agentId || this.http.getAgentId();
    if (!id) {
      throw new Error('Agent ID is required');
    }
    return this.http.post(`/api/v1/resource/quota/${id}/check`, { tokens_needed: tokensNeeded });
  }
}
