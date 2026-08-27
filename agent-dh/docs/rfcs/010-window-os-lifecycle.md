# RFC 010: Window-OS Lifecycle Management and Role-Based Task Binding (Phase 1)

**Status**: Draft  
**Author**: Kiro (w-29882338)  
**Created**: 2026-08-21  
**Updated**: 2026-08-21  
**Supersedes**: 010-reminder-fallback.md (archived as .bak)

---

## Problem Statement

### Current Failure Mode

定时提醒系统（reminder）在 2026-08-21 13:00 发生沉默故障：

```
scheduled_task: 午盘检查 @ 13:00 → window: investor-session-75cb5ccd
             ↓
delivery: followup() sent to investor-session-75cb5ccd
             ↓
recipient: window not found in ctx.agents.roots()
             ↓
result: silent failure, no alert, no log
```

**根本原因**：生命周期不匹配

| 维度 | 任务（Task） | 窗口（Window） |
|------|-------------|---------------|
| 存储 | PostgreSQL (Agent OS) | Memory (DSH Session) |
| 生命周期 | 持久化（周/月级别） | 临时（会话级别） |
| 标识符 | `window: "w-xxx"` | `agent.id` (动态分配) |
| 重启后 | 任务仍在 | 窗口 ID 变化 |

结果：**任务绑定到已死窗口 → 投递失败 → 沉默丢失**

### Why Not Just Update Window IDs?

临时修复（删旧任务 + 创建新任务指向 w-29882338）只是**治标**，下次重启又会断：

1. **窗口是分身**（incarnation），不是持久身份 — 每次启动 DSH 分配新 ID
2. **窗口私有会话**（dialog history） — 窗口死 = 上下文丢失
3. **任务是角色职责**（investor 的职责） — 不应绑定到具体分身

**正确架构**：任务绑定到**角色**（role），窗口动态发现；Agent OS 维护**窗口注册表**（谁在线、谁健康）。

---

## Solution: Window-OS Lifecycle Management

### Core Concepts

#### 1. Role vs Window

| 概念 | 定义 | 生命周期 | 示例 |
|------|------|---------|------|
| **Role** (角色) | 持久化的逻辑身份 | 长期（不变） | `investor`, `market_analyst` |
| **Window** (窗口) | 角色的临时化身（分身） | 临时（会话级） | `w-29882338`, `w-5b8aac2a` |

**类比**：角色 = 员工岗位，窗口 = 当前值班员工（可换人，职责不变）

#### 2. Agent OS as "Office Manager"

Agent OS 现在不仅管理**任务**（scheduler），还管理**窗口注册表**（window registry）：

```
Agent OS (port 8080)
├── Scheduler        (已有) — 管理定时任务
├── Memory           (已有) — 管理长期记忆
├── Notification     (已有) — 管理通知渠道
└── Window Registry  (新增) — 管理窗口生命周期
    ├── 窗口注册/注销
    ├── 心跳监控
    ├── 超时检测
    └── 在线状态查询
```

#### 3. Task-Role Binding

任务 schema 变更（向前兼容）：

```typescript
// 旧 schema（弃用）
{
  name: "午盘检查",
  window: "w-29882338",  // ❌ 绑定到具体窗口 → 窗口死任务断
  cron: "0 13 * * 1-5",
  prompt: "执行午盘检查"
}

// 新 schema（推荐）
{
  name: "午盘检查",
  role: "investor",            // ✅ 绑定到角色（持久）
  preferred_window: "w-29882338", // 可选：优先投递目标
  cron: "0 13 * * 1-5",
  prompt: "执行午盘检查"
}
```

投递时**动态查询** Agent OS 窗口注册表：

```
Scheduler: 任务触发 → role="investor"
     ↓
Window Registry: 查询在线窗口 → [w-29882338 (idle), w-abc123 (active)]
     ↓
Selection: preferred_window 优先 → w-29882338
     ↓
Delivery: followup(w-29882338, prompt)
```

---

## Architecture

### Window Lifecycle Flow

