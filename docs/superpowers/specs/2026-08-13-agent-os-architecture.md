# Agent OS 架构设计详细规范

> **创建时间**: 2026-08-13  
> **状态**: Draft  
> **目标**: 从 OS 本质出发，构建 AI Agent 的运行时操作系统

---

## 1. 技术栈详细设计

### 1.1 内核层：Go

#### 为什么选 Go？

**性能维度**：
- 并发原语（goroutine + channel）天然适合调度器实现
- GC 延迟低（Go 1.20+ sub-millisecond pause time），适合实时调度
- 单一二进制部署，无 Python 依赖地狱

**生态维度**：
- **Web 框架**: Gin（高性能 HTTP 路由）/ Fiber（类 Express 语法）
- **数据库**: sqlx（轻量 SQL）/ gorm（ORM）/ pgx（原生 PostgreSQL 驱动）
- **消息队列**: Redis Go 客户端（go-redis）/ NATS（云原生消息系统）
- **配置管理**: Viper（支持 YAML/ENV/etcd）
- **日志**: Zap（结构化日志，性能极高）/ Logrus
- **监控**: Prometheus client / OpenTelemetry

**工具链维度**：
- 交叉编译：`GOOS=linux GOARCH=amd64 go build` 一键生成 Linux 二进制
- 测试：内置 `go test`，benchmark 原生支持
- 依赖管理：go modules（无需额外工具）

#### Go 项目结构（Clean Architecture）

```
agent-os/
├── cmd/
│   ├── agent-osd/          # OS daemon 主进程
│   │   └── main.go
│   └── agent-os-ctl/       # CLI 工具
│       └── main.go
├── internal/               # 内部包（不对外暴露）
│   ├── kernel/            # 内核层
│   │   ├── scheduler/     # 调度器
│   │   │   ├── scheduler.go
│   │   │   ├── dag.go     # DAG 依赖解析
│   │   │   ├── queue.go   # 任务队列
│   │   │   └── executor.go
│   │   ├── resource/      # 资源管理器
│   │   │   ├── quota.go   # Token/Memory 配额
│   │   │   ├── namespace.go
│   │   │   └── limiter.go # Rate limiter
│   │   ├── memory/        # Memory System
│   │   │   ├── store.go
│   │   │   ├── index.go   # BM25 + Vector 索引
│   │   │   └── gc.go      # 垃圾回收
│   │   ├── ipc/           # 进程间通信
│   │   │   ├── eventbus.go
│   │   │   └── pubsub.go
│   │   └── security/      # 权限管理
│   │       ├── auth.go
│   │       └── capability.go
│   ├── drivers/           # 设备驱动层（调用 Python）
│   │   ├── market/        # 市场数据驱动
│   │   ├── trading/       # 交易驱动
│   │   └── grpc/          # gRPC client 调用 Python 驱动
│   ├── api/               # 系统调用接口
│   │   ├── syscall/       # syscall handlers
│   │   ├── middleware/    # 认证、限流、日志
│   │   └── router.go
│   └── storage/           # 存储层抽象
│       ├── postgres/
│       ├── redis/
│       └── repository/    # Repository 模式
├── pkg/                   # 公开包（可被外部引用）
│   ├── types/             # 核心类型定义
│   │   ├── task.go
│   │   ├── memory.go
│   │   └── agent.go
│   └── client/            # Go client SDK
│       └── client.go
├── drivers/               # Python 设备驱动（独立进程）
│   ├── market_driver/
│   │   ├── main.py
│   │   ├── akshare_adapter.py
│   │   └── proto/         # gRPC proto
│   └── trading_driver/
│       └── ...
├── configs/
│   ├── agent-os.yaml      # OS 配置
│   └── agents.yaml        # Agent 定义（角色、配额）
├── scripts/
│   ├── build.sh
│   └── deploy.sh
├── go.mod
├── go.sum
└── README.md
```

#### 核心依赖（go.mod）

```go
module github.com/pi-investment/agent-os

go 1.21

require (
    // Web 框架
    github.com/gin-gonic/gin v1.9.1
    
    // 数据库
    github.com/jackc/pgx/v5 v5.4.3
    github.com/jmoiron/sqlx v1.3.5
    
    // Redis
    github.com/redis/go-redis/v9 v9.2.1
    
    // gRPC（调用 Python 驱动）
    google.golang.org/grpc v1.58.2
    google.golang.org/protobuf v1.31.0
    
    // 配置管理
    github.com/spf13/viper v1.17.0
    
    // 日志
    go.uber.org/zap v1.26.0
    
    // 监控
    github.com/prometheus/client_golang v1.17.0
    
    // 工具库
    github.com/google/uuid v1.3.1
    github.com/robfig/cron/v3 v3.0.1  // Cron 表达式解析
)
```

---

### 1.2 设备驱动层：Python

#### 为什么保留 Python？

**金融数据源生态**：
- AKShare、Tushare、yfinance 只有 Python SDK
- 重写适配器成本高且容易出 bug

**架构设计**：
- Python 驱动作为**独立进程**运行
- 通过 **gRPC** 与 Go 内核通信
- 驱动崩溃不影响 OS 内核

#### Python 驱动架构

```
drivers/
├── market_driver/          # 市场数据驱动
│   ├── main.py            # gRPC server 入口
│   ├── proto/
│   │   ├── market.proto   # gRPC 接口定义
│   │   └── market_pb2_grpc.py
│   ├── adapters/
│   │   ├── akshare_adapter.py
│   │   ├── tushare_adapter.py
│   │   └── yahoo_adapter.py
│   ├── cache.py           # Redis 缓存层
│   └── requirements.txt
│
└── trading_driver/         # 交易驱动
    ├── main.py
    ├── proto/
    │   └── trading.proto
    ├── brokers/
    │   ├── mock_broker.py  # 虚拟盘
    │   └── futu_broker.py  # 富途 API
    └── requirements.txt
```

#### gRPC 接口定义示例

