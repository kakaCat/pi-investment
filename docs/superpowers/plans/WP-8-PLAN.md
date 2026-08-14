# WP-8: Permissions + Event Bus

> **工作包**: WP-8  
> **批次**: Batch 4  
> **工期**: 2 天 (Day 9-10)  
> **并行任务数**: 1 个  
> **负责人**: Agent-Auth

---

## 📋 目标

实现权限系统和事件总线，完成 Agent OS 的安全和通信基础设施。

### 核心功能

1. **AuthManager (权限管理器)**
   - Agent 身份识别
   - 基于角色的权限控制 (RBAC)
   - 命令级别的权限检查
   - 权限配置加载

2. **Event Bus (事件总线)**
   - PostgreSQL NOTIFY/LISTEN 机制
   - 事件发布/订阅
   - WebSocket 服务器
   - 事件过滤和路由

3. **CLI/API 集成**
   - 所有命令集成权限检查
   - WebSocket 订阅接口
   - 实时事件推送

---

## 🏗️ 架构设计

### 权限模型

```
Agent 身份
  ↓
Role (角色)
  ↓
Permissions (权限列表)
  ↓
Command Check (命令检查)
```

#### 预定义角色

| Role | 权限范围 | 典型 Agent |
|------|---------|-----------|
| **admin** | 全部命令 | system-admin |
| **trading** | scheduler, trading, decision, data | fin-agent |
| **memory** | memory, resource | memory-agent |
| **notification** | notify | feishu-bot |
| **readonly** | 只读命令 (list, get, search) | web-frontend |

#### 权限配置文件

```yaml
# config/permissions.yaml
roles:
  admin:
    permissions: ["*"]
  
  trading:
    permissions:
      - "scheduler:*"
      - "trading:*"
      - "decision:*"
      - "data:*"
      - "memory:read"
  
  memory:
    permissions:
      - "memory:*"
      - "resource:*"
  
  notification:
    permissions:
      - "notify:*"
  
  readonly:
    permissions:
      - "scheduler:list"
      - "scheduler:get"
      - "memory:search"
      - "decision:list"
      - "decision:get"

agents:
  fin-agent:
    role: trading
  
  memory-agent:
    role: memory
  
  feishu-bot:
    role: notification
  
  web-frontend:
    role: readonly
```

### Event Bus 架构

```
┌─────────────────────────────────────────────┐
│  Event Publishers (发布者)                   │
│  • SchedulerService (任务完成)              │
│  • DecisionService (决策记录)               │
│  • MemoryService (记忆更新)                 │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│  Event Bus (事件总线)                        │
│  • PostgreSQL NOTIFY                        │
│  • Channel: agent_os_events                 │
│  • Payload: JSON {type, data, timestamp}    │
└─────────────────┬───────────────────────────┘
                  ↓
┌─────────────────────────────────────────────┐
│  Event Listeners (监听者)                    │
│  • WebSocket Server (实时推送)              │
│  • Agent Webhooks (异步通知)                │
│  • Audit Logger (审计日志)                  │
└─────────────────────────────────────────────┘
```

#### 事件类型

```go
type EventType string

const (
    EventTaskCompleted    EventType = "task.completed"
    EventTaskFailed       EventType = "task.failed"
    EventDecisionRecorded EventType = "decision.recorded"
    EventMemoryCreated    EventType = "memory.created"
    EventQuotaExceeded    EventType = "quota.exceeded"
)

type Event struct {
    Type      EventType              `json:"type"`
    Data      map[string]interface{} `json:"data"`
    Timestamp time.Time              `json:"timestamp"`
    AgentID   string                 `json:"agent_id"`
}
```

### WebSocket 协议

#### 连接

```
ws://localhost:8080/ws/events?agent_id=fin-agent&filters=task.*,decision.*
```

#### 消息格式

```json
{
  "type": "task.completed",
  "data": {
    "task_id": "daily-pool-refresh",
    "status": "success",
    "duration_ms": 1234
  },
  "timestamp": "2026-08-14T10:30:00Z",
  "agent_id": "fin-agent"
}
```

