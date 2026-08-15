# 下一步任务计划 - 2026-08-15

> **调查完成时间**: 2026-08-15  
> **调查结论**: W2.2-W2.4 已全部完成，Agent OS 核心服务已实现但 HTTP API 未完整暴露

---

## 📊 当前状态总结

### ✅ 已完成的工作

#### P1: 记忆服务化（100%）
- ✅ W1.1-W1.6 全部完成
- ✅ 统一记忆表、混合检索、证据链门禁、Web 面板

#### P2: 运行时治理（100%）
- ✅ W2.1: Tool Search 三段式（commit: cc8af43）
- ✅ W2.2: Compaction 四件套（commit: e834c4a）
- ✅ W2.3: Cron 硬化（commit: 8d26b14）
- ✅ W2.4: Hook 三件套（commit: 782a9f8）
- ✅ W2.5: Prompt Cache 审计（commit: fdd9870）

#### P3: Agent OS（50%）
- ✅ WP-4: agent-os-client SDK + agent-ts 集成
- ✅ Agent OS 内核实现（Scheduler/Memory/Decision 服务已实现）
- ✅ Agent OS CLI 完整实现
- ⚠️ Agent OS HTTP API 仅部分实现（只有 Notification）
- ❌ agent-ts 尚未连接到 Agent OS（等待 HTTP API）

#### WP-9: Production Optimization（90%）
- ✅ Phase 1-4 完成（性能基准/监控/部署/文档）
- ⏸️ Phase 5 回归测试未完成

---

## 🔍 关键发现

### Agent OS HTTP API 缺口

**已实现的 HTTP API**（`internal/api/http_server.go`）：
```go
// 仅实现 Notification 相关路由
/api/v1/notifications/send
/api/v1/notifications/channels
/api/v1/notifications/logs
/api/v1/notifications/providers
```

**缺失的 HTTP API**：
```
/api/v1/scheduler/*      // Scheduler 服务
/api/v1/memory/*         // Memory 服务
/api/v1/decision/*       // Decision 服务
/api/v1/resource/*       // Resource 服务
```

**服务层已实现**：
- ✅ `internal/service/memory_service.go`
- ✅ `internal/service/decision_service.go`
- ✅ `internal/service/notification_service.go`
- ✅ `internal/kernel/scheduler/scheduler.go`

**结论**：Agent OS 核心逻辑已实现，只需要添加 HTTP API 路由层。

---

## 🎯 推荐任务顺序

### 方案 A：先重启服务，再补全 Agent OS HTTP API（推荐）

这是最稳健的路线：
1. 立即重启生产服务，激活 P1/P2 所有功能
2. 补全 Agent OS HTTP API（1-2天）
3. agent-ts 完全迁移到 Agent OS（1天）
4. 完成 WP-9 回归测试

**理由**：
- P1/P2 功能已经积压待生效（W1.4 记忆召回、W2.1 Tool Search 等）
- Agent OS HTTP API 缺口不大，可快速补全
- 稳扎稳打，避免风险

---

### 方案 B：直接完成 Agent OS 迁移（激进）

跳过服务重启，全力完成 P3：
1. 补全 Agent OS HTTP API（1-2天）
2. 启动 Agent OS HTTP Server（1小时）
3. agent-ts 迁移验证（1天）
4. 一次性重启切换到新架构

**理由**：
- 避免两次重启（先重启 v2，再重启切 OS）
- 直接达成最终架构目标
- 风险较高，但时间更紧凑

---

## 📋 详细任务分解

### 🔥 P0 任务：重启生产服务（立即）

#### **Task 0.1: 重启 quantsys-v2 (5001)**
```bash
cd /Users/yunpeng/pi-investment/quantsys-v2

# 方法 1: launchd 重启
launchctl kickstart -k com.pi-investment.v2-api

# 方法 2: 手动重启
# 找到进程并 kill，launchd 会自动重启
ps aux | grep "python.*quantsys-v2" | grep -v grep
kill -9 <PID>

# 验证
curl http://127.0.0.1:5001/health
```

**解除积压功能**：
- W1.2 /api/memory API
- W1.3 混合检索
- W1.4 MemoryProvider
- W1.5 周日蒸馏
- W2.1 Tool Search（后端部分）

#### **Task 0.2: 重启 agent-ts**
```bash
cd /Users/yunpeng/pi-investment/agent-ts

# 停止当前进程（Ctrl+C 或 kill）
# 重新启动
npm run dev
```

**解除积压功能**：
- W1.4 召回注入
- W2.1 Tool Search 三段式
- W2.2 Compaction 四件套
- W2.3 Cron 持久化
- W2.4 Hook 系统
- W2.5 缓存修复
- WP-4 Agent OS SDK 集成

