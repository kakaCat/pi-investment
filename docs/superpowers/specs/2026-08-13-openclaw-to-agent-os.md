# OpenClaw 理念在 Agent OS 中的应用

> **基于**: [openclaw-optimization-analysis.md](../openclaw-optimization-analysis.md) 分析  
> **目标**: 将 OpenClaw 的生产级可靠性理念融入 Agent OS 设计

---

## 核心问题：OpenClaw 是 Agent 框架，Agent OS 是操作系统

**OpenClaw 职责**：
- 管理 agent 会话生命周期
- 工具调用循环检测
- LLM 交互与重试
- Prompt 管理

**Agent OS 职责**：
- 资源管理（Token 配额、Memory 空间）
- 任务调度（Cron、DAG、并发控制）
- 持久化存储（Memory、Decision、Knowledge）
- Agent 间通信（Event Bus）

**借鉴原则**：OpenClaw 的**可靠性模式**适用于 Agent OS，但**实现层次不同**。

---

## 1. 循环检测 → Agent OS Scheduler 的死循环保护

### OpenClaw 的实现（Agent 框架层）

```typescript
// 检测 agent 工具调用陷入循环
detectToolCallLoop(state, toolName, params) {
  const hash = hashToolCall(toolName, params);
  if (callCount(hash) > threshold) {
    throw new CircuitBreakerError();
  }
}
```

### Agent OS 的对应职责（OS 调度器层）

**场景**：任务调度陷入死循环

```go
// internal/kernel/scheduler/loop_detector.go
type TaskLoopDetector struct {
    executionHistory map[uint64][]time.Time  // taskID -> execution times
}

// DetectStuckTask 检测任务是否陷入高频重复
func (d *TaskLoopDetector) DetectStuckTask(taskID uint64) bool {
    history := d.executionHistory[taskID]
    
    // 最近 1 小时执行超过 100 次 → 死循环
    recentCount := 0
    oneHourAgo := time.Now().Add(-1 * time.Hour)
    for _, execTime := range history {
        if execTime.After(oneHourAgo) {
            recentCount++
        }
    }
    
    if recentCount > 100 {
        logger.Error("Task stuck in loop, circuit breaker triggered",
            zap.Uint64("taskID", taskID),
            zap.Int("recentCount", recentCount))
        return true
    }
    
    return false
}

// 在调度器中应用
func (s *Scheduler) triggerTask(taskID uint64) error {
    if s.loopDetector.DetectStuckTask(taskID) {
        // 熔断：禁用任务 10 分钟
        s.taskRepo.DisableTask(taskID, 10*time.Minute)
        return ErrTaskStuckInLoop
    }
    // ... 正常调度
}
```

**Agent OS 应用点**：
- ✅ 调度器层面检测任务死循环（频率异常）
- ✅ 自动熔断机制（临时禁用任务）
- ✅ 记录到执行历史表（scheduler_executions）供分析
- ❌ 不管 agent 内部的工具调用循环（那是 agent-ts 的 LoopGuardian 职责）

---

## 2. 重试策略 → Agent OS 的统一重试基础设施

### OpenClaw 的实现（Agent 框架层）

```typescript
// 重试 LLM API 调用
retryAsync(() => callLLM(), {
  attempts: 5,
  minDelayMs: 500,
  maxDelayMs: 30_000,
  jitter: 0.3,
  shouldRetry: (err) => err.code === 'ECONNRESET',
});
```

### Agent OS 的对应职责（OS 基础设施层）

**场景**：OS 内部调用失败（数据库、Redis、gRPC 驱动）

