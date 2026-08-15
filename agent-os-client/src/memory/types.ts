/**
 * Memory record in Agent OS
 */
export interface Memory {
  id: string;
  namespace: string;
  content: string;
  category?: string;
  importance?: number;
  metadata?: any;
  created_at: string;
  updated_at?: string;
}

/**
 * Memory write request
 */
export interface MemoryWriteRequest {
  namespace: string;
  content: string;
  category?: string;
  importance?: number;
  metadata?: any;
}

/**
 * Memory search request
 */
export interface MemorySearchRequest {
  namespace: string;
  query: string;
  top_k?: number;
  min_importance?: number;
  category?: string;
  filters?: {
    date_from?: string;
    date_to?: string;
    tags?: string[];
  };
}

/**
 * Memory search result
 */
export interface MemorySearchResult {
  memory: Memory;
  score: number;
  relevance: number;
}

/**
 * Memory list filters
 */
export interface MemoryListFilters {
  namespace?: string;
  category?: string;
  min_importance?: number;
  limit?: number;
  offset?: number;
}

/**
 * Memory stats
 */
export interface MemoryStats {
  total_count: number;
  by_category: Record<string, number>;
  by_namespace: Record<string, number>;
  avg_importance: number;
}