---

## 📁 文件结构

```
agent-os/
├── internal/
│   ├── auth/
│   │   ├── auth_manager.go          # 权限管理器
│   │   ├── auth_manager_test.go     # 单元测试
│   │   └── permissions.go           # 权限模型
│   ├── events/
│   │   ├── event_bus.go             # 事件总线
│   │   ├── event_bus_test.go        # 单元测试
│   │   ├── websocket_server.go      # WebSocket 服务器
│   │   └── types.go                 # 事件类型定义
│   └── middleware/
│       └── auth_middleware.go       # CLI/API 权限中间件
├── config/
│   └── permissions.yaml             # 权限配置
└── cmd/
    └── agent-os/
        └── main.go                  # 集成 WebSocket 服务器
```

---

## 🔧 实现计划

### Day 1: 权限系统

#### 1. AuthManager 实现

**文件**: `internal/auth/auth_manager.go`

```go
package auth

import (
    "fmt"
    "gopkg.in/yaml.v3"
    "os"
    "strings"
)

type Permission string

type Role struct {
    Name        string       `yaml:"name"`
    Permissions []Permission `yaml:"permissions"`
}

type AgentConfig struct {
    AgentID string `yaml:"agent_id"`
    Role    string `yaml:"role"`
}

type PermissionsConfig struct {
    Roles  map[string]Role        `yaml:"roles"`
    Agents map[string]AgentConfig `yaml:"agents"`
}

type AuthManager struct {
    config *PermissionsConfig
}

func NewAuthManager(configPath string) (*AuthManager, error) {
    // Load permissions.yaml
    // Parse config
    // Return AuthManager
}

func (am *AuthManager) CheckPermission(agentID, command string) error {
    // 1. Get agent's role
    // 2. Get role's permissions
    // 3. Check if command matches any permission
    // 4. Return error if denied
}

func (am *AuthManager) GetAgentRole(agentID string) (string, error) {
    // Return agent's role
}

func (am *AuthManager) GetRolePermissions(role string) ([]Permission, error) {
    // Return role's permissions
}

func matchPermission(permission Permission, command string) bool {
    // Support wildcard matching
    // "scheduler:*" matches "scheduler:list", "scheduler:trigger"
    // "*" matches everything
}
```

**单元测试**: `internal/auth/auth_manager_test.go`

- ✅ 测试管理员全部权限
- ✅ 测试 trading agent 权限
- ✅ 测试 memory agent 被拒绝 trading 命令
- ✅ 测试 readonly agent 只能查询
- ✅ 测试通配符匹配

#### 2. CLI 中间件集成

**文件**: `internal/middleware/auth_middleware.go`

```go
package middleware

import (
    "fmt"
    "os"
    "github.com/spf13/cobra"
    "agent-os/internal/auth"
)

var authManager *auth.AuthManager

func InitAuth(configPath string) error {
    var err error
    authManager, err = auth.NewAuthManager(configPath)
    return err
}

func AuthMiddleware(cmd *cobra.Command, args []string) error {
    agentID := os.Getenv("AGENT_ID")
    if agentID == "" {
        agentID = "admin" // Default to admin for CLI
    }

    command := getCommandPath(cmd) // e.g., "scheduler:list"
    
    return authManager.CheckPermission(agentID, command)
}

func getCommandPath(cmd *cobra.Command) string {
    // Build command path from cobra command tree
    // scheduler list -> "scheduler:list"
}
```

#### 3. 所有 CLI 命令集成权限检查

修改每个命令文件，添加 `PreRunE` 钩子：

```go
// internal/cmd/scheduler.go
var schedulerListCmd = &cobra.Command{
    Use:   "list",
    Short: "List all tasks",
    PreRunE: middleware.AuthMiddleware, // Add this
    RunE: func(cmd *cobra.Command, args []string) error {
        // Original logic
    },
}
```

#### Day 1 验收

