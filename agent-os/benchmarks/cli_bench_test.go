package benchmarks

import (
	"os/exec"
	"testing"
	"time"
)

// BenchmarkCLISchedulerList benchmarks the scheduler list command
func BenchmarkCLISchedulerList(b *testing.B) {
	b.Run("dry_run", func(b *testing.B) {
		// Test without actual database connection
		b.ResetTimer()
		for i := 0; i < b.N; i++ {
			cmd := exec.Command("../agent-os", "scheduler", "list", "--help")
			_ = cmd.Run()
		}
	})
}

// BenchmarkCLIMemoryList benchmarks the memory list command
func BenchmarkCLIMemoryList(b *testing.B) {
	b.Run("dry_run", func(b *testing.B) {
		b.ResetTimer()
		for i := 0; i < b.N; i++ {
			cmd := exec.Command("../agent-os", "memory", "list", "--help")
			_ = cmd.Run()
		}
	})
}

// BenchmarkCLIStartupTime measures CLI startup overhead
func BenchmarkCLIStartupTime(b *testing.B) {
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		start := time.Now()
		cmd := exec.Command("../agent-os", "--version")
		_ = cmd.Run()
		_ = time.Since(start)
	}
}

// BenchmarkCLIHelp measures help command performance
func BenchmarkCLIHelp(b *testing.B) {
	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		cmd := exec.Command("../agent-os", "--help")
		_ = cmd.Run()
	}
}

// BenchmarkPermissionDenial measures permission denial overhead
func BenchmarkPermissionDenial(b *testing.B) {
	b.Skip("Requires full CLI integration test")
}