```protobuf
// drivers/market_driver/proto/market.proto
syntax = "proto3";

package market;

service MarketDataService {
  // 获取实时行情
  rpc GetQuote(QuoteRequest) returns (QuoteResponse);
  
  // 获取 K 线数据
  rpc GetKline(KlineRequest) returns (KlineResponse);
  
  // 流式订阅实时数据
  rpc SubscribeRealtime(SubscribeRequest) returns (stream TickData);
}

message QuoteRequest {
  string symbol = 1;        // 股票代码
  string market = 2;        // sh/sz/hk/us
}

message QuoteResponse {
  string symbol = 1;
  double price = 2;
  double change_pct = 3;
  int64 volume = 4;
  int64 timestamp = 5;
}

message KlineRequest {
  string symbol = 1;
  string period = 2;        // 1d/1h/5m
  string start_date = 3;
  string end_date = 4;
}

message KlineResponse {
  repeated Kline data = 1;
}

message Kline {
  int64 timestamp = 1;
  double open = 2;
  double high = 3;
  double low = 4;
  double close = 5;
  int64 volume = 6;
}
```

#### Go 侧调用 Python 驱动

```go
// internal/drivers/market/client.go
package market

import (
    "context"
    "google.golang.org/grpc"
    pb "agent-os/drivers/market_driver/proto"
)

type MarketDriver struct {
    conn   *grpc.ClientConn
    client pb.MarketDataServiceClient
}

func NewMarketDriver(addr string) (*MarketDriver, error) {
    conn, err := grpc.Dial(addr, grpc.WithInsecure())
    if err != nil {
        return nil, err
    }
    return &MarketDriver{
        conn:   conn,
        client: pb.NewMarketDataServiceClient(conn),
    }, nil
}

func (d *MarketDriver) GetQuote(ctx context.Context, symbol string) (*Quote, error) {
    resp, err := d.client.GetQuote(ctx, &pb.QuoteRequest{
        Symbol: symbol,
        Market: "sh",
    })
    if err != nil {
        return nil, err
    }
    return &Quote{
        Symbol:    resp.Symbol,
        Price:     resp.Price,
        ChangePct: resp.ChangePct,
        Volume:    resp.Volume,
    }, nil
}
```

#### 驱动进程管理

```go
// internal/drivers/manager.go
package drivers

import (
    "os/exec"
    "syscall"
)

type DriverManager struct {
    processes map[string]*exec.Cmd
}

func (m *DriverManager) StartDriver(name string, scriptPath string) error {
    cmd := exec.Command("python3", scriptPath)
    cmd.SysProcAttr = &syscall.SysProcAttr{
        Setpgid: true,  // 独立进程组，崩溃不影响 OS
    }
    
    if err := cmd.Start(); err != nil {
        return err
    }
    
    m.processes[name] = cmd
    
    // 监控进程健康
    go m.monitorDriver(name, cmd)
    
    return nil
}

func (m *DriverManager) monitorDriver(name string, cmd *exec.Cmd) {
    cmd.Wait()  // 等待进程退出
    log.Error("Driver crashed", zap.String("name", name))
    
    // 自动重启
    time.Sleep(5 * time.Second)
    m.StartDriver(name, ...)
}
```

---

### 1.3 未来优化：Rust 重写性能热点

#### 什么时候考虑 Rust？

**场景 1：调度器性能瓶颈**
- 症状：任务队列处理延迟 > 100ms
- 原因：Go GC 在高并发场景下 pause time 累积
- 方案：Rust 实现调度器核心，通过 FFI 暴露给 Go

**场景 2：Memory 索引引擎**
- 症状：BM25 + Vector 检索延迟 > 500ms（召回 1000 条记忆）
- 原因：Go 的向量计算库性能不如 Rust
- 方案：Rust 实现混合检索引擎（调用 tantivy + hnswlib），通过 gRPC 暴露

**场景 3：实时流处理**
- 症状：实时信号监控（每秒 1000+ tick）时 Go 出现 GC 压力
- 方案：Rust 实现流处理引擎（类似 Apache Flink）

#### Rust-Go 互操作方案

**方案 A：FFI（C ABI）**
```rust
// rust/scheduler/src/lib.rs
#[no_mangle]
pub extern "C" fn schedule_task(task_id: u64) -> i32 {
    // Rust 调度逻辑
    0
}
```

```go
// internal/kernel/scheduler/ffi.go
// #cgo LDFLAGS: -L./rust/scheduler/target/release -lscheduler
// #include "scheduler.h"
import "C"

func ScheduleTask(taskID uint64) error {
    ret := C.schedule_task(C.ulong(taskID))
    if ret != 0 {
        return errors.New("schedule failed")
    }
    return nil
}
```

**方案 B：gRPC（推荐）**
- Rust 实现独立服务，Go 通过 gRPC 调用
- 解耦更好，Rust 服务可以独立升级

---

## 2. MVP 核心模块详细设计

### 2.1 统一调度器（Scheduler）

#### 2.1.1 核心数据结构

