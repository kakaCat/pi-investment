# WP-4 (Revised): agent-os-client SDK + Integration Plan

> **Work Package**: WP-4 (Revised)  
> **Title**: agent-os-client SDK 封装 + agent-ts 集成  
> **Duration**: 2-3 days  
> **Status**: 🚧 Planning  
> **Architecture**: HTTP-based client SDK, NOT CLI binary

---

## 📋 Overview

提供一个 **agent-os-client** TypeScript SDK 包，通过 HTTP 调用 Agent OS API。

### 核心理念

1. **agent-os-client** = 轻量级 HTTP 客户端库
2. agent-ts 通过 SDK 调用 OS 功能（Scheduler/Memory/Decision/Data）
3. 所有通信走 HTTP API，不依赖 CLI 二进制
4. SDK 封装标准接口，agent-ts 业务代码不感知底层实现

---

## 🎯 Architecture Design

### Target Architecture

```
┌─────────────────────────────────────────────────────┐
│                   agent-ts                          │
│                                                     │
│  ┌──────────────────────────────────────┐         │
│  │  Business Logic (Tools/Skills)       │         │
│  └────────────────┬─────────────────────┘         │
│                   │                                │
│                   ↓ import                         │
│  ┌──────────────────────────────────────┐         │
│  │  agent-os-client SDK                 │         │
│  │  • SchedulerClient                   │         │
│  │  • MemoryClient                      │         │
│  │  • DecisionClient                    │         │
│  │  • DataClient                        │         │
│  │  • NotificationClient                │         │
│  └────────────────┬─────────────────────┘         │
│                   │                                │
│                   │ HTTP/JSON                      │
└───────────────────┼────────────────────────────────┘
                    ↓
    ┌───────────────────────────────────────┐
    │       Agent OS HTTP API               │
    │       (Go, port 8080)                 │
    │                                       │
    │  GET  /api/v1/scheduler/tasks        │
    │  POST /api/v1/scheduler/tasks        │
    │  POST /api/v1/scheduler/trigger      │
    │  GET  /api/v1/memory/search          │
    │  POST /api/v1/memory/write           │
    │  POST /api/v1/decisions              │
    │  POST /api/v1/data/quote             │
    │  ...                                 │
    └───────────────────────────────────────┘
```

**Benefits**:
- ✅ 轻量级（纯 HTTP，无进程调用开销）
- ✅ 跨语言（任何语言都可以实现 client）
- ✅ 易调试（HTTP 请求可抓包、日志）
- ✅ 性能好（HTTP keep-alive 复用连接）
- ✅ 类型安全（TypeScript SDK 提供完整类型）

---

## 📦 Part A: agent-os-client SDK (1 day)

### Task A1: SDK Project Setup (2 hours)

**Objective**: 创建独立的 TypeScript SDK 包

**Implementation**:

```bash
# Create SDK package
mkdir -p agent-os-client
cd agent-os-client

# Initialize
npm init -y
npm install axios @types/node

# Project structure
agent-os-client/
├── src/
│   ├── index.ts                    # Main entry
│   ├── client.ts                   # AgentOSClient
│   ├── scheduler/
│   │   ├── client.ts               # SchedulerClient
│   │   └── types.ts                # Task, Execution types
│   ├── memory/
│   │   ├── client.ts               # MemoryClient
│   │   └── types.ts                # Memory types
│   ├── decision/
│   │   ├── client.ts               # DecisionClient
│   │   └── types.ts                # Decision types
│   ├── data/
│   │   ├── client.ts               # DataClient
│   │   └── types.ts                # Quote, Kline types
│   ├── notification/
│   │   ├── client.ts               # NotificationClient
│   │   └── types.ts                # Notification types
│   └── http/
│       ├── client.ts               # Base HTTP client
│       └── types.ts                # Request/Response types
├── package.json
├── tsconfig.json
└── README.md
```

**Deliverables**:
- [ ] Package scaffolding
- [ ] TypeScript configuration
- [ ] Build script

---

### Task A2: Base HTTP Client (2 hours)

**Objective**: 实现基础 HTTP 客户端

