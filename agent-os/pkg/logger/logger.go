package logger

import (
	"fmt"

	"github.com/pi-investment/agent-os/internal/config"
	"go.uber.org/zap"
	"go.uber.org/zap/zapcore"
)

// Logger wraps zap logger
type Logger struct {
	*zap.Logger
}

// New creates a new logger instance
func New(cfg config.LogConfig) (*Logger, error) {
	var zapCfg zap.Config

	// Set log level
	level, err := zapcore.ParseLevel(cfg.Level)
	if err != nil {
		return nil, fmt.Errorf("invalid log level: %w", err)
	}

	// Configure based on format
	if cfg.Format == "json" {
		zapCfg = zap.NewProductionConfig()
	} else {
		zapCfg = zap.NewDevelopmentConfig()
	}

	zapCfg.Level = zap.NewAtomicLevelAt(level)

	// Set output path
	if cfg.OutputPath != "" && cfg.OutputPath != "stdout" {
		zapCfg.OutputPaths = []string{cfg.OutputPath}
	}

	// Build logger
	l, err := zapCfg.Build()
	if err != nil {
		return nil, fmt.Errorf("failed to build logger: %w", err)
	}

	return &Logger{Logger: l}, nil
}

// Default returns a default logger
func Default() *Logger {
	l, _ := zap.NewProduction()
	return &Logger{Logger: l}
}

var globalLogger *zap.SugaredLogger

func init() {
	l, _ := zap.NewProduction()
	globalLogger = l.Sugar()
}

// Info logs an info message
func Info(msg string, keysAndValues ...interface{}) {
	globalLogger.Infow(msg, keysAndValues...)
}

// Error logs an error message
func Error(msg string, keysAndValues ...interface{}) {
	globalLogger.Errorw(msg, keysAndValues...)
}

// Debug logs a debug message
func Debug(msg string, keysAndValues ...interface{}) {
	globalLogger.Debugw(msg, keysAndValues...)
}

// Warn logs a warning message
func Warn(msg string, keysAndValues ...interface{}) {
	globalLogger.Warnw(msg, keysAndValues...)
}