```
┌─────────────────────────────────────────────────────────────┐
│ DSH Window (investor w-29882338) Lifecycle                   │
└─────────────────────────────────────────────────────────────┘

1. Startup (DSH start.sh 启动)
   ├─ Lifecycle plugin: onCreate hook
   │   └─ POST /api/v1/windows/register
   │       body: { id: "w-29882338", role: "investor", name: "PI投资脑", instance: "investment" }
   │       ← 201 Created
   │
   ├─ Agent OS: 写入 window_registry 表
   │   └─ { id, role, name, instance, status: "online", last_heartbeat: NOW(), metadata: {...} }
   │
   └─ Lifecycle plugin: 启动 heartbeat sender (30s interval)

2. Running (正常运行中)
   ├─ Heartbeat sender (每 30 秒)
   │   └─ POST /api/v1/windows/{id}/heartbeat
   │       body: { current_task: "分析市场", memory_mb: 1200 }
   │       ← 200 OK
   │
   ├─ Agent OS: 更新 last_heartbeat
   │   └─ UPDATE window_registry SET last_heartbeat = NOW(), metadata = ...
   │
   └─ Scheduler: 任务触发时查询在线窗口
       └─ GET /api/v1/windows?role=investor&status=online
           ← 200 [{ id: "w-29882338", status: "online", current_task: null, ... }]

3. Shutdown (正常关闭)
   ├─ Lifecycle plugin: onDispose hook
   │   └─ POST /api/v1/windows/{id}/unregister
   │       ← 200 OK
   │
   └─ Agent OS: 标记 offline
       └─ UPDATE window_registry SET status = "offline", offline_at = NOW()

4. Timeout (异常死亡)
   ├─ Agent OS: heartbeat monitor (每 60 秒扫描)
   │   └─ SELECT * FROM window_registry WHERE status = 'online' AND last_heartbeat < NOW() - 60s
   │
   ├─ 检测到超时窗口: w-29882338
   │   └─ UPDATE window_registry SET status = "timeout", offline_at = NOW()
   │
   └─ Trigger alerts
       ├─ Feishu notification: "窗口 w-29882338 (investor) 心跳超时"
       └─ Optional: board_post (如有待处理任务)
```

### Agent OS Window Registry Schema

```sql
-- 新表: window_registry
CREATE TABLE window_registry (
    id VARCHAR(64) PRIMARY KEY,          -- 窗口 ID (如 w-29882338)
    role VARCHAR(64) NOT NULL,           -- 角色 (如 investor, market_analyst)
    name VARCHAR(255),                   -- 窗口名称 (如 PI投资脑)
    instance VARCHAR(64),                -- 实例名 (如 investment, 区分多实例)
    
    status VARCHAR(32) NOT NULL,         -- online / offline / timeout
    
    registered_at TIMESTAMP NOT NULL,    -- 注册时间
    last_heartbeat TIMESTAMP NOT NULL,   -- 最后心跳时间
    offline_at TIMESTAMP,                -- 离线时间
    
    metadata JSONB,                      -- 扩展元数据
                                         -- { current_task, memory_mb, skills, ... }
    
    INDEX idx_role (role),
    INDEX idx_status (status),
    INDEX idx_last_heartbeat (last_heartbeat)
);

-- 任务表 schema 变更（向前兼容）
ALTER TABLE scheduled_tasks 
    ADD COLUMN role VARCHAR(64),              -- 新：绑定到角色
    ADD COLUMN preferred_window VARCHAR(64);  -- 可选：优先窗口

-- 迁移脚本（将旧 window 绑定迁移到 role 绑定）
UPDATE scheduled_tasks 
SET role = 'investor' 
WHERE window LIKE 'investor-%' OR window LIKE 'w-%';
```

### API Endpoints (Agent OS)

#### 1. Register Window

```http
POST /api/v1/windows/register
Content-Type: application/json

{
  "id": "w-29882338",
  "role": "investor",
  "name": "PI投资脑",
  "instance": "investment",
  "metadata": {
    "port": 13080,
    "pid": 12345,
    "skills": ["市场感知", "交易执行"]
  }
}

Response 201:
{
  "ok": true,
  "window": {
    "id": "w-29882338",
    "role": "investor",
    "status": "online",
    "registered_at": "2026-08-21T13:00:00Z"
  }
}
```

#### 2. Heartbeat

```http
POST /api/v1/windows/{id}/heartbeat
Content-Type: application/json

{
  "current_task": "分析市场主线",
  "memory_mb": 1200
}

Response 200:
{
  "ok": true,
  "last_heartbeat": "2026-08-21T13:05:00Z"
}

Response 404:
{
  "error": "window_not_found",
  "message": "Window w-29882338 not registered"
}
```