**Implementation**: `src/http/client.ts`

```typescript
import axios, { AxiosInstance, AxiosRequestConfig } from 'axios';

export interface AgentOSConfig {
  baseURL: string;
  timeout?: number;
  agentId?: string;
  apiKey?: string;
}

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  error?: {
    code: string;
    message: string;
    details?: any;
  };
  metadata?: {
    timestamp: string;
    latency_ms?: number;
  };
}

export class BaseHTTPClient {
  private axios: AxiosInstance;
  private config: AgentOSConfig;

  constructor(config: AgentOSConfig) {
    this.config = config;
    this.axios = axios.create({
      baseURL: config.baseURL,
      timeout: config.timeout || 30000,
      headers: {
        'Content-Type': 'application/json',
        ...(config.agentId && { 'X-Agent-ID': config.agentId }),
        ...(config.apiKey && { 'Authorization': `Bearer ${config.apiKey}` }),
      },
    });

    // Response interceptor
    this.axios.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response) {
          const apiError = error.response.data?.error || {
            code: 'HTTP_ERROR',
            message: error.message,
          };
          throw new AgentOSError(apiError.code, apiError.message, apiError.details);
        }
        throw error;
      }
    );
  }

  async get<T>(path: string, params?: any): Promise<T> {
    const response = await this.axios.get<ApiResponse<T>>(path, { params });
    if (!response.data.success) {
      throw new AgentOSError(
        response.data.error?.code || 'UNKNOWN_ERROR',
        response.data.error?.message || 'Unknown error'
      );
    }
    return response.data.data;
  }

  async post<T>(path: string, data?: any): Promise<T> {
    const response = await this.axios.post<ApiResponse<T>>(path, data);
    if (!response.data.success) {
      throw new AgentOSError(
        response.data.error?.code || 'UNKNOWN_ERROR',
        response.data.error?.message || 'Unknown error'
      );
    }
    return response.data.data;
  }

  async put<T>(path: string, data?: any): Promise<T> {
    const response = await this.axios.put<ApiResponse<T>>(path, data);
    if (!response.data.success) {
      throw new AgentOSError(
        response.data.error?.code || 'UNKNOWN_ERROR',
        response.data.error?.message || 'Unknown error'
      );
    }
    return response.data.data;
  }

  async delete<T>(path: string): Promise<T> {
    const response = await this.axios.delete<ApiResponse<T>>(path);
    if (!response.data.success) {
      throw new AgentOSError(
        response.data.error?.code || 'UNKNOWN_ERROR',
        response.data.error?.message || 'Unknown error'
      );
    }
    return response.data.data;
  }
}

export class AgentOSError extends Error {
  constructor(
    public code: string,
    message: string,
    public details?: any
  ) {
    super(message);
    this.name = 'AgentOSError';
  }
}
```

**Deliverables**:
- [ ] BaseHTTPClient with error handling
- [ ] Request/response interceptors
- [ ] AgentOSError class
- [ ] Unit tests

---

### Task A3: SchedulerClient (3 hours)

**Objective**: 封装 Scheduler API

**Implementation**: `src/scheduler/client.ts`