```go
// pkg/types/task.go
package types

import "time"

// TaskDefinition 任务定义（持久化到 DB）
type TaskDefinition struct {
    ID          uint64    `db:"id"`
    Name        string    `db:"name"`          // daily_recall_audit
    Owner       string    `db:"owner"`         // memory-agent
    TaskType    TaskType  `db:"task_type"`     // AgentTurn / PythonService
    CronExpr    string    `db:"cron_expr"`     // 0 19 * * *
    Enabled     bool      `db:"enabled"`
    
    // 执行控制
    TimeoutSec  int       `db:"timeout_sec"`   // 1800
    MaxRetries  int       `db:"max_retries"`   // 3
    RetryBackoff int      `db:"retry_backoff"` // 60
    MaxConcurrent int     `db:"max_concurrent"` // 1
    
    // 依赖编排
    DependsOn   []string  `db:"depends_on"`    // [market_data_sync, pool_scan]
    
    // Agent 任务字段
    AgentKind   string    `db:"agent_kind"`    // memory / evolution / fin
    AgentPrompt string    `db:"agent_prompt"`  // 执行提示词
    
    // Python 任务字段
    ServiceName string    `db:"service_name"`  // pool_scan_scheduler
    ServiceMethod string  `db:"service_method"` // run_scan
    
    CreatedAt   time.Time `db:"created_at"`
    UpdatedAt   time.Time `db:"updated_at"`
}

type TaskType string
const (
    TaskTypeAgentTurn     TaskType = "agent_turn"
    TaskTypePythonService TaskType = "python_service"
)

// TaskExecution 执行记录（每次运行一条）
type TaskExecution struct {
    ID           uint64        `db:"id"`
    TaskID       uint64        `db:"task_id"`
    TriggerType  TriggerType   `db:"trigger_type"`  // cron / manual / dependency
    TriggeredBy  string        `db:"triggered_by"`  // system / user@fin-agent
    
    StartedAt    time.Time     `db:"started_at"`
    EndedAt      *time.Time    `db:"ended_at"`
    Status       ExecutionStatus `db:"status"`      // running / success / failed / timeout
    
    // 性能指标
    DurationSec  *int          `db:"duration_sec"`
    TokenConsumed *int         `db:"token_consumed"` // agent 任务有效
    
    // 错误信息
    ErrorMessage *string       `db:"error_message"`
    RetryCount   int           `db:"retry_count"`
    
    // 日志路径
    LogPath      string        `db:"log_path"`
}

type TriggerType string
const (
    TriggerTypeCron       TriggerType = "cron"
    TriggerTypeManual     TriggerType = "manual"
    TriggerTypeDependency TriggerType = "dependency"
)

type ExecutionStatus string
const (
    StatusRunning ExecutionStatus = "running"
    StatusSuccess ExecutionStatus = "success"
    StatusFailed  ExecutionStatus = "failed"
    StatusTimeout ExecutionStatus = "timeout"
)
```

#### 2.1.2 调度器核心逻辑

```go
// internal/kernel/scheduler/scheduler.go
package scheduler

import (
    "context"
    "sync"
    "time"
    
    "agent-os/pkg/types"
    "github.com/robfig/cron/v3"
    "go.uber.org/zap"
)

type Scheduler struct {
    cron        *cron.Cron
    taskRepo    TaskRepository
    execRepo    ExecutionRepository
    executor    *Executor
    resourceMgr *resource.Manager
    
    runningTasks sync.Map  // taskID -> *TaskExecution（正在运行的任务）
    logger      *zap.Logger
}

func NewScheduler(
    taskRepo TaskRepository,
    execRepo ExecutionRepository,
    executor *Executor,
    resourceMgr *resource.Manager,
    logger *zap.Logger,
) *Scheduler {
    return &Scheduler{
        cron:        cron.New(),
        taskRepo:    taskRepo,
        execRepo:    execRepo,
        executor:    executor,
        resourceMgr: resourceMgr,
        logger:      logger,
    }
}

// Start 启动调度器
func (s *Scheduler) Start(ctx context.Context) error {
    // 从数据库加载所有 enabled 任务
    tasks, err := s.taskRepo.ListEnabled(ctx)
    if err != nil {
        return err
    }
    
    // 注册到 cron
    for _, task := range tasks {
        s.registerTask(task)
    }
    
    s.cron.Start()
    s.logger.Info("Scheduler started", zap.Int("tasks", len(tasks)))
    
    return nil
}

// registerTask 注册任务到 cron
func (s *Scheduler) registerTask(task *types.TaskDefinition) {
    _, err := s.cron.AddFunc(task.CronExpr, func() {
        s.triggerTask(context.Background(), task.ID, types.TriggerTypeCron, "system")
    })
    if err != nil {
        s.logger.Error("Failed to register task", 
            zap.String("task", task.Name), 
            zap.Error(err))
    }
}

// triggerTask 触发任务（核心调度逻辑）
func (s *Scheduler) triggerTask(
    ctx context.Context, 
    taskID uint64, 
    triggerType types.TriggerType,
    triggeredBy string,
) error {
    task, err := s.taskRepo.Get(ctx, taskID)
    if err != nil {
        return err
    }
    
    // 1. 检查依赖（DAG）
    if !s.checkDependencies(ctx, task) {
        s.logger.Warn("Task dependencies not met", zap.String("task", task.Name))
        return ErrDependenciesNotMet
    }
    
    // 2. 检查并发限制
    if !s.checkConcurrency(task) {
        s.logger.Warn("Task concurrency limit reached", zap.String("task", task.Name))
        return ErrConcurrencyLimit
    }
    
    // 3. 检查资源配额（Token）
    if !s.resourceMgr.CheckQuota(ctx, task.Owner) {
        s.logger.Warn("Agent quota exceeded", zap.String("agent", task.Owner))
        return ErrQuotaExceeded
    }
    
    // 4. 创建执行记录
    exec := &types.TaskExecution{
        TaskID:      taskID,
        TriggerType: triggerType,
        TriggeredBy: triggeredBy,
        StartedAt:   time.Now(),
        Status:      types.StatusRunning,
    }
    execID, err := s.execRepo.Create(ctx, exec)
    if err != nil {
        return err
    }
    exec.ID = execID
    
    // 5. 异步执行任务
    go s.executeTask(ctx, task, exec)
    
    return nil
}

// checkDependencies 检查 DAG 依赖
func (s *Scheduler) checkDependencies(ctx context.Context, task *types.TaskDefinition) bool {
    if len(task.DependsOn) == 0 {
        return true
    }
    
    for _, depName := range task.DependsOn {
        depTask, err := s.taskRepo.GetByName(ctx, depName)
        if err != nil {
            s.logger.Error("Dependency task not found", zap.String("dep", depName))
            return false
        }
        
        // 检查依赖任务最近一次执行是否成功
        lastExec, err := s.execRepo.GetLastExecution(ctx, depTask.ID)
        if err != nil || lastExec.Status != types.StatusSuccess {
            return false
        }
        
        // 检查依赖任务是否在合理时间窗口内完成（避免使用过期结果）
        if time.Since(lastExec.EndedAt) > 24*time.Hour {
            return false
        }
    }
    
    return true
}

// checkConcurrency 检查并发限制
func (s *Scheduler) checkConcurrency(task *types.TaskDefinition) bool {
    count := 0
    s.runningTasks.Range(func(key, value interface{}) bool {
        exec := value.(*types.TaskExecution)
        if exec.TaskID == task.ID {
            count++
        }
        return true
    })
    
    return count < task.MaxConcurrent
}

// executeTask 执行任务（带超时、重试）
func (s *Scheduler) executeTask(ctx context.Context, task *types.TaskDefinition, exec *types.TaskExecution) {
    s.runningTasks.Store(exec.ID, exec)
    defer s.runningTasks.Delete(exec.ID)
    
    // 超时控制
    ctx, cancel := context.WithTimeout(ctx, time.Duration(task.TimeoutSec)*time.Second)
    defer cancel()
    
    // 执行任务
    err := s.executor.Execute(ctx, task, exec)
    
    // 更新执行记录
    now := time.Now()
    exec.EndedAt = &now
    duration := int(now.Sub(exec.StartedAt).Seconds())
    exec.DurationSec = &duration
    
    if err != nil {
        if ctx.Err() == context.DeadlineExceeded {
            exec.Status = types.StatusTimeout
        } else {
            exec.Status = types.StatusFailed
            errMsg := err.Error()
            exec.ErrorMessage = &errMsg
        }
        
        // 重试逻辑
        if exec.RetryCount < task.MaxRetries {
            s.logger.Info("Retrying task", 
                zap.String("task", task.Name), 
                zap.Int("retry", exec.RetryCount+1))
            
            exec.RetryCount++
            time.Sleep(time.Duration(task.RetryBackoff) * time.Second)
            s.executeTask(ctx, task, exec)
            return
        }
    } else {
        exec.Status = types.StatusSuccess
    }
    
    s.execRepo.Update(ctx, exec)
    s.logger.Info("Task completed", 
        zap.String("task", task.Name),
        zap.String("status", string(exec.Status)),
        zap.Int("duration", duration))
}
```