```go
// pkg/retry/retry.go (公共库，Go 生态标准做法)
package retry

import (
    "context"
    "math"
    "math/rand"
    "time"
)

type Policy struct {
    MaxAttempts  int
    MinDelay     time.Duration
    MaxDelay     time.Duration
    Jitter       float64  // 0.0 - 1.0
    ShouldRetry  func(error) bool
}

var DefaultPolicy = Policy{
    MaxAttempts: 3,
    MinDelay:    100 * time.Millisecond,
    MaxDelay:    10 * time.Second,
    Jitter:      0.2,
    ShouldRetry: func(err error) bool {
        // 默认：网络错误重试，业务错误不重试
        return isNetworkError(err)
    },
}

func Do(ctx context.Context, policy Policy, fn func() error) error {
    var lastErr error
    
    for attempt := 1; attempt <= policy.MaxAttempts; attempt++ {
        lastErr = fn()
        if lastErr == nil {
            return nil
        }
        
        // 最后一次尝试或不应该重试，直接返回
        if attempt >= policy.MaxAttempts || !policy.ShouldRetry(lastErr) {
            return lastErr
        }
        
        // 指数退避 + jitter
        delay := calculateDelay(attempt, policy)
        
        select {
        case <-time.After(delay):
            // 继续重试
        case <-ctx.Done():
            return ctx.Err()
        }
    }
    
    return lastErr
}

func calculateDelay(attempt int, policy Policy) time.Duration {
    // 指数退避：minDelay * 2^(attempt-1)
    delay := policy.MinDelay * time.Duration(math.Pow(2, float64(attempt-1)))
    if delay > policy.MaxDelay {
        delay = policy.MaxDelay
    }
    
    // 加 jitter（防止雷鸣群效应）
    if policy.Jitter > 0 {
        jitterRange := float64(delay) * policy.Jitter
        jitterOffset := rand.Float64()*jitterRange*2 - jitterRange
        delay = time.Duration(float64(delay) + jitterOffset)
    }
    
    return delay
}
```

**Agent OS 应用场景**：

```go
// 1. 数据库查询重试
func (r *MemoryRepository) Search(ctx context.Context, query string) ([]*Memory, error) {
    var result []*Memory
    
    err := retry.Do(ctx, retry.Policy{
        MaxAttempts: 3,
        MinDelay:    100 * time.Millisecond,
        MaxDelay:    2 * time.Second,
        Jitter:      0.2,
        ShouldRetry: func(err error) bool {
            // PG 连接失败重试，语法错误不重试
            return isPgConnectionError(err)
        },
    }, func() error {
        var err error
        result, err = r.db.Query(ctx, "SELECT * FROM agent_memory WHERE ...")
        return err
    })
    
    return result, err
}

// 2. gRPC 驱动调用重试
func (d *MarketDriver) GetQuote(ctx context.Context, symbol string) (*Quote, error) {
    var quote *Quote
    
    err := retry.Do(ctx, retry.Policy{
        MaxAttempts: 5,
        MinDelay:    500 * time.Millisecond,
        MaxDelay:    30 * time.Second,
        Jitter:      0.3,
        ShouldRetry: func(err error) bool {
            // gRPC Unavailable/DeadlineExceeded 重试
            code := status.Code(err)
            return code == codes.Unavailable || code == codes.DeadlineExceeded
        },
    }, func() error {
        var err error
        quote, err = d.client.GetQuote(ctx, &pb.QuoteRequest{Symbol: symbol})
        return err
    })
    
    return quote, err
}

// 3. Redis 操作重试
func (e *EventBus) Publish(ctx context.Context, channel string, payload []byte) error {
    return retry.Do(ctx, retry.Policy{
        MaxAttempts: 3,
        MinDelay:    100 * time.Millisecond,
        MaxDelay:    1 * time.Second,
        Jitter:      0.1,
    }, func() error {
        return e.redis.Publish(ctx, channel, payload).Err()
    })
}
```

**Agent OS 应用点**：
- ✅ OS 内部所有外部调用（DB、Redis、gRPC）统一重试
- ✅ 配置化策略（不同服务不同策略）
- ✅ Jitter 防止雷鸣群（多个 agent 同时重启时不会同时重试）
- ❌ 不管 agent 对 OS syscall 的重试（那是 agent-ts 的 client SDK 职责）

---

## 3. 结构化错误 → Agent OS 的错误码体系

### OpenClaw 的实现（Agent 框架层）

```typescript
enum ErrorCode {
  TOOL_EXECUTION_FAILED = 'TOOL_EXECUTION_FAILED',
  LLM_API_ERROR = 'LLM_API_ERROR',
  SESSION_TIMEOUT = 'SESSION_TIMEOUT',
}

class AgentError extends Error {
  constructor(public code: ErrorCode, message: string, public recoverable: boolean) {
    super(message);
  }
}
```

### Agent OS 的对应职责（OS 错误码体系）

