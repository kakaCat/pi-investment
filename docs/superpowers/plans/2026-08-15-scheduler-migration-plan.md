# Scheduler 迁移完整方案

> **创建时间**: 2026-08-15  
> **目标**: 将 agent-ts 的本地调度器完全迁移到 Agent OS

---

## 📊 迁移范围

### 当前状态

**agent-ts 本地调度器**：
```
agent-ts/src/services/scheduler/
├── scheduler-service.ts        // 核心调度逻辑
├── scheduler-runtime.ts        // 运行时管理
├── init-agent-tasks.ts         // 任务初始化
├── persistent-store.ts         // 持久化存储
└── tasks/
    └── agent-decision-tasks.ts // 7个定时任务定义
```

**7个定时任务**：
1. `morning_ai_analysis` - 早盘分析（工作日 9:00）
2. `daily_ai_review` - 日终复盘（每天 18:00）
3. `weekly_evolution` - 周进化（周日 20:00）
4. `monthly_strategy_review` - 月度策略审查（每月1日 20:00）
5. `tool_roi_review` - 工具ROI审查（每周六 20:00）
6. `weekly_memory_distill` - 周记忆蒸馏（周日 21:00）
7. `daily_recall_audit` - 每日召回审计（每天 19:00）

---

## 🎯 迁移目标

### 迁移后的架构

```
Agent OS Scheduler
    ↓ 定时触发
    ↓ HTTP POST /webhook/agent-os/trigger
agent-ts Webhook Handler
    ↓ 解析 task payload
    ↓ 创建 agent session
    ↓ 执行任务
    ↓ 返回结果
Agent OS
    ↓ 更新 execution 状态
```

**好处**：
1. ✅ 统一调度管理（所有任务在 Agent OS 可视化）
2. ✅ 跨进程任务调度（未来可以触发其他 agent）
3. ✅ 任务执行审计（Agent OS 记录所有执行历史）
4. ✅ 分布式就绪（Agent OS 可以分配任务给多个 agent）

---

## 📋 迁移步骤

### Phase 1: Agent OS HTTP API 补全（8小时）

这部分在 Task 1 中已规划，补充 Scheduler 特定需求：

#### 需要的 API 端点

```go
// Tasks 管理
POST   /api/v1/scheduler/tasks          // 注册任务
GET    /api/v1/scheduler/tasks          // 列出所有任务
GET    /api/v1/scheduler/tasks/:id      // 获取任务详情
PUT    /api/v1/scheduler/tasks/:id      // 更新任务
DELETE /api/v1/scheduler/tasks/:id      // 删除任务
POST   /api/v1/scheduler/tasks/:id/pause   // 暂停任务
POST   /api/v1/scheduler/tasks/:id/resume  // 恢复任务

// Executions 管理
GET    /api/v1/scheduler/executions     // 列出执行记录
GET    /api/v1/scheduler/executions/:id // 获取执行详情
PUT    /api/v1/scheduler/executions/:id // 更新执行状态
POST   /api/v1/scheduler/executions/:id/cancel  // 取消执行

// Trigger 触发
POST   /api/v1/scheduler/tasks/:id/trigger  // 手动触发任务
```

---

### Phase 2: agent-ts Webhook Endpoint（4小时）

#### Step 1: 创建 Webhook 路由（1小时）

**文件**: `agent-ts/src/api/webhook/agent-os-trigger.ts`

