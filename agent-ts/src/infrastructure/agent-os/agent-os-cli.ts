/**
 * Agent OS CLI Executor
 *
 * Provides a TypeScript interface to execute agent-os CLI commands
 * and parse their JSON output.
 */

import { execSync } from 'child_process';
import path from 'path';

// Agent OS CLI 路径配置
const AGENT_OS_PATH = process.env.AGENT_OS_PATH || path.join(__dirname, '../../../../agent-os/agent-os');

/**
 * Execute agent-os CLI command and return raw output
 */
export function execAgentOS(args: string[]): string {
  try {
    const command = `${AGENT_OS_PATH} ${args.join(' ')}`;
    const output = execSync(command, {
      encoding: 'utf-8',
      stdio: ['pipe', 'pipe', 'pipe'],
      maxBuffer: 10 * 1024 * 1024, // 10MB
    });
    return output.trim();
  } catch (error: any) {
    throw new Error(`Agent OS CLI error: ${error.message}\nStderr: ${error.stderr?.toString() || ''}`);
  }
}

/**
 * Execute agent-os CLI command with --json flag and parse result
 */
export function execAgentOSJSON<T = any>(args: string[]): T {
  const argsWithJSON = [...args, '--json'];
  const output = execAgentOS(argsWithJSON);

  try {
    return JSON.parse(output) as T;
  } catch (error: any) {
    throw new Error(`Failed to parse Agent OS JSON output: ${error.message}\nOutput: ${output}`);
  }
}

// ============================================================================
// Type Definitions
// ============================================================================

export interface Task {
  id: string;
  name: string;
  description?: string;
  schedule?: string;
  command: string;
  enabled: boolean;
  owner: string;
  created_at: string;
  updated_at: string;
  last_run_at?: string;
  last_run_status?: string;
  total_runs?: number;
  success_rate?: number;
}

export interface TaskRun {
  id: string;
  task_id: string;
  status: 'pending' | 'running' | 'success' | 'failed' | 'timeout' | 'canceled';
  started_at: string;
  ended_at?: string;
  duration_ms?: number;
  triggered_by: 'scheduler' | 'manual' | 'webhook' | 'dependency';
  output?: string;
  error?: string;
}

export interface ResourceQuota {
  namespace: string;
  resource_type: 'api_calls' | 'tokens' | 'memory';
  used: number;
  limit: number;
  usage_percent: number;
  unit: string;
  status: 'OK' | 'WARNING' | 'CRITICAL';
}

export interface Memory {
  id: string;
  namespace: string;
  content: string;
  category: 'user' | 'feedback' | 'project' | 'reference';
  importance: number;
  tags: string[];
  metadata: Record<string, any>;
  embedding?: number[];
  access_count: number;
  created_at: string;
  updated_at: string;
  last_accessed_at?: string;
}

export interface MemorySearchResult {
  memory: Memory;
  score: number;
  rank: number;
}

// ============================================================================
// Scheduler Namespace
// ============================================================================

export namespace Scheduler {
  export interface RegisterParams {
    name: string;
    description?: string;
    schedule?: string;
    command: string;
    enabled?: boolean;
    owner?: string;
  }

  export interface ListOptions {
    enabledOnly?: boolean;
    stats?: boolean;
  }

  /**
   * Register a new task
   */
  export function register(params: RegisterParams): string {
    const args = [
      'scheduler', 'register',
      '--name', params.name,
      '--command', params.command,
    ];

    if (params.description) {
      args.push('--description', params.description);
    }

    if (params.schedule) {
      args.push('--schedule', params.schedule);
    }

    if (params.enabled !== undefined) {
      args.push('--enabled', String(params.enabled));
    }

    if (params.owner) {
      args.push('--owner', params.owner);
    }

    const output = execAgentOS(args);

    // Extract task ID from output (format: "✓ Registered task: <name> (ID: <uuid>)")
    const match = output.match(/ID:\s*([a-f0-9-]+)/i);
    if (match) {
      return match[1];
    }

    throw new Error(`Failed to extract task ID from output: ${output}`);
  }

  /**
   * List all tasks
   */
  export function list(options: ListOptions = {}): Task[] {
    const args = ['scheduler', 'list'];

    if (options.enabledOnly) {
      args.push('--enabled-only');
    }

    if (options.stats) {
      args.push('--stats');
    }

    return execAgentOSJSON<Task[]>(args);
  }

  /**
   * Trigger a task manually
   */
  export function trigger(taskIdOrName: string): void {
    const args = ['scheduler', 'trigger'];

    // Check if it's a UUID or name
    if (/^[a-f0-9-]{36}$/i.test(taskIdOrName)) {
      args.push('--task-id', taskIdOrName);
    } else {
      args.push('--name', taskIdOrName);
    }

    execAgentOS(args);
  }

