import type { AxiosInstance } from 'axios';

/**
 * Namespace clients for Agent OS capabilities:
 * memory / notification / scheduler / evolution.
 *
 * Remote mode talks to the Agent OS HTTP API (/api/v1/...).
 * Local mode (no backend) provides safe in-memory or stub fallbacks
 * so callers never crash in standalone mode.
 */

// ==================== Memory ====================

export interface MemorySearchParams {
  namespace?: string;
  query: string;
  top_k?: number;
}

export interface MemoryWriteParams {
  namespace?: string;
  content: string;
  importance?: number;
  tags?: string[];
}

interface MemoryEntry {
  memory_id: string;
  namespace: string;
  content: string;
  importance: number;
  tags?: string[];
  created_at: string;
}

export class MemoryClient {
  private local: MemoryEntry[] | null = null;

  constructor(private http: AxiosInstance | null) {
    if (!http) this.local = [];
  }

  async search(params: MemorySearchParams): Promise<any> {
    if (this.http) {
      // Real endpoint: GET /api/v1/memory/search?q=...&limit=...
      const response = await this.http.get('/api/v1/memory/search', {
        params: { q: params.query, limit: params.top_k },
      });
      const data = response.data;
      return {
        query: params.query,
        results: data.memories ?? data.results ?? [],
        total: data.total ?? 0,
      };
    }
    const items = (this.local ?? []).filter(
      (m) =>
        (!params.namespace || m.namespace === params.namespace) &&
        m.content.includes(params.query)
    );
    return { query: params.query, results: items.slice(0, params.top_k || 5), total: items.length };
  }

  async write(params: MemoryWriteParams): Promise<any> {
    if (this.http) {
      // Endpoint: POST /api/v1/memory (backend write route is WIP)
      const response = await this.http.post('/api/v1/memory', params);
      return response.data;
    }
    const entry: MemoryEntry = {
      memory_id: `local-${Date.now()}`,
      namespace: params.namespace || 'default',
      content: params.content,
      importance: params.importance ?? 0.5,
      tags: params.tags,
      created_at: new Date().toISOString(),
    };
    this.local?.push(entry);
    return { success: true, memory_id: entry.memory_id, message: 'stored in local memory' };
  }
}

// ==================== Notification ====================

export interface NotificationSendParams {
  channel?: string;
  title: string;
  content: string;
  urgency?: string;
}

export class NotificationClient {
  constructor(private http: AxiosInstance | null) {}

  async send(params: NotificationSendParams): Promise<any> {
    if (!this.http) {
      console.log(`[NotificationClient] (local mode) ${params.title}: ${params.content}`);
      return { success: true, message_id: `local-${Date.now()}`, note: 'local mode: logged only' };
    }
    // Real endpoint: POST /api/v1/notifications/send {channel, title, content}
    const response = await this.http.post('/api/v1/notifications/send', {
      channel: params.channel || 'feishu',
      title: params.title,
      content: params.content,
      urgency: params.urgency,
    });
    return response.data;
  }
}

// ==================== Scheduler ====================

export class SchedulerClient {
  constructor(private http: AxiosInstance | null) {}

  private ensureRemote() {
    if (!this.http) {
      throw new Error('Scheduler requires Agent OS backend (currently in local mode)');
    }
    return this.http;
  }

  async listTasks(): Promise<any> {
    // Real endpoint: GET /api/v1/scheduler/tasks
    const response = await this.ensureRemote().get('/api/v1/scheduler/tasks');
    return response.data;
  }

  async registerTask(params: {
    name: string;
    owner?: string;
    cron: string;
    command: string;
  }): Promise<any> {
    // Real endpoint: POST /api/v1/scheduler/tasks
    const response = await this.ensureRemote().post('/api/v1/scheduler/tasks', params);
    return response.data;
  }

  async triggerTask(params: { task_id: string }): Promise<any> {
    // Real endpoint: POST /api/v1/scheduler/tasks/{id}/trigger
    const response = await this.ensureRemote().post(
      `/api/v1/scheduler/tasks/${params.task_id}/trigger`
    );
    return response.data;
  }
}

// ==================== Evolution ====================

export class EvolutionClient {
  constructor(private http: AxiosInstance | null) {}

  private ensureRemote() {
    if (!this.http) {
      throw new Error('Evolution requires Agent OS backend (currently in local mode)');
    }
    return this.http;
  }

  async run(params: {
    strategy_id?: number;
    mode?: string;
    generations?: number;
  }): Promise<any> {
    // Endpoint: POST /api/v1/evolution/run (backend route is WIP)
    const response = await this.ensureRemote().post('/api/v1/evolution/run', params);
    return response.data;
  }

  async getLeaderboard(params?: { limit?: number }): Promise<any> {
    // Endpoint: GET /api/v1/evolution/leaderboard (backend route is WIP)
    const response = await this.ensureRemote().get('/api/v1/evolution/leaderboard', { params });
    return response.data;
  }
}