**预计时间**: 30 分钟  
**验收标准**:
- 5001 和 agent-ts 正常启动
- 日志中无错误
- Tool Search 三段式生效（/tool_search 工具可用）
- Memory API 可访问

---

### 🚀 P1 任务：补全 Agent OS HTTP API（1-2天）

#### **Task 1.1: 添加 Scheduler HTTP 路由**

**文件**: `agent-os/internal/api/scheduler_handler.go`

**路由**：
```go
// Tasks
POST   /api/v1/scheduler/tasks          // RegisterTask
GET    /api/v1/scheduler/tasks          // ListTasks
GET    /api/v1/scheduler/tasks/:id      // GetTask
PUT    /api/v1/scheduler/tasks/:id      // UpdateTask
DELETE /api/v1/scheduler/tasks/:id      // DeleteTask
POST   /api/v1/scheduler/tasks/:id/trigger  // TriggerTask

// Executions
GET    /api/v1/scheduler/executions     // ListExecutions
GET    /api/v1/scheduler/executions/:id // GetExecution
PUT    /api/v1/scheduler/executions/:id // UpdateExecution
POST   /api/v1/scheduler/executions/:id/cancel  // CancelExecution
```

**预计时间**: 4 小时

#### **Task 1.2: 添加 Memory HTTP 路由**

**文件**: `agent-os/internal/api/memory_handler.go`

**路由**：
```go
POST   /api/v1/memory               // Write
POST   /api/v1/memory/search        // Search
GET    /api/v1/memory               // List
GET    /api/v1/memory/:id           // Get
PUT    /api/v1/memory/:id           // Update
DELETE /api/v1/memory/:id           // Delete
GET    /api/v1/memory/stats         // Stats
POST   /api/v1/memory/recall-audit  // RecallAudit
```

**预计时间**: 3 小时

#### **Task 1.3: 添加 Decision HTTP 路由**

**文件**: `agent-os/internal/api/decision_handler.go`

**路由**：
```go
POST   /api/v1/decision             // Record
GET    /api/v1/decision             // List
GET    /api/v1/decision/:id         // Get
POST   /api/v1/decision/:id/track   // Track
GET    /api/v1/decision/stats       // Stats
GET    /api/v1/decision/query       // Query
```

**预计时间**: 2 小时

#### **Task 1.4: 添加 Resource HTTP 路由**

**文件**: `agent-os/internal/api/resource_handler.go`

**路由**：
```go
GET    /api/v1/resource/quota       // GetQuota
GET    /api/v1/resource/quota/:agentId  // GetQuota by agent
GET    /api/v1/resource/usage       // GetUsage
POST   /api/v1/resource/check       // CheckQuota
GET    /api/v1/resource/namespaces  // ListNamespaces
```

**预计时间**: 2 小时

#### **Task 1.5: 更新 http_server.go 注册路由**

**修改**: `agent-os/internal/api/http_server.go`

```go
func (s *HTTPServer) Start(addr string) error {
    router := mux.NewRouter()

    // Health check
    router.HandleFunc("/health", s.handleHealth).Methods("GET")

    // API v1
    api := router.PathPrefix("/api/v1").Subrouter()
    
    // Scheduler routes
    s.registerSchedulerRoutes(api)
    
    // Memory routes
    s.registerMemoryRoutes(api)
    
    // Decision routes
    s.registerDecisionRoutes(api)
    
    // Resource routes
    s.registerResourceRoutes(api)
    
    // Notification routes (existing)
    s.registerNotificationRoutes(api)

    // ...
}
```

**预计时间**: 1 小时

#### **Task 1.6: 编译和测试**

```bash
cd /Users/yunpeng/pi-investment/agent-os

# 编译
make build

# 运行测试
make test

# 启动服务（测试）
./agent-os serve --port 8080

# 验证端点
curl http://localhost:8080/health
curl http://localhost:8080/api/v1/scheduler/tasks
curl http://localhost:8080/api/v1/memory
```

**预计时间**: 2 小时

**总计时间**: 1-1.5 天

---

### 🔗 P2 任务：agent-ts 完全切换到 Agent OS（1天）

#### **Task 2.1: 启动 Agent OS HTTP Server**

```bash
cd /Users/yunpeng/pi-investment/agent-os

# 启动服务（后台运行）
nohup ./agent-os serve --port 8080 > agent-os.log 2>&1 &

# 或使用 launchd（生产）
# 创建 ~/Library/LaunchAgents/com.pi-investment.agent-os.plist
```

**预计时间**: 1 小时

#### **Task 2.2: 验证 SDK 连接**