```bash
# 1. 编译
cd .claude/worktrees/wp-8-permissions-eventbus/agent-os
go build -o agent-os ./cmd/agent-os

# 2. 测试 admin 权限
AGENT_ID=admin ./agent-os scheduler list
# 预期: 成功

# 3. 测试 memory-agent 被拒绝
AGENT_ID=memory-agent ./agent-os trading order
# 预期: Error: permission denied

# 4. 单元测试
go test ./internal/auth/... -v
# 预期: 全部通过
```

---

### Day 2: Event Bus

#### 1. Event Bus 实现

**文件**: `internal/events/event_bus.go`

```go
package events

import (
    "context"
    "encoding/json"
    "fmt"
    "time"
    "github.com/jackc/pgx/v5/pgxpool"
)

type EventType string

const (
    EventTaskCompleted    EventType = "task.completed"
    EventTaskFailed       EventType = "task.failed"
    EventDecisionRecorded EventType = "decision.recorded"
    EventMemoryCreated    EventType = "memory.created"
    EventQuotaExceeded    EventType = "quota.exceeded"
)

type Event struct {
    Type      EventType              `json:"type"`
    Data      map[string]interface{} `json:"data"`
    Timestamp time.Time              `json:"timestamp"`
    AgentID   string                 `json:"agent_id"`
}

type EventBus struct {
    db        *pgxpool.Pool
    listeners map[string][]chan Event // event_type -> channels
}

func NewEventBus(db *pgxpool.Pool) *EventBus {
    return &EventBus{
        db:        db,
        listeners: make(map[string][]chan Event),
    }
}

func (eb *EventBus) Publish(ctx context.Context, event Event) error {
    event.Timestamp = time.Now()
    payload, _ := json.Marshal(event)
    
    _, err := eb.db.Exec(ctx, 
        "SELECT pg_notify('agent_os_events', $1)", 
        string(payload))
    
    return err
}

func (eb *EventBus) Subscribe(ctx context.Context, filters []string) (<-chan Event, error) {
    // 1. Connect to PostgreSQL LISTEN channel
    // 2. Create event channel
    // 3. Start goroutine to forward events
    // 4. Apply filters
    // 5. Return channel
}

func (eb *EventBus) Start(ctx context.Context) error {
    // Start listening to PostgreSQL NOTIFY
    conn, err := eb.db.Acquire(ctx)
    if err != nil {
        return err
    }

    _, err = conn.Exec(ctx, "LISTEN agent_os_events")
    if err != nil {
        return err
    }

    go eb.listenLoop(ctx, conn)
    return nil
}

func (eb *EventBus) listenLoop(ctx context.Context, conn *pgxpool.Conn) {
    for {
        notification, err := conn.Conn().WaitForNotification(ctx)
        if err != nil {
            return
        }

        var event Event
        json.Unmarshal([]byte(notification.Payload), &event)

        // Broadcast to all listeners
        eb.broadcast(event)
    }
}
```

#### 2. WebSocket 服务器

**文件**: `internal/events/websocket_server.go`

```go
package events

import (
    "context"
    "encoding/json"
    "net/http"
    "strings"
    "github.com/gorilla/websocket"
)

var upgrader = websocket.Upgrader{
    CheckOrigin: func(r *http.Request) bool { return true },
}

type WebSocketServer struct {
    eventBus *EventBus
}

func NewWebSocketServer(eventBus *EventBus) *WebSocketServer {
    return &WebSocketServer{eventBus: eventBus}
}

func (wss *WebSocketServer) HandleWebSocket(w http.ResponseWriter, r *http.Request) {
    conn, err := upgrader.Upgrade(w, r, nil)
    if err != nil {
        return
    }
    defer conn.Close()

    // Parse query params
    agentID := r.URL.Query().Get("agent_id")
    filters := strings.Split(r.URL.Query().Get("filters"), ",")

    // Subscribe to events
    ctx := context.Background()
    eventChan, err := wss.eventBus.Subscribe(ctx, filters)
    if err != nil {
        return
    }

    // Forward events to WebSocket
    for event := range eventChan {
        if agentID != "" && event.AgentID != agentID {
            continue // Filter by agent_id
        }

        data, _ := json.Marshal(event)
        conn.WriteMessage(websocket.TextMessage, data)
    }
}

func (wss *WebSocketServer) Start(addr string) error {
    http.HandleFunc("/ws/events", wss.HandleWebSocket)
    return http.ListenAndServe(addr, nil)
}
```

