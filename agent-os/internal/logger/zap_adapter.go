package logger

import (
	"context"
	"os"

	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
)

// zapLogger zap 适配器（实现 Logger 接口）
type zapLogger struct {
	z *zap.Logger
}

// newZapLogger 创建 zap logger
func newZapLogger(cfg LoggerConfig) (Logger, error) {
	// 1. 解析日志级别
	level := zapcore.InfoLevel
	switch cfg.Level {
	case "debug":
		level = zapcore.DebugLevel
	case "info":
		level = zapcore.InfoLevel
	case "warn":
		level = zapcore.WarnLevel
	case "error":
		level = zapcore.ErrorLevel
	}

	// 2. 配置输出格式
	encoderConfig := zap.NewProductionEncoderConfig()
	if cfg.Development {
		encoderConfig = zap.NewDevelopmentEncoderConfig()
		encoderConfig.EncodeLevel = zapcore.CapitalColorLevelEncoder // 彩色输出
	}
	encoderConfig.EncodeTime = zapcore.ISO8601TimeEncoder // 时间格式

	var encoder zapcore.Encoder
	if cfg.Format == "json" {
		encoder = zapcore.NewJSONEncoder(encoderConfig)
	} else {
		encoder = zapcore.NewConsoleEncoder(encoderConfig)
	}

	// 3. 配置输出目标
	var writer zapcore.WriteSyncer
	switch cfg.Output {
	case "stderr":
		writer = zapcore.AddSync(os.Stderr)
	case "file":
		file, err := os.OpenFile(cfg.FilePath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
		if err != nil {
			return nil, err
		}
		writer = zapcore.AddSync(file)
	default: // stdout
		writer = zapcore.AddSync(os.Stdout)
	}

	// 4. 创建 zap logger
	core := zapcore.NewCore(encoder, writer, level)
	z := zap.New(core, zap.AddCaller(), zap.AddStacktrace(zapcore.ErrorLevel))

	return &zapLogger{z: z}, nil
}

// 实现 Logger 接口

func (l *zapLogger) Debug(msg string, fields ...Field) {
	l.z.Debug(msg, convertFields(fields)...)
}

func (l *zapLogger) Info(msg string, fields ...Field) {
	l.z.Info(msg, convertFields(fields)...)
}

func (l *zapLogger) Warn(msg string, fields ...Field) {
	l.z.Warn(msg, convertFields(fields)...)
}

func (l *zapLogger) Error(msg string, fields ...Field) {
	l.z.Error(msg, convertFields(fields)...)
}

func (l *zapLogger) DebugContext(ctx context.Context, msg string, fields ...Field) {
	// 可从 ctx 提取 trace_id 等
	l.z.Debug(msg, convertFields(fields)...)
}

func (l *zapLogger) InfoContext(ctx context.Context, msg string, fields ...Field) {
	l.z.Info(msg, convertFields(fields)...)
}

func (l *zapLogger) WarnContext(ctx context.Context, msg string, fields ...Field) {
	l.z.Warn(msg, convertFields(fields)...)
}

func (l *zapLogger) ErrorContext(ctx context.Context, msg string, fields ...Field) {
	l.z.Error(msg, convertFields(fields)...)
}

func (l *zapLogger) With(fields ...Field) Logger {
	return &zapLogger{z: l.z.With(convertFields(fields)...)}
}

func (l *zapLogger) Sync() error {
	return l.z.Sync()
}

// convertFields 转换 Field → zap.Field
func convertFields(fields []Field) []zap.Field {
	zapFields := make([]zap.Field, len(fields))
	for i, f := range fields {
		switch v := f.Value.(type) {
		case string:
			zapFields[i] = zap.String(f.Key, v)
		case int:
			zapFields[i] = zap.Int(f.Key, v)
		case int64:
			zapFields[i] = zap.Int64(f.Key, v)
		case float64:
			zapFields[i] = zap.Float64(f.Key, v)
		case bool:
			zapFields[i] = zap.Bool(f.Key, v)
		case error:
			zapFields[i] = zap.Error(v)
		default:
			zapFields[i] = zap.Any(f.Key, v)
		}
	}
	return zapFields
}