#### 3. Unregister Window

```http
POST /api/v1/windows/{id}/unregister

Response 200:
{
  "ok": true,
  "status": "offline",
  "offline_at": "2026-08-21T15:00:00Z"
}
```

#### 4. Query Online Windows

```http
GET /api/v1/windows?role=investor&status=online

Response 200:
{
  "windows": [
    {
      "id": "w-29882338",
      "role": "investor",
      "name": "PI投资脑",
      "status": "online",
      "last_heartbeat": "2026-08-21T13:05:00Z",
      "current_task": "分析市场主线",
      "idle": true
    },
    {
      "id": "w-abc123",
      "role": "investor",
      "status": "online",
      "last_heartbeat": "2026-08-21T13:05:30Z",
      "current_task": "回测策略",
      "idle": false
    }
  ]
}
```

---

## Implementation Plan

### Phase 1: Window Lifecycle Management (Current RFC)

**Scope**: 窗口注册/心跳/注销 + 任务角色绑定

#### Step 1.1: Agent OS Window Registry API

**Location**: `agent-os/internal/api/windows.go` (新增)

**Tasks**:
- [ ] `POST /api/v1/windows/register` — 窗口注册
- [ ] `POST /api/v1/windows/{id}/heartbeat` — 心跳更新
- [ ] `POST /api/v1/windows/{id}/unregister` — 注销窗口
- [ ] `GET /api/v1/windows` — 查询在线窗口（支持 role/status 过滤）
- [ ] Background heartbeat monitor (60s 扫描超时窗口)

**Schema**:
```sql
-- 创建 window_registry 表（见上）
-- 修改 scheduled_tasks 表（添加 role/preferred_window 列）
```

**Validation**:
```bash
# 测试窗口注册
curl -X POST http://localhost:8080/api/v1/windows/register \
  -H "Content-Type: application/json" \
  -d '{"id":"w-test","role":"investor","name":"测试窗口","instance":"investment"}'

# 测试心跳
curl -X POST http://localhost:8080/api/v1/windows/w-test/heartbeat \
  -H "Content-Type: application/json" \
  -d '{"current_task":"测试任务"}'

# 查询在线窗口
curl http://localhost:8080/api/v1/windows?role=investor&status=online

# 测试注销
curl -X POST http://localhost:8080/api/v1/windows/w-test/unregister
```

#### Step 1.2: Lifecycle Plugin Auto-Registration

**Location**: `agent-dh/packages/lifecycle/src/index.ts`

**Current Code** (简化):
```typescript
// setupOsReminderPoller() — 需要重构
setInterval(() => {
  const reminders = await fetchOsReminders();
  const roots = ctx.agents.roots(); // ❌ 问题：只看本地窗口
  for (const reminder of reminders) {
    const target = roots.find(a => a.id === reminder.window);
    if (target) {
      await target.followup(reminder.prompt);
    } else {
      // ❌ 沉默失败
    }
  }
}, 60000);
```