#### 2.1.3 DAG 依赖解析

```go
// internal/kernel/scheduler/dag.go
package scheduler

import (
    "context"
    "fmt"
)

type DAG struct {
    tasks map[string]*types.TaskDefinition
    edges map[string][]string  // taskName -> dependents
}

func NewDAG(tasks []*types.TaskDefinition) (*DAG, error) {
    dag := &DAG{
        tasks: make(map[string]*types.TaskDefinition),
        edges: make(map[string][]string),
    }
    
    for _, task := range tasks {
        dag.tasks[task.Name] = task
    }
    
    // 构建依赖图
    for _, task := range tasks {
        for _, dep := range task.DependsOn {
            dag.edges[dep] = append(dag.edges[dep], task.Name)
        }
    }
    
    // 检测循环依赖
    if dag.hasCycle() {
        return nil, fmt.Errorf("circular dependency detected")
    }
    
    return dag, nil
}

// hasCycle 检测循环依赖（DFS）
func (d *DAG) hasCycle() bool {
    visited := make(map[string]bool)
    recStack := make(map[string]bool)
    
    for taskName := range d.tasks {
        if d.hasCycleUtil(taskName, visited, recStack) {
            return true
        }
    }
    
    return false
}

func (d *DAG) hasCycleUtil(taskName string, visited, recStack map[string]bool) bool {
    visited[taskName] = true
    recStack[taskName] = true
    
    for _, dependent := range d.edges[taskName] {
        if !visited[dependent] {
            if d.hasCycleUtil(dependent, visited, recStack) {
                return true
            }
        } else if recStack[dependent] {
            return true
        }
    }
    
    recStack[taskName] = false
    return false
}

// GetExecutionOrder 返回拓扑排序（任务执行顺序）
func (d *DAG) GetExecutionOrder() ([]string, error) {
    inDegree := make(map[string]int)
    
    // 计算入度
    for taskName := range d.tasks {
        inDegree[taskName] = len(d.tasks[taskName].DependsOn)
    }
    
    // Kahn 算法
    queue := []string{}
    for taskName, degree := range inDegree {
        if degree == 0 {
            queue = append(queue, taskName)
        }
    }
    
    result := []string{}
    for len(queue) > 0 {
        taskName := queue[0]
        queue = queue[1:]
        result = append(result, taskName)
        
        for _, dependent := range d.edges[taskName] {
            inDegree[dependent]--
            if inDegree[dependent] == 0 {
                queue = append(queue, dependent)
            }
        }
    }
    
    if len(result) != len(d.tasks) {
        return nil, fmt.Errorf("cycle detected")
    }
    
    return result, nil
}
```

---

### 2.2 资源管理器（Resource Manager）

#### 2.2.1 配额管理

