package logger

import "context"

// Logger 日志接口（框架无关）
// 设计原则：
// 1. 不依赖任何具体实现（zap/logrus/框架自带）
// 2. 支持结构化日志（key-value pairs）
// 3. 支持上下文传递（trace ID 等）
type Logger interface {
	// 基础日志方法
	Debug(msg string, fields ...Field)
	Info(msg string, fields ...Field)
	Warn(msg string, fields ...Field)
	Error(msg string, fields ...Field)

	// 带上下文的日志方法（用于分布式追踪）
	DebugContext(ctx context.Context, msg string, fields ...Field)
	InfoContext(ctx context.Context, msg string, fields ...Field)
	WarnContext(ctx context.Context, msg string, fields ...Field)
	ErrorContext(ctx context.Context, msg string, fields ...Field)

	// 创建子 logger（用于模块级日志）
	With(fields ...Field) Logger

	// 同步刷新缓冲区（程序退出时调用）
	Sync() error
}

// Field 结构化日志字段
type Field struct {
	Key   string
	Value interface{}
}

// 便捷的字段构造函数
func String(key, val string) Field {
	return Field{Key: key, Value: val}
}

func Int(key string, val int) Field {
	return Field{Key: key, Value: val}
}

func Int64(key string, val int64) Field {
	return Field{Key: key, Value: val}
}

func Float64(key string, val float64) Field {
	return Field{Key: key, Value: val}
}

func Bool(key string, val bool) Field {
	return Field{Key: key, Value: val}
}

func Any(key string, val interface{}) Field {
	return Field{Key: key, Value: val}
}

func Error(err error) Field {
	return Field{Key: "error", Value: err}
}

// LoggerConfig 日志配置
type LoggerConfig struct {
	// Level 日志级别：debug/info/warn/error
	Level string

	// Format 输出格式：json/console
	Format string

	// Output 输出目标：stdout/stderr/file
	Output string

	// FilePath 日志文件路径（当 Output=file 时）
	FilePath string

	// Development 开发模式（更人性化的输出）
	Development bool
}

// DefaultConfig 返回默认配置
func DefaultConfig() LoggerConfig {
	return LoggerConfig{
		Level:       "info",
		Format:      "console",
		Output:      "stdout",
		Development: false,
	}
}

// New 创建 logger 实例（工厂方法）
// 未来可根据配置返回不同实现（zap/logrus/框架自带）
func New(cfg LoggerConfig) (Logger, error) {
	// 当前默认使用 zap 实现
	return newZapLogger(cfg)
}

// global logger instance
var globalLogger Logger

// InitGlobal 初始化全局 logger
func InitGlobal(cfg LoggerConfig) error {
	logger, err := New(cfg)
	if err != nil {
		return err
	}
	globalLogger = logger
	return nil
}

// L 返回全局 logger（类似 zap.L()）
func L() Logger {
	if globalLogger == nil {
		// 如果未初始化，返回默认 logger
		globalLogger, _ = New(DefaultConfig())
	}
	return globalLogger
}