```typescript
import { BaseHTTPClient } from '../http/client.js';
import { Task, TaskCreateRequest, Execution, TriggerRequest } from './types.js';

export class SchedulerClient {
  constructor(private http: BaseHTTPClient) {}

  /**
   * 列出所有任务
   */
  async listTasks(filters?: {
    owner?: string;
    status?: 'active' | 'paused';
    tags?: string[];
  }): Promise<Task[]> {
    return this.http.get<Task[]>('/api/v1/scheduler/tasks', filters);
  }

  /**
   * 注册新任务
   */
  async registerTask(request: TaskCreateRequest): Promise<Task> {
    return this.http.post<Task>('/api/v1/scheduler/tasks', request);
  }

  /**
   * 获取任务详情
   */
  async getTask(taskId: string): Promise<Task> {
    return this.http.get<Task>(`/api/v1/scheduler/tasks/${taskId}`);
  }

  /**
   * 手动触发任务
   */
  async triggerTask(taskId: string, params?: any): Promise<Execution> {
    return this.http.post<Execution>(`/api/v1/scheduler/tasks/${taskId}/trigger`, {
      params,
    });
  }

  /**
   * 删除任务
   */
  async deleteTask(taskId: string): Promise<void> {
    return this.http.delete<void>(`/api/v1/scheduler/tasks/${taskId}`);
  }

  /**
   * 列出任务执行历史
   */
  async listExecutions(taskId: string, limit?: number): Promise<Execution[]> {
    return this.http.get<Execution[]>(`/api/v1/scheduler/tasks/${taskId}/executions`, {
      limit: limit || 50,
    });
  }

  /**
   * 获取执行详情
   */
  async getExecution(executionId: string): Promise<Execution> {
    return this.http.get<Execution>(`/api/v1/scheduler/executions/${executionId}`);
  }

  /**
   * 更新执行状态（agent 回调）
   */
  async updateExecution(
    executionId: string,
    update: {
      status: 'running' | 'completed' | 'failed';
      result?: any;
      error?: string;
    }
  ): Promise<Execution> {
    return this.http.put<Execution>(`/api/v1/scheduler/executions/${executionId}`, update);
  }
}
```

**Types**: `src/scheduler/types.ts`

```typescript
export interface Task {
  id: string;
  name: string;
  description?: string;
  owner: string;
  cron?: string;
  priority: number;
  status: 'active' | 'paused';
  tags: string[];
  webhook_url?: string;
  created_at: string;
  updated_at: string;
}

export interface TaskCreateRequest {
  name: string;
  description?: string;
  owner: string;
  cron?: string;
  priority?: number;
  tags?: string[];
  webhook_url?: string;
}

export interface Execution {
  id: string;
  task_id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  started_at?: string;
  completed_at?: string;
  result?: any;
  error?: string;
  metadata?: any;
}
```

**Deliverables**:
- [ ] SchedulerClient implementation
- [ ] Type definitions
- [ ] JSDoc comments
- [ ] Unit tests

---

### Task A4: MemoryClient (2 hours)

**Objective**: 封装 Memory API

**Implementation**: `src/memory/client.ts`

```typescript
import { BaseHTTPClient } from '../http/client.js';
import { Memory, MemoryWriteRequest, MemorySearchRequest } from './types.js';

export class MemoryClient {
  constructor(private http: BaseHTTPClient) {}

  async write(request: MemoryWriteRequest): Promise<Memory> {
    return this.http.post<Memory>('/api/v1/memory', request);
  }

  async search(request: MemorySearchRequest): Promise<Memory[]> {
    return this.http.post<Memory[]>('/api/v1/memory/search', request);
  }

  async get(id: string): Promise<Memory> {
    return this.http.get<Memory>(`/api/v1/memory/${id}`);
  }

  async list(filters?: {
    namespace?: string;
    category?: string;
    limit?: number;
  }): Promise<Memory[]> {
    return this.http.get<Memory[]>('/api/v1/memory', filters);
  }
}
```

**Types**: `src/memory/types.ts`

```typescript
export interface Memory {
  id: string;
  namespace: string;
  content: string;
  category?: string;
  importance?: number;
  metadata?: any;
  created_at: string;
}

export interface MemoryWriteRequest {
  namespace: string;
  content: string;
  category?: string;
  importance?: number;
  metadata?: any;
}

export interface MemorySearchRequest {
  namespace: string;
  query: string;
  top_k?: number;
  min_importance?: number;
  category?: string;
}
```

---

### Task A5: DecisionClient & DataClient (2 hours)

**Implementation**: Similar to SchedulerClient and MemoryClient

`src/decision/client.ts`:
```typescript
export class DecisionClient {
  async record(request: DecisionRecordRequest): Promise<Decision> { ... }
  async list(filters?: DecisionFilters): Promise<Decision[]> { ... }
  async get(id: string): Promise<Decision> { ... }
}
```

