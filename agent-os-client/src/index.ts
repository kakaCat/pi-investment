/**
 * @pi-investment/agent-os-client
 *
 * TypeScript SDK for Agent OS
 *
 * @example
 * ```typescript
 * import { AgentOSClient } from '@pi-investment/agent-os-client';
 *
 * const client = new AgentOSClient({
 *   baseURL: 'http://localhost:8080',
 *   agentId: 'fin-agent',
 * });
 *
 * // Scheduler
 * const tasks = await client.scheduler.listTasks();
 * await client.scheduler.registerTask({
 *   name: 'daily-task',
 *   owner: 'fin-agent',
 *   cron: '0 9 * * *',
 * });
 *
 * // Memory
 * await client.memory.write({
 *   namespace: 'fin-agent',
 *   content: 'Important insight',
 *   importance: 0.8,
 * });
 *
 * const results = await client.memory.search({
 *   namespace: 'fin-agent',
 *   query: 'insight',
 *   top_k: 10,
 * });
 *
 * // Decision
 * await client.decision.record({
 *   namespace: 'fin-agent',
 *   action: 'buy',
 *   targets: ['600519.SH'],
 *   reasoning: 'Strong fundamentals',
 *   confidence: 0.85,
 * });
 *
 * // Notification
 * await client.notification.send({
 *   title: 'Alert',
 *   content: 'Market condition changed',
 *   urgency: 'high',
 * });
 *
 * // Resource
 * const quota = await client.resource.getQuota();
 * console.log(`Tokens remaining: ${quota.token_quota - quota.token_used}`);
 * ```
 */

export { AgentOSClient } from './client.js';
export type { AgentOSConfig } from './http/client.js';
export { AgentOSError } from './http/client.js';

// Scheduler types
export type {
  Task,
  TaskCreateRequest,
  Execution,
  ExecutionUpdateRequest,
  TaskListFilters,
  ExecutionListFilters,
} from './scheduler/types.js';

// Memory types
export type {
  Memory,
  MemoryWriteRequest,
  MemorySearchRequest,
  MemorySearchResult,
  MemoryListFilters,
  MemoryStats,
} from './memory/types.js';

// Memory adapter (for backward compatibility with os-memory package)
export { OsMemoryStore } from './memory/adapter.js';
export type { OsMemoryEntry, OsMemorySearchResult } from './memory/adapter.js';

// Decision types
export type {
  Decision,
  DecisionRecordRequest,
  DecisionTrackingRequest,
  DecisionListFilters,
  DecisionStats,
} from './decision/types.js';

// Notification types
export type {
  NotificationChannel,
  NotificationSendRequest,
  Notification,
  NotificationListFilters,
} from './notification/types.js';

// Resource types
export type {
  ResourceQuota,
  Namespace,
  ResourceUsage,
} from './resource/types.js';
