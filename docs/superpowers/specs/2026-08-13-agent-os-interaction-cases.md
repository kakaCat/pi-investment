# Agent OS 系统交互图与协作案例

> **创建时间**: 2026-08-13  
> **目标**: 用图和案例说清楚 OS、Agent、Web 三者的关系

---

## 1. 系统交互全景图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Human User（人类用户）                       │
│                                                                       │
│  浏览器访问 → http://localhost:3001                                  │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ HTTP Requests
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    web-frontend (Vue3 前端)                          │
│                         Port: 3001                                   │
│                                                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ 页面组成                                                       │  │
│  │  - 持仓监控页（实时持仓、收益曲线）                           │  │
│  │  - 记忆管理页（搜索记忆、查看召回审计）                       │  │
│  │  - 任务管理页（查看所有任务、手动触发、执行历史）【新增】    │  │
│  │  - 进化排行榜（查看进化建议、执行进度）                       │  │
│  │  - Agent 监控页（Token 消耗、配额使用、健康状态）【新增】    │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  前端调用 API：                                                      │
│    - GET /api/registry/capabilities  → 查询服务健康状态             │
│    - GET /api/scheduler/tasks        → 获取任务列表                 │
│    - POST /api/scheduler/tasks/{id}/trigger → 手动触发任务          │
│    - GET /api/resource/quota?agent=fin → 查询 fin-agent 配额使用    │
│    - GET /api/memory/search          → 搜索记忆                     │
│    - GET /api/portfolio/positions    → 查询持仓                     │
└────────────────────────────┬────────────────────────────────────────┘
                             │
                             │ HTTP Calls
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Agent OS (Go 内核)                              │
│                         Port: 8080                                   │
│                                                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Syscall API Layer (HTTP/gRPC)                                 │  │
│  │  - /api/registry/*      → 服务注册表（健康检查、能力查询）    │  │
│  │  - /api/scheduler/*     → 调度器 API                          │  │
│  │  - /api/resource/*      → 资源管理 API                        │  │
│  │  - /api/memory/*        → Memory 子系统                       │  │
│  │  - /api/decision/*      → Decision 子系统                     │  │
│  │  - /api/evolution/*     → Evolution 子系统                    │  │
│  │  - /api/data/*          → 数据服务代理（调用 Driver）         │  │
│  │  - /api/trading/*       → 交易服务代理（调用 Trading Service）│  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Core Services (Go Modules)                                    │  │
│  │                                                                │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │  │
│  │  │  Scheduler  │  │  Resource   │  │  Memory     │          │  │
│  │  │             │  │  Manager    │  │  System     │          │  │
│  │  │  - DAG 解析 │  │  - Token 配额│  │  - BM25     │          │  │
│  │  │  - 优先级队列│  │  - 优先级   │  │  - Vector   │          │  │
│  │  │  - 并发控制 │  │  - 命名空间 │  │  - 命名空间 │          │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘          │  │
│  │                                                                │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐          │  │
│  │  │  Decision   │  │  Evolution  │  │  Event Bus  │          │  │
│  │  │  System     │  │  System     │  │  (PG NOTIFY)│          │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘          │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │ Storage Layer                                                  │  │
│  │  PostgreSQL: scheduler_tasks, agent_memory, agent_decisions   │  │
│  │  Redis: Event Bus, Cache                                      │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────┬──────────────────────┬──────────────────────┬─────────────┘
          │                      │                      │
          │ gRPC                 │ HTTP                 │ Event Publish/Subscribe
          ▼                      ▼                      ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐
│ Market Driver    │  │ Trading Service  │  │    agent-ts (Node.js)    │
│ (Python)         │  │ (Python/v2)      │  │       Port: 3000         │
│ Port: 50051      │  │ Port: 5002       │  │                          │
│                  │  │                  │  │  ┌────────────────────┐  │
│ gRPC Server:     │  │ HTTP Server:     │  │  │ 三个 Agent 实例   │  │
│  - GetQuote()    │  │  - POST /order   │  │  │                    │  │
│  - GetKline()    │  │  - GET /positions│  │  │  ┌──────────────┐ │  │
│  - GetFinancials│  │  - GET /pool     │  │  │  │  fin-agent   │ │  │
│                  │  │                  │  │  │  │  (80 tools)  │ │  │
│ Adapters:        │  │ Features:        │  │  │  └──────────────┘ │  │
│  - AKShare       │  │  - 订单管理      │  │  │                    │  │
│  - Tushare       │  │  - 持仓管理      │  │  │  ┌──────────────┐ │  │
│  - yfinance      │  │  - 风控          │  │  │  │memory-agent  │ │  │
└──────────────────┘  │  - 虚拟盘        │  │  │  │  (11 tools)  │ │  │
                      └──────────────────┘  │  │  └──────────────┘ │  │
                                            │  │                    │  │
                                            │  │  ┌──────────────┐ │  │
                                            │  │  │evolution-agt │ │  │
                                            │  │  │  (15 tools)  │ │  │
                                            │  │  └──────────────┘ │  │
                                            │  └────────────────────┘  │
                                            │                          │
                                            │  启动时行为：             │
                                            │  1. 向 OS 注册 3 个任务  │
                                            │  2. 订阅 Event Bus       │
                                            │  3. 提供 Webhook 接口   │
                                            │     /api/agent/trigger  │
                                            └──────────────────────────┘
```

---

## 2. 数据流向图（简化版）

```
┌─────────┐                    ┌─────────┐                    ┌─────────┐
│  Human  │ ──── 浏览器 ────▶  │   Web   │ ──── HTTP API ──▶  │   OS    │
│  User   │                    │Frontend │                    │ Kernel  │
└─────────┘                    └─────────┘                    └────┬────┘
                                    ▲                               │
                                    │                               │
                                    │      ┌────────────────────────┤
                                    │      │                        │
                                    │      ▼                        ▼
                                    │  ┌─────────┐            ┌─────────┐
                                    │  │ Agent   │            │ Driver  │
                                    │  │  (ts)   │            │(Python) │
                                    │  └─────────┘            └─────────┘
                                    │      ▲                        ▲
                                    │      │                        │
                                    └──────┴────────────────────────┘
                                       OS 推送事件、调度通知
```

---

## 3. 角色职责表

| 组件 | 端口 | 核心职责 | 不负责 |
|---|---|---|---|
| **web-frontend** | 3001 | 可视化观测、用户交互 | 不存储数据、不做业务逻辑 |
| **Agent OS** | 8080 | 资源管理、任务调度、持久化、权限管控 | 不做 LLM 推理、不做策略决策 |
| **agent-ts** | 3000 | Agent 推理、工具执行、Prompt 工程 | 不管调度、不管资源配额 |
| **Market Driver** | 50051 | 金融数据获取（gRPC） | 不做数据分析 |
| **Trading Service** | 5002 | 订单执行、持仓管理、风控 | 不做策略决策 |

---

## 4. 案例 1：用户手动触发「每日复盘」任务

### 场景描述
用户在晚上 8 点通过 web 前端点击"立即执行每日复盘"按钮

### 完整流程

```
┌─────────────────────────────────────────────────────────────────────┐
│ Step 1: 用户操作                                                     │
└─────────────────────────────────────────────────────────────────────┘

人类用户在浏览器：
  1. 打开 http://localhost:3001/tasks（任务管理页）
  2. 看到任务列表：
     - daily_recall_audit (memory-agent)  [上次执行: 19:00, 成功]
     - morning_analysis (fin-agent)       [上次执行: 08:30, 成功]
     - weekly_evolution (evolution-agent) [上次执行: 周日 20:00, 成功]
  3. 点击 daily_recall_audit 旁边的「立即执行」按钮

┌─────────────────────────────────────────────────────────────────────┐
│ Step 2: Web Frontend → Agent OS                                     │
└─────────────────────────────────────────────────────────────────────┘

// web-frontend/src/api/scheduler.ts
async function triggerTask(taskId: number) {
  const resp = await fetch('http://localhost:8080/api/scheduler/tasks/${taskId}/trigger', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-User': 'human@web'  // 标记是人类触发
    },
    body: JSON.stringify({
      trigger_type: 'manual',
      triggered_by: 'user@web'
    })
  });
  
  if (!resp.ok) {
    throw new Error('触发任务失败');
  }
  
  return await resp.json();  // { "execution_id": 123, "status": "scheduled" }
}

┌─────────────────────────────────────────────────────────────────────┐
│ Step 3: Agent OS Scheduler 处理                                     │
└─────────────────────────────────────────────────────────────────────┘

// Agent OS (Go)
func (h *SchedulerHandler) TriggerTask(c *gin.Context) {
    taskID := c.Param("id")
    
    // 1. 权限检查（Web 可以触发任何任务吗？）
    if !h.authManager.CanTrigger(c.GetHeader("X-User"), taskID) {
        c.JSON(403, gin.H{"error": "permission denied"})
        return
    }
    
    // 2. 检查资源配额
    task := h.scheduler.GetTask(taskID)
    if !h.resourceMgr.CheckQuota(task.Owner) {  // task.Owner = "memory-agent"
        c.JSON(429, gin.H{"error": "quota exceeded", "agent": task.Owner})
        return
    }
    
    // 3. 检查依赖（daily_recall_audit 无依赖）
    if !h.scheduler.CheckDependencies(taskID) {
        c.JSON(412, gin.H{"error": "dependencies not met"})
        return
    }
    
    // 4. 调度任务
    execID, err := h.scheduler.TriggerTask(ctx, taskID, TriggerTypeManual, "user@web")
    if err != nil {
        c.JSON(500, gin.H{"error": err.Error()})
        return
    }
    
    c.JSON(200, gin.H{"execution_id": execID, "status": "scheduled"})
}

┌─────────────────────────────────────────────────────────────────────┐
│ Step 4: Agent OS → agent-ts                                         │
└─────────────────────────────────────────────────────────────────────┘

// Agent OS 调度器异步执行
func (e *Executor) executeAgentTask(execCtx *ExecutionContext, task *TaskDefinition) error {
    // 调用 agent-ts 的 Webhook
    webhookURL := "http://localhost:3000/api/agent/trigger"
    payload := map[string]interface{}{
        "execution_id": execCtx.ExecutionID,
        "agent_kind":   task.AgentKind,  // "memory"
        "prompt":       task.AgentPrompt, // "执行每日召回审计..."
    }
    
    resp, err := httpClient.Post(webhookURL, "application/json", marshalJSON(payload))
    if err != nil {
        return errors.Wrap(err, "failed to call agent webhook")
    }
    
    // Agent 异步执行，OS 周期性查询状态
    for {
        select {
        case <-time.After(30 * time.Second):
            status := e.checkAgentStatus(execCtx.ExecutionID)
            if status.Completed {
                execCtx.ConsumeToken(status.TokenConsumed)  // 记录 token 消耗
                return nil
            }
        case <-execCtx.Context().Done():
            return errors.New("task timeout")
        }
    }
}

┌─────────────────────────────────────────────────────────────────────┐
│ Step 5: agent-ts 执行                                                │
└─────────────────────────────────────────────────────────────────────┘

// agent-ts/src/api/agent-trigger.ts
app.post('/api/agent/trigger', async (req, res) => {
  const { execution_id, agent_kind, prompt } = req.body;
  
  // 创建 memory-agent 会话
  const agent = await createAgent({
    kind: 'memory',
    sessionId: `exec-${execution_id}`
  });
  
  // 异步执行（立即返回 202）
  res.status(202).json({ status: 'accepted', execution_id });
  
  // 后台执行
  executeInBackground(async () => {
    try {
      const result = await agent.run(prompt);
      
      // 完成后回调 OS
      await fetch(`http://localhost:8080/api/scheduler/executions/${execution_id}/complete`, {
        method: 'POST',
        body: JSON.stringify({
          status: 'success',
          token_consumed: agent.getTokenCount(),
          output: result
        })
      });
    } catch (err) {
      // 失败回调
      await fetch(`http://localhost:8080/api/scheduler/executions/${execution_id}/complete`, {
        method: 'POST',
        body: JSON.stringify({
          status: 'failed',
          error_message: err.message
        })
      });
    }
  });
});

┌─────────────────────────────────────────────────────────────────────┐
│ Step 6: memory-agent 推理（agent-ts 内部）                          │
└─────────────────────────────────────────────────────────────────────┘

memory-agent 接收到 prompt: "执行每日召回审计..."

推理过程：
  1. 调用工具 recall_audit.list({date_from: '2026-08-12', date_to: '2026-08-13'})
     → 发送 HTTP 请求到 OS: GET /api/memory/recall-audit/list
     
  2. OS 返回 10 条召回记录
  
  3. memory-agent 分析：
     - 哪些召回质量高？
     - 哪些被抑制了（empty-result）？
     - 是否有低分注入问题？
     
  4. 调用工具 recall_audit.feedback({audit_id: 2, memory_id: 9, feedback: 'relevant'})
     → 发送 HTTP 请求到 OS: POST /api/memory/recall-audit/feedback
     
  5. 重复标注 25 条记忆
  
  6. 调用工具 memory_write({content: "每日召回审计报告...", category: "daily-recall-audit"})
     → 发送 HTTP 请求到 OS: POST /api/memory/write
     
  7. 完成，返回总结

Token 消耗：1200 tokens

┌─────────────────────────────────────────────────────────────────────┐
│ Step 7: Agent OS 记录执行结果                                        │
└─────────────────────────────────────────────────────────────────────┘

// agent-ts 回调 OS
POST /api/scheduler/executions/123/complete
Body: {
  "status": "success",
  "token_consumed": 1200,
  "output": "已完成每日召回审计，标注 25 条记忆，发现低分注入问题..."
}

// OS 更新执行记录
UPDATE scheduler_executions SET
  status = 'success',
  ended_at = NOW(),
  duration_sec = 45,
  token_consumed = 1200
WHERE id = 123;

// OS 更新 memory-agent 的配额使用
UPDATE quota_usage SET
  token_used = token_used + 1200
WHERE agent_id = 'memory-agent';

// OS 发布事件（Event Bus）
NOTIFY task_completed, '{"task_id": 1, "execution_id": 123, "status": "success"}';

┌─────────────────────────────────────────────────────────────────────┐
│ Step 8: Web Frontend 实时更新                                        │
└─────────────────────────────────────────────────────────────────────┘

// web-frontend 订阅 WebSocket
const ws = new WebSocket('ws://localhost:8080/api/events/subscribe?channels=task.*');

ws.onmessage = (event) => {
  const { channel, payload } = JSON.parse(event.data);
  
  if (channel === 'task_completed' && payload.execution_id === 123) {
    // 更新 UI：任务状态变为「成功」
    updateTaskStatus(payload.task_id, 'success');
    
    // 显示通知："每日召回审计已完成"
    showNotification('任务完成', '每日召回审计已成功执行');
    
    // 刷新执行历史列表
    fetchExecutionHistory(payload.task_id);
  }
};

用户在浏览器看到：
  - 任务状态从「执行中」变为「成功」（绿色）
  - 执行历史新增一条：
    - 开始时间: 20:00:00
    - 结束时间: 20:00:45
    - 耗时: 45 秒
    - Token 消耗: 1200
    - 状态: 成功
```

### 时序图

```
User    Web     Agent OS    agent-ts    memory-agent    PostgreSQL
 │       │          │           │            │              │
 │  点击  │          │           │            │              │
 │ ────▶ │          │           │            │              │
 │       │ POST /trigger         │            │              │
 │       │ ────────▶│           │            │              │
 │       │          │ 检查配额   │            │              │
 │       │          │ ──────────────────────────────────▶  │
 │       │          │◀──────────────────────────────────   │
 │       │          │ 创建执行记录                         │
 │       │          │ ──────────────────────────────────▶  │
 │       │          │           │            │              │
 │       │          │ POST /agent/trigger    │              │
 │       │          │ ─────────▶│            │              │
 │       │          │           │ 创建 memory-agent         │
 │       │          │           │ ──────────▶│              │
 │       │◀─────────│           │            │              │
 │       │ 202 Accepted         │            │              │
 │◀──────│          │           │            │              │
 │ 显示   │          │           │            │              │
 │「执行中」│         │           │            │              │
 │       │          │           │            │ LLM 推理     │
 │       │          │           │            │ (Anthropic)  │
 │       │          │           │            │              │
 │       │          │           │   调用工具：recall_audit.list │
 │       │          │◀──────────────────────────            │
 │       │          │ GET /memory/recall-audit/list        │
 │       │          │ ──────────────────────────────────▶  │
 │       │          │◀──────────────────────────────────   │
 │       │          │ ─────────────────────────▶│          │
 │       │          │           │            │              │
 │       │          │           │   调用工具：memory_write  │
 │       │          │◀──────────────────────────            │
 │       │          │ POST /memory/write                   │
 │       │          │ ──────────────────────────────────▶  │
 │       │          │◀──────────────────────────────────   │
 │       │          │           │            │              │
 │       │          │           │ 完成，回调 OS              │
 │       │          │◀──────────│            │              │
 │       │          │ POST /executions/123/complete        │
 │       │          │           │            │              │
 │       │          │ 更新执行记录 + 配额                  │
 │       │          │ ──────────────────────────────────▶  │
 │       │          │           │            │              │
 │       │          │ 发布事件：task_completed             │
 │       │          │ ─────────▶│            │              │
 │       │          │           WebSocket Push              │
 │       │◀─────────────────────│            │              │
 │       │ 事件：task_completed  │            │              │
 │◀──────│          │           │            │              │
 │ 刷新UI │          │           │            │              │
 │ 显示   │          │           │            │              │
 │「成功」 │          │           │            │              │
```

---

## 5. 案例 2：自动化定时任务「早盘分析」

### 场景描述
每个交易日早上 8:30，fin-agent 自动执行早盘分析任务

### 完整流程

```
┌─────────────────────────────────────────────────────────────────────┐
│ Step 0: 任务注册（系统启动时，一次性）                              │
└─────────────────────────────────────────────────────────────────────┘

// agent-ts 启动时（start-headless.ts）
async function registerTasks() {
  await fetch('http://localhost:8080/api/scheduler/tasks', {
    method: 'POST',
    body: JSON.stringify({
      name: 'morning_analysis',
      owner: 'fin-agent',
      task_type: 'agent_turn',
      cron: '30 8 * * 1-5',  // 工作日 8:30
      agent_kind: 'fin',
      agent_prompt: '执行早盘分析：扫描股票池，分析市场情绪，生成今日关注列表...',
      timeout_sec: 1800,
      max_retries: 3,
      depends_on: ['market_data_sync']  // 依赖市场数据同步完成
    })
  });
}

┌─────────────────────────────────────────────────────────────────────┐
│ Step 1: Agent OS Scheduler 定时触发（每天 8:30）                    │
└─────────────────────────────────────────────────────────────────────┘

// Agent OS (Go)
// Cron 到达 8:30
func (s *Scheduler) onCronTrigger(task *TaskDefinition) {
    logger.Info("Cron triggered", zap.String("task", task.Name))
    
    // 1. 检查依赖：market_data_sync 是否在 1 小时内成功执行过？
    depTask := s.taskRepo.GetByName("market_data_sync")
    lastExec := s.execRepo.GetLastExecution(depTask.ID)
    
    if lastExec.Status != "success" || time.Since(lastExec.EndedAt) > 1*time.Hour {
        logger.Warn("Dependency not met, skipping task", 
            zap.String("task", task.Name),
            zap.String("dependency", "market_data_sync"))
        return
    }
    
    // 2. 检查配额：fin-agent 今天还有 token 吗？
    if !s.resourceMgr.CheckQuota("fin-agent") {
        logger.Warn("Quota exceeded, skipping task",
            zap.String("agent", "fin-agent"))
        return
    }
    
    // 3. 检查优先级：当前是交易时段，fin-agent 优先级最高（10）
    currentPriority := s.resourceMgr.GetPriority("fin-agent", time.Now())
    logger.Info("Task priority", zap.Int("priority", currentPriority))  // 10
    
    // 4. 触发任务
    s.triggerTask(context.Background(), task.ID, TriggerTypeCron, "system")
}

┌─────────────────────────────────────────────────────────────────────┐
│ Step 2: Agent OS → agent-ts                                         │
└─────────────────────────────────────────────────────────────────────┘

// OS 调用 agent-ts webhook（同案例 1 Step 4）
POST http://localhost:3000/api/agent/trigger
Body: {
  "execution_id": 456,
  "agent_kind": "fin",
  "prompt": "执行早盘分析：扫描股票池，分析市场情绪，生成今日关注列表..."
}

┌─────────────────────────────────────────────────────────────────────┐
│ Step 3: fin-agent 推理与工具调用                                     │
└─────────────────────────────────────────────────────────────────────┘

fin-agent 接收 prompt，开始推理：

工具调用序列：

1. pool_list() → 获取股票池列表
   agent-ts 调用：POST /api/pool/list（通过 OS 代理到 Trading Service）
   返回：['600519.SH', '000858.SZ', ...]（50 只股票）

2. data.market.quote({symbols: ['600519.SH', '000858.SZ', ...]})
   agent-ts 调用：POST /api/data/market/quote
   OS 转发给 Market Driver (gRPC): GetQuote()
   Market Driver 调用 AKShare: stock.get_realtime_quotes()
   返回：实时行情数据

3. data.market.sentiment() → 获取市场情绪
   agent-ts 调用：POST /api/data/market/sentiment
   OS → Market Driver → AKShare: index.get_market_sentiment()
   返回：{"overall": "positive", "north_flow": "+5.2B", ...}

4. memory_search({query: "早盘强势 开盘涨停", top_k: 10})
   agent-ts 调用：POST /api/memory/search
   OS → Memory System → BM25 + Vector 检索
   返回：10 条历史记忆（类似场景的复盘）

5. decision_record({action: "watch", targets: ['600519.SH'], reason: "..."})
   agent-ts 调用：POST /api/decision/record
   OS → Decision System → 写入 agent_decisions 表

6. memory_write({content: "2026-08-13 早盘分析：市场情绪积极，北向资金净流入 52 亿...", category: "morning-analysis"})
   agent-ts 调用：POST /api/memory/write
   OS → Memory System → 写入 agent_memory 表 + 向量化

完成，返回总结："已完成早盘分析，关注 5 只强势股..."

Token 消耗：3500 tokens

┌─────────────────────────────────────────────────────────────────────┐
│ Step 4: Agent OS 更新配额与发布事件                                  │
└─────────────────────────────────────────────────────────────────────┘

// agent-ts 回调 OS
POST /api/scheduler/executions/456/complete
Body: {
  "status": "success",
  "token_consumed": 3500,
  "output": "已完成早盘分析，关注 5 只强势股：600519.SH(茅台), ..."
}

// OS 更新
UPDATE scheduler_executions SET ... WHERE id = 456;
UPDATE quota_usage SET token_used = token_used + 3500 WHERE agent_id = 'fin-agent';

// OS 发布事件
NOTIFY task_completed, '{"task_id": 5, "agent_id": "fin-agent", "output": "..."}';

┌─────────────────────────────────────────────────────────────────────┐
│ Step 5: Web Frontend 被动接收通知（用户在看页面的话）               │
└─────────────────────────────────────────────────────────────────────┘

如果用户此时在浏览 web-frontend:
  - WebSocket 收到 task_completed 事件
  - 右上角弹出通知："早盘分析已完成"
  - 任务管理页自动刷新，显示最新执行记录
  - Agent 监控页更新：fin-agent 今日已用 token: 3500 / 100000

用户可以点击查看：
  - 执行历史详情
  - 决策记录（今日关注 5 只股票）
  - 新写入的早盘分析记忆

┌─────────────────────────────────────────────────────────────────────┐
│ Step 6: 其他 Agent 通过 Event Bus 收到通知（可选）                  │
└─────────────────────────────────────────────────────────────────────┘

如果 memory-agent 订阅了 task_completed 事件：
  - 收到通知：fin-agent 完成了早盘分析
  - 可以触发：分析该决策是否需要记录到长期记忆
  - 可以触发：评估是否需要进化建议（fin-agent 的分析模式是否需要改进）

（Phase 2 才实现）
```

### 时序图

```
Cron   Agent OS   agent-ts   fin-agent   Market Driver   Trading Service   PostgreSQL
 │        │          │           │            │              │                │
8:30 触发 │          │           │            │              │                │
 │ ──────▶│          │           │            │              │                │
 │        │ 检查依赖：market_data_sync 成功了吗？                            │
 │        │ ────────────────────────────────────────────────────────────────▶│
 │        │◀────────────────────────────────────────────────────────────────│
 │        │ OK，继续                                                          │
 │        │          │           │            │              │                │
 │        │ 检查配额：fin-agent 还有 token 吗？                              │
 │        │ ────────────────────────────────────────────────────────────────▶│
 │        │◀────────────────────────────────────────────────────────────────│
 │        │ OK (今日已用 0 / 100000)                                         │
 │        │          │           │            │              │                │
 │        │ POST /agent/trigger  │            │              │                │
 │        │ ─────────▶│           │            │              │                │
 │        │          │ 创建 fin-agent          │              │                │
 │        │          │ ──────────▶│            │              │                │
 │        │          │           │ LLM 推理    │              │                │
 │        │          │           │            │              │                │
 │        │          │           │ 调用 pool_list()           │                │
 │        │◀──────────────────────────────────│              │                │
 │        │ POST /api/pool/list（代理）       │              │                │
 │        │ ───────────────────────────────────────────────▶│                │
 │        │◀───────────────────────────────────────────────│                │
 │        │ ─────────────────────────▶│      │              │                │
 │        │          │           │            │              │                │
 │        │          │           │ 调用 data.market.quote()  │                │
 │        │◀──────────────────────────────────│              │                │
 │        │ POST /api/data/market/quote       │              │                │
 │        │ gRPC: GetQuote()                  │              │                │
 │        │ ─────────────────────────────────▶│              │                │
 │        │          │           │            │ AKShare API  │                │
 │        │          │           │            │ (外部调用)   │                │
 │        │◀─────────────────────────────────│              │                │
 │        │ ─────────────────────────▶│      │              │                │
 │        │          │           │            │              │                │
 │        │          │           │ 调用 memory_search()      │                │
 │        │◀──────────────────────────────────│              │                │
 │        │ POST /api/memory/search           │              │                │
 │        │ 检索 Memory System                │              │                │
 │        │ ────────────────────────────────────────────────────────────────▶│
 │        │◀────────────────────────────────────────────────────────────────│
 │        │ ─────────────────────────▶│      │              │                │
 │        │          │           │            │              │                │
 │        │          │           │ 调用 decision_record()    │                │
 │        │◀──────────────────────────────────│              │                │
 │        │ POST /api/decision/record         │              │                │
 │        │ ────────────────────────────────────────────────────────────────▶│
 │        │          │           │            │              │                │
 │        │          │           │ 完成，回调 OS              │                │
 │        │◀──────────│           │            │              │                │
 │        │ POST /executions/456/complete     │              │                │
 │        │          │           │            │              │                │
 │        │ 更新执行记录 + 配额 (token += 3500)                                │
 │        │ ────────────────────────────────────────────────────────────────▶│
 │        │          │           │            │              │                │
 │        │ 发布事件：task_completed          │              │                │
 │        │          WebSocket Push (如果 Web 在线)          │                │
 │        │          │           │            │              │                │
```

---

## 6. 关键交互模式总结

### 模式 1：同步调用（Web → OS）
```
用户操作 → Web 发起 HTTP 请求 → OS 处理 → 返回结果 → Web 更新 UI
场景：查询任务列表、查询配额、搜索记忆
```

### 模式 2：异步调度（OS → Agent）
```
OS Scheduler 触发 → Webhook 通知 agent-ts → agent 异步执行 → 回调 OS
场景：定时任务、手动触发任务
```

### 模式 3：工具调用代理（Agent → OS → Driver/Service）
```
agent 调用工具 → OS syscall → OS 转发 gRPC/HTTP → Driver/Service 处理 → 返回 agent
场景：获取市场数据、执行交易、写记忆
```

### 模式 4：事件驱动（OS → Web/Agent）
```
OS 发生事件 → Event Bus 发布 → WebSocket 推送 → Web/Agent 收到通知
场景：任务完成通知、Agent 间协作（Phase 2）
```

---

## 7. 数据流向汇总

| 数据类型 | 起点 | 终点 | 路径 | 存储位置 |
|---|---|---|---|---|
| **任务定义** | agent-ts 启动 | Agent OS | HTTP POST | OS DB: scheduler_tasks |
| **任务触发** | Web / Cron | Agent OS | HTTP POST / Cron | OS DB: scheduler_executions |
| **Agent 推理** | Agent OS | agent-ts | HTTP Webhook | agent-ts 内存 |
| **工具调用** | agent-ts | Agent OS | HTTP POST | - |
| **市场数据** | Market Driver | agent-ts | gRPC (OS 代理) | 缓存在 Driver |
| **记忆写入** | agent-ts | Agent OS | HTTP POST | OS DB: agent_memory |
| **决策记录** | agent-ts | Agent OS | HTTP POST | OS DB: agent_decisions |
| **交易执行** | agent-ts | Trading Service | HTTP (OS 代理) | v2 DB: positions, orders |
| **任务完成通知** | Agent OS | Web | WebSocket | - |
| **配额查询** | Web | Agent OS | HTTP GET | OS DB: quota_usage |

---

## 8. 与当前架构的对比

### 当前架构（分裂）
```
agent-ts ──硬编码 5001──▶ quantsys-v2 (单体)
  │                           │
  本地 Cron (3 tasks)      后端调度器 (40+ tasks)
  互不可见                 互不可见

web ────硬编码 5001──────▶ quantsys-v2
```

### Agent OS 架构（统一）
```
             ┌─────────┐
             │   Web   │
             └────┬────┘
                  │
            ┌─────▼─────┐
            │ Agent OS  │ ◀─── 统一调度、资源管理、权限管控
            └─┬────┬────┘
              │    │
          ┌───▼┐ ┌▼────────┐
          │agent│ │ Driver/ │
          │ -ts │ │ Service │
          └─────┘ └─────────┘
```

---

**关键收益**：
1. **统一视图**：Web 能看到所有任务（agent + 后端）
2. **资源可控**：Token 配额、优先级、并发限制
3. **解耦**：agent 不知道 v2 存在，只知道 OS syscall
4. **可靠**：依赖检查、重试、超时控制
5. **可观测**：执行历史、配额使用、健康状态

---

你满意这个交互设计吗？有哪里需要调整？
