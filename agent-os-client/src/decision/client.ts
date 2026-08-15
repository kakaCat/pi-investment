import { BaseHTTPClient } from '../http/client.js';
import {
  Decision,
  DecisionRecordRequest,
  DecisionTrackingRequest,
  DecisionListFilters,
  DecisionStats,
} from './types.js';

/**
 * Decision Client - Record and track agent decisions
 */
export class DecisionClient {
  constructor(private http: BaseHTTPClient) {}

  /**
   * Record a decision
   */
  async record(request: DecisionRecordRequest): Promise<Decision> {
    return this.http.post<Decision>('/api/v1/decisions', request);
  }

  /**
   * Get decision by ID
   */
  async get(id: string): Promise<Decision> {
    return this.http.get<Decision>(`/api/v1/decisions/${id}`);
  }

  /**
   * List decisions with filters
   */
  async list(filters?: DecisionListFilters): Promise<Decision[]> {
    return this.http.get<Decision[]>('/api/v1/decisions', filters);
  }

  /**
   * Update decision result (tracking)
   */
  async track(request: DecisionTrackingRequest): Promise<Decision> {
    return this.http.post<Decision>('/api/v1/decisions/track', request);
  }

  /**
   * Get decision statistics
   */
  async stats(namespace?: string): Promise<DecisionStats> {
    return this.http.get<DecisionStats>('/api/v1/decisions/stats', { namespace });
  }

  /**
   * Query decisions by action and targets
   */
  async query(action: string, targets?: string[], namespace?: string): Promise<Decision[]> {
    return this.http.post<Decision[]>('/api/v1/decisions/query', {
      action,
      targets,
      namespace,
    });
  }
}
