# WP-12: Agent OS Scheduler HTTP API

> **优先级**: P0 - Critical  
> **工作量**: 1天  
> **状态**: 🔴 待执行  
> **依赖**: 无  
> **阻塞**: WP-13, WP-14, WP-15

---

## 1. 背景与目标

### 1.1 问题

Agent OS Scheduler 目前只有 **CLI 接口**，缺少 **HTTP API**，导致：

❌ agent-ts 无法通过 HTTP 注册任务  
❌ quantsys-v2 无法通过 HTTP 注册任务  
❌ Webhook 触发机制不可用  
❌ 无法实现统一调度架构  

### 1.2 目标

为 Agent OS Scheduler 添加完整的 HTTP API：

✅ 支持通过 HTTP 注册/查询/触发/删除任务  
✅ 支持 Webhook 回调机制  
✅ 与现有 CLI 功能对等  
✅ 为 agent-ts 和 v2 对接做好准备  

---

## 2. 核心工作

### 2.1 创建 Scheduler HTTP Handler

**新建文件**: `agent-os/internal/handlers/scheduler_handler.go`

```go
package handlers

import (
	"encoding/json"
	"net/http"

	"github.com/gorilla/mux"
	"github.com/google/uuid"
	"github.com/pi-investment/agent-os/internal/kernel/scheduler"
	"github.com/pi-investment/agent-os/pkg/types"
)

type SchedulerHandler struct {
	scheduler *scheduler.Scheduler
}

func NewSchedulerHandler(s *scheduler.Scheduler) *SchedulerHandler {
	return &SchedulerHandler{scheduler: s}
}

// RegisterRoutes 注册所有路由
func (h *SchedulerHandler) RegisterRoutes(r *mux.Router) {
	r.HandleFunc("/api/v1/scheduler/tasks", h.RegisterTask).Methods("POST")
	r.HandleFunc("/api/v1/scheduler/tasks", h.ListTasks).Methods("GET")
	r.HandleFunc("/api/v1/scheduler/tasks/{id}", h.GetTask).Methods("GET")
	r.HandleFunc("/api/v1/scheduler/tasks/{id}/trigger", h.TriggerTask).Methods("POST")
	r.HandleFunc("/api/v1/scheduler/tasks/{id}", h.DeleteTask).Methods("DELETE")
	r.HandleFunc("/api/v1/scheduler/tasks/{id}/runs", h.GetTaskRuns).Methods("GET")
}

// POST /api/v1/scheduler/tasks - 注册任务
func (h *SchedulerHandler) RegisterTask(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Name        string                 `json:"name"`
		Description string                 `json:"description"`
		Schedule    string                 `json:"schedule"`
		Command     string                 `json:"command"`
		WebhookURL  string                 `json:"webhook_url"`
		Enabled     bool                   `json:"enabled"`
		Owner       string                 `json:"owner"`
		Metadata    map[string]interface{} `json:"metadata"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	// 验证必填字段
	if req.Name == "" {
		http.Error(w, "name is required", http.StatusBadRequest)
		return
	}

	// 创建任务
	task := &types.Task{
		Name:        req.Name,
		Description: req.Description,
		Schedule:    req.Schedule,
		Command:     req.Command,
		WebhookURL:  req.WebhookURL,
		Enabled:     req.Enabled,
		CreatedBy:   req.Owner,
		Metadata:    req.Metadata,
	}

	if err := h.scheduler.RegisterTask(r.Context(), task); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(task)
}

// GET /api/v1/scheduler/tasks - 列出任务
func (h *SchedulerHandler) ListTasks(w http.ResponseWriter, r *http.Request) {
	enabledOnly := r.URL.Query().Get("enabled_only") == "true"
	owner := r.URL.Query().Get("owner")

	tasks, err := h.scheduler.ListTasks(r.Context(), enabledOnly, owner)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"tasks": tasks,
	})
}

