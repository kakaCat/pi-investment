package benchmarks

import (
	"context"
	"testing"
	"time"

	"github.com/pi-investment/agent-os/internal/auth"
	"github.com/pi-investment/agent-os/internal/middleware"
	"github.com/spf13/cobra"
)

// BenchmarkAuthMiddleware benchmarks the authentication middleware
func BenchmarkAuthMiddleware(b *testing.B) {
	// Initialize auth manager
	err := middleware.InitAuth("../config/permissions.yaml")
	if err != nil {
		b.Fatalf("Failed to initialize auth: %v", err)
	}

	// Create test command
	cmd := &cobra.Command{
		Use: "test",
		RunE: func(cmd *cobra.Command, args []string) error {
			return nil
		},
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_ = middleware.AuthMiddleware(cmd, []string{})
	}
}

// BenchmarkPermissionCheck benchmarks permission checking
func BenchmarkPermissionCheck(b *testing.B) {
	authManager, err := auth.NewAuthManager("../config/permissions.yaml")
	if err != nil {
		b.Fatalf("Failed to initialize auth: %v", err)
	}

	b.ResetTimer()
	for i := 0; i < b.N; i++ {
		_ = authManager.CheckPermission("fin-agent", "scheduler:list")
	}
}

// BenchmarkWildcardMatching benchmarks wildcard permission matching
func BenchmarkWildcardMatching(b *testing.B) {
	authManager, err := auth.NewAuthManager("../config/permissions.yaml")
	if err != nil {
		b.Fatalf("Failed to initialize auth: %v", err)
	}

	b.Run("exact_match", func(b *testing.B) {
		for i := 0; i < b.N; i++ {
			_ = authManager.CheckPermission("system-admin", "scheduler:list")
		}
	})

	b.Run("wildcard_match", func(b *testing.B) {
		for i := 0; i < b.N; i++ {
			_ = authManager.CheckPermission("fin-agent", "scheduler:trigger")
		}
	})
}

// BenchmarkConcurrentAuthChecks benchmarks concurrent permission checks
func BenchmarkConcurrentAuthChecks(b *testing.B) {
	authManager, err := auth.NewAuthManager("../config/permissions.yaml")
	if err != nil {
		b.Fatalf("Failed to initialize auth: %v", err)
	}

	b.RunParallel(func(pb *testing.PB) {
		for pb.Next() {
			_ = authManager.CheckPermission("fin-agent", "scheduler:list")
		}
	})
}

// BenchmarkEventPublish benchmarks event publishing (without DB)
func BenchmarkEventPublish(b *testing.B) {
	// This would require a test database connection
	// Skipping for now as it's an integration test
	b.Skip("Requires database connection")
}

// BenchmarkMemoryAllocation tracks memory allocations
func BenchmarkMemoryAllocation(b *testing.B) {
	authManager, err := auth.NewAuthManager("../config/permissions.yaml")
	if err != nil {
		b.Fatalf("Failed to initialize auth: %v", err)
	}

	b.ReportAllocs()
	b.ResetTimer()

	for i := 0; i < b.N; i++ {
		_ = authManager.CheckPermission("fin-agent", "scheduler:list")
	}
}

// BenchmarkContextCreation benchmarks context creation overhead
func BenchmarkContextCreation(b *testing.B) {
	b.Run("background_context", func(b *testing.B) {
		for i := 0; i < b.N; i++ {
			ctx := context.Background()
			_ = ctx
		}
	})

	b.Run("with_timeout", func(b *testing.B) {
		for i := 0; i < b.N; i++ {
			ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
			_ = ctx
			cancel()
		}
	})

	b.Run("with_cancel", func(b *testing.B) {
		for i := 0; i < b.N; i++ {
			ctx, cancel := context.WithCancel(context.Background())
			_ = ctx
			cancel()
		}
	})
}
