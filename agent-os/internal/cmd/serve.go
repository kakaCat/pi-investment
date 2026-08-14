package cmd

import (
	"context"
	"database/sql"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/spf13/cobra"
	"github.com/pi-investment/agent-os/internal/api"
	"github.com/pi-investment/agent-os/internal/config"
	"github.com/pi-investment/agent-os/internal/repository"
	"github.com/pi-investment/agent-os/internal/service"
)

var serveCmd = &cobra.Command{
	Use:   "serve",
	Short: "Start HTTP API server",
	Long:  "Start the Agent OS HTTP API server for external applications to use",
	RunE: func(cmd *cobra.Command, args []string) error {
		port, _ := cmd.Flags().GetInt("port")
		host, _ := cmd.Flags().GetString("host")

		// Get config
		cfg := config.Get()

		// Build connection string
		connStr := fmt.Sprintf("host=%s port=%d user=%s password=%s dbname=%s sslmode=%s",
			cfg.Database.Host,
			cfg.Database.Port,
			cfg.Database.User,
			cfg.Database.Password,
			cfg.Database.DBName,
			cfg.Database.SSLMode,
		)

		// Connect to database
		db, err := sql.Open("postgres", connStr)
		if err != nil {
			return fmt.Errorf("failed to connect to database: %w", err)
		}
		defer db.Close()

		// Test connection
		if err := db.Ping(); err != nil {
			return fmt.Errorf("failed to ping database: %w", err)
		}

		// Create service
		repo := repository.NewNotificationRepository(db)
		svc := service.NewNotificationService(repo)

		// Create HTTP server
		server := api.NewHTTPServer(svc)

		// Start server in goroutine
		addr := fmt.Sprintf("%s:%d", host, port)
		go func() {
			fmt.Printf("🚀 Agent OS API Server starting on http://%s\n", addr)
			fmt.Printf("📚 API endpoints:\n")
			fmt.Printf("   POST   /api/v1/notifications/send\n")
			fmt.Printf("   GET    /api/v1/notifications/channels\n")
			fmt.Printf("   GET    /api/v1/notifications/logs\n")
			fmt.Printf("   GET    /api/v1/notifications/providers\n")
			fmt.Printf("   GET    /health\n")
			fmt.Printf("\n")

			if err := server.Start(addr); err != nil {
				fmt.Printf("❌ Server error: %v\n", err)
			}
		}()

		// Wait for interrupt signal
		quit := make(chan os.Signal, 1)
		signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
		<-quit

		fmt.Println("\n🛑 Shutting down server...")

		// Graceful shutdown
		ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()

		if err := server.Stop(ctx); err != nil {
			return fmt.Errorf("failed to stop server: %w", err)
		}

		fmt.Println("✅ Server stopped gracefully")
		return nil
	},
}

func init() {
	serveCmd.Flags().Int("port", 8080, "HTTP port")
	serveCmd.Flags().String("host", "0.0.0.0", "HTTP host")
	rootCmd.AddCommand(serveCmd)
}