**New Code** (伪代码):
```typescript
class LifecyclePlugin extends Service {
  private heartbeatTimer?: NodeJS.Timeout;
  private windowId?: string;
  private agentOsClient: AgentOsClient;

  constructor(ctx: Context, config: Config) {
    super(ctx, 'lifecycle');
    this.agentOsClient = new AgentOsClient(config.agentOs.baseURL);

    // 1. 窗口启动时自动注册
    ctx.on('ready', () => this.registerWindow());
    
    // 2. 定期心跳
    this.startHeartbeat();
    
    // 3. 关闭时注销
    ctx.on('dispose', () => this.unregisterWindow());
    
    // 4. 重构 reminder poller（查询 OS 注册表，不依赖 ctx.agents.roots()）
    this.setupRoleBasedReminderPoller();
  }

  private async registerWindow() {
    const agentId = this.ctx.config.agent?.id || 'unknown';
    const agentName = this.ctx.config.agent?.name || 'Unnamed Agent';
    const role = this.ctx.config.agent?.role || 'investor';
    const instance = this.ctx.config.agent?.instance || 'investment';

    this.windowId = agentId; // DSH 的 agent.id

    try {
      await this.agentOsClient.post('/api/v1/windows/register', {
        id: this.windowId,
        role,
        name: agentName,
        instance,
        metadata: {
          port: this.config.port,
          pid: process.pid,
        },
      });
      this.ctx.logger.info(`Window registered: ${this.windowId} (${role})`);
    } catch (err) {
      this.ctx.logger.error('Failed to register window:', err);
    }
  }

  private startHeartbeat() {
    this.heartbeatTimer = setInterval(async () => {
      if (!this.windowId) return;

      try {
        await this.agentOsClient.post(`/api/v1/windows/${this.windowId}/heartbeat`, {
          current_task: this.getCurrentTask(), // 从某处读取当前任务
          memory_mb: process.memoryUsage().heapUsed / 1024 / 1024,
        });
      } catch (err) {
        this.ctx.logger.warn('Heartbeat failed:', err);
      }
    }, 30000); // 30 秒
  }

  private async unregisterWindow() {
    if (!this.windowId) return;

    try {
      await this.agentOsClient.post(`/api/v1/windows/${this.windowId}/unregister`);
      this.ctx.logger.info(`Window unregistered: ${this.windowId}`);
    } catch (err) {
      this.ctx.logger.error('Failed to unregister window:', err);
    }

    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
    }
  }

  private setupRoleBasedReminderPoller() {
    setInterval(async () => {
      try {
        // 1. 获取待投递的提醒
        const reminders = await this.agentOsClient.get('/api/v1/reminders/pending');

        for (const reminder of reminders) {
          // 2. 查询该角色的在线窗口
          const windows = await this.agentOsClient.get('/api/v1/windows', {
            params: {
              role: reminder.role,
              status: 'online',
            },
          });

          if (windows.length === 0) {
            // 3. 无在线窗口 → 记录失败 + Feishu 告警
            this.ctx.logger.error(`No online windows for role ${reminder.role}, task: ${reminder.name}`);
            await this.sendNoWindowAlert(reminder);
            continue;
          }

          // 4. 选择目标窗口（优先 preferred_window，否则取 idle 或第一个）
          const target = this.selectTargetWindow(windows, reminder.preferred_window);

          // 5. 投递任务（通过 DSH agents API）
          const agent = this.ctx.agents.get(target.id);
          if (agent) {
            await agent.followup(reminder.prompt);
            this.ctx.logger.info(`Delivered reminder to ${target.id}: ${reminder.name}`);
          } else {
            // 注册表说在线，但 DSH 找不到 → 可能同步延迟，记录 warning
            this.ctx.logger.warn(`Window ${target.id} registered but not found in ctx.agents`);
          }
        }
      } catch (err) {
        this.ctx.logger.error('Reminder poller failed:', err);
      }
    }, 60000); // 60 秒
  }

  private selectTargetWindow(windows: any[], preferred?: string) {
    // 优先策略：preferred_window > idle > first available
    if (preferred) {
      const match = windows.find(w => w.id === preferred);
      if (match) return match;
    }

    const idle = windows.find(w => w.idle);
    if (idle) return idle;

    return windows[0];
  }

  private async sendNoWindowAlert(reminder: any) {
    // 通过 notification 插件发送飞书告警
    // 或者调用 Agent OS notification API
  }

  private getCurrentTask(): string | null {
    // TODO: 从 DSH context 或 state 读取当前任务
    return null;
  }
}
```

**Validation**:
1. 启动 DSH → 检查 Agent OS 窗口注册表有新记录
2. 等待 30 秒 → 检查 last_heartbeat 更新
3. 停止 DSH → 检查窗口标记为 offline
4. 不正常杀进程 → 等待 60 秒检查超时检测是否触发

#### Step 1.3: Task Schema Migration

**Location**: Agent OS database migration

**Migration Script**:
```sql
-- 添加新列
ALTER TABLE scheduled_tasks 
    ADD COLUMN role VARCHAR(64),
    ADD COLUMN preferred_window VARCHAR(64);

-- 迁移现有任务（根据 window 字段推断 role）
UPDATE scheduled_tasks 
SET role = CASE
    WHEN window LIKE 'investor-%' THEN 'investor'
    WHEN window LIKE 'market_analyst-%' THEN 'market_analyst'
    ELSE 'investor' -- 默认
END
WHERE role IS NULL;

-- 保留 preferred_window = 原 window（兼容）
UPDATE scheduled_tasks 
SET preferred_window = window 
WHERE preferred_window IS NULL;

-- 将来可废弃 window 列（但保留一段时间用于回滚）
```