```typescript
/**
 * Agent OS Webhook Handler
 * 接收 Agent OS 的任务触发请求
 */
import { Router } from 'express';
import { createSchedulerSession } from '../../services/scheduler/scheduler-session.js';
import { getAgentOSClient } from '../../infrastructure/agent-os/client.js';
import { logger } from '../../infrastructure/logging/index.js';
import type { AgentKind } from '../../domain/agent-roles/types.js';

export const agentOSWebhookRouter = Router();

interface AgentOSWebhookPayload {
  task_id: string;
  task_name: string;
  execution_id: string;
  payload: {
    kind: 'agent_turn';
    message: string;
    agentKind?: AgentKind;
  };
}

/**
 * Agent OS 任务触发端点
 * POST /api/webhook/agent-os/trigger
 */
agentOSWebhookRouter.post('/agent-os/trigger', async (req, res) => {
  const payload: AgentOSWebhookPayload = req.body;
  
  logger.info('[AgentOS Webhook] Task triggered', {
    task_id: payload.task_id,
    task_name: payload.task_name,
    execution_id: payload.execution_id,
  });

  try {
    // 1. 创建 agent session
    const agentKind = payload.payload.agentKind || 'fin';
    const { session } = await createSchedulerSession(agentKind);

    // 2. 执行任务
    logger.info('[AgentOS Webhook] Executing task', {
      task_name: payload.task_name,
      agentKind,
    });

    await session.prompt(payload.payload.message, {
      source: 'agent-os-trigger',
      metadata: {
        task_id: payload.task_id,
        execution_id: payload.execution_id,
      },
    });

    logger.info('[AgentOS Webhook] Task completed', {
      execution_id: payload.execution_id,
    });

    // 3. 更新 Agent OS execution 状态
    const client = getAgentOSClient();
    await client.scheduler.updateExecution(payload.execution_id, {
      status: 'completed',
      result: { success: true },
    });

    // 4. 返回成功响应
    res.json({
      success: true,
      execution_id: payload.execution_id,
    });

  } catch (error) {
    logger.error('[AgentOS Webhook] Task failed', {
      execution_id: payload.execution_id,
      error: error instanceof Error ? error.message : String(error),
    });

    // 更新失败状态
    try {
      const client = getAgentOSClient();
      await client.scheduler.updateExecution(payload.execution_id, {
        status: 'failed',
        error: error instanceof Error ? error.message : String(error),
      });
    } catch (updateError) {
      logger.error('[AgentOS Webhook] Failed to update execution status', {
        error: updateError,
      });
    }

    // 返回错误响应
    res.status(500).json({
      success: false,
      error: error instanceof Error ? error.message : 'Unknown error',
    });
  }
});
```

#### Step 2: 注册 Webhook 路由（30分钟）

**修改**: `agent-ts/src/api/index.ts`

```typescript
import { agentOSWebhookRouter } from './webhook/agent-os-trigger.js';

// ... 现有代码

// 注册 Agent OS webhook 路由
app.use('/api/webhook', agentOSWebhookRouter);
```

#### Step 3: 配置 Webhook URL（30分钟）

**环境变量**: `agent-ts/.env`

```bash
# Agent Gateway
AGENT_WEBHOOK_BASE_URL=http://localhost:3002

# Agent OS 会调用：
# POST http://localhost:3002/api/webhook/agent-os/trigger
```

---

### Phase 3: Task Registration（4小时）

#### Step 1: 创建任务注册逻辑（2小时）

**文件**: `agent-ts/src/core/bootstrap/agent-os-task-registration.ts`