```bash
cd /Users/yunpeng/pi-investment/agent-ts

# 设置环境变量
export AGENT_OS_API_URL=http://localhost:8080
export AGENT_ID=fin-agent

# 启动 agent-ts
npm run dev

# 验证工具调用
# - memory_write 应该调用 Agent OS
# - decision_record 应该调用 Agent OS
# - notification_send 应该调用 Agent OS
```

**预计时间**: 2 小时

#### **Task 2.3: Task Registration（可选）**

如果 Agent OS Scheduler 就绪，实现：

**文件**: `agent-ts/src/core/bootstrap/task-registration.ts`

```typescript
export async function registerAgentTasks() {
  const client = getAgentOSClient();
  
  // 注册 daily_ai_review
  await client.scheduler.registerTask({
    name: 'daily_ai_review',
    owner: 'fin-agent',
    cron: '0 18 * * *',
    command: 'daily_ai_review',
    enabled: true,
  });
  
  // 注册 morning_ai_analysis
  // ...
}
```

**预计时间**: 3 小时（如果执行）

#### **Task 2.4: Webhook Endpoint（可选）**

**文件**: `agent-ts/src/api/webhook/trigger.ts`

```typescript
app.post('/api/webhook/trigger', async (req, res) => {
  const { task_id, execution_id } = req.body;
  
  // 创建 session 执行任务
  const { session } = await createSchedulerSession('fin');
  await session.prompt(message, { source: 'agent-os-trigger' });
  
  res.json({ success: true });
});
```

**预计时间**: 2 小时（如果执行）

**总计时间**: 3-8 小时（取决于是否做 Scheduler 迁移）

---

### 🧪 P3 任务：WP-9 Phase 5 回归测试（4-6小时）

#### **Task 3.1: 运行测试套件**

```bash
# Agent OS 测试
cd /Users/yunpeng/pi-investment/agent-os
go test ./... -v -cover

# agent-ts 测试
cd /Users/yunpeng/pi-investment/agent-ts
npm test

# quantsys-v2 测试
cd /Users/yunpeng/pi-investment/quantsys-v2
python -m pytest tests/
```

#### **Task 3.2: 24小时稳定性测试**

```bash
# 启动所有服务
# 运行监控脚本
./scripts/stability-test.sh

# 检查内存泄漏
# 检查错误日志
```

#### **Task 3.3: 文档更新**

- 更新 README.md
- 更新 agent-ts/CLAUDE.md
- 更新 agent-os/docs/

**总计时间**: 4-6 小时

---

## 🗓️ 推荐执行计划

### **方案 A：稳健路线（推荐）**

```
Day 1（今天）:
  [x] Task 0.1-0.2: 重启生产服务（30分钟）✅ 立即执行
  [ ] Task 1.1-1.6: 补全 Agent OS HTTP API（8小时）

Day 2:
  [ ] Task 2.1-2.2: agent-ts 连接 Agent OS（3小时）
  [ ] Task 3.1: 运行测试套件（2小时）
  [ ] 文档更新（2小时）

Day 3（可选）:
  [ ] Task 2.3-2.4: Scheduler 迁移（5小时）
  [ ] Task 3.2: 24小时稳定性测试（后台）

总计: 2-3 天
```

### **方案 B：激进路线（高风险）**

```
Day 1（今天）:
  [ ] Task 1.1-1.6: 补全 Agent OS HTTP API（8小时）

Day 2:
  [ ] Task 2.1-2.4: agent-ts 完全迁移（8小时）
  [ ] Task 0.1-0.2: 一次性切换到新架构
  [ ] Task 3.1: 测试验证（2小时）

总计: 2 天（更紧凑，但风险高）
```

---

## 🎯 我的建议

### **立即执行：Task 0（重启服务）**

先重启服务，激活 P1/P2 所有功能。这是零风险操作，立即见效。

### **然后执行：方案 A（稳健路线）**

1. **Day 1**: 补全 Agent OS HTTP API
2. **Day 2**: agent-ts 连接验证 + 测试
3. **Day 3**: 可选的 Scheduler 迁移

**理由**：
- P1/P2 功能已经积压太久（W1.4-W2.5 等待生效）
- Agent OS HTTP API 缺口不大，1天可补完
- 分步推进，每步可验证，风险可控
- 给 Scheduler 迁移留出充足时间思考和测试

---

## ❓ 需要你确认

1. **是否立即重启服务？**（强烈推荐 ✅）
2. **选择方案 A 还是方案 B？**（推荐方案 A）
3. **是否执行 Scheduler 迁移？**（可以推迟到下周）

请告诉我你的决定，我立即开始执行！