```go
// internal/kernel/resource/quota.go
package resource

import (
    "context"
    "sync"
    "time"
)

type AgentQuota struct {
    AgentID       string
    TokenPerDay   int   // 每天 token 配额
    MemorySizeMB  int   // 记忆空间配额（MB）
    Priority      int   // 优先级（1-10）
}

type QuotaUsage struct {
    TokenUsed     int
    MemoryUsedMB  int
    LastResetAt   time.Time
}

type Manager struct {
    quotas map[string]*AgentQuota  // agentID -> quota
    usage  map[string]*QuotaUsage  // agentID -> usage
    mu     sync.RWMutex
}

func NewManager() *Manager {
    return &Manager{
        quotas: make(map[string]*AgentQuota),
        usage:  make(map[string]*QuotaUsage),
    }
}

// LoadQuotas 从配置文件加载配额
func (m *Manager) LoadQuotas(quotas []*AgentQuota) {
    m.mu.Lock()
    defer m.mu.Unlock()
    
    for _, quota := range quotas {
        m.quotas[quota.AgentID] = quota
        m.usage[quota.AgentID] = &QuotaUsage{
            LastResetAt: time.Now(),
        }
    }
}

// CheckQuota 检查配额是否足够
func (m *Manager) CheckQuota(ctx context.Context, agentID string) bool {
    m.mu.RLock()
    defer m.mu.RUnlock()
    
    quota, ok := m.quotas[agentID]
    if !ok {
        return false  // 未定义配额的 agent 拒绝
    }
    
    usage := m.usage[agentID]
    
    // 检查是否需要重置（每日凌晨 0 点）
    now := time.Now()
    if now.Sub(usage.LastResetAt) > 24*time.Hour {
        m.mu.RUnlock()
        m.mu.Lock()
        m.resetQuota(agentID)
        m.mu.Unlock()
        m.mu.RLock()
    }
    
    return usage.TokenUsed < quota.TokenPerDay
}

// ConsumeToken 消费 token（任务完成后调用）
func (m *Manager) ConsumeToken(agentID string, tokens int) {
    m.mu.Lock()
    defer m.mu.Unlock()
    
    if usage, ok := m.usage[agentID]; ok {
        usage.TokenUsed += tokens
    }
}

// ConsumeMemory 消费记忆空间
func (m *Manager) ConsumeMemory(agentID string, sizeMB int) error {
    m.mu.Lock()
    defer m.mu.Unlock()
    
    quota := m.quotas[agentID]
    usage := m.usage[agentID]
    
    if usage.MemoryUsedMB+sizeMB > quota.MemorySizeMB {
        return ErrQuotaExceeded
    }
    
    usage.MemoryUsedMB += sizeMB
    return nil
}

// GetQuota 查询配额信息
func (m *Manager) GetQuota(agentID string) (*AgentQuota, *QuotaUsage, error) {
    m.mu.RLock()
    defer m.mu.RUnlock()
    
    quota, ok := m.quotas[agentID]
    if !ok {
        return nil, nil, ErrQuotaNotFound
    }
    
    usage := m.usage[agentID]
    return quota, usage, nil
}

func (m *Manager) resetQuota(agentID string) {
    m.usage[agentID] = &QuotaUsage{
        LastResetAt: time.Now(),
    }
}
```

#### 2.2.2 命名空间隔离

```go
// internal/kernel/resource/namespace.go
package resource

import (
    "fmt"
    "strings"
)

type Namespace struct {
    AgentID string
    Path    string  // /memory/fin-agent/decisions/...
}

func NewNamespace(agentID string) *Namespace {
    return &Namespace{
        AgentID: agentID,
        Path:    fmt.Sprintf("/memory/%s", agentID),
    }
}

// ResolvePath 解析路径（确保在命名空间内）
func (ns *Namespace) ResolvePath(userPath string) (string, error) {
    fullPath := fmt.Sprintf("%s/%s", ns.Path, strings.TrimPrefix(userPath, "/"))
    
    // 防止路径穿越攻击
    if !strings.HasPrefix(fullPath, ns.Path) {
        return "", fmt.Errorf("path outside namespace")
    }
    
    return fullPath, nil
}

// CheckPermission 检查权限
func (ns *Namespace) CheckPermission(targetPath string, operation string) bool {
    // fin-agent 可以读 memory-agent 的记忆（复盘需要）
    if ns.AgentID == "fin-agent" && operation == "read" {
        return true
    }
    
    // 其他 agent 只能访问自己的命名空间
    return strings.HasPrefix(targetPath, ns.Path)
}
```

---

### 2.3 系统调用接口（Syscall API）

#### 2.3.1 API 设计原则

**统一前缀**：所有系统调用走 `/syscall/*` 路径
**RESTful 风格**：但从 OS 视角命名（`memory.write` 而非 `/memories`）
**gRPC 备选**：未来高性能场景可以提供 gRPC 接口

#### 2.3.2 路由定义

```go
// internal/api/router.go
package api

import (
    "agent-os/internal/api/syscall"
    "agent-os/internal/api/middleware"
    "github.com/gin-gonic/gin"
)

func NewRouter(
    schedulerHandler *syscall.SchedulerHandler,
    memoryHandler *syscall.MemoryHandler,
    resourceHandler *syscall.ResourceHandler,
) *gin.Engine {
    r := gin.Default()
    
    // 全局中间件
    r.Use(middleware.Logger())
    r.Use(middleware.Auth())         // 验证 agent 身份
    r.Use(middleware.RateLimit())    // 限流
    
    // Syscall API
    syscallGroup := r.Group("/syscall")
    {
        // Scheduler 系统调用
        scheduler := syscallGroup.Group("/scheduler")
        {
            scheduler.POST("/register", schedulerHandler.RegisterTask)
            scheduler.GET("/tasks", schedulerHandler.ListTasks)
            scheduler.GET("/tasks/:id", schedulerHandler.GetTask)
            scheduler.POST("/tasks/:id/trigger", schedulerHandler.TriggerTask)
            scheduler.GET("/executions", schedulerHandler.ListExecutions)
            scheduler.GET("/executions/:id", schedulerHandler.GetExecution)
        }
        
        // Memory 系统调用
        memory := syscallGroup.Group("/memory")
        {
            memory.POST("/write", memoryHandler.Write)
            memory.POST("/search", memoryHandler.Search)
            memory.GET("/query", memoryHandler.Query)
            memory.POST("/gc", memoryHandler.GC)
        }
        
        // Resource 系统调用
        resource := syscallGroup.Group("/resource")
        {
            resource.GET("/quota", resourceHandler.GetQuota)
            resource.POST("/quota/consume", resourceHandler.ConsumeQuota)
        }
        
        // Event 系统调用（IPC）
        event := syscallGroup.Group("/event")
        {
            event.POST("/publish", nil)   // TODO
            event.GET("/subscribe", nil)  // WebSocket
        }
    }
    
    // Health & Metrics
    r.GET("/health", func(c *gin.Context) {
        c.JSON(200, gin.H{"status": "ok"})
    })
    r.GET("/metrics", gin.WrapH(promhttp.Handler()))
    
    return r
}
```

