# Agent OS 统一架构完成计划

> **创建时间**: 2026-08-15 23:10  
> **计划负责人**: Claude (Opus 5) - MacBook 主窗口  
> **执行模式**: 多窗口并行执行  
> **目标**: 9天完成 Agent OS 统一架构

---

## 0. 执行原则

### 0.1 窗口分工

- **主窗口（我）**: 计划制定、审查、协调、测试验收
- **执行窗口**: 具体实现工作（由我分配任务）
- **审查标准**: 每个任务完成后，我负责 code review + 测试验收

### 0.2 并行策略

- **Phase 1** 可独立执行（无依赖）
- **Phase 2-4** 依赖 Phase 1 完成
- **Phase 3-4** 可并行执行

### 0.3 质量门禁

每个任务必须通过：
- ✅ 单元测试
- ✅ 集成测试
- ✅ Code Review
- ✅ 功能验收

---

## 1. Phase 1: Agent OS Scheduler HTTP API（1天）⚠️ 最高优先级

### 任务卡：WP-12-scheduler-http-api

**优先级**: P0 - Critical  
**依赖**: 无  
**预计工作量**: 1天  
**执行窗口**: 待分配

---

### 1.1 背景

**问题**: Agent OS Scheduler 只有 CLI，缺 HTTP API，导致：
- agent-ts 无法通过 HTTP 注册任务
- Webhook 触发机制不可用
- 无法统一调度架构

**目标**: 实现 Scheduler HTTP API，支持：
- 任务注册/查询/触发/删除
- Webhook 回调机制
- 与现有 CLI 功能对等

---

### 1.2 需求清单

#### A. HTTP Handler 实现

**文件**: `agent-os/internal/handlers/scheduler_handler.go`

**需实现的方法**:

```go
type SchedulerHandler struct {
    scheduler *scheduler.Scheduler
}

func NewSchedulerHandler(s *scheduler.Scheduler) *SchedulerHandler

// HTTP Handlers
func (h *SchedulerHandler) RegisterTask(w http.ResponseWriter, r *http.Request)
func (h *SchedulerHandler) ListTasks(w http.ResponseWriter, r *http.Request)
func (h *SchedulerHandler) GetTask(w http.ResponseWriter, r *http.Request)
func (h *SchedulerHandler) TriggerTask(w http.ResponseWriter, r *http.Request)
func (h *SchedulerHandler) DeleteTask(w http.ResponseWriter, r *http.Request)
func (h *SchedulerHandler) GetTaskRuns(w http.ResponseWriter, r *http.Request)
func (h *SchedulerHandler) RegisterRoutes(r *mux.Router)
```

**API 契约**:

```
POST   /api/v1/scheduler/tasks              # 注册任务
GET    /api/v1/scheduler/tasks              # 列出任务
GET    /api/v1/scheduler/tasks/{id}         # 获取任务详情
POST   /api/v1/scheduler/tasks/{id}/trigger # 手动触发
DELETE /api/v1/scheduler/tasks/{id}         # 删除任务
GET    /api/v1/scheduler/tasks/{id}/runs    # 执行历史
```

**Request/Response 格式**: 参考现有 CLI 的输入输出结构

---

#### B. serve.go 集成

**文件**: `agent-os/internal/cmd/serve.go`

**需修改**:

```go
// 第 99-104 行附近
// 添加 Scheduler 初始化
schedulerSvc := scheduler.New(nil)
if err := schedulerSvc.Start(ctx); err != nil {
    return fmt.Errorf("failed to start scheduler: %w", err)
}
defer schedulerSvc.Stop()

schedulerHandler := handlers.NewSchedulerHandler(schedulerSvc)

// 修改 server 初始化
server := api.NewHTTPServer(svc, skillHandler, schedulerHandler)
```

---

#### C. HTTP Server 路由注册

**文件**: `agent-os/internal/api/http_server.go`

**需修改**:

```go
type HTTPServer struct {
    notificationService *service.NotificationService
    skillHandler        *handlers.SkillHandler
    schedulerHandler    *handlers.SchedulerHandler  // 新增
    // ...
}

func NewHTTPServer(
    notificationService *service.NotificationService,
    skillHandler *handlers.SkillHandler,
    schedulerHandler *handlers.SchedulerHandler,  // 新增
) *HTTPServer

func (s *HTTPServer) setupRoutes() {
    // 注册 Scheduler 路由
    s.schedulerHandler.RegisterRoutes(s.router)
}
```

---

#### D. Webhook 触发机制

**需求**: 任务触发时，调用配置的 webhook URL

**实现位置**: `internal/kernel/scheduler/executor.go`

**逻辑**:

```go
func (e *Executor) executeTask(ctx context.Context, task *types.Task, run *types.TaskRun) error {
    // 执行前：调用 webhook
    if task.WebhookURL != "" {
        webhookPayload := map[string]interface{}{
            "task_id":   task.ID.String(),
            "task_name": task.Name,
            "run_id":    run.ID.String(),
            "params":    task.Metadata,
        }
        
        resp, err := http.Post(task.WebhookURL, "application/json", ...)
        if err != nil {
            return fmt.Errorf("webhook failed: %w", err)
        }
        
        // 根据 webhook 响应判断任务是否成功
        // ...
    }
    
    return nil
}
```

---

#### E. 数据库 Schema 更新

**文件**: `migrations/010_add_webhook_url.sql`

**SQL**:

```sql
-- 添加 webhook_url 字段到 tasks 表
ALTER TABLE scheduler_tasks
ADD COLUMN webhook_url TEXT;

CREATE INDEX idx_scheduler_tasks_webhook ON scheduler_tasks(webhook_url) 
WHERE webhook_url IS NOT NULL;
```

---

### 1.3 验收标准

#### ✅ 功能验收

```bash
# 1. 启动 Agent OS HTTP 服务器
./agent-os serve --port 8080

# 2. 注册任务
curl -X POST http://localhost:8080/api/v1/scheduler/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test_task",
    "schedule": "*/5 * * * *",
    "command": "echo test",
    "webhook_url": "http://localhost:3002/api/webhook/trigger",
    "enabled": true
  }'

# 3. 列出任务
curl http://localhost:8080/api/v1/scheduler/tasks

# 4. 手动触发
curl -X POST http://localhost:8080/api/v1/scheduler/tasks/{id}/trigger

# 5. 查看执行历史
curl http://localhost:8080/api/v1/scheduler/tasks/{id}/runs

# 6. 删除任务
curl -X DELETE http://localhost:8080/api/v1/scheduler/tasks/{id}
```

#### ✅ Webhook 验收

```bash
# 启动一个简单的 webhook 接收服务器
python3 -m http.server 3002 &

# 等待任务触发，观察是否收到 webhook 回调
```

#### ✅ 单元测试

**文件**: `internal/handlers/scheduler_handler_test.go`

测试覆盖：
- RegisterTask 成功/失败
- ListTasks 过滤
- TriggerTask 成功/失败
- DeleteTask 成功/失败

---

### 1.4 交付物清单

- [ ] `internal/handlers/scheduler_handler.go` (新建)
- [ ] `internal/handlers/scheduler_handler_test.go` (新建)
- [ ] `internal/cmd/serve.go` (修改)
- [ ] `internal/api/http_server.go` (修改)
- [ ] `internal/kernel/scheduler/executor.go` (修改 - webhook)
- [ ] `migrations/010_add_webhook_url.sql` (新建)
- [ ] API 测试脚本 (新建)
- [ ] 文档更新

---

### 1.5 风险与注意事项

⚠️ **风险**:
1. Scheduler 实例生命周期管理（Start/Stop）
2. Webhook 调用超时处理
3. 并发任务执行（已有，需验证）

⚠️ **注意**:
1. 保持与 CLI 功能对等（相同的参数、相同的行为）
2. 错误返回格式统一（JSON）
3. 日志记录完整（请求/响应/错误）

---

## 2. Phase 2: agent-ts 接入 Scheduler（2天）

### 任务卡：WP-13-agent-ts-scheduler-integration

**优先级**: P0  
**依赖**: WP-12 完成  
**预计工作量**: 2天  
**执行窗口**: 待分配

---

### 2.1 背景

**问题**: agent-ts 仍用本地 node-cron，与 Agent OS 并存

**目标**:
- 移除本地 node-cron
- 接入 Agent OS Scheduler
- 实现 Webhook 接收

---

### 2.2 需求清单

#### A. 移除本地 SchedulerService

**文件**: `agent-ts/src/services/scheduler/scheduler-service.ts`

**操作**: 
- 标记为 `@deprecated`
- 添加迁移说明注释
- 停止使用（不删除文件，保留回滚能力）

---

#### B. 实现 Webhook 接收端点

**文件**: `agent-ts/src/api/webhook/trigger.ts` (已存在，需修改)

**需求**:

```typescript
router.post('/trigger', async (req, res) => {
  const { task_id, task_name, run_id, params } = req.body;
  
  logger.info(`[Webhook] Task triggered: ${task_name} (run: ${run_id})`);
  
  try {
    // 根据 task_name 或 params.skill_id 执行对应的 skill
    const { skill_id, skill_name } = params;
    
    if (skill_id) {
      // 从 Agent OS Skill Hub 获取 skill 并执行
      await executeSkillById(skill_id, { 
        source: 'agent-os-scheduler',
        taskId: task_id,
        runId: run_id 
      });
    } else if (skill_name) {
      // 通过 name 查找并执行
      await executeSkillByName(skill_name, { ... });
    } else {
      return res.status(400).json({ 
        success: false, 
        error: 'Missing skill_id or skill_name' 
      });
    }
    
    // 立即返回成功（不等待 LLM）
    res.json({ success: true, run_id });
    
  } catch (error) {
    logger.error('[Webhook] Task execution failed:', error);
    res.status(500).json({ 
      success: false, 
      error: error.message 
    });
  }
});
```

---

#### C. 启动时注册任务到 Agent OS

**文件**: `agent-ts/src/core/bootstrap/task-registration.ts`

**需求**:

```typescript
import axios from 'axios';

const AGENT_OS_URL = process.env.AGENT_OS_BASE_URL || 'http://localhost:8080';
const WEBHOOK_URL = 'http://localhost:3002/api/webhook/trigger';

export async function registerScheduledTasks(): Promise<void> {
  logger.info('[TaskRegistry] Registering tasks to Agent OS...');
  
  // 获取所有需要调度的 skills（从本地或从 Agent OS）
  const skills = await loadSkillsWithSchedule();
  
  for (const skill of skills) {
    try {
      await axios.post(`${AGENT_OS_URL}/api/v1/scheduler/tasks`, {
        name: skill.name,
        schedule: skill.metadata.schedule,
        webhook_url: WEBHOOK_URL,
        enabled: true,
        metadata: {
          skill_id: skill.id,  // 传递给 webhook 的参数
          description: skill.description
        }
      });
      
      logger.info(`[TaskRegistry] ✅ Registered: ${skill.name}`);
    } catch (error) {
      logger.error(`[TaskRegistry] ❌ Failed: ${skill.name}`, error);
    }
  }
}
```

---

#### D. 启动流程集成

**文件**: `agent-ts/src/index.ts`

**修改**:

```typescript
async function bootstrap() {
  // 1. 初始化配置
  await initializeConfig();
  
  // 2. 加载 Skills（如果已接入 Skill Hub，从 Agent OS 加载）
  await loadSkillRegistry();
  
  // 3. 注册任务到 Agent OS Scheduler
  await registerScheduledTasks();
  
  // 4. 启动 Gateway API（接收 webhook）
  await startGatewayServer();
  
  console.log('✅ agent-ts started with Agent OS Scheduler');
}
```

---

### 2.3 验收标准

#### ✅ 功能验收

```bash
# 1. 启动 agent-ts
cd agent-ts
npm run start

# 观察日志：
# ✅ [TaskRegistry] Registered: morning_ai_analysis
# ✅ [TaskRegistry] Registered: pool_maintenance
# ...

# 2. 验证任务已注册到 Agent OS
curl http://localhost:8080/api/v1/scheduler/tasks | jq '.tasks[] | {name, schedule}'

# 3. 手动触发测试
curl -X POST http://localhost:8080/api/v1/scheduler/tasks/{task_id}/trigger

# 4. 观察 agent-ts 日志，确认收到 webhook 触发

# 5. 等待 cron 自动触发，验证正常工作
```

#### ✅ 回归测试

- agent-ts 启动成功
- Skills 正常执行
- 日志记录完整
- 错误处理正确

---

### 2.4 交付物清单

- [ ] `src/api/webhook/trigger.ts` (修改)
- [ ] `src/core/bootstrap/task-registration.ts` (新建)
- [ ] `src/services/scheduler/scheduler-service.ts` (标记 deprecated)
- [ ] `src/index.ts` (修改)
- [ ] 集成测试 (新建)
- [ ] 文档更新

---

## 3. Phase 3: agent-ts 接入 Skill Hub（3天）

### 任务卡：WP-14-agent-ts-skill-hub-integration

**优先级**: P0  
**依赖**: WP-12 完成  
**预计工作量**: 3天  
**执行窗口**: 待分配（可与 WP-15 并行）

---

### 3.1 背景

**问题**: agent-ts 仍从本地文件读取 skills，Agent OS Skill Hub 后端已就绪但未集成

**目标**:
- 实现 agent-os-client SkillsClient
- 启动时从 Agent OS 加载 skill 元数据
- 运行时通过 ID 获取 skill content
- 实现 3 个 tools
- 迁移现有 skills

---

### 3.2 需求清单

#### Day 1: SDK Client

**文件**: `agent-os-client/src/skills.ts` (新建)

**需实现**: 参考设计文档 `2026-08-15-skill-hub-implementation.md` 的 SDK 部分