`src/data/client.ts`:
```typescript
export class DataClient {
  async getQuote(symbol: string): Promise<Quote> { ... }
  async getKline(symbol: string, options?: KlineOptions): Promise<Kline[]> { ... }
  async getFundamentals(symbol: string): Promise<Fundamentals> { ... }
}
```

---

### Task A6: Main AgentOSClient (1 hour)

**Objective**: 聚合所有子客户端

**Implementation**: `src/client.ts`

```typescript
import { BaseHTTPClient, AgentOSConfig } from './http/client.js';
import { SchedulerClient } from './scheduler/client.js';
import { MemoryClient } from './memory/client.js';
import { DecisionClient } from './decision/client.js';
import { DataClient } from './data/client.js';
import { NotificationClient } from './notification/client.js';

export class AgentOSClient {
  private http: BaseHTTPClient;

  public scheduler: SchedulerClient;
  public memory: MemoryClient;
  public decision: DecisionClient;
  public data: DataClient;
  public notification: NotificationClient;

  constructor(config: AgentOSConfig) {
    this.http = new BaseHTTPClient(config);

    this.scheduler = new SchedulerClient(this.http);
    this.memory = new MemoryClient(this.http);
    this.decision = new DecisionClient(this.http);
    this.data = new DataClient(this.http);
    this.notification = new NotificationClient(this.http);
  }
}

// Export everything
export * from './http/client.js';
export * from './scheduler/types.js';
export * from './memory/types.js';
export * from './decision/types.js';
export * from './data/types.js';
export * from './notification/types.js';
```

**Main entry**: `src/index.ts`

```typescript
export { AgentOSClient, AgentOSConfig, AgentOSError } from './client.js';
export * from './scheduler/types.js';
export * from './memory/types.js';
export * from './decision/types.js';
export * from './data/types.js';
export * from './notification/types.js';
```

**Deliverables**:
- [ ] AgentOSClient main class
- [ ] Clean exports
- [ ] README with usage examples

---

## 📦 Part B: agent-ts Integration (1-1.5 days)

### Task B1: Install SDK (0.5 hour)

```bash
cd agent-ts
npm install ../agent-os-client  # Local path or publish to npm
```

Or publish to npm:
```bash
cd agent-os-client
npm publish
cd ../agent-ts
npm install @pi-investment/agent-os-client
```

---

### Task B2: Initialize Client (1 hour)

**Implementation**: `agent-ts/src/infrastructure/agent-os/client.ts`

```typescript
import { AgentOSClient } from '@pi-investment/agent-os-client';

let clientInstance: AgentOSClient | null = null;

export function initAgentOSClient(config?: {
  baseURL?: string;
  agentId?: string;
  apiKey?: string;
}): AgentOSClient {
  if (!clientInstance) {
    clientInstance = new AgentOSClient({
      baseURL: config?.baseURL || process.env.AGENT_OS_API_URL || 'http://localhost:8080',
      agentId: config?.agentId || process.env.AGENT_ID || 'fin-agent',
      apiKey: config?.apiKey || process.env.AGENT_OS_API_KEY,
      timeout: 30000,
    });

    console.log('✅ Agent OS Client initialized');
  }

  return clientInstance;
}

export function getAgentOSClient(): AgentOSClient {
  if (!clientInstance) {
    throw new Error('Agent OS Client not initialized. Call initAgentOSClient() first.');
  }
  return clientInstance;
}
```

**Startup hook**: `agent-ts/src/index.ts`

```typescript
import { initAgentOSClient } from './infrastructure/agent-os/client.js';

async function main() {
  // Initialize Agent OS client
  const osClient = initAgentOSClient();

  // Register tasks
  await registerTasksToOS(osClient);

  // Start agent
  // ...
}
```

---

### Task B3: Update Tools to Use SDK (4 hours)

**Example**: Update `pool-manage` tool

**Before** (`agent-ts/src/infrastructure/tools/pool-manage.ts`):
```typescript
// Direct call to quantsys-v2
const response = await axios.post('http://localhost:5001/api/pools/manage', params);
```

