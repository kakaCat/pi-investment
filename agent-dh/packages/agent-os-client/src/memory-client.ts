import { AxiosInstance } from 'axios';
import { createHttpClient } from './http.js';
import type {
  MemorySearchParams,
  MemorySearchResponse,
  MemoryWriteParams,
  MemoryWriteResponse,
  RegistryClientConfig,
} from './types.js';

/**
 * MemoryClient — Agent OS memory APIs.
 *
 * Server contract (verified live):
 *   GET  /api/v1/memory/search?q=&limit=&category=&tag=
 *   GET  /api/v1/memory (list, category/tag/limit)
 *   POST /api/v1/memory (write — added for the tool chain)
 *
 * Client translation: plugin passes `top_k` / `namespace`,
 * the server understands `limit` / `category`.
 */
export class MemoryClient {
  private client: AxiosInstance;

  constructor(config: RegistryClientConfig) {
    this.client = createHttpClient(config);
  }

  /**
   * Semantic / keyword memory search.
   */
  async search(params: MemorySearchParams): Promise<MemorySearchResponse> {
    if (!params.query || params.query.trim() === '') {
      throw new Error('query is required');
    }
    const response = await this.client.get<MemorySearchResponse>(
      '/api/v1/memory/search',
      {
        params: {
          q: params.query,
          limit: params.top_k && params.top_k > 0 ? params.top_k : undefined,
          category: params.category || undefined,
          tag: params.tag || undefined,
          include_closed: params.includeClosed || undefined,
        },
      }
    );
    return response.data;
  }

  /**
   * Write a memory record. `namespace` maps to the server `category`
   * (knowledge | experience | decision | data); `importance` is a
   * client-side hint attached to the content metadata.
   */
  async write(params: MemoryWriteParams): Promise<MemoryWriteResponse> {
    if (!params.content || params.content.trim() === '') {
      throw new Error('content is required');
    }
    const namespace = params.namespace || 'knowledge';
    const categories = ['knowledge', 'experience', 'decision', 'data'];
    const category = categories.includes(namespace) ? namespace : 'knowledge';

    const response = await this.client.post<MemoryWriteResponse>(
      '/api/v1/memory',
      {
        title: params.title || namespace,
        content: params.content,
        category,
        tags: params.tags || [],
        // importance rides along in metadata — kept for the learning pipeline
        metadata: params.importance !== undefined
          ? { importance: params.importance }
          : undefined,
      }
    );
    return response.data;
  }

  /**
   * Update a memory record (RFC 009 W3).
   * Supports content updates and metadata patches with optional optimistic locking.
   */
  async patchMemory(
    id: string,
    patch: {
      content?: string;
      metadataPatch?: Record<string, any>;
      expectedRevision?: number;
    }
  ): Promise<any> {
    if (!id) {
      throw new Error('id is required');
    }
    const response = await this.client.patch(`/api/v1/memory/${id}`, {
      content: patch.content,
      metadata_patch: patch.metadataPatch,
      expected_revision: patch.expectedRevision,
    });
    return response.data;
  }

  /**
   * Delete a memory record (RFC 009 W3).
   * Soft delete: sets board_status=dropped in metadata.
   */
  async deleteMemory(id: string, reason?: string): Promise<void> {
    if (!id) {
      throw new Error('id is required');
    }
    await this.client.delete(`/api/v1/memory/${id}`, {
      data: reason ? { reason } : undefined,
    });
  }
}