```typescript
export class SkillsClient extends BaseClient {
  async list(params?: { owner?: string; status?: string }): Promise<SkillMetadata[]>
  async get(id: string): Promise<SkillDetail>
  async create(data: CreateSkillRequest): Promise<Skill>
  async update(id: string, data: UpdateSkillRequest): Promise<SkillVersion>
  async findByName(name: string): Promise<SkillMetadata | null>
}
```

---

#### Day 2: agent-ts 集成

**文件**:
- `agent-ts/src/core/bootstrap/skill-registry.ts` (新建)
- `agent-ts/src/core/skills/skill-executor.ts` (新建)

**需实现**: 参考设计文档的 agent-ts 集成部分

---

#### Day 3: Tools + Migration

**文件**:
- `agent-ts/src/infrastructure/tools/skill/skill-list-tool.ts` (新建)
- `agent-ts/src/infrastructure/tools/skill/skill-get-tool.ts` (新建)
- `agent-ts/src/infrastructure/tools/skill/skill-update-tool.ts` (新建)
- `agent-ts/scripts/migrate-skills-to-os.ts` (新建)

**需实现**: 参考设计文档的 Tools 和迁移脚本部分

---

### 3.3 验收标准

参考设计文档 `2026-08-15-skill-hub-implementation.md` 的验收标准

---

### 3.4 交付物清单

- [ ] agent-os-client SDK (SkillsClient)
- [ ] agent-ts 集成代码
- [ ] 3 个 tools
- [ ] 迁移脚本
- [ ] 测试
- [ ] 文档

---

## 4. Phase 4: quantsys-v2 接入 Scheduler（3天）

### 任务卡：WP-15-v2-scheduler-integration

**优先级**: P0  
**依赖**: WP-12 完成  
**预计工作量**: 3天  
**执行窗口**: 待分配（可与 WP-14 并行）

---

### 4.1 背景

**问题**: quantsys-v2 有独立调度器，30+ 任务独立运行

**目标**:
- 实现 v2 Webhook 端点
- 注册 30+ 任务到 Agent OS
- 移除本地调度器

---

### 4.2 需求清单

参考设计文档 `2026-08-15-wp11-v2-scheduler-migration.md`

#### Day 1: Webhook 实现

**文件**: `quantsys-v2/api/routes/webhook.py` (新建)

**需实现**: 参考设计文档的 webhook 实现部分

---

#### Day 2: 任务注册

**文件**: `quantsys-v2/scripts/register_tasks_to_agent_os.py` (新建)

**需实现**: 参考设计文档的任务注册部分

---

#### Day 3: 测试与部署

- 集成测试
- 灰度部署
- 监控验证

---

### 4.3 验收标准

参考设计文档 `2026-08-15-wp11-v2-scheduler-migration.md` 的验收标准

---

### 4.4 交付物清单

- [ ] Webhook 端点
- [ ] 任务注册脚本
- [ ] 测试
- [ ] 部署文档

---

## 5. 执行时间线

```
Day 1:   WP-12 (Scheduler HTTP API)
         ↓
Day 2-3: WP-13 (agent-ts Scheduler)
         ↓
Day 4-6: WP-14 (agent-ts Skill Hub) ← 并行
Day 4-6: WP-15 (v2 Scheduler)       ← 并行
         ↓
Day 7-8: 集成测试 + Bug 修复
Day 9:   最终验收 + 文档完善
```

---

## 6. 我的工作（主窗口）

### 每日工作

- **每天早上**: 分配当日任务给执行窗口
- **每天晚上**: Code Review + 验收

### Phase 完成时

- 执行集成测试
- 验证功能完整性
- 更新架构文档

---

## 7. 成功标准

### 最终验收标准

- [ ] Agent OS Scheduler HTTP API 可用
- [ ] agent-ts 无本地调度器
- [ ] agent-ts Skills 从 Agent OS 获取
- [ ] quantsys-v2 无本地调度器
- [ ] 所有任务在 Agent OS 统一调度
- [ ] 集成测试通过
- [ ] 架构文档更新

### 性能指标

- Webhook 响应时间 < 1s
- 任务触发准时性 ± 1 分钟
- 任务执行成功率 > 95%

---

## 8. 风险管理

### 已识别风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| Scheduler HTTP API 实现复杂 | 中 | 高 | 参考现有 CLI 实现 |
| agent-ts 集成破坏现有功能 | 中 | 高 | 保留回滚能力 |
| v2 任务迁移遗漏 | 中 | 中 | 清单验证 |
| 性能下降 | 低 | 中 | 性能测试 |

---

**计划制定完成**: 2026-08-15 23:10  
**计划负责人**: Claude (Opus 5) - MacBook 主窗口  
**执行开始**: 待分配任务给执行窗口
