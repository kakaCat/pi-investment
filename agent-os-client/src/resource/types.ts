/**
 * Resource quota
 */
export interface ResourceQuota {
  agent_id: string;
  token_quota: number;
  token_used: number;
  memory_quota_mb: number;
  memory_used_mb: number;
  cpu_quota_percent: number;
  cpu_used_percent: number;
  reset_at?: string;
}

/**
 * Namespace info
 */
export interface Namespace {
  id: string;
  name: string;
  owner: string;
  quota?: ResourceQuota;
  permissions: string[];
  created_at: string;
}

/**
 * Resource usage
 */
export interface ResourceUsage {
  agent_id: string;
  timestamp: string;
  tokens_consumed: number;
  memory_mb: number;
  cpu_percent: number;
  requests_count: number;
}
