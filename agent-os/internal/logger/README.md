# Logger 使用指南

## 📋 设计理念

**框架无关的日志抽象层**：不直接依赖 zap/logrus，定义统一接口，未来可无缝切换到任何日志实现。

## 🎯 架构

```
业务代码 → logger.Logger 接口 → 适配器 (zap/logrus/框架自带)
```

**优势**：
- ✅ 业务代码不依赖具体日志库
- ✅ 支持结构化日志（key-value）
- ✅ 未来引入 Gin/Echo 时可直接用框架自带 logger
- ✅ 支持上下文传递（trace ID 等）

---

## 🚀 快速开始

### 1. 初始化（仅在 main.go 或 serve.go）

```go
import "github.com/pi-investment/agent-os/internal/logger"

// 从配置文件初始化
cfg := logger.LoggerConfig{
    Level:       "info",        // debug/info/warn/error
    Format:      "console",     // json/console
    Output:      "stdout",      // stdout/stderr/file
    Development: false,
}
if err := logger.InitGlobal(cfg); err != nil {
    panic(err)
}
defer logger.L().Sync()
```

### 2. 业务代码使用

```go
import "github.com/pi-investment/agent-os/internal/logger"

// 简单日志
logger.L().Info("Server started")
logger.L().Error("Failed to connect", logger.Error(err))

// 结构化日志（推荐）
logger.L().Info("Order created",
    logger.String("order_id", "12345"),
    logger.Int("quantity", 100),
    logger.Float64("price", 15.5),
)

// 警告日志
logger.L().Warn("Retry limit reached",
    logger.String("log_id", logID),
    logger.Int("retry_count", 3),
)

// 错误日志（自动记录堆栈）
logger.L().Error("Database connection failed",
    logger.String("host", "localhost"),
    logger.Int("port", 5432),
    logger.Error(err),
)
```

### 3. 模块级 Logger（带前缀）

```go
type OrderService struct {
    logger logger.Logger
}

func NewOrderService() *OrderService {
    return &OrderService{
        logger: logger.L().With(logger.String("module", "order")),
    }
}

func (s *OrderService) CreateOrder() {
    // 自动带 "module":"order" 前缀
    s.logger.Info("Creating order", logger.String("user_id", "123"))
}
```

### 4. 上下文日志（分布式追踪）

```go
// 从 context 提取 trace_id（未来实现）
ctx := context.WithValue(context.Background(), "trace_id", "abc123")
logger.L().InfoContext(ctx, "Request received")
```

---

## 📦 可用字段类型

```go
logger.String("key", "value")
logger.Int("key", 123)
logger.Int64("key", 123456789)
logger.Float64("key", 3.14)
logger.Bool("key", true)
logger.Error(err)              // 专门处理错误
logger.Any("key", anyValue)    // 任意类型
```

---

## ⚙️ 配置说明

### config.yaml

```yaml
log:
  level: info          # debug/info/warn/error
  format: console      # json（生产）/ console（开发）
  output_path: stdout  # stdout/stderr
```

### 环境变量覆盖（可选）

```bash
export LOG_LEVEL=debug
export LOG_FORMAT=json
```

---

## 🔄 从旧日志迁移

### 旧代码（标准库 log）

```go
log.Println("Server started")
log.Printf("User %s logged in", userID)
```

### 新代码（结构化日志）

```go
logger.L().Info("Server started")
logger.L().Info("User logged in", logger.String("user_id", userID))
```

**迁移原则**：
- `log.Println()` → `logger.L().Info()`
- `log.Printf()` → `logger.L().Info()` + 结构化字段
- 字符串拼接 → 独立字段（便于查询和分析）

---

## 🎨 输出示例

### Console 格式（开发模式）

```
2026-08-27T10:50:30.123+0800    INFO    Found stuck pending notifications    {"count": 20}
2026-08-27T10:50:31.456+0800    WARN    Notification retry failed    {"log_id": "abc-123", "retry_count": 2, "error": "timeout"}
```

### JSON 格式（生产模式）

```json
{"level":"info","ts":"2026-08-27T10:50:30.123+0800","msg":"Found stuck pending notifications","count":20}
{"level":"warn","ts":"2026-08-27T10:50:31.456+0800","msg":"Notification retry failed","log_id":"abc-123","retry_count":2,"error":"timeout"}
```

---

## 🔌 未来扩展：切换到 Gin 框架日志

当引入 Gin 框架时，只需创建 `gin_adapter.go`：

```go
package logger

import (
    "github.com/gin-gonic/gin"
)

type ginLogger struct {
    g *gin.Logger
}

func newGinLogger(cfg LoggerConfig) (Logger, error) {
    // 实现 Logger 接口，内部用 gin.Logger
    return &ginLogger{g: gin.DefaultWriter}, nil
}
```

业务代码**完全不需要改动**，只修改 `logger.New()` 的实现。

---

## 🛠️ 最佳实践

### ✅ 推荐

```go
// 1. 结构化日志（便于查询）
logger.L().Info("Order created",
    logger.String("order_id", orderID),
    logger.Int("quantity", qty),
)

// 2. 错误必须记录上下文
logger.L().Error("Failed to update log",
    logger.String("log_id", logID),
    logger.Error(err),
)

// 3. 模块级 logger
type Service struct {
    logger logger.Logger
}
```

### ❌ 避免

```go
// 1. 字符串拼接（无法查询）
logger.L().Info(fmt.Sprintf("Order %s created with qty %d", orderID, qty))

// 2. 吞掉错误
if err != nil {
    // 什么都不做 ❌
}

// 3. 过度日志
logger.L().Debug("Entering function")  // 仅在 debug 模式需要时
```

---

## 📊 日志级别使用指南

| 级别 | 用途 | 示例 |
|-----|------|------|
| **Debug** | 开发调试 | "Entering function", "SQL: SELECT ..." |
| **Info** | 正常流程 | "Server started", "Order created" |
| **Warn** | 可恢复异常 | "Retry failed (will retry)", "Slow query" |
| **Error** | 需要关注的错误 | "Database connection failed", "API timeout" |

---

## 🔍 日志查询示例

### Console 格式

```bash
# 查找所有错误
grep "ERROR" /var/log/agent-os.log

# 查找特定 log_id
grep "log_id.*abc-123" /var/log/agent-os.log
```

### JSON 格式（推荐）

```bash
# 使用 jq 查询
cat /var/log/agent-os.log | jq 'select(.level=="error")'
cat /var/log/agent-os.log | jq 'select(.log_id=="abc-123")'

# ELK/Loki 查询
level="error" AND log_id="abc-123"
```

---

## 📚 相关文档

- [Zap 文档](https://pkg.go.dev/go.uber.org/zap) - 当前底层实现
- [架构设计](../../docs/adr/XXX-logger-abstraction.md) - 设计决策（待创建）

---

**Last Updated**: 2026-08-27  
**Version**: 1.0.0