// GET /api/v1/scheduler/tasks/{id} - 获取任务详情
func (h *SchedulerHandler) GetTask(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]

	taskID, err := uuid.Parse(id)
	if err != nil {
		http.Error(w, "invalid task ID", http.StatusBadRequest)
		return
	}

	task, err := h.scheduler.GetTask(r.Context(), taskID)
	if err != nil {
		http.Error(w, err.Error(), http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(task)
}

// POST /api/v1/scheduler/tasks/{id}/trigger - 手动触发任务
func (h *SchedulerHandler) TriggerTask(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]

	taskID, err := uuid.Parse(id)
	if err != nil {
		http.Error(w, "invalid task ID", http.StatusBadRequest)
		return
	}

	run, err := h.scheduler.TriggerTask(r.Context(), taskID)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(run)
}

// DELETE /api/v1/scheduler/tasks/{id} - 删除任务
func (h *SchedulerHandler) DeleteTask(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]

	taskID, err := uuid.Parse(id)
	if err != nil {
		http.Error(w, "invalid task ID", http.StatusBadRequest)
		return
	}

	if err := h.scheduler.DeleteTask(r.Context(), taskID); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"success": true,
		"message": "Task deleted successfully",
	})
}

// GET /api/v1/scheduler/tasks/{id}/runs - 获取任务执行历史
func (h *SchedulerHandler) GetTaskRuns(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]

	taskID, err := uuid.Parse(id)
	if err != nil {
		http.Error(w, "invalid task ID", http.StatusBadRequest)
		return
	}

	// 默认限制 20 条
	limit := 20
	if limitStr := r.URL.Query().Get("limit"); limitStr != "" {
		// parse limit...
	}

	runs, err := h.scheduler.GetTaskRuns(r.Context(), taskID, limit)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"runs": runs,
	})
}
```

---

### 2.2 修改 serve.go 集成 Scheduler

**修改文件**: `agent-os/internal/cmd/serve.go`

在第 99 行附近添加：

```go
// 创建 Scheduler 实例
schedulerSvc := scheduler.New(nil)

// 启动 Scheduler
if err := schedulerSvc.Start(ctx); err != nil {
	return fmt.Errorf("failed to start scheduler: %w", err)
}
defer schedulerSvc.Stop()

// 创建 Scheduler Handler
schedulerHandler := handlers.NewSchedulerHandler(schedulerSvc)
```

在第 104 行修改：

```go
// 修改前
server := api.NewHTTPServer(svc, skillHandler)

// 修改后
server := api.NewHTTPServer(svc, skillHandler, schedulerHandler)
```

---

### 2.3 修改 HTTP Server 注册路由

**修改文件**: `agent-os/internal/api/http_server.go`

修改 `HTTPServer` 结构体：

```go
type HTTPServer struct {
	notificationService *service.NotificationService
	skillHandler        *handlers.SkillHandler
	schedulerHandler    *handlers.SchedulerHandler  // 新增
	router              *mux.Router
	server              *http.Server
}
```

修改 `NewHTTPServer` 函数签名：

```go
func NewHTTPServer(
	notificationService *service.NotificationService,
	skillHandler *handlers.SkillHandler,
	schedulerHandler *handlers.SchedulerHandler,  // 新增
) *HTTPServer {
	s := &HTTPServer{
		notificationService: notificationService,
		skillHandler:        skillHandler,
		schedulerHandler:    schedulerHandler,  // 新增
		router:              mux.NewRouter(),
	}
	s.setupRoutes()
	return s
}
```

在 `setupRoutes` 函数中添加：

```go
func (s *HTTPServer) setupRoutes() {
	// ... 现有路由 ...
	
	// 注册 Scheduler 路由
	s.schedulerHandler.RegisterRoutes(s.router)
	
	// ... 其他路由 ...
}
```

---

### 2.4 添加 Webhook 触发机制

**修改文件**: `agent-os/internal/kernel/scheduler/executor.go`

找到任务执行的地方，添加 Webhook 调用逻辑：

```go
import (
	"bytes"
	"encoding/json"
	"net/http"
	"time"
)

func (e *Executor) executeTask(ctx context.Context, task *types.Task, run *types.TaskRun) error {
	// 如果配置了 webhook_url，调用 webhook
	if task.WebhookURL != "" {
		return e.executeViaWebhook(ctx, task, run)
	}
	
	// 否则执行 command（现有逻辑）
	return e.executeCommand(ctx, task, run)
}