```go
// pkg/errors/errors.go
package errors

type ErrorCode string

const (
    // Scheduler 错误码
    ErrTaskNotFound         ErrorCode = "TASK_NOT_FOUND"
    ErrTaskDependencyFailed ErrorCode = "TASK_DEPENDENCY_FAILED"
    ErrTaskTimeout          ErrorCode = "TASK_TIMEOUT"
    ErrTaskConcurrencyLimit ErrorCode = "TASK_CONCURRENCY_LIMIT"
    ErrTaskStuckInLoop      ErrorCode = "TASK_STUCK_IN_LOOP"
    
    // Resource 错误码
    ErrQuotaExceeded        ErrorCode = "QUOTA_EXCEEDED"
    ErrQuotaNotFound        ErrorCode = "QUOTA_NOT_FOUND"
    ErrNamespaceViolation   ErrorCode = "NAMESPACE_VIOLATION"
    
    // Memory 错误码
    ErrMemoryNotFound       ErrorCode = "MEMORY_NOT_FOUND"
    ErrMemoryIndexCorrupted ErrorCode = "MEMORY_INDEX_CORRUPTED"
    ErrMemoryGCFailed       ErrorCode = "MEMORY_GC_FAILED"
    
    // Driver 错误码
    ErrDriverUnavailable    ErrorCode = "DRIVER_UNAVAILABLE"
    ErrDriverTimeout        ErrorCode = "DRIVER_TIMEOUT"
    
    // Infrastructure 错误码
    ErrDatabaseConnection   ErrorCode = "DATABASE_CONNECTION"
    ErrRedisConnection      ErrorCode = "REDIS_CONNECTION"
)

type OSError struct {
    Code       ErrorCode
    Message    string
    Recoverable bool
    Cause      error  // 原始错误
    Metadata   map[string]interface{}  // 上下文信息
}

func (e *OSError) Error() string {
    return fmt.Sprintf("[%s] %s", e.Code, e.Message)
}

func (e *OSError) Unwrap() error {
    return e.Cause
}

// 构造函数
func NewOSError(code ErrorCode, message string, recoverable bool) *OSError {
    return &OSError{
        Code:       code,
        Message:    message,
        Recoverable: recoverable,
        Metadata:   make(map[string]interface{}),
    }
}

func WrapOSError(code ErrorCode, cause error, message string) *OSError {
    return &OSError{
        Code:       code,
        Message:    message,
        Cause:      cause,
        Recoverable: false,
        Metadata:   make(map[string]interface{}),
    }
}
```

**使用示例**：

```go
// Scheduler 使用
func (s *Scheduler) triggerTask(taskID uint64) error {
    task, err := s.taskRepo.Get(ctx, taskID)
    if err != nil {
        if errors.Is(err, sql.ErrNoRows) {
            return errors.NewOSError(
                errors.ErrTaskNotFound,
                fmt.Sprintf("task %d not found", taskID),
                false,  // 不可恢复
            )
        }
        return errors.WrapOSError(
            errors.ErrDatabaseConnection,
            err,
            "failed to fetch task",
        )
    }
    
    if !s.resourceMgr.CheckQuota(task.Owner) {
        return errors.NewOSError(
            errors.ErrQuotaExceeded,
            fmt.Sprintf("agent %s quota exceeded", task.Owner),
            true,  // 可恢复（等配额重置）
        ).WithMetadata("agent_id", task.Owner)
    }
    
    // ...
}

// API Handler 根据错误码返回 HTTP 状态码
func (h *SchedulerHandler) TriggerTask(c *gin.Context) {
    err := h.scheduler.TriggerTask(taskID)
    if err != nil {
        osErr, ok := err.(*errors.OSError)
        if !ok {
            c.JSON(500, gin.H{"error": "internal server error"})
            return
        }
        
        // 根据错误码映射 HTTP 状态码
        statusCode := mapErrorCodeToHTTP(osErr.Code)
        c.JSON(statusCode, gin.H{
            "error": osErr.Message,
            "code": osErr.Code,
            "recoverable": osErr.Recoverable,
        })
        return
    }
    
    c.JSON(200, gin.H{"message": "task triggered"})
}

func mapErrorCodeToHTTP(code errors.ErrorCode) int {
    switch code {
    case errors.ErrTaskNotFound, errors.ErrQuotaNotFound:
        return http.StatusNotFound
    case errors.ErrQuotaExceeded, errors.ErrTaskConcurrencyLimit:
        return http.StatusTooManyRequests
    case errors.ErrTaskDependencyFailed:
        return http.StatusPreconditionFailed
    case errors.ErrDatabaseConnection, errors.ErrRedisConnection:
        return http.StatusServiceUnavailable
    default:
        return http.StatusInternalServerError
    }
}
```