```typescript
/**
 * Agent OS Task Registration
 * 启动时将所有定时任务注册到 Agent OS
 */
import { getAgentOSClient } from '../../infrastructure/agent-os/client.js';
import { createAgentDecisionTasks } from '../../services/scheduler/tasks/agent-decision-tasks.js';
import { logger } from '../../infrastructure/logging/index.js';

interface TaskRegistrationOptions {
  webhookBaseUrl: string;  // agent-ts webhook URL
  force?: boolean;         // 是否强制重新注册
}

/**
 * 注册所有任务到 Agent OS
 */
export async function registerTasksToAgentOS(options: TaskRegistrationOptions) {
  logger.info('[TaskRegistration] Starting task registration to Agent OS', {
    webhookBaseUrl: options.webhookBaseUrl,
  });

  const client = getAgentOSClient();
  
  // 1. 获取任务模板
  const taskTemplates = createAgentDecisionTasks();
  
  // 2. 检查已存在的任务
  const existingTasks = await client.scheduler.listTasks();
  const existingTaskMap = new Map(
    existingTasks.map(t => [t.name, t])
  );

  logger.info('[TaskRegistration] Found existing tasks', {
    count: existingTasks.length,
    tasks: existingTasks.map(t => t.name),
  });

  // 3. 注册或更新任务
  const results = [];
  
  for (const template of taskTemplates) {
    try {
      const existingTask = existingTaskMap.get(template.name);
      
      if (existingTask && !options.force) {
        // 任务已存在，跳过
        logger.info('[TaskRegistration] Task already exists, skipping', {
          task_name: template.name,
        });
        results.push({ task: template.name, status: 'skipped', id: existingTask.id });
        continue;
      }

      // 构建任务请求
      const taskRequest = {
        name: template.name,
        owner: 'fin-agent',
        enabled: template.enabled,
        cron: template.scheduleKind === 'cron' ? template.scheduleExpr : undefined,
        webhook_url: `${options.webhookBaseUrl}/api/webhook/agent-os/trigger`,
        payload: template.payload,
        timeout: 3600,  // 1小时超时
        retry_count: template.compensationEnabled ? template.compensationMaxAttempts : 0,
      };

      if (existingTask && options.force) {
        // 更新已存在的任务
        logger.info('[TaskRegistration] Updating existing task', {
          task_name: template.name,
          task_id: existingTask.id,
        });
        
        await client.scheduler.updateTask(existingTask.id, taskRequest);
        results.push({ task: template.name, status: 'updated', id: existingTask.id });
      } else {
        // 注册新任务
        logger.info('[TaskRegistration] Registering new task', {
          task_name: template.name,
          cron: taskRequest.cron,
        });
        
        const newTask = await client.scheduler.registerTask(taskRequest);
        results.push({ task: template.name, status: 'created', id: newTask.id });
      }

      logger.info('[TaskRegistration] Task registered successfully', {
        task_name: template.name,
        status: results[results.length - 1].status,
      });

    } catch (error) {
      logger.error('[TaskRegistration] Failed to register task', {
        task_name: template.name,
        error: error instanceof Error ? error.message : String(error),
      });
      
      results.push({
        task: template.name,
        status: 'failed',
        error: error instanceof Error ? error.message : String(error),
      });
    }
  }

  // 4. 汇总结果
  const summary = {
    total: taskTemplates.length,
    created: results.filter(r => r.status === 'created').length,
    updated: results.filter(r => r.status === 'updated').length,
    skipped: results.filter(r => r.status === 'skipped').length,
    failed: results.filter(r => r.status === 'failed').length,
  };

  logger.info('[TaskRegistration] Task registration completed', summary);

  return {
    summary,
    results,
  };
}
```

#### Step 2: 集成到启动流程（1小时）

**修改**: `agent-ts/src/index.ts`

```typescript
import { registerTasksToAgentOS } from './core/bootstrap/agent-os-task-registration.js';

async function main() {
  try {
    // ... 现有代码（Agent OS client 初始化）

    // 注册任务到 Agent OS
    if (process.env.AGENT_OS_SCHEDULER_ENABLED === 'true') {
      console.log('📋 正在注册任务到 Agent OS Scheduler...');
      
      const webhookBaseUrl = process.env.AGENT_WEBHOOK_BASE_URL || 'http://localhost:3002';
      const result = await registerTasksToAgentOS({ webhookBaseUrl });
      
      console.log('✅ 任务注册完成:', result.summary);
      
      // 不再启动本地调度器
      console.log('ℹ️ 使用 Agent OS Scheduler，跳过本地调度器');
    } else {
      // 使用本地调度器（向后兼容）
      console.log('ℹ️ 使用本地调度器');
      await initAgentDecisionTasks();
      await startSchedulerRuntime({...});
    }

    // ... 剩余代码
  } catch (error) {
    console.error('❌ 启动失败:', error);
    process.exit(1);
  }
}
```

#### Step 3: 环境变量配置（30分钟）

**修改**: `agent-ts/.env.example`

```bash
# Agent OS Scheduler 配置
AGENT_OS_SCHEDULER_ENABLED=false  # 设为 true 启用 Agent OS 调度器
AGENT_WEBHOOK_BASE_URL=http://localhost:3002  # agent-ts webhook 地址
```

---

### Phase 4: Agent OS Webhook 配置（2小时）

#### Step 1: Agent OS 添加 Webhook 触发逻辑

**修改**: `agent-os/internal/kernel/scheduler/executor.go`