#### 2.3.3 Scheduler Syscall Handler

```go
// internal/api/syscall/scheduler.go
package syscall

import (
    "net/http"
    "strconv"
    
    "agent-os/internal/kernel/scheduler"
    "agent-os/pkg/types"
    "github.com/gin-gonic/gin"
)

type SchedulerHandler struct {
    scheduler *scheduler.Scheduler
}

// RegisterTask syscall: scheduler.register
func (h *SchedulerHandler) RegisterTask(c *gin.Context) {
    var req types.TaskDefinition
    if err := c.ShouldBindJSON(&req); err != nil {
        c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
        return
    }
    
    // 从 middleware 获取 agent 身份
    agentID := c.GetString("agent_id")
    req.Owner = agentID
    
    taskID, err := h.scheduler.RegisterTask(c.Request.Context(), &req)
    if err != nil {
        c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
        return
    }
    
    c.JSON(http.StatusOK, gin.H{
        "task_id": taskID,
        "message": "task registered",
    })
}

// ListTasks syscall: scheduler.tasks
func (h *SchedulerHandler) ListTasks(c *gin.Context) {
    agentID := c.Query("owner")  // 可选过滤
    
    tasks, err := h.scheduler.ListTasks(c.Request.Context(), agentID)
    if err != nil {
        c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
        return
    }
    
    c.JSON(http.StatusOK, gin.H{
        "tasks": tasks,
        "total": len(tasks),
    })
}

// TriggerTask syscall: scheduler.trigger
func (h *SchedulerHandler) TriggerTask(c *gin.Context) {
    taskIDStr := c.Param("id")
    taskID, err := strconv.ParseUint(taskIDStr, 10, 64)
    if err != nil {
        c.JSON(http.StatusBadRequest, gin.H{"error": "invalid task_id"})
        return
    }
    
    agentID := c.GetString("agent_id")
    
    err = h.scheduler.TriggerTask(c.Request.Context(), taskID, types.TriggerTypeManual, agentID)
    if err != nil {
        c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
        return
    }
    
    c.JSON(http.StatusOK, gin.H{"message": "task triggered"})
}

// ListExecutions syscall: scheduler.executions
func (h *SchedulerHandler) ListExecutions(c *gin.Context) {
    taskIDStr := c.Query("task_id")
    limit := c.DefaultQuery("limit", "10")
    
    executions, err := h.scheduler.ListExecutions(c.Request.Context(), taskIDStr, limit)
    if err != nil {
        c.JSON(http.StatusInternalServerError, gin.H{"error": err.Error()})
        return
    }
    
    c.JSON(http.StatusOK, gin.H{
        "executions": executions,
    })
}
```

---

### 2.4 CLI 工具（agent-os-ctl）

#### 2.4.1 设计目标

类比 `kubectl` / `systemctl`，提供直观的命令行接口

#### 2.4.2 命令结构

```bash
# 任务管理
agent-os-ctl task list                     # 列出所有任务
agent-os-ctl task list --owner=fin-agent   # 按 owner 过滤
agent-os-ctl task get daily_recall_audit   # 查看任务详情
agent-os-ctl task trigger daily_recall_audit # 手动触发

# 执行历史
agent-os-ctl exec list --task=daily_recall_audit --limit=10
agent-os-ctl exec get <exec_id>            # 查看执行详情
agent-os-ctl exec logs <exec_id>           # 查看日志

# 配额管理
agent-os-ctl quota show fin-agent          # 查看配额
agent-os-ctl quota list                    # 所有 agent 配额

# Memory 操作
agent-os-ctl memory search "止盈"          # 搜索记忆
agent-os-ctl memory write --file=/path/to/memory.json

# 健康检查
agent-os-ctl health                        # OS 健康状态
agent-os-ctl version                       # 版本信息
```

#### 2.4.3 实现示例

