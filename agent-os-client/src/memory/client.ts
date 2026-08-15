import { BaseHTTPClient } from '../http/client.js';
import {
  Memory,
  MemoryWriteRequest,
  MemorySearchRequest,
  MemorySearchResult,
  MemoryListFilters,
  MemoryStats,
} from './types.js';

/**
 * Memory Client - Manage agent memories
 */
export class MemoryClient {
  constructor(private http: BaseHTTPClient) {}

  /**
   * Write a memory
   */
  async write(request: MemoryWriteRequest): Promise<Memory> {
    return this.http.post<Memory>('/api/v1/memory', request);
  }

  /**
   * Search memories by query
   */
  async search(request: MemorySearchRequest): Promise<MemorySearchResult[]> {
    return this.http.post<MemorySearchResult[]>('/api/v1/memory/search', request);
  }

  /**
   * Get memory by ID
   */
  async get(id: string): Promise<Memory> {
    return this.http.get<Memory>(`/api/v1/memory/${id}`);
  }

  /**
   * List memories with filters
   */
  async list(filters?: MemoryListFilters): Promise<Memory[]> {
    return this.http.get<Memory[]>('/api/v1/memory', filters);
  }

  /**
   * Update memory
   */
  async update(id: string, updates: Partial<MemoryWriteRequest>): Promise<Memory> {
    return this.http.put<Memory>(`/api/v1/memory/${id}`, updates);
  }

  /**
   * Delete memory
   */
  async delete(id: string): Promise<void> {
    return this.http.delete<void>(`/api/v1/memory/${id}`);
  }

  /**
   * Get memory statistics
   */
  async stats(namespace?: string): Promise<MemoryStats> {
    return this.http.get<MemoryStats>('/api/v1/memory/stats', { namespace });
  }

  /**
   * Recall audit - trigger memory consolidation
   */
  async recallAudit(namespace: string, context?: string): Promise<{ consolidated: number }> {
    return this.http.post('/api/v1/memory/recall-audit', { namespace, context });
  }
}
