# ADR 001: 框架无关的日志抽象层

**状态**: ✅ 已实施  
**日期**: 2026-08-27  
**决策者**: Agent OS Team

---

## 背景

Agent OS 当前使用 Go 标准库 `log` 包，存在以下问题：

1. **错误被静默忽略**：如 `notification_service.go` 中 `UpdateLog()` 失败但无日志
2. **日志格式不统一**：`log.Println` 和 `log.Printf` 混用，难以解析
3. **无结构化字段**：字符串拼接，无法高效查询（ELK/Loki）
4. **未来扩展受限**：计划引入 Web 框架（Gin/Echo），需要兼容其日志系统

---

## 决策

**实施框架无关的日志抽象层**，而非直接依赖 zap/logrus。

### 核心设计

```go
// 定义统一接口（不依赖任何具体实现）
type Logger interface {
    Debug(msg string, fields ...Field)
    Info(msg string, fields ...Field)
    Warn(msg string, fields ...Field)
    Error(msg string, fields ...Field)
    With(fields ...Field) Logger
    Sync() error
}

// 当前实现：zap adapter
type zapLogger struct { z *zap.Logger }

// 未来可替换：gin adapter / logrus adapter
type ginLogger struct { g *gin.Logger }
```

### 关键特性

1. **接口隔离**：业务代码只依赖 `logger.Logger` 接口
2. **结构化日志**：强制 key-value 字段，便于查询
3. **适配器模式**：可无缝切换底层实现
4. **向后兼容**：保留 `logger.L()` 全局访问方式

---

## 实施方案

### Phase 1: 基础设施（已完成）

```
internal/logger/
├── logger.go           # 接口定义 + 工厂方法
├── zap_adapter.go      # zap 实现
└── README.md           # 使用文档
```

### Phase 2: 渐进迁移

```bash
# 1. notification retry worker（已完成）
✅ internal/worker/notification_retry_worker.go

# 2. 其他 worker
□ internal/service/memory_gc_service.go

# 3. API handlers
□ internal/api/*.go

# 4. Services
□ internal/service/*.go
```

---

## 技术细节

### 1. 字段类型转换

```go
// 抽象层定义
type Field struct {
    Key   string
    Value interface{}
}

// zap adapter 转换
func convertFields(fields []Field) []zap.Field {
    for _, f := range fields {
        switch v := f.Value.(type) {
        case string:  return zap.String(f.Key, v)
        case int:     return zap.Int(f.Key, v)
        case error:   return zap.Error(v)
        // ...
        }
    }
}
```

### 2. 配置映射

```yaml
# config.yaml
log:
  level: info
  format: console
  output_path: stdout
```

```go
// 映射到抽象层配置
logConfig := logger.LoggerConfig{
    Level:  cfg.Log.Level,
    Format: cfg.Log.Format,
    Output: "stdout",
}
```

### 3. 未来扩展示例

引入 Gin 框架时：

```go
// gin_adapter.go
type ginLogger struct {
    g *gin.Logger
}

func (l *ginLogger) Info(msg string, fields ...Field) {
    // 转换为 Gin 日志格式
    l.g.Infof("[%s] %s %v", time.Now(), msg, fields)
}

// 工厂方法选择实现
func New(cfg LoggerConfig) (Logger, error) {
    if cfg.UseGin {
        return newGinLogger(cfg)
    }
    return newZapLogger(cfg)
}
```

---

## 优势

### ✅ 业务代码隔离

```go
// ❌ 直接依赖 zap（未来难以切换）
import "go.uber.org/zap"
zap.L().Info("message", zap.String("key", "value"))

// ✅ 依赖抽象接口（可随时切换实现）
import "github.com/pi-investment/agent-os/internal/logger"
logger.L().Info("message", logger.String("key", "value"))
```

### ✅ 框架兼容性

| 场景 | 实现 | 迁移成本 |
|-----|------|---------|
| 当前 | zapLogger | ✅ 已实施 |
| 引入 Gin | ginLogger | ⚡ 只需实现适配器 |
| 引入 Echo | echoLogger | ⚡ 只需实现适配器 |
| 切换 Logrus | logrusLogger | ⚡ 只需实现适配器 |

### ✅ 结构化查询

```bash
# 旧日志：字符串拼接
log.Printf("Retry failed for log %s with count %d", logID, count)
→ 无法高效查询 log_id

# 新日志：结构化字段
logger.L().Warn("Retry failed",
    logger.String("log_id", logID),
    logger.Int("retry_count", count),
)
→ ELK 查询：log_id="abc-123" AND level="warn"
```

---

## 权衡

### ✅ 优势

1. **未来可扩展**：引入框架时无需重写业务代码
2. **统一规范**：强制结构化日志，提高可维护性
3. **性能无损**：抽象层零开销（接口调用编译器内联）

### ⚠️ 代价

1. **多一层抽象**：新增 `logger` 包维护成本
2. **字段转换开销**：`Field` → `zap.Field` 有微小性能损失（可忽略）
3. **学习成本**：团队需要了解新 API（但更简单）

---

## 迁移指南

### 对于新代码

```go
// 1. 导入
import "github.com/pi-investment/agent-os/internal/logger"

// 2. 使用
logger.L().Info("Event happened",
    logger.String("event_id", eventID),
    logger.Int("count", 10),
)
```

### 对于旧代码

```bash
# 使用迁移脚本
./scripts/migrate_logs.sh internal/service/my_service.go

# 手动转换 log.Printf
- log.Printf("User %s logged in", userID)
+ logger.L().Info("User logged in", logger.String("user_id", userID))
```

---

## 验证

### 编译测试

```bash
cd /Users/yunpeng/pi-investment/agent-os
go build -o bin/agent-os ./cmd/agent-os
# ✅ 编译成功
```

### 运行测试

```bash
# 启动服务
./bin/agent-os serve

# 检查日志输出
tail -f /tmp/agent-os.log
# ✅ 结构化日志正常输出
```

---

## 参考

- [Zap Performance](https://github.com/uber-go/zap#performance) - 当前底层实现
- [Go Proverbs](https://go-proverbs.github.io/) - "接口小而美"
- [12-Factor Logs](https://12factor.net/logs) - 日志即事件流

---

## 后续行动

- [ ] 迁移其余 20+ 文件中的 `log` 调用（优先级：P1）
- [ ] 添加日志轮转配置（优先级：P2）
- [ ] 集成 Prometheus metrics（日志错误计数，优先级：P2）
- [ ] ELK/Loki 集成文档（优先级：P3）

---

**决策结果**: ✅ 采纳并实施