**Agent OS 应用点**：
- ✅ 统一的错误码体系（便于日志分析、告警规则）
- ✅ 可恢复 vs 不可恢复（调度器决定是否重试）
- ✅ 错误链（Unwrap 保留原始错误栈）
- ✅ 元数据（记录上下文信息供诊断）

---

## 4. 会话状态管理 → Agent OS 的执行上下文

### OpenClaw 的实现（Agent 框架层）

```typescript
interface SessionState {
  sessionId: string;
  toolCallHistory: ToolCallRecord[];
  issuedWarnings: Set<string>;
  consecutiveErrors: number;
  metadata: Record<string, unknown>;
}
```

### Agent OS 的对应职责（任务执行上下文）

```go
// internal/kernel/scheduler/context.go
type ExecutionContext struct {
    ExecutionID   uint64
    TaskID        uint64
    AgentID       string
    
    // 状态跟踪
    StartedAt     time.Time
    LastHeartbeat time.Time
    
    // 资源使用
    TokenConsumed int
    MemoryUsedMB  int
    
    // 错误追踪
    ErrorCount    int
    LastError     *errors.OSError
    
    // 元数据
    Metadata      map[string]interface{}
    
    // Context 取消信号
    ctx           context.Context
    cancel        context.CancelFunc
}

func NewExecutionContext(taskID uint64, agentID string, timeout time.Duration) *ExecutionContext {
    ctx, cancel := context.WithTimeout(context.Background(), timeout)
    
    return &ExecutionContext{
        TaskID:    taskID,
        AgentID:   agentID,
        StartedAt: time.Now(),
        Metadata:  make(map[string]interface{}),
        ctx:       ctx,
        cancel:    cancel,
    }
}

// Heartbeat 更新心跳（检测任务是否存活）
func (ec *ExecutionContext) Heartbeat() {
    ec.LastHeartbeat = time.Now()
}

// IsAlive 检查任务是否还活着
func (ec *ExecutionContext) IsAlive() bool {
    // 超过 5 分钟无心跳 → 认为任务卡死
    return time.Since(ec.LastHeartbeat) < 5*time.Minute
}

// ConsumeToken 记录 token 消耗
func (ec *ExecutionContext) ConsumeToken(tokens int) {
    ec.TokenConsumed += tokens
}

// RecordError 记录错误
func (ec *ExecutionContext) RecordError(err *errors.OSError) {
    ec.ErrorCount++
    ec.LastError = err
}

// Cancel 取消执行
func (ec *ExecutionContext) Cancel() {
    ec.cancel()
}

// Context 返回可取消的 context
func (ec *ExecutionContext) Context() context.Context {
    return ec.ctx
}
```

**在 Executor 中使用**：

```go
// internal/kernel/scheduler/executor.go
func (e *Executor) Execute(ctx context.Context, task *types.TaskDefinition, exec *types.TaskExecution) error {
    // 创建执行上下文
    execCtx := NewExecutionContext(task.ID, task.Owner, time.Duration(task.TimeoutSec)*time.Second)
    defer execCtx.Cancel()
    
    // 根据任务类型执行
    if task.TaskType == types.TaskTypeAgentTurn {
        return e.executeAgentTask(execCtx, task, exec)
    } else {
        return e.executePythonTask(execCtx, task, exec)
    }
}

func (e *Executor) executeAgentTask(execCtx *ExecutionContext, task *types.TaskDefinition, exec *types.TaskExecution) error {
    // 调用 agent-ts 的 webhook
    webhookURL := "http://localhost:3000/api/agent/trigger"
    payload := map[string]interface{}{
        "execution_id": execCtx.ExecutionID,
        "agent_kind":   task.AgentKind,
        "prompt":       task.AgentPrompt,
    }
    
    resp, err := e.httpClient.Post(webhookURL, "application/json", marshalJSON(payload))
    if err != nil {
        return errors.WrapOSError(errors.ErrDriverUnavailable, err, "failed to call agent webhook")
    }
    
    // agent 异步执行，周期性心跳
    ticker := time.NewTicker(30 * time.Second)
    defer ticker.Stop()
    
    for {
        select {
        case <-execCtx.Context().Done():
            // 超时或取消
            return errors.NewOSError(errors.ErrTaskTimeout, "task execution timeout", false)
            
        case <-ticker.C:
            // 检查 agent 是否完成
            status, err := e.checkAgentStatus(execCtx.ExecutionID)
            if err != nil {
                execCtx.RecordError(errors.WrapOSError(errors.ErrDriverTimeout, err, "agent status check failed"))
                continue
            }
            
            if status.Completed {
                execCtx.ConsumeToken(status.TokenConsumed)
                exec.TokenConsumed = &status.TokenConsumed
                return nil
            }
            
            execCtx.Heartbeat()
        }
    }
}
```