```go
// cmd/agent-os-ctl/main.go
package main

import (
    "fmt"
    "os"
    
    "github.com/spf13/cobra"
    "agent-os/pkg/client"
)

var (
    apiURL string
    osClient *client.Client
)

func main() {
    rootCmd := &cobra.Command{
        Use:   "agent-os-ctl",
        Short: "Agent OS control tool",
        PersistentPreRun: func(cmd *cobra.Command, args []string) {
            osClient = client.NewClient(apiURL)
        },
    }
    
    rootCmd.PersistentFlags().StringVar(&apiURL, "api", "http://localhost:8080", "Agent OS API URL")
    
    // 子命令
    rootCmd.AddCommand(taskCmd())
    rootCmd.AddCommand(execCmd())
    rootCmd.AddCommand(quotaCmd())
    rootCmd.AddCommand(memoryCmd())
    rootCmd.AddCommand(healthCmd())
    
    if err := rootCmd.Execute(); err != nil {
        fmt.Println(err)
        os.Exit(1)
    }
}

func taskCmd() *cobra.Command {
    cmd := &cobra.Command{
        Use:   "task",
        Short: "Manage tasks",
    }
    
    // task list
    listCmd := &cobra.Command{
        Use:   "list",
        Short: "List all tasks",
        Run: func(cmd *cobra.Command, args []string) {
            owner, _ := cmd.Flags().GetString("owner")
            tasks, err := osClient.ListTasks(owner)
            if err != nil {
                fmt.Println("Error:", err)
                return
            }
            
            fmt.Printf("%-5s %-30s %-15s %-20s %-10s\n", "ID", "NAME", "OWNER", "CRON", "ENABLED")
            for _, task := range tasks {
                fmt.Printf("%-5d %-30s %-15s %-20s %-10v\n",
                    task.ID, task.Name, task.Owner, task.CronExpr, task.Enabled)
            }
        },
    }
    listCmd.Flags().String("owner", "", "Filter by owner")
    cmd.AddCommand(listCmd)
    
    // task trigger
    triggerCmd := &cobra.Command{
        Use:   "trigger <task_name>",
        Short: "Trigger a task manually",
        Args:  cobra.ExactArgs(1),
        Run: func(cmd *cobra.Command, args []string) {
            taskName := args[0]
            err := osClient.TriggerTask(taskName)
            if err != nil {
                fmt.Println("Error:", err)
                return
            }
            fmt.Println("Task triggered:", taskName)
        },
    }
    cmd.AddCommand(triggerCmd)
    
    return cmd
}

func quotaCmd() *cobra.Command {
    cmd := &cobra.Command{
        Use:   "quota",
        Short: "Manage quotas",
    }
    
    showCmd := &cobra.Command{
        Use:   "show <agent_id>",
        Short: "Show agent quota",
        Args:  cobra.ExactArgs(1),
        Run: func(cmd *cobra.Command, args []string) {
            agentID := args[0]
            quota, usage, err := osClient.GetQuota(agentID)
            if err != nil {
                fmt.Println("Error:", err)
                return
            }
            
            fmt.Printf("Agent: %s\n", agentID)
            fmt.Printf("Token Quota:  %d / day\n", quota.TokenPerDay)
            fmt.Printf("Token Used:   %d (%.1f%%)\n", usage.TokenUsed, 
                float64(usage.TokenUsed)/float64(quota.TokenPerDay)*100)
            fmt.Printf("Memory Quota: %d MB\n", quota.MemorySizeMB)
            fmt.Printf("Memory Used:  %d MB (%.1f%%)\n", usage.MemoryUsedMB,
                float64(usage.MemoryUsedMB)/float64(quota.MemorySizeMB)*100)
        },
    }
    cmd.AddCommand(showCmd)
    
    return cmd
}
```

#### 2.4.4 Go Client SDK

```go
// pkg/client/client.go
package client

import (
    "bytes"
    "encoding/json"
    "fmt"
    "net/http"
    
    "agent-os/pkg/types"
)

type Client struct {
    baseURL    string
    httpClient *http.Client
}

func NewClient(baseURL string) *Client {
    return &Client{
        baseURL:    baseURL,
        httpClient: &http.Client{},
    }
}

func (c *Client) ListTasks(owner string) ([]*types.TaskDefinition, error) {
    url := fmt.Sprintf("%s/syscall/scheduler/tasks", c.baseURL)
    if owner != "" {
        url += "?owner=" + owner
    }
    
    resp, err := c.httpClient.Get(url)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()
    
    var result struct {
        Tasks []*types.TaskDefinition `json:"tasks"`
    }
    if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
        return nil, err
    }
    
    return result.Tasks, nil
}

func (c *Client) TriggerTask(taskName string) error {
    // 先根据 name 查 ID
    tasks, err := c.ListTasks("")
    if err != nil {
        return err
    }
    
    var taskID uint64
    for _, task := range tasks {
        if task.Name == taskName {
            taskID = task.ID
            break
        }
    }
    
    if taskID == 0 {
        return fmt.Errorf("task not found: %s", taskName)
    }
    
    url := fmt.Sprintf("%s/syscall/scheduler/tasks/%d/trigger", c.baseURL, taskID)
    resp, err := c.httpClient.Post(url, "application/json", nil)
    if err != nil {
        return err
    }
    defer resp.Body.Close()
    
    if resp.StatusCode != http.StatusOK {
        return fmt.Errorf("trigger failed: %s", resp.Status)
    }
    
    return nil
}

func (c *Client) GetQuota(agentID string) (*types.AgentQuota, *types.QuotaUsage, error) {
    url := fmt.Sprintf("%s/syscall/resource/quota?agent_id=%s", c.baseURL, agentID)
    
    resp, err := c.httpClient.Get(url)
    if err != nil {
        return nil, nil, err
    }
    defer resp.Body.Close()
    
    var result struct {
        Quota *types.AgentQuota   `json:"quota"`
        Usage *types.QuotaUsage   `json:"usage"`
    }
    if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
        return nil, nil, err
    }
    
    return result.Quota, result.Usage, nil
}
```

---

## 3. 配置文件设计

### 3.1 主配置文件（agent-os.yaml）

```yaml
# configs/agent-os.yaml

# Server 配置
server:
  host: "0.0.0.0"
  port: 8080
  mode: "release"  # debug / release

# 数据库配置
database:
  postgres:
    host: "127.0.0.1"
    port: 5432
    user: "yunpeng"
    password: ""
    dbname: "agent_os"
    sslmode: "disable"
  
  redis:
    host: "127.0.0.1"
    port: 6379
    password: ""
    db: 0

# 调度器配置
scheduler:
  max_concurrent_tasks: 5        # 全局最大并发任务数
  default_timeout_sec: 1800      # 默认超时 30 分钟
  default_max_retries: 3         # 默认最大重试次数
  execution_history_retention_days: 30  # 执行历史保留天数

# 资源管理器配置
resource:
  quota_reset_hour: 0            # 配额重置时间（凌晨 0 点）

# 驱动配置
drivers:
  market_data:
    grpc_addr: "localhost:50051"
    enabled: true
  
  trading:
    grpc_addr: "localhost:50052"
    enabled: false               # 生产环境关闭虚拟盘

# 日志配置
logging:
  level: "info"                  # debug / info / warn / error
  format: "json"                 # json / console
  output: "/var/log/agent-os/agent-os.log"

# 监控配置
monitoring:
  prometheus:
    enabled: true
    port: 9090
  
  tracing:
    enabled: false
    jaeger_endpoint: ""
```

### 3.2 Agent 配置文件（agents.yaml）