```go
// ExecuteTask 执行任务
func (e *Executor) ExecuteTask(ctx context.Context, task *types.Task, execution *types.TaskRun) error {
    logger.Info("Executing task",
        "task_id", task.ID,
        "task_name", task.Name,
        "execution_id", execution.ID)

    // 如果任务配置了 webhook，通过 HTTP 触发
    if task.WebhookURL != "" {
        return e.triggerWebhook(ctx, task, execution)
    }

    // 否则使用本地执行逻辑
    return e.executeLocal(ctx, task, execution)
}

// triggerWebhook 通过 HTTP Webhook 触发任务
func (e *Executor) triggerWebhook(ctx context.Context, task *types.Task, execution *types.TaskRun) error {
    // 构建 webhook payload
    payload := map[string]interface{}{
        "task_id":      task.ID.String(),
        "task_name":    task.Name,
        "execution_id": execution.ID.String(),
        "payload":      task.Payload,
    }

    // 发送 HTTP POST 请求
    body, _ := json.Marshal(payload)
    req, err := http.NewRequestWithContext(ctx, "POST", task.WebhookURL, bytes.NewReader(body))
    if err != nil {
        return fmt.Errorf("failed to create webhook request: %w", err)
    }

    req.Header.Set("Content-Type", "application/json")
    req.Header.Set("X-Agent-OS-Task-ID", task.ID.String())
    req.Header.Set("X-Agent-OS-Execution-ID", execution.ID.String())

    client := &http.Client{Timeout: time.Duration(task.Timeout) * time.Second}
    resp, err := client.Do(req)
    if err != nil {
        return fmt.Errorf("webhook request failed: %w", err)
    }
    defer resp.Body.Close()

    if resp.StatusCode >= 400 {
        return fmt.Errorf("webhook returned error: %d", resp.StatusCode)
    }

    logger.Info("Webhook triggered successfully",
        "task_id", task.ID,
        "execution_id", execution.ID,
        "status_code", resp.StatusCode)

    return nil
}
```

#### Step 2: 添加 webhook_url 字段到 Task 类型

**修改**: `agent-os/pkg/types/scheduler.go`

```go
type Task struct {
    ID          uuid.UUID              `json:"id"`
    Name        string                 `json:"name"`
    Owner       string                 `json:"owner"`
    Cron        string                 `json:"cron,omitempty"`
    WebhookURL  string                 `json:"webhook_url,omitempty"`  // 新增
    Payload     map[string]interface{} `json:"payload"`
    Timeout     int                    `json:"timeout"`
    RetryCount  int                    `json:"retry_count"`
    Enabled     bool                   `json:"enabled"`
    CreatedAt   time.Time              `json:"created_at"`
    UpdatedAt   time.Time              `json:"updated_at"`
}
```

---

### Phase 5: 测试和验证（4小时）

#### Test 1: 端到端测试（2小时）

```bash
# 1. 启动 Agent OS
cd /Users/yunpeng/pi-investment/agent-os
./agent-os serve --port 8080

# 2. 启动 agent-ts（启用 Agent OS Scheduler）
cd /Users/yunpeng/pi-investment/agent-ts
export AGENT_OS_SCHEDULER_ENABLED=true
export AGENT_WEBHOOK_BASE_URL=http://localhost:3002
npm run dev

# 3. 验证任务注册
curl http://localhost:8080/api/v1/scheduler/tasks
# 应该看到 7 个任务

# 4. 手动触发测试
curl -X POST http://localhost:8080/api/v1/scheduler/tasks/<task-id>/trigger

# 5. 检查 agent-ts 日志
# 应该看到：
# [AgentOS Webhook] Task triggered
# [AgentOS Webhook] Executing task
# [AgentOS Webhook] Task completed

# 6. 检查 execution 状态
curl http://localhost:8080/api/v1/scheduler/executions
# 应该看到执行记录，status = 'completed'
```

#### Test 2: 定时触发测试（2小时）

```bash
# 注册一个测试任务（1分钟后触发）
curl -X POST http://localhost:8080/api/v1/scheduler/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test_cron_trigger",
    "owner": "fin-agent",
    "cron": "'$(date -u -d '+1 minute' +'%M %H * * *')'",
    "webhook_url": "http://localhost:3002/api/webhook/agent-os/trigger",
    "payload": {
      "kind": "agent_turn",
      "message": "这是一个测试任务"
    },
    "timeout": 60,
    "retry_count": 0,
    "enabled": true
  }'

# 等待 1 分钟，检查日志
tail -f /path/to/agent-ts.log

# 应该看到任务自动触发
```

---

### Phase 6: 清理本地调度器（2小时）

#### 仅在测试通过后执行

**保留的文件**（Agent OS 可能需要）：
- `scheduler-service.ts` - 数据结构定义
- `persistent-store.ts` - 持久化逻辑（Agent OS 可能需要）
- `agent-decision-tasks.ts` - 任务定义（给 Agent OS 注册用）

