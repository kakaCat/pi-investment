# WP-4: agent-ts 集成计划

> **开始时间**: 2026-08-14  
> **预计工期**: 2 天  
> **目标**: agent-ts 完全依赖 Agent OS，删除本地调度和存储逻辑

---

## 📋 工作内容

### 1. CLI 执行器（agent-os-cli.ts）

**位置**: `agent-ts/src/infrastructure/agent-os/agent-os-cli.ts`

**功能**:
```typescript
// 执行 agent-os CLI 命令的封装
export async function execAgentOS(args: string[]): Promise<any>
export async function execAgentOSJSON(args: string[]): Promise<any>

// 便捷方法
export namespace AgentOS {
  export namespace Scheduler {
    function register(task: TaskDef): Promise<string>
    function list(options?: ListOptions): Promise<Task[]>
    function trigger(taskId: string): Promise<void>
    function executions(taskId: string): Promise<TaskRun[]>
  }
  
  export namespace Resource {
    function getQuota(agent: string): Promise<Quota[]>
    function checkQuota(agent: string, type: string, amount: number): Promise<boolean>
  }
  
  export namespace Memory {
    function write(memory: MemoryInput): Promise<string>
    function search(query: SearchQuery): Promise<Memory[]>
    function read(id: string): Promise<Memory>
  }
}
```

**实现要点**:
- 使用 `child_process.execSync` 或 `execa` 调用 `agent-os` CLI
- 自动解析 JSON 输出
- 错误处理和重试
- 日志记录

---

### 2. 工具改写

#### 2.1 memory_write 工具

**当前**: 直接写入本地文件 `.claude/memory/`  
**改为**: 调用 `agent-os memory write`

**代码位置**: `agent-ts/src/infrastructure/tools/memory/memory_write.ts`

**改写后**:
```typescript
async execute(params: MemoryWriteParams): Promise<string> {
  const result = await AgentOS.Memory.write({
    namespace: 'fin-agent',
    content: params.content,
    category: params.category,
    importance: params.importance || 0.5,
    tags: params.tags || [],
    metadata: params.metadata || {}
  });
  
  return `Memory written with ID: ${result}`;
}
```

#### 2.2 memory_search 工具

**当前**: 直接读取本地文件  
**改为**: 调用 `agent-os memory search`

**代码位置**: `agent-ts/src/infrastructure/tools/memory/memory_search.ts`

**改写后**:
```typescript
async execute(params: MemorySearchParams): Promise<Memory[]> {
  return await AgentOS.Memory.search({
    namespace: 'fin-agent',
    query: params.query,
    categories: params.categories,
    tags: params.tags,
    minImportance: params.minImportance,
    limit: params.limit || 10,
    hybrid: true  // 使用混合搜索
  });
}
```

#### 2.3 新增工具: scheduler_register

**目的**: Agent 启动时注册任务到 OS

**代码位置**: `agent-ts/src/infrastructure/tools/scheduler/scheduler_register.ts`

**功能**:
```typescript
async execute(params: {
  name: string;
  schedule: string;  // Cron 表达式
  description: string;
  webhookUrl: string;  // Agent 的 webhook 地址
}): Promise<string> {
  const taskId = await AgentOS.Scheduler.register({
    name: params.name,
    description: params.description,
    schedule: params.schedule,
    command: `curl -X POST ${params.webhookUrl}`,
    enabled: true,
    owner: 'fin-agent'
  });
  
  return `Task registered with ID: ${taskId}`;
}
```

---

### 3. 任务注册逻辑

**位置**: `agent-ts/src/core/bootstrap/task-registration.ts`

**功能**: Agent 启动时自动注册所有定时任务到 OS

**实现**:
```typescript
export async function registerTasksToOS() {
  const tasks = [
    {
      name: 'daily_recall_audit',
      schedule: '0 2 * * *',  // 每天 02:00
      description: 'Daily memory recall and audit',
      prompt: 'Review and audit memory system'
    },
    {
      name: 'market_open_scan',
      schedule: '0 9 * * 1-5',  // 工作日 09:00
      description: 'Scan for buy signals before market opens',
      prompt: 'Scan buy signals for all pools'
    },
    {
      name: 'market_close_review',
      schedule: '30 15 * * 1-5',  // 工作日 15:30
      description: 'Analyze performance after market closes',
      prompt: 'Review today\'s performance and adjust positions'
    }
  ];
  
  for (const task of tasks) {
    await AgentOS.Scheduler.register({
      name: task.name,
      description: task.description,
      schedule: task.schedule,
      command: `curl -X POST http://localhost:3000/api/agent/trigger -H "Content-Type: application/json" -d '{"task":"${task.name}","prompt":"${task.prompt}"}'`,
      enabled: true,
      owner: 'fin-agent'
    });
    
    console.log(`✓ Registered task: ${task.name}`);
  }
}
```

**调用位置**: `agent-ts/src/index.ts` 启动逻辑

---

### 4. Webhook 接口

**位置**: `agent-ts/src/infrastructure/gateway/webhook-server.ts`

**功能**: 接收 OS 触发的任务请求

**实现**:
```typescript
import express from 'express';
import { AgentService } from '../../core/services/agent-service';