func (e *Executor) executeViaWebhook(ctx context.Context, task *types.Task, run *types.TaskRun) error {
	// 构造 webhook payload
	payload := map[string]interface{}{
		"task_id":   task.ID.String(),
		"task_name": task.Name,
		"run_id":    run.ID.String(),
		"params":    task.Metadata,
	}
	
	payloadBytes, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("failed to marshal webhook payload: %w", err)
	}
	
	// 发送 HTTP POST 请求
	req, err := http.NewRequestWithContext(ctx, "POST", task.WebhookURL, bytes.NewBuffer(payloadBytes))
	if err != nil {
		return fmt.Errorf("failed to create webhook request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	
	// 设置超时
	client := &http.Client{
		Timeout: 30 * time.Second,
	}
	
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("webhook request failed: %w", err)
	}
	defer resp.Body.Close()
	
	// 检查响应状态
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return fmt.Errorf("webhook returned non-2xx status: %d", resp.StatusCode)
	}
	
	logger.Info("Webhook executed successfully",
		"task_id", task.ID,
		"task_name", task.Name,
		"webhook_url", task.WebhookURL,
		"status", resp.StatusCode)
	
	return nil
}
```

---

### 2.5 数据库 Schema 更新

**新建文件**: `agent-os/migrations/010_add_webhook_url.sql`

```sql
-- Migration: Add webhook_url to scheduler_tasks
-- Created: 2026-08-15
-- Purpose: Support webhook-based task execution

ALTER TABLE scheduler_tasks
ADD COLUMN webhook_url TEXT;

-- Create index for webhook tasks
CREATE INDEX idx_scheduler_tasks_webhook 
ON scheduler_tasks(webhook_url) 
WHERE webhook_url IS NOT NULL;

-- Add comment
COMMENT ON COLUMN scheduler_tasks.webhook_url IS 'HTTP webhook URL to call when task is triggered';
```

---

### 2.6 添加缺失的 Scheduler 方法

检查 `internal/kernel/scheduler/scheduler.go`，如果缺少以下方法，需要添加：

```go
// ListTasks 列出任务
func (s *Scheduler) ListTasks(ctx context.Context, enabledOnly bool, owner string) ([]*types.Task, error) {
	return s.taskRepo.List(ctx, enabledOnly)
}

// GetTask 获取单个任务
func (s *Scheduler) GetTask(ctx context.Context, taskID uuid.UUID) (*types.Task, error) {
	return s.taskRepo.GetByID(ctx, taskID)
}

// GetTaskRuns 获取任务执行历史
func (s *Scheduler) GetTaskRuns(ctx context.Context, taskID uuid.UUID, limit int) ([]*types.TaskRun, error) {
	return s.taskRunRepo.ListByTaskID(ctx, taskID, limit)
}
```

---

### 2.7 更新 types.Task 结构

**修改文件**: `agent-os/pkg/types/scheduler.go`

确保 `Task` 结构体包含 `WebhookURL` 字段：

```go
type Task struct {
	ID          uuid.UUID              `json:"id"`
	Name        string                 `json:"name"`
	Description string                 `json:"description"`
	Schedule    string                 `json:"schedule"`
	Command     string                 `json:"command"`
	WebhookURL  string                 `json:"webhook_url"`  // 新增
	Enabled     bool                   `json:"enabled"`
	CreatedBy   string                 `json:"created_by"`
	CreatedAt   time.Time              `json:"created_at"`
	UpdatedAt   time.Time              `json:"updated_at"`
	Metadata    map[string]interface{} `json:"metadata"`
}
```

---

## 3. 验收标准

### 3.1 启动测试

```bash
# 1. 应用数据库迁移
psql -d quant_investment -f migrations/010_add_webhook_url.sql

# 2. 编译 Agent OS
cd agent-os
go build -o agent-os ./cmd/agent-os

# 3. 启动 HTTP 服务器
./agent-os serve --port 8080

# 应该看到输出：
# 🚀 Agent OS API Server starting on http://0.0.0.0:8080
# 📚 API endpoints:
#    ...
#    POST   /api/v1/scheduler/tasks
#    GET    /api/v1/scheduler/tasks
#    ...
```

---

### 3.2 API 功能测试

```bash
# 1. 注册任务
curl -X POST http://localhost:8080/api/v1/scheduler/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test_task",
    "description": "测试任务",
    "schedule": "*/5 * * * *",
    "webhook_url": "http://localhost:3002/api/webhook/trigger",
    "enabled": true,
    "owner": "test",
    "metadata": {
      "skill_id": "test-skill-id"
    }
  }'

