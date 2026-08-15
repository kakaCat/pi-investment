package cmd

import (
	"context"
	"database/sql"
	"fmt"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/spf13/cobra"
	"github.com/pi-investment/agent-os/internal/api"
	"github.com/pi-investment/agent-os/internal/config"
	"github.com/pi-investment/agent-os/internal/events"
	"github.com/pi-investment/agent-os/internal/handlers"
	"github.com/pi-investment/agent-os/internal/repository"
	"github.com/pi-investment/agent-os/internal/service"
	"github.com/pi-investment/agent-os/internal/services"
)

var serveCmd = &cobra.Command{
	Use:   "serve",
	Short: "Start HTTP API server",
	Long:  "Start the Agent OS HTTP API server for external applications to use",
	RunE: func(cmd *cobra.Command, args []string) error {
		port, _ := cmd.Flags().GetInt("port")
		host, _ := cmd.Flags().GetString("host")
		wsPort, _ := cmd.Flags().GetInt("ws-port")

		// Get config
		cfg := config.Get()

		// Build connection string for sql.DB (notification service)
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

		// Build connection string for pgxpool (event bus)
		pgxConnStr := fmt.Sprintf("postgres://%s:%s@%s:%d/%s?sslmode=%s",
			cfg.Database.User,
			cfg.Database.Password,
			cfg.Database.Host,
			cfg.Database.Port,
			cfg.Database.DBName,
			cfg.Database.SSLMode,
		)

		// Create pgx connection pool for event bus
		ctx := context.Background()
		poolConfig, err := pgxpool.ParseConfig(pgxConnStr)
		if err != nil {
			return fmt.Errorf("failed to parse pgx config: %w", err)
		}

		pool, err := pgxpool.NewWithConfig(ctx, poolConfig)
		if err != nil {
			return fmt.Errorf("failed to create pgx pool: %w", err)
		}
		defer pool.Close()

		// Test pool connection
		if err := pool.Ping(ctx); err != nil {
			return fmt.Errorf("failed to ping database (pgx): %w", err)
		}

		// Initialize Event Bus
		eventBus := events.NewEventBus(pool)
		if err := eventBus.Start(ctx); err != nil {
			return fmt.Errorf("failed to start event bus: %w", err)
		}
		defer eventBus.Stop()

		// Set global event bus for publishers
		events.InitGlobalEventBus(eventBus)

		// Create notification service
		repo := repository.NewNotificationRepository(db)
		svc := service.NewNotificationService(repo)

		// Create skill service
		skillService := services.NewSkillService(pool)
		skillHandler := handlers.NewSkillHandler(skillService)

		// Create HTTP server
		server := api.NewHTTPServer(svc, skillHandler)

		// Start HTTP server in goroutine
		addr := fmt.Sprintf("%s:%d", host, port)
		go func() {
			fmt.Printf("🚀 Agent OS API Server starting on http://%s\n", addr)
			fmt.Printf("📚 API endpoints:\n")
			fmt.Printf("   POST   /api/v1/notifications/send\n")
			fmt.Printf("   GET    /api/v1/notifications/channels\n")
			fmt.Printf("   GET    /api/v1/notifications/logs\n")
			fmt.Printf("   GET    /api/v1/notifications/providers\n")
			fmt.Printf("   GET    /api/v1/skills\n")
			fmt.Printf("   GET    /api/v1/skills/{id}\n")
			fmt.Printf("   POST   /api/v1/skills\n")
			fmt.Printf("   PUT    /api/v1/skills/{id}\n")
			fmt.Printf("   DELETE /api/v1/skills/{id}\n")
			fmt.Printf("   GET    /health\n")
			fmt.Printf("\n")

			if err := server.Start(addr); err != nil {
				fmt.Printf("❌ Server error: %v\n", err)
			}
		}()

		// Start WebSocket server in goroutine
		wsAddr := fmt.Sprintf("%s:%d", host, wsPort)
		wsServer := events.NewWebSocketServer(eventBus, wsAddr)
		go func() {
			fmt.Printf("🔌 WebSocket Server starting on ws://%s/ws/events\n", wsAddr)
			fmt.Printf("📡 Event streaming:\n")
			fmt.Printf("   WS     ws://%s/ws/events?filters=task.*,decision.*\n", wsAddr)
			fmt.Printf("   HTTP   http://%s/api/v1/events/subscribe\n", wsAddr)
			fmt.Printf("\n")

			if err := wsServer.Start(); err != nil {
				fmt.Printf("❌ WebSocket server error: %v\n", err)
			}
		}()

		// Wait for interrupt signal
		quit := make(chan os.Signal, 1)
		signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
		<-quit

		fmt.Println("\n🛑 Shutting down servers...")

		// Graceful shutdown
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
		defer cancel()

		if err := server.Stop(shutdownCtx); err != nil {
			return fmt.Errorf("failed to stop server: %w", err)
		}

		fmt.Println("✅ Servers stopped gracefully")
		return nil
	},
}

func init() {
	serveCmd.Flags().Int("port", 8080, "HTTP port")
	serveCmd.Flags().String("host", "0.0.0.0", "HTTP host")
	serveCmd.Flags().Int("ws-port", 8081, "WebSocket port")
	rootCmd.AddCommand(serveCmd)
}