#### 3. 集成到主程序

**文件**: `cmd/agent-os/main.go`

```go
func main() {
    // ... existing code ...

    // Initialize Event Bus
    eventBus := events.NewEventBus(db)
    err = eventBus.Start(context.Background())
    if err != nil {
        log.Fatal("Failed to start event bus:", err)
    }

    // Start WebSocket server (goroutine)
    wsServer := events.NewWebSocketServer(eventBus)
    go func() {
        log.Println("WebSocket server listening on :8080")
        wsServer.Start(":8080")
    }()

    // Execute CLI command
    if err := rootCmd.Execute(); err != nil {
        os.Exit(1)
    }
}
```

#### 4. 在服务中发布事件

修改 SchedulerService, DecisionService 等：

```go
// internal/service/scheduler_service.go
func (s *SchedulerService) executorLoop() {
    // ... existing code ...

    // After task execution
    s.eventBus.Publish(context.Background(), events.Event{
        Type: events.EventTaskCompleted,
        Data: map[string]interface{}{
            "task_id":     task.ID,
            "status":      "success",
            "duration_ms": duration.Milliseconds(),
        },
        AgentID: task.AgentID,
    })
}
```

#### Day 2 验收

```bash
# 1. 编译
go build -o agent-os ./cmd/agent-os

# 2. 启动 daemon (后台)
./agent-os scheduler daemon &

# 3. WebSocket 测试 (使用 websocat 或浏览器)
websocat ws://localhost:8080/ws/events?agent_id=fin-agent&filters=task.*

# 4. 触发任务 (另一个终端)
AGENT_ID=fin-agent ./agent-os scheduler trigger --task-id daily-pool-refresh

# 5. 检查 WebSocket 是否收到事件
# 预期输出:
# {
#   "type": "task.completed",
#   "data": {"task_id": "daily-pool-refresh", "status": "success"},
#   "timestamp": "...",
#   "agent_id": "fin-agent"
# }

# 6. 单元测试
go test ./internal/events/... -v
```

---

## ✅ 验收标准

### Day 1: 权限系统

- [ ] `config/permissions.yaml` 配置文件完整
- [ ] `AuthManager` 实现并通过单元测试
- [ ] 所有 CLI 命令集成权限检查
- [ ] `memory-agent` 调用 `trading` 命令被拒绝
- [ ] `admin` 可以执行所有命令
- [ ] 单元测试 10/10 通过

### Day 2: Event Bus

- [ ] `EventBus` 实现并通过单元测试
- [ ] PostgreSQL NOTIFY/LISTEN 正常工作
- [ ] WebSocket 服务器正常启动 (端口 8080)
- [ ] WebSocket 能收到任务完成事件
- [ ] 事件过滤正常工作 (agent_id, filters)
- [ ] 集成测试通过 (端到端场景)

### 最终交付

- [ ] 代码编译无错误
- [ ] 所有单元测试通过
- [ ] 权限拒绝生效
- [ ] WebSocket 推送正常
- [ ] 文档完整 (WP-8-COMPLETION-REPORT.md)
- [ ] 准备合并到 main

---

## 📊 工作量估算

| 模块 | 代码行数 | 测试行数 | 预计耗时 |
|------|---------|---------|---------|
| AuthManager | ~300 | ~200 | 4h |
| CLI 中间件 | ~150 | ~100 | 2h |
| Event Bus | ~400 | ~300 | 5h |
| WebSocket 服务器 | ~200 | ~150 | 3h |
| 服务集成 | ~100 | - | 2h |
| **总计** | **~1,150** | **~750** | **16h** |

---

## 🚀 开始执行

准备好后告诉我：**"开始 WP-8"**

我会立即开始实现权限系统。