**After**:
```typescript
import { getAgentOSClient } from '../agent-os/client.js';

async function poolManage(params: PoolManageParams) {
  const client = getAgentOSClient();
  
  // Call through Agent OS Data API
  const pools = await client.data.poolManage(params);
  
  return pools;
}
```

**Tools to update**:
- `pool-manage` → `client.data.poolManage()`
- `signal-scan` → `client.data.signalScan()`
- `memory-write` → `client.memory.write()`
- `memory-search` → `client.memory.search()`
- `decision-record` → `client.decision.record()`

---

### Task B4: Task Registration (3 hours)

**Implementation**: `agent-ts/src/infrastructure/agent-os/task-registry.ts`

```typescript
import { getAgentOSClient } from './client.js';
import { loadAllSkills } from '../skills/loader.js';

export async function registerTasksToOS(): Promise<void> {
  const client = getAgentOSClient();
  const skills = await loadAllSkills();

  const tasks = skills
    .filter((skill) => skill.schedule)
    .map((skill) => ({
      name: skill.name,
      description: skill.description || '',
      owner: 'fin-agent',
      cron: skill.schedule!.cron,
      priority: skill.schedule!.priority || 5,
      tags: skill.schedule!.tags || [],
      webhook_url: process.env.AGENT_WEBHOOK_URL || 'http://localhost:3000/api/webhook/trigger',
    }));

  console.log(`📝 Registering ${tasks.length} tasks to Agent OS...`);

  for (const task of tasks) {
    try {
      const existing = await client.scheduler.listTasks({ owner: 'fin-agent' });
      const found = existing.find((t) => t.name === task.name);

      if (found) {
        console.log(`  ✓ Task already registered: ${task.name}`);
      } else {
        await client.scheduler.registerTask(task);
        console.log(`  ✅ Registered: ${task.name}`);
      }
    } catch (error: any) {
      console.error(`  ❌ Failed to register ${task.name}:`, error.message);
    }
  }

  console.log('✅ Task registration complete');
}
```

---

### Task B5: Webhook Endpoint (3 hours)

**Implementation**: `agent-ts/src/api/webhook.ts`

```typescript
import express from 'express';
import { SessionOrchestrator } from '../core/orchestrator.js';
import { getAgentOSClient } from '../infrastructure/agent-os/client.js';

const router = express.Router();

router.post('/trigger', async (req, res) => {
  const { task_id, task_name, execution_id, params } = req.body;

  console.log(`📥 Webhook: ${task_name} (execution: ${execution_id})`);

  // Respond immediately (async execution)
  res.status(202).json({ success: true, execution_id });

  // Execute in background
  executeTask(task_name, execution_id, params).catch((error) => {
    console.error(`❌ Task execution failed:`, error);
  });
});

async function executeTask(taskName: string, executionId: string, params: any) {
  const client = getAgentOSClient();

  try {
    // Update status to running
    await client.scheduler.updateExecution(executionId, { status: 'running' });

    // Create session and run task
    const orchestrator = new SessionOrchestrator();
    const session = await orchestrator.createSession({
      mode: 'auto',
      initialPrompt: `/skill ${taskName}`,
      metadata: { execution_id: executionId, params },
    });

    const result = await session.run();

    // Update status to completed
    await client.scheduler.updateExecution(executionId, {
      status: 'completed',
      result: result.summary,
    });

    console.log(`✅ Task completed: ${taskName}`);
  } catch (error: any) {
    // Update status to failed
    await client.scheduler.updateExecution(executionId, {
      status: 'failed',
      error: error.message,
    });

    console.error(`❌ Task failed: ${taskName}`, error);
  }
}

export default router;
```

---

### Task B6: Remove Local Cron (1 hour)

Same as original plan - remove `node-cron` code.

---

## 🗂️ File Structure

