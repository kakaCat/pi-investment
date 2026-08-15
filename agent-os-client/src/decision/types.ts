/**
 * Decision record in Agent OS
 */
export interface Decision {
  id: string;
  namespace: string;
  action: string;
  targets: string[];
  reasoning: string;
  confidence?: number;
  result?: 'pending' | 'approved' | 'rejected' | 'executed' | 'failed';
  metadata?: any;
  created_at: string;
  updated_at?: string;
}

/**
 * Decision record request
 */
export interface DecisionRecordRequest {
  namespace: string;
  action: string;
  targets: string[];
  reasoning: string;
  confidence?: number;
  metadata?: any;
}

/**
 * Decision tracking update
 */
export interface DecisionTrackingRequest {
  decision_id: string;
  result: 'approved' | 'rejected' | 'executed' | 'failed';
  outcome?: any;
  notes?: string;
}

/**
 * Decision list filters
 */
export interface DecisionListFilters {
  namespace?: string;
  action?: string;
  result?: 'pending' | 'approved' | 'rejected' | 'executed' | 'failed';
  date_from?: string;
  date_to?: string;
  limit?: number;
  offset?: number;
}

/**
 * Decision stats
 */
export interface DecisionStats {
  total_count: number;
  by_action: Record<string, number>;
  by_result: Record<string, number>;
  avg_confidence: number;
  success_rate: number;
}
