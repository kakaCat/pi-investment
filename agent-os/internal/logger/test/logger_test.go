package test

import (
	"testing"

	"github.com/pi-investment/agent-os/internal/logger"
)

func TestLoggerBasic(t *testing.T) {
	// 测试初始化
	cfg := logger.DefaultConfig()
	cfg.Level = "debug"
	cfg.Format = "console"
	
	if err := logger.InitGlobal(cfg); err != nil {
		t.Fatalf("Failed to init logger: %v", err)
	}
	defer logger.L().Sync()

	// 测试各种日志级别
	logger.L().Debug("Debug message", logger.String("test", "value"))
	logger.L().Info("Info message", logger.Int("count", 123))
	logger.L().Warn("Warn message", logger.Bool("flag", true))
	logger.L().Error("Error message", logger.Float64("rate", 0.95))

	t.Log("✅ Basic logging test passed")
}

func TestLoggerWithModule(t *testing.T) {
	cfg := logger.DefaultConfig()
	if err := logger.InitGlobal(cfg); err != nil {
		t.Fatalf("Failed to init logger: %v", err)
	}

	// 测试模块级 logger
	moduleLogger := logger.L().With(logger.String("module", "order"))
	moduleLogger.Info("Module log", logger.String("action", "create"))

	t.Log("✅ Module logger test passed")
}

func TestLoggerJSONFormat(t *testing.T) {
	cfg := logger.LoggerConfig{
		Level:  "info",
		Format: "json",
		Output: "stdout",
	}
	
	if err := logger.InitGlobal(cfg); err != nil {
		t.Fatalf("Failed to init logger: %v", err)
	}

	logger.L().Info("JSON test", 
		logger.String("user_id", "12345"),
		logger.Int("count", 100),
	)

	t.Log("✅ JSON format test passed")
}

func BenchmarkLogger(b *testing.B) {
	cfg := logger.DefaultConfig()
	cfg.Output = "stderr"
	logger.InitGlobal(cfg)
	
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		logger.L().Info("Benchmark message",
			logger.String("key", "value"),
			logger.Int("count", i),
		)
	}
}

func BenchmarkLoggerWithModule(b *testing.B) {
	cfg := logger.DefaultConfig()
	cfg.Output = "stderr"
	logger.InitGlobal(cfg)
	
	moduleLogger := logger.L().With(logger.String("module", "test"))
	
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		moduleLogger.Info("Benchmark message", logger.Int("count", i))
	}
}
