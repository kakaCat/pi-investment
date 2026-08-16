import { BaseHTTPClient } from './http/client.js';

export interface SkillMetadata {
  id: string;
  name: string;
  description: string;
  category: string;
  owner: string;
  status: string;
  metadata?: Record<string, any>;
}

export interface SkillDetail {
  id: string;
  name: string;
  description: string;
  category: string;
  owner: string;
  status: string;
  content: string;
  version: string;
  created_at: string;
  updated_at: string;
  current_version_id?: string;
  metadata?: Record<string, any>;
}

export interface CreateSkillRequest {
  name: string;
  description: string;
  category: string;
  owner: string;
  content: string;
  author: string;
  metadata?: Record<string, any>;
}

export interface UpdateSkillRequest {
  content: string;
  author: string;
  commit_message: string;
}

export interface SkillVersion {
  id: string;
  skill_id: string;
  version: string;
  content: string;
  content_hash: string;
  author: string;
  commit_message: string;
  parent_version_id?: string;
  created_at: string;
  metadata?: Record<string, any>;
}

/**
 * Skills API Client
 *
 * Manages skills in Agent OS - versioned markdown documents that define
 * agent capabilities and instructions.
 */
export class SkillsClient {
  constructor(private http: BaseHTTPClient) {}

  /**
   * List all skills (metadata only, no content)
   */
  async list(params?: {
    owner?: string;
    status?: string;
  }): Promise<SkillMetadata[]> {
    const queryParams = new URLSearchParams();
    if (params?.owner) queryParams.append('owner', params.owner);
    if (params?.status) queryParams.append('status', params.status);

    const url = `/api/v1/skills${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
    const response = await this.http.get<{ skills: SkillMetadata[] }>(url);
    return response.skills || [];
  }

  /**
   * Get skill detail (includes content)
   */
  async get(id: string): Promise<SkillDetail> {
    return this.http.get<SkillDetail>(`/api/v1/skills/${id}`);
  }

  /**
   * Create a new skill
   */
  async create(data: CreateSkillRequest): Promise<SkillDetail> {
    return this.http.post<SkillDetail>('/api/v1/skills', data);
  }

  /**
   * Update skill (creates new version)
   */
  async update(id: string, data: UpdateSkillRequest): Promise<SkillVersion> {
    return this.http.put<SkillVersion>(`/api/v1/skills/${id}`, data);
  }

  /**
   * Delete a skill
   */
  async delete(id: string): Promise<void> {
    return this.http.delete<void>(`/api/v1/skills/${id}`);
  }

  /**
   * Find skill by name (convenience method)
   */
  async findByName(name: string, owner?: string): Promise<SkillMetadata | null> {
    const skills = await this.list({ owner });
    return skills.find(s => s.name === name) || null;
  }

  /**
   * Batch get skills by IDs
   */
  async batchGet(ids: string[]): Promise<SkillDetail[]> {
    const promises = ids.map(id => this.get(id));
    return Promise.all(promises);
  }
}