```
pi-investment/
├── agent-os-client/                    # NEW SDK Package
│   ├── src/
│   │   ├── index.ts
│   │   ├── client.ts
│   │   ├── http/
│   │   │   ├── client.ts
│   │   │   └── types.ts
│   │   ├── scheduler/
│   │   │   ├── client.ts
│   │   │   └── types.ts
│   │   ├── memory/
│   │   ├── decision/
│   │   ├── data/
│   │   └── notification/
│   ├── package.json
│   ├── tsconfig.json
│   └── README.md
│
├── agent-ts/
│   ├── src/
│   │   ├── infrastructure/
│   │   │   └── agent-os/
│   │   │       ├── client.ts           # NEW - SDK wrapper
│   │   │       └── task-registry.ts    # NEW
│   │   ├── api/
│   │   │   └── webhook.ts              # NEW
│   │   └── index.ts                    # UPDATED - init client
│   └── package.json                    # UPDATED - add dependency
│
└── agent-os/
    └── internal/
        └── api/
            └── http_server.go          # ENSURE HTTP API routes exist
```

---

## 🧪 Testing

### SDK Unit Tests

```typescript
// agent-os-client/src/__tests__/scheduler.test.ts
import { AgentOSClient } from '../client.js';

describe('SchedulerClient', () => {
  let client: AgentOSClient;

  beforeAll(() => {
    client = new AgentOSClient({
      baseURL: 'http://localhost:8080',
      agentId: 'test-agent',
    });
  });

  it('should list tasks', async () => {
    const tasks = await client.scheduler.listTasks();
    expect(Array.isArray(tasks)).toBe(true);
  });

  it('should register a task', async () => {
    const task = await client.scheduler.registerTask({
      name: 'test-task',
      owner: 'test-agent',
      cron: '*/5 * * * *',
    });
    expect(task.id).toBeDefined();
  });
});
```

### Integration Tests

```bash
# Start Agent OS
agent-os serve --port 8080

# Run SDK tests
cd agent-os-client
npm test

# Start agent-ts
cd agent-ts
npm start

# Verify tasks registered
agent-os scheduler list | grep fin-agent
```

---

## 📊 Timeline

### Day 1: SDK Development (8 hours)
- Hour 1-2: Project setup + Base HTTP client
- Hour 3-5: SchedulerClient
- Hour 6-7: MemoryClient
- Hour 8: DecisionClient + DataClient

### Day 2: SDK Completion + Integration (8 hours)
- Hour 1: Main AgentOSClient + exports
- Hour 2: SDK tests + documentation
- Hour 3: Install SDK in agent-ts
- Hour 4: Initialize client + update tools (Part 1)
- Hour 5-7: Update tools (Part 2)
- Hour 8: Task registration

### Day 3: Webhook + Cleanup (6 hours)
- Hour 1-3: Webhook endpoint
- Hour 4-5: Remove local cron
- Hour 6: Integration testing

**Total: 22 hours (~3 days)**

---

## ✅ Acceptance Criteria

### SDK
- [ ] agent-os-client package compiles
- [ ] All clients (Scheduler/Memory/Decision/Data) implemented
- [ ] TypeScript types complete
- [ ] Unit tests passing
- [ ] README with examples
- [ ] Published to npm (or local install)

### agent-ts Integration
- [ ] SDK installed and initialized
- [ ] Tools updated to use SDK
- [ ] Tasks auto-register on startup
- [ ] Webhook receives triggers
- [ ] Local cron removed
- [ ] Integration tests passing

### Performance
- [ ] HTTP call latency < 100ms (local)
- [ ] Task registration < 5s (all tasks)
- [ ] Webhook response < 1s

---

## 🚀 Usage Example

```typescript
// In agent-ts tools
import { getAgentOSClient } from '../infrastructure/agent-os/client.js';

async function myTool() {
  const client = getAgentOSClient();
  
  // Use SDK
  const quote = await client.data.getQuote('600519.SH');
  
  await client.memory.write({
    namespace: 'fin-agent',
    content: `获取了 ${quote.symbol} 报价`,
    category: 'tool-execution',
  });
  
  await client.decision.record({
    namespace: 'fin-agent',
    action: 'watch',
    targets: [quote.symbol],
    reasoning: '价格合适',
  });
  
  return quote;
}
```

---

**Status**: Ready to start  
**Next Action**: Create agent-os-client package structure  
**Key Difference**: HTTP SDK, NOT CLI binary!