# 预期输出：201 Created + 任务 JSON

# 2. 列出任务
curl http://localhost:8080/api/v1/scheduler/tasks

# 预期输出：任务列表

# 3. 获取任务详情
curl http://localhost:8080/api/v1/scheduler/tasks/{task_id}

# 预期输出：任务详情

# 4. 手动触发任务
curl -X POST http://localhost:8080/api/v1/scheduler/tasks/{task_id}/trigger

# 预期输出：TaskRun JSON

# 5. 查看执行历史
curl http://localhost:8080/api/v1/scheduler/tasks/{task_id}/runs

# 预期输出：执行历史列表

# 6. 删除任务
curl -X DELETE http://localhost:8080/api/v1/scheduler/tasks/{task_id}

# 预期输出：{"success": true, "message": "Task deleted successfully"}
```

---

### 3.3 Webhook 测试

```bash
# 1. 启动一个简单的 webhook 接收服务器
python3 -c "
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length)
        print('Received webhook:', body.decode())
        
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'success': True}).encode())

HTTPServer(('', 3002), Handler).serve_forever()
" &

# 2. 注册一个 webhook 任务
curl -X POST http://localhost:8080/api/v1/scheduler/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "webhook_test",
    "schedule": "*/1 * * * *",
    "webhook_url": "http://localhost:3002/api/webhook/trigger",
    "enabled": true
  }'

# 3. 等待 1 分钟，观察 webhook 接收服务器是否收到请求
# 预期：每分钟收到一次 webhook 调用
```

---

### 3.4 单元测试（可选）

**新建文件**: `agent-os/internal/handlers/scheduler_handler_test.go`

```go
package handlers

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gorilla/mux"
	"github.com/stretchr/testify/assert"
)

func TestSchedulerHandler_RegisterTask(t *testing.T) {
	// TODO: 实现测试
	// 1. 创建 mock scheduler
	// 2. 创建 handler
	// 3. 发送 POST 请求
	// 4. 验证响应状态码和内容
}

func TestSchedulerHandler_ListTasks(t *testing.T) {
	// TODO: 实现测试
}

// ... 其他测试
```

---

## 4. 交付物清单

- [ ] `internal/handlers/scheduler_handler.go` (新建)
- [ ] `internal/handlers/scheduler_handler_test.go` (新建，可选)
- [ ] `internal/cmd/serve.go` (修改)
- [ ] `internal/api/http_server.go` (修改)
- [ ] `internal/kernel/scheduler/executor.go` (修改)
- [ ] `internal/kernel/scheduler/scheduler.go` (可能需要添加方法)
- [ ] `pkg/types/scheduler.go` (修改)
- [ ] `migrations/010_add_webhook_url.sql` (新建)
- [ ] API 测试脚本 (新建，可选)

---

## 5. 注意事项

### 5.1 代码风格

- 遵循现有代码风格
- 使用 Go 标准错误处理
- 添加适当的日志记录

### 5.2 错误处理

- 参数验证要完整
- 错误信息要清晰
- HTTP 状态码要正确

### 5.3 兼容性

- 保持与 CLI 功能对等
- Request/Response 格式与 CLI 一致
- 不破坏现有功能

### 5.4 安全性

- Webhook URL 验证
- 超时控制
- 错误日志脱敏

---

## 6. 常见问题

### Q1: Scheduler 实例如何管理生命周期？

在 `serve.go` 中：
- Start: 在 HTTP 服务器启动前调用
- Stop: 在 HTTP 服务器关闭时调用（defer）

### Q2: Webhook 调用失败如何处理？

- 记录错误日志
- 更新 TaskRun 状态为 failed
- 不影响其他任务执行

### Q3: 如何测试 Webhook？

使用简单的 HTTP 服务器或 `nc` 命令监听端口，观察是否收到请求。

---

## 7. 完成后通知

完成后请通知主窗口进行 Code Review，提供：
- 修改的文件列表
- 测试结果（API 测试 + Webhook 测试）
- 遇到的问题和解决方案

---

**任务文档版本**: v1.0  
**创建时间**: 2026-08-15 23:30  
**创建人**: Claude (Opus 5) - 主窗口