**Update Existing Tasks** (Agent 调用):
```typescript
// 示例：更新午盘检查任务
await ctx.tools.call('reminder_update', {
  task_id: '<午盘检查任务ID>',
  role: 'investor',
  preferred_window: 'w-29882338', // 可选
});
```

#### Step 1.4: Testing & Validation

**Test Cases**:

1. **正常注册与心跳**
   - 启动 DSH → 检查注册
   - 等待 30s → 检查心跳更新
   - 停止 DSH → 检查注销

2. **任务投递（角色绑定）**
   - 创建任务绑定到 role=investor
   - 启动 w-29882338 (investor)
   - 等待任务触发 → 检查投递成功

3. **窗口切换**
   - 停止 w-29882338
   - 启动 w-abc123 (investor)
   - 任务触发 → 检查投递到新窗口

4. **超时检测**
   - 启动窗口
   - kill -9 杀死进程（不走正常注销）
   - 等待 60s → 检查超时标记

5. **无在线窗口场景**
   - 停止所有 investor 窗口
   - 任务触发 → 检查飞书告警

6. **多窗口并存**
   - 启动两个 investor 窗口（w-1 idle, w-2 active）
   - 任务触发 → 检查投递到 idle 窗口

**Acceptance Criteria**:
- ✅ 窗口启动自动注册
- ✅ 心跳每 30s 更新
- ✅ 正常关闭自动注销
- ✅ 异常死亡 60s 内检测
- ✅ 任务按角色投递（不依赖具体窗口 ID）
- ✅ 无在线窗口时告警
- ✅ 多窗口时选择 idle 优先

---

## Phase 2: Session Summary Sync (Deferred)

**Scope**: 窗口定期上传会话摘要到 Agent OS（关键上下文恢复）

**Motivation**: Phase 1 中，窗口死亡 = 会话历史全丢。新窗口启动时是完全空白状态，需要重新理解用户目标/偏好/约束。

**Solution**: 窗口定期提取会话摘要（current_task, recent_decisions, user_instructions, key_context）上传到 Agent OS；新窗口启动时下载最近摘要，快速恢复上下文。

**Implementation** (postponed to later RFC):
- Agent OS API: `POST /api/v1/windows/{id}/session-summary`
- Lifecycle plugin: 每 5 分钟或重大决策后提取摘要上传
- Session summary schema: 
  ```json
  {
    "window_id": "w-29882338",
    "role": "investor",
    "timestamp": "2026-08-21T13:00:00Z",
    "summary": {
      "current_task": "分析市场主线",
      "recent_decisions": [
        "买入 600519 @ 1800 (R-001 买入前确认)"
      ],
      "user_instructions": [
        "优先关注白酒板块"
      ],
      "key_context": {
        "regime": "偏多",
        "circuit_breaker": false,
        "portfolio_value": 100000
      }
    }
  }
  ```

**Why Deferred**: Phase 1 已能解决任务投递问题；摘要恢复是**锦上添花**（提升体验），但不影响系统可用性。

---

## Comparison: Before vs After

| 维度 | Before (Window Binding) | After (Role Binding + Lifecycle) |
|------|------------------------|----------------------------------|
| **任务绑定** | `window: "w-xxx"` (临时) | `role: "investor"` (持久) |
| **窗口重启** | 任务断开（window ID 变） | 自动发现新窗口 |
| **窗口死亡检测** | 无（沉默失败） | 60s 超时检测 + 告警 |
| **无在线窗口** | 沉默失败 | Feishu 告警 + board 记录 |
| **多窗口并存** | 不支持（window 唯一） | 支持（按 idle 优先分配） |
| **状态可见性** | 无 | Agent OS 窗口注册表集中查询 |
| **会话恢复** | 无（窗口死 = 上下文全丢） | Phase 2: 摘要恢复（可选） |

---

## Rollout Plan

### Stage 1: Agent OS API (Week 1)

- [ ] 创建 `window_registry` 表
- [ ] 实现 4 个 Window API endpoints
- [ ] 实现 heartbeat monitor 后台任务
- [ ] 单元测试 + 集成测试