**Agent OS 应用点**：
- ✅ 执行上下文跟踪（心跳、资源使用、错误）
- ✅ 超时控制（context.WithTimeout）
- ✅ 心跳机制（检测任务卡死）
- ✅ 资源计量（token、内存消耗记录）

---

## 5. 配置验证 → Agent OS 的配置 Schema

### OpenClaw 的实现（Agent 框架层）

```typescript
import { z } from 'zod';

const ConfigSchema = z.object({
  llm: z.object({
    apiKey: z.string(),
    model: z.string(),
    maxTokens: z.number().positive(),
  }),
  tools: z.array(z.string()),
});

const config = ConfigSchema.parse(rawConfig);  // 启动时验证
```

### Agent OS 的对应职责（OS 配置验证）

```go
// internal/config/schema.go
package config

import (
    "fmt"
    "os"
    "time"
    
    "github.com/go-playground/validator/v10"
    "gopkg.in/yaml.v3"
)

type Config struct {
    Server    ServerConfig    `yaml:"server" validate:"required"`
    Database  DatabaseConfig  `yaml:"database" validate:"required"`
    Scheduler SchedulerConfig `yaml:"scheduler" validate:"required"`
    Resource  ResourceConfig  `yaml:"resource" validate:"required"`
    Drivers   DriversConfig   `yaml:"drivers" validate:"required"`
}

type ServerConfig struct {
    Host string `yaml:"host" validate:"required,ip_addr|hostname"`
    Port int    `yaml:"port" validate:"required,min=1,max=65535"`
    Mode string `yaml:"mode" validate:"required,oneof=debug release"`
}

type DatabaseConfig struct {
    Postgres PostgresConfig `yaml:"postgres" validate:"required"`
    Redis    RedisConfig    `yaml:"redis" validate:"required"`
}

type PostgresConfig struct {
    Host     string `yaml:"host" validate:"required,hostname_rfc1123"`
    Port     int    `yaml:"port" validate:"required,min=1,max=65535"`
    User     string `yaml:"user" validate:"required"`
    Password string `yaml:"password"`
    DBName   string `yaml:"dbname" validate:"required"`
    SSLMode  string `yaml:"sslmode" validate:"required,oneof=disable require verify-ca verify-full"`
}

type SchedulerConfig struct {
    MaxConcurrentTasks int `yaml:"max_concurrent_tasks" validate:"required,min=1,max=100"`
    DefaultTimeoutSec  int `yaml:"default_timeout_sec" validate:"required,min=60,max=7200"`
    DefaultMaxRetries  int `yaml:"default_max_retries" validate:"required,min=0,max=10"`
}

type ResourceConfig struct {
    QuotaResetHour int `yaml:"quota_reset_hour" validate:"required,min=0,max=23"`
}

type DriversConfig struct {
    MarketData DriverConfig `yaml:"market_data" validate:"required"`
    Trading    DriverConfig `yaml:"trading" validate:"required"`
}

type DriverConfig struct {
    GRPCAddr string `yaml:"grpc_addr" validate:"required,hostname_port"`
    Enabled  bool   `yaml:"enabled"`
}

// LoadConfig 加载并验证配置
func LoadConfig(path string) (*Config, error) {
    data, err := os.ReadFile(path)
    if err != nil {
        return nil, fmt.Errorf("failed to read config file: %w", err)
    }
    
    var config Config
    if err := yaml.Unmarshal(data, &config); err != nil {
        return nil, fmt.Errorf("failed to parse config: %w", err)
    }
    
    // 验证
    validate := validator.New()
    if err := validate.Struct(&config); err != nil {
        return nil, fmt.Errorf("config validation failed: %w", err)
    }
    
    return &config, nil
}

// main.go 中使用
func main() {
    config, err := config.LoadConfig("configs/agent-os.yaml")
    if err != nil {
        log.Fatal("Invalid configuration:", err)
        os.Exit(1)
    }
    
    log.Info("Configuration loaded successfully",
        zap.String("mode", config.Server.Mode),
        zap.Int("port", config.Server.Port))
    
    // 启动 Agent OS
    // ...
}
```