```yaml
# configs/agents.yaml

agents:
  - id: "fin-agent"
    name: "Financial Agent"
    capabilities:
      - "memory.read"
      - "memory.write"
      - "decision.record"
      - "data.market.read"
      - "trading.execute"
    quotas:
      token_per_day: 100000
      memory_size_mb: 500
    priority: 10                 # 最高优先级
    
  - id: "memory-agent"
    name: "Memory Agent"
    capabilities:
      - "memory.read"
      - "memory.write"
      - "memory.audit"
      - "decision.read"          # 只读决策（复盘需要）
    quotas:
      token_per_day: 20000
      memory_size_mb: 100
    priority: 5
    
  - id: "evolution-agent"
    name: "Evolution Agent"
    capabilities:
      - "memory.read"
      - "evolution.suggest"
      - "evolution.execute"
    quotas:
      token_per_day: 50000
      memory_size_mb: 200
    priority: 7
```

---

## 4. 数据库 Schema

### 4.1 核心表

```sql
-- 任务定义表
CREATE TABLE scheduler_tasks (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    owner VARCHAR(50) NOT NULL,
    task_type VARCHAR(50) NOT NULL,
    cron_expr VARCHAR(100) NOT NULL,
    enabled BOOLEAN DEFAULT true,
    
    timeout_sec INT DEFAULT 1800,
    max_retries INT DEFAULT 3,
    retry_backoff_sec INT DEFAULT 60,
    max_concurrent INT DEFAULT 1,
    
    depends_on TEXT[],
    
    agent_kind VARCHAR(50),
    agent_prompt TEXT,
    
    service_name VARCHAR(100),
    service_method VARCHAR(100),
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_tasks_owner ON scheduler_tasks(owner);
CREATE INDEX idx_tasks_enabled ON scheduler_tasks(enabled);

-- 执行历史表
CREATE TABLE scheduler_executions (
    id SERIAL PRIMARY KEY,
    task_id INT REFERENCES scheduler_tasks(id),
    trigger_type VARCHAR(50) NOT NULL,
    triggered_by VARCHAR(100) NOT NULL,
    
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ,
    status VARCHAR(50) NOT NULL,
    
    duration_sec INT,
    token_consumed INT,
    
    error_message TEXT,
    retry_count INT DEFAULT 0,
    
    log_path TEXT
);

CREATE INDEX idx_executions_task_id ON scheduler_executions(task_id);
CREATE INDEX idx_executions_status ON scheduler_executions(status);
CREATE INDEX idx_executions_started_at ON scheduler_executions(started_at DESC);

-- Agent 记忆表（命名空间隔离）
CREATE TABLE agent_memory (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    namespace VARCHAR(200) NOT NULL,  -- /memory/fin-agent/decisions/...
    
    content TEXT NOT NULL,
    metadata JSONB,
    
    embedding vector(1536),           -- OpenAI ada-002
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_memory_agent_id ON agent_memory(agent_id);
CREATE INDEX idx_memory_namespace ON agent_memory(namespace);
CREATE INDEX idx_memory_embedding ON agent_memory USING ivfflat(embedding vector_cosine_ops);

-- 配额使用记录表
CREATE TABLE quota_usage (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(50) NOT NULL,
    
    token_used INT DEFAULT 0,
    memory_used_mb INT DEFAULT 0,
    
    last_reset_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(agent_id)
);
```

---

## 5. 开发路线图

### Phase 1：MVP 核心（2-3 周）

**Week 1：调度器**
- [ ] Go 项目脚手架 + 依赖配置
- [ ] 数据库 schema + migration
- [ ] Scheduler 核心逻辑（注册、触发、执行）
- [ ] DAG 依赖解析
- [ ] 单元测试

**Week 2：资源管理器 + API**
- [ ] 配额管理（Token + Memory）
- [ ] 命名空间隔离
- [ ] Syscall API（Gin 路由 + Handlers）
- [ ] 中间件（Auth、RateLimit、Logger）
- [ ] 集成测试

**Week 3：CLI + 驱动**
- [ ] agent-os-ctl CLI 工具
- [ ] Go Client SDK
- [ ] Python Market Data Driver（gRPC）
- [ ] 端到端测试
- [ ] 部署脚本

### Phase 2：高级特性（2-3 周）

- [ ] Event Bus（IPC）
- [ ] Memory System（BM25 + Vector 检索）
- [ ] 权限模型细化
- [ ] Prometheus 监控
- [ ] Web Dashboard（可选，或复用现有 web-frontend）

### Phase 3：生产优化（1-2 周）

- [ ] 性能测试 + 调优
- [ ] Rust 重写性能热点（可选）
- [ ] 高可用部署（多实例 + 负载均衡）
- [ ] 文档完善

---

## 6. 迁移策略（quantsys-v2 → Agent OS）

### 6.1 分批迁移（推荐）

**批次 1：调度器迁移**（MVP 完成后立即开始）
- agent-ts 任务注册到 Agent OS
- v2 后端任务迁移到 Agent OS scheduler_tasks 表
- 验收：`agent-os-ctl task list` 能看到所有任务

**批次 2：Memory 迁移**
- quantsys-v2 的 agent_memory 表迁移到 Agent OS
- agent-ts 的 memory_write/search 切换到 Agent OS

**批次 3：其他子系统**
- Decision、Evolution、Knowledge 逐个迁移

### 6.2 双跑期（过渡方案）

- Agent OS 和 quantsys-v2 同时运行
- agent-ts 优先调用 Agent OS，失败时 fallback 到 v2
- 观察 1-2 周稳定后，下线 v2

---

## 7. 你的下一步决策

1. **技术栈确认**：Go + Python 驱动 + 未来 Rust 优化，OK 吗？
2. **MVP 范围**：Phase 1 的三周计划，覆盖面够吗？还是要调整？
3. **启动时机**：现在立即开工？还是等观察期结束（明晚首次 daily_recall_audit 触发）？
4. **项目命名**：`agent-os` 还是别的名字？

告诉我你的决定，我们开始建项目脚手架。