### Stage 2: Lifecycle Plugin (Week 1-2)

- [ ] 实现自动注册/心跳/注销
- [ ] 重构 reminder poller（角色查询）
- [ ] 集成测试（与 Agent OS 联调）

### Stage 3: Task Migration (Week 2)

- [ ] 数据库 migration script
- [ ] 迁移现有 4 个任务（午盘检查、盘后例程、熔断检查、周报）
- [ ] 验证迁移后任务正常投递

### Stage 4: Monitoring & Alerts (Week 2)

- [ ] 窗口超时告警（Feishu）
- [ ] 无在线窗口告警
- [ ] 窗口注册表查询 UI（可选）

### Stage 5: Documentation (Week 3)

- [ ] 更新 reminder 工具文档（标注 role 绑定）
- [ ] 更新 agents.json 维护指南
- [ ] 编写窗口生命周期故障排查指南

---

## Edge Cases & Error Handling

### 1. 窗口注册失败

**Scenario**: DSH 启动时 Agent OS 不可达

**Handling**:
- Lifecycle plugin log warning
- 允许窗口继续运行（降级模式）
- 心跳持续重试注册（backoff）

### 2. 心跳超时但窗口实际在线

**Scenario**: 网络抖动导致心跳丢失

**Handling**:
- 60s timeout 容忍短暂抖动
- 窗口下次心跳成功自动恢复 online
- 避免误报（不在单次心跳失败时告警）

### 3. 多个相同角色窗口并存

**Scenario**: 同时运行两个 investor 窗口（正常场景：多分身）

**Handling**:
- 任务投递选择策略：preferred_window > idle > first
- 未来可实现负载均衡（Phase 3）

### 4. 窗口 ID 冲突

**Scenario**: 重启后 DSH 分配了相同的 window ID（理论上不应发生）

**Handling**:
- Agent OS 注册时检查 ID 冲突
- 如已存在且 online → 拒绝注册，返回 409 Conflict
- 客户端收到 409 → 生成新 ID 重试

### 5. 任务投递到死窗口（同步延迟）

**Scenario**: 注册表显示 online，但窗口实际已死（心跳刚超时）

**Handling**:
- followup() 失败 → 记录 log
- Scheduler 下次重试时重新查询注册表
- 不视为严重错误（自然容错）

---

## Non-Goals (Out of Scope for Phase 1)

### ❌ Full Session Sync

**Why Not**: 完整会话历史（数万 tokens）上传到 Agent OS 过重：
- 存储开销大
- 隐私/安全风险（会话可能含敏感数据）
- 同步复杂度高（增量同步/冲突解决）

**Alternative**: Phase 2 摘要恢复已足够（关键上下文 < 1KB）

### ❌ Load Balancing Across Windows

**Why Not**: 当前场景下，多窗口通常是**备份**（故障切换），不是**并行**（负载分担）。

**Future**: 如果 investor 角色负载确实很高，可在 Phase 3 实现任务队列 + 负载均衡。

### ❌ Window-to-Window Direct Messaging

**Why Not**: 窗口间通信现在通过 Agent OS memory / notification 已足够。

**Future**: 如需实时协作（如 investor 问 market_analyst 意见），可实现 Window Messaging API。

---

## Success Metrics

### Reliability
- ✅ **Zero silent failures**: 任务投递失败必有日志/告警
- ✅ **< 60s failure detection**: 窗口死亡 1 分钟内检测

### Robustness
- ✅ **Window restart transparent**: 窗口重启任务自动切换
- ✅ **Multi-window failover**: 主窗口死，备窗口自动接管

### Observability
- ✅ **Centralized window state**: 一个 API 查询所有窗口状态
- ✅ **Proactive alerts**: 超时/无窗口主动告警，不等用户发现

---

## Future Enhancements (Phase 3+)

### 1. Task Queue & Job Distribution

**Problem**: 当前任务是**定时触发**（cron），如果一个窗口处理很慢，会阻塞后续任务。

**Solution**: 引入任务队列（类似 Celery/BullMQ）：
- Scheduler 生产任务到队列
- 多个窗口并行消费
- 支持优先级/重试/超时

### 2. Window Capabilities & Skill Matching

**Problem**: 不是所有窗口都能处理所有任务（如某些窗口只能分析，不能交易）