**Agent OS 应用点**：
- ✅ 启动时验证配置（Fail Fast）
- ✅ 类型安全（Go struct + validator tags）
- ✅ 友好的错误提示（哪个字段不合法）
- ✅ 防止生产配置错误（端口冲突、超时值不合理等）

---

## 6. 不适合放入 Agent OS 的 OpenClaw 特性

### ❌ Plugin Architecture（插件架构）

**OpenClaw 的实现**：动态加载工具插件

**为什么不适合 Agent OS**：
- Agent OS 是**编译型系统**（Go binary），不是解释型
- 驱动层已经通过 gRPC 实现了"插件化"（Python 驱动独立进程）
- Go 的插件机制（.so）不成熟，跨平台兼容性差

**替代方案**：
- 新增数据源 → 写新的 Python gRPC 驱动
- 新增 OS 能力 → 编译进内核（Go 模块）

### ❌ Memory Provider Fallback（嵌入模型降级）

**OpenClaw 的实现**：OpenAI embedding API 挂了，降级到本地模型

**为什么不适合 Agent OS**：
- Embedding 是 Memory 子系统的内部实现细节
- Agent OS 只提供 `memory.write` / `memory.search` syscall
- 嵌入模型的选择由 Memory 子系统决定，对外透明

**如果要做**：
- 在 Memory 子系统内部实现（不暴露给 agent）
- 配置文件指定 primary/fallback embedding provider

---

## 总结：OpenClaw → Agent OS 的理念映射表

| OpenClaw 特性 | 适用层次 | Agent OS 实现 | 优先级 |
|---|---|---|---|
| **循环检测** | Agent 框架层 | Scheduler 死循环保护 | P0 |
| **重试策略** | Agent 框架层 | OS 基础设施统一重试 | P0 |
| **结构化错误** | Agent 框架层 | OS 错误码体系 | P1 |
| **会话状态管理** | Agent 框架层 | 执行上下文跟踪 | P1 |
| **配置验证** | Agent 框架层 | OS 配置 Schema | P2 |
| **插件架构** | Agent 框架层 | ❌ 不适用（用 gRPC 驱动） | - |
| **Memory Fallback** | Agent 框架层 | ❌ 内部实现，不暴露 | - |

---

## 实施建议

### Phase 1（MVP）：必须有的可靠性基础

```
Week 1-3: Agent OS 核心 + 基础可靠性
├── Scheduler (全新设计)
├── Resource Manager
├── Syscall API
├── pkg/retry (统一重试库) ← OpenClaw 启发
├── pkg/errors (错误码体系) ← OpenClaw 启发
└── CLI 工具
```

### Phase 2（生产强化）：从 OpenClaw 学来的可靠性

```
Week 4-6: 可靠性强化
├── Scheduler Loop Detector ← OpenClaw 启发
├── Execution Context (心跳、资源跟踪) ← OpenClaw 启发
├── Config Schema Validation ← OpenClaw 启发
└── 监控指标（Prometheus）
```

### Phase 3（持续优化）：生产观测与调优

```
Week 7+: 观测与优化
├── 结构化日志（Zap）
├── Distributed Tracing（OpenTelemetry，可选）
├── 性能测试 + 调优
└── Rust 重写热点（可选）
```

---

## 关键启示

1. **OpenClaw 是 Agent 框架，Agent OS 是操作系统** → 借鉴理念，不照搬实现
2. **可靠性模式通用** → 重试、错误码、循环检测都适用于 OS 层
3. **实现层次不同** → OpenClaw 管 agent 会话，Agent OS 管任务调度
4. **Go 生态不同** → 用 Go 标准做法（validator、zap、Prometheus），不强行模仿 TypeScript
5. **分层清晰** → agent-ts 有 LoopGuardian，Agent OS 有 Scheduler Loop Detector，各司其职

---

**下一步**：你认可这个映射吗？还是有哪些 OpenClaw 特性你觉得必须放入 Agent OS？