**删除的文件**：
- `scheduler-runtime.ts` - 本地 cron 运行时
- `cron-hardening.test.ts` - 本地 cron 测试

**修改的文件**：
- `init-agent-tasks.ts` - 改为调用 `registerTasksToAgentOS`

---

## 🗓️ 执行时间表

### 推荐顺序

```
Day 1 (今天):
  [8小时] Phase 1: Agent OS HTTP API 补全
           (与 Task 1 合并执行)

Day 2:
  [4小时] Phase 2: agent-ts Webhook Endpoint
  [4小时] Phase 3: Task Registration

Day 3:
  [2小时] Phase 4: Agent OS Webhook 配置
  [4小时] Phase 5: 测试和验证
  [2小时] Phase 6: 清理本地调度器

总计: 3 天
```

---

## ⚠️ 风险和注意事项

### 1. 向后兼容

**保留本地调度器作为 fallback**：

```typescript
// 通过环境变量控制
if (process.env.AGENT_OS_SCHEDULER_ENABLED === 'true') {
  // 使用 Agent OS Scheduler
  await registerTasksToAgentOS({...});
} else {
  // 使用本地调度器（默认）
  await initAgentDecisionTasks();
  await startSchedulerRuntime({...});
}
```

### 2. 任务执行超时

Agent OS 的任务超时设置要足够长（建议 3600 秒 = 1 小时）。

### 3. Webhook 网络问题

- agent-ts 必须能被 Agent OS 访问
- 生产环境可能需要配置内网 DNS
- 考虑添加 webhook 鉴权（Bearer token）

### 4. 任务重复执行

- Agent OS 和本地调度器不能同时运行
- 启动时检查环境变量，二选一

---

## ✅ 验收标准

迁移完成的标准：

1. ✅ Agent OS HTTP API 完整实现（Scheduler 路由）
2. ✅ agent-ts Webhook Endpoint 工作正常
3. ✅ 7个任务成功注册到 Agent OS
4. ✅ 手动触发测试通过
5. ✅ 定时触发测试通过（至少运行1个完整周期）
6. ✅ 任务执行状态正确更新
7. ✅ 错误处理正常（任务失败时 execution 状态正确）
8. ✅ 向后兼容（可以通过环境变量切回本地调度器）

---

## 📊 迁移前后对比

### 迁移前

```
agent-ts 本地调度器
  ├─ 7个任务定义
  ├─ node-cron 执行
  ├─ 持久化到本地文件
  └─ 日志在 agent-ts 进程

优点: 简单，独立
缺点: 分散管理，无法跨进程调度
```

### 迁移后

```
Agent OS Scheduler
  ├─ 统一任务管理
  ├─ Cron 调度引擎
  ├─ PostgreSQL 持久化
  └─ HTTP Webhook 触发
      ↓
  agent-ts Webhook Handler
      ├─ 接收触发
      ├─ 执行 agent session
      └─ 返回状态

优点: 统一管理，可扩展，可视化
缺点: 增加网络依赖
```

---

## 🎯 最终状态

完成后，系统架构：

```
┌─────────────────────────────────────┐
│  Agent OS :8080                     │
│  ├─ Scheduler 调度器                │
│  │   ├─ 7个定时任务                 │
│  │   ├─ Cron 引擎                   │
│  │   └─ Execution 记录              │
│  ├─ Memory 记忆服务                 │
│  ├─ Decision 决策服务               │
│  └─ Notification 通知服务           │
└────────────┬────────────────────────┘
             ↓ Webhook HTTP POST
┌─────────────────────────────────────┐
│  agent-ts :3002                     │
│  ├─ /api/webhook/agent-os/trigger   │
│  │   ↓ 接收任务触发                 │
│  ├─ createSchedulerSession()        │
│  │   ↓ 创建 agent 会话              │
│  └─ session.prompt(message)         │
│      ↓ 执行任务                      │
└─────────────────────────────────────┘
```

所有调度逻辑在 Agent OS，agent-ts 只负责执行。

---

**准备好开始了吗？**

我建议先执行 **Phase 1（Agent OS HTTP API 补全）**，这是所有后续工作的基础。

你希望我：
1. 立即开始 Phase 1？
2. 还是先重启服务（Task 0）？
3. 还是有其他问题？