**Solution**: 窗口注册时声明 capabilities：
```json
{
  "id": "w-29882338",
  "role": "investor",
  "capabilities": ["market_analysis", "trading", "backtesting"]
}
```

任务声明 required_capability，投递时匹配。

### 3. Session Summary & Context Recovery (Phase 2)

如前文 Phase 2 所述。

### 4. Window Health Scoring

**Problem**: 窗口可能"活着但不健康"（内存泄漏/CPU 高/频繁重启）

**Solution**: 心跳时上报健康指标（memory/CPU/error_rate），Scheduler 根据健康分数选择窗口。

---

## References

- **agents.json**: `~/.dsh/profiles/investment/agents.json` — 窗口-角色注册表（手动维护，将来自动化）
- **Lifecycle Plugin**: `packages/lifecycle/src/index.ts` — DSH 生命周期管理
- **Agent OS Memory**: 现有的 scope-based 存储（market, portfolio, analytics 等）
- **RFC 002**: Self-Restart 机制（窗口自修复）

---

## Appendix: Current Reminder Tasks (To Migrate)

迁移这 4 个现有任务：

```typescript
// 1. 午盘检查 (13:00)
{
  name: "午盘检查",
  role: "investor",              // ← 改这里
  preferred_window: "w-29882338", // ← 可选
  cron: "0 13 * * 1-5",
  prompt: "现在是 13:00，午盘开盘时间。执行午盘例行检查：1. 调用 market_alert 查看市场告警；2. 调用 position_list 检查持仓；3. 如有异常立即处理。"
}

// 2. 盘后例程 (15:30)
{
  name: "盘后例程",
  role: "investor",
  preferred_window: "w-29882338",
  cron: "30 15 * * 1-5",
  prompt: "现在是 15:30，执行盘后例程（R-004）：1. trade_verify 对账；2. risk_metrics 评估组合风险；3. 记录今日决策到 memory_write。"
}

// 3. 熔断检查 (16:30)
{
  name: "熔断检查",
  role: "investor",
  preferred_window: "w-29882338",
  cron: "30 16 * * 1-5",
  prompt: "执行组合回撤熔断检查（M4-2, R-007）：调用 regime_position_limit 检查 circuit_breaker 状态。如触发熔断，立即飞书告警并准备减仓。"
}

// 4. 周报生成 (周五 16:00)
{
  name: "周报生成",
  role: "investor",
  preferred_window: "w-29882338",
  cron: "0 16 * * 5",
  prompt: "今天是周五 16:00，生成本周投资周报：调用 weekly_report_push 生成周报并推送到飞书。"
}
```

迁移脚本（Python 示例）:
```python
# agent-os/scripts/migrate_tasks_to_role.py
import psycopg2

conn = psycopg2.connect(dbname='agent_os', user='...')
cur = conn.cursor()

# 查询所有 window 绑定的任务
cur.execute("SELECT id, name, window FROM scheduled_tasks WHERE role IS NULL")
tasks = cur.fetchall()

for task_id, name, window in tasks:
    # 推断 role（根据 window 前缀或任务名称）
    if 'investor' in window.lower() or 'investor' in name.lower():
        role = 'investor'
    elif 'market_analyst' in window.lower():
        role = 'market_analyst'
    else:
        role = 'investor'  # 默认
    
    # 更新任务
    cur.execute("""
        UPDATE scheduled_tasks 
        SET role = %s, preferred_window = %s 
        WHERE id = %s
    """, (role, window, task_id))
    
    print(f"Migrated task {task_id} ({name}): window={window} -> role={role}")

conn.commit()
cur.close()
conn.close()
```

---

## Decision Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-08-21 | 采用 Role-based 任务绑定 | 窗口是临时化身，角色是持久身份 |
| 2026-08-21 | Phase 1 不同步完整 session | 存储/安全/复杂度高；摘要恢复足够（Phase 2） |
| 2026-08-21 | 心跳间隔 30s，超时阈值 60s | 平衡及时性与网络抖动容忍 |
| 2026-08-21 | 窗口选择策略：preferred > idle > first | 简单有效，未来可扩展负载均衡 |

---

**Status**: Ready for Implementation  
**Next Steps**: 开始 Step 1.1 (Agent OS Window Registry API)