export function createWebhookServer(agentService: AgentService) {
  const app = express();
  app.use(express.json());
  
  // OS 触发任务的接口
  app.post('/api/agent/trigger', async (req, res) => {
    const { task, prompt, execution_id } = req.body;
    
    console.log(`[Webhook] Received task trigger: ${task}`);
    
    try {
      // 创建新的 agent session 执行任务
      const result = await agentService.executeTask({
        taskName: task,
        prompt: prompt,
        executionId: execution_id
      });
      
      res.json({
        success: true,
        result: result
      });
    } catch (error) {
      console.error(`[Webhook] Task execution failed:`, error);
      res.status(500).json({
        success: false,
        error: error.message
      });
    }
  });
  
  // 健康检查
  app.get('/health', (req, res) => {
    res.json({ status: 'ok' });
  });
  
  return app;
}
```

**启动**:
```typescript
// 在 agent-ts/src/index.ts 中
const webhookServer = createWebhookServer(agentService);
webhookServer.listen(3000, () => {
  console.log('✓ Webhook server listening on http://localhost:3000');
});
```

---

### 5. 删除本地 Cron

**要删除的文件**:
- `agent-ts/src/infrastructure/scheduler/` (整个目录)
- `agent-ts/src/core/services/cron-service.ts`
- 所有对本地 cron 的引用

**修改的文件**:
- `agent-ts/src/index.ts`: 删除 cron 初始化逻辑
- 相关的配置文件

---

## 🧪 验收标准

### 端到端测试流程

1. **启动 OS daemon** (暂时跳过，因为还没实现)
   ```bash
   # 未来会有: agent-os daemon start
   ```

2. **启动 agent-ts**:
   ```bash
   cd agent-ts
   npm run dev
   ```
   
   **预期输出**:
   ```
   ✓ Registered task: daily_recall_audit
   ✓ Registered task: market_open_scan
   ✓ Registered task: market_close_review
   ✓ Webhook server listening on http://localhost:3000
   ✓ Agent started successfully
   ```

3. **验证任务注册**:
   ```bash
   cd ../agent-os
   ./agent-os scheduler list
   ```
   
   **预期输出**: 显示 3 个注册的任务

4. **手动触发任务**:
   ```bash
   ./agent-os scheduler trigger --name daily_recall_audit
   ```
   
   **预期**: agent-ts 收到 webhook 请求并执行

5. **验证 agent 调用工具**:
   - agent 执行任务时调用 `memory_write`
   - 应该调用 `agent-os memory write`
   - 通过 `agent-os memory list` 验证记忆已保存

---

## 📦 交付物

1. ✅ `agent-os-cli.ts` - CLI 执行器
2. ✅ 改写后的 `memory_write.ts` 和 `memory_search.ts`
3. ✅ `task-registration.ts` - 任务注册逻辑
4. ✅ `webhook-server.ts` - Webhook 接口
5. ✅ 删除本地 Cron 相关代码
6. ✅ 更新 `agent-ts/CLAUDE.md` 文档
7. ✅ 集成测试脚本 `test-wp4.sh`
8. ✅ WP-4 验收报告

---

## 🚀 实施步骤

### Day 1 (2026-08-14)
- [ ] 创建 worktree `feat/wp-4-agent-integration`
- [ ] 实现 `agent-os-cli.ts`
- [ ] 改写 `memory_write` 和 `memory_search` 工具
- [ ] 测试工具调用

### Day 2 (2026-08-15)
- [ ] 实现任务注册逻辑
- [ ] 实现 Webhook 接口
- [ ] 删除本地 Cron
- [ ] 端到端测试
- [ ] 编写验收报告

---

## 🔗 依赖项

- ✅ WP-1: Scheduler Core (已完成)
- ✅ WP-2: Resource Manager (已完成)
- ✅ WP-3: Memory System (已完成)
- ⏸️ OS Daemon (未实现，暂时手动测试)

---

**准备开始实施！**