  /**
   * Get task execution history
   */
  export function executions(taskIdOrName: string, limit: number = 20): TaskRun[] {
    const args = ['scheduler', 'executions'];

    // Check if it's a UUID or name
    if (/^[a-f0-9-]{36}$/i.test(taskIdOrName)) {
      args.push('--task-id', taskIdOrName);
    } else {
      args.push('--name', taskIdOrName);
    }

    args.push('--limit', String(limit));

    return execAgentOSJSON<TaskRun[]>(args);
  }

  /**
   * Delete a task
   */
  export function deleteTask(taskIdOrName: string): void {
    const args = ['scheduler', 'delete'];

    // Check if it's a UUID or name
    if (/^[a-f0-9-]{36}$/i.test(taskIdOrName)) {
      args.push('--task-id', taskIdOrName);
    } else {
      args.push('--name', taskIdOrName);
    }

    execAgentOS(args);
  }
}

// ============================================================================
// Resource Namespace
// ============================================================================

export namespace Resource {
  /**
   * Get quotas for an agent
   */
  export function getQuota(agent: string): ResourceQuota[] {
    const args = ['resource', 'quota', 'get', '--agent', agent];
    return execAgentOSJSON<ResourceQuota[]>(args);
  }

  /**
   * Check if agent has enough quota
   */
  export function checkQuota(agent: string, type: string, amount: number): boolean {
    try {
      const quotas = getQuota(agent);
      const quota = quotas.find(q => q.resource_type === type);

      if (!quota) {
        return false;
      }

      return (quota.limit - quota.used) >= amount;
    } catch (error) {
      console.error(`Failed to check quota: ${error}`);
      return false;
    }
  }

  /**
   * Get usage overview for all agents
   */
  export function usageOverview(): ResourceQuota[] {
    const args = ['resource', 'usage', 'overview'];
    return execAgentOSJSON<ResourceQuota[]>(args);
  }
}

// ============================================================================
// Memory Namespace
// ============================================================================

export namespace Memory {
  export interface WriteParams {
    namespace?: string;
    content: string;
    category?: 'user' | 'feedback' | 'project' | 'reference';
    importance?: number;
    tags?: string[];
    metadata?: Record<string, any>;
  }

  export interface SearchParams {
    namespace?: string;
    query: string;
    categories?: string[];
    tags?: string[];
    minImportance?: number;
    limit?: number;
    hybrid?: boolean;
  }

  /**
   * Write a new memory
   */
  export function write(params: WriteParams): string {
    const args = [
      'memory', 'write',
      '--content', params.content,
    ];

    if (params.namespace) {
      args.push('--namespace', params.namespace);
    }

    if (params.category) {
      args.push('--category', params.category);
    }

    if (params.importance !== undefined) {
      args.push('--importance', String(params.importance));
    }

    if (params.tags && params.tags.length > 0) {
      args.push('--tags', params.tags.join(','));
    }

    if (params.metadata) {
      args.push('--metadata', JSON.stringify(params.metadata));
    }

    const output = execAgentOS(args);

    // Extract memory ID from output
    const match = output.match(/ID:\s*([a-f0-9-]+)/i);
    if (match) {
      return match[1];
    }

    throw new Error(`Failed to extract memory ID from output: ${output}`);
  }

  /**
   * Search memories
   */
  export function search(params: SearchParams): MemorySearchResult[] {
    const args = ['memory', 'search', '--query', params.query];

    if (params.namespace) {
      args.push('--namespace', params.namespace);
    }

    if (params.categories && params.categories.length > 0) {
      args.push('--categories', params.categories.join(','));
    }

    if (params.tags && params.tags.length > 0) {
      args.push('--tags', params.tags.join(','));
    }

    if (params.minImportance !== undefined) {
      args.push('--min-importance', String(params.minImportance));
    }

    if (params.limit) {
      args.push('--limit', String(params.limit));
    }

    if (params.hybrid) {
      args.push('--hybrid');
    }

    return execAgentOSJSON<MemorySearchResult[]>(args);
  }

  /**
   * Read a memory by ID
   */
  export function read(id: string): Memory {
    const args = ['memory', 'read', '--id', id];
    return execAgentOSJSON<Memory>(args);
  }

  /**
   * List memories with filters
   */
  export function list(options: {
    namespace?: string;
    category?: string;
    tags?: string[];
    limit?: number;
  } = {}): Memory[] {
    const args = ['memory', 'list'];

    if (options.namespace) {
      args.push('--namespace', options.namespace);
    }

    if (options.category) {
      args.push('--category', options.category);
    }

    if (options.tags && options.tags.length > 0) {
      args.push('--tags', options.tags.join(','));
    }

    if (options.limit) {
      args.push('--limit', String(options.limit));
    }

    return execAgentOSJSON<Memory[]>(args);
  }

  /**
   * Delete a memory
   */
  export function deleteMemory(id: string): void {
    const args = ['memory', 'delete', '--id', id];
    execAgentOS(args);
  }
}
