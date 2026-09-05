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
	"github.com/pi-investment/agent-os/internal/kernel/scheduler"
	"github.com/pi-investment/agent-os/internal/logger"
	"github.com/pi-investment/agent-os/internal/repository"
	"github.com/pi-investment/agent-os/internal/service"
	"github.com/pi-investment/agent-os/internal/services"
	"github.com/pi-investment/agent-os/internal/storage/postgres"
	"github.com/pi-investment/agent-os/internal/worker"
	"github.com/pi-investment/agent-os/pkg/types"
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

		// Initialize logger (框架无关的抽象层)
		logConfig := logger.LoggerConfig{
			Level:       cfg.Log.Level,
			Format:      cfg.Log.Format,
			Output:      "stdout", // 从 config.yaml 的 output_path 映射
			Development: cfg.Log.Level == "debug",
		}
		if cfg.Log.OutputPath == "stderr" {
			logConfig.Output = "stderr"
		}
		if err := logger.InitGlobal(logConfig); err != nil {
			return fmt.Errorf("failed to initialize logger: %w", err)
		}
		defer logger.L().Sync()

		logger.L().Info("Agent OS starting",
			logger.String("version", "0.1.0"),
			logger.String("host", host),
			logger.Int("port", port),
		)

		// Build connection string for sql.DB (notification service) - use URL format
		connStr := fmt.Sprintf("postgres://%s@%s:%d/%s?sslmode=%s",
			cfg.Database.User,
			cfg.Database.Host,
			cfg.Database.Port,
			cfg.Database.DBName,
			cfg.Database.SSLMode,
		)
		// Add password if not empty
		if cfg.Database.Password != "" {
			connStr = fmt.Sprintf("postgres://%s:%s@%s:%d/%s?sslmode=%s",
				cfg.Database.User,
				cfg.Database.Password,
				cfg.Database.Host,
				cfg.Database.Port,
				cfg.Database.DBName,
				cfg.Database.SSLMode,
			)
		}

		// Debug: print connection string (mask password)
		fmt.Printf("DEBUG: Connection string: %s\n", connStr)

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

		// Debug: print pgx connection string (mask password)
		fmt.Printf("DEBUG: PGX Connection string: %s\n", pgxConnStr)

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

		// Initialize global postgres pool for scheduler
		if err := postgres.InitPool(ctx); err != nil {
			return fmt.Errorf("failed to initialize postgres pool: %w", err)
		}
		defer postgres.Close()

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

		// Start notification retry worker
		retryWorker := worker.NewNotificationRetryWorker(repo, svc)
		if err := retryWorker.Start(); err != nil {
			return fmt.Errorf("failed to start notification retry worker: %w", err)
		}
		defer retryWorker.Stop()

		// Create skill service
		skillService := services.NewSkillService(pool)
		skillHandler := handlers.NewSkillHandler(skillService)

		// Create Scheduler instance (service bindings from config.services
		// override the built-in defaults such as quantsys-v2)
		schedulerSvc := scheduler.New(&types.SchedulerConfig{
			MaxConcurrentTasks: 5,
			DefaultTimeout:     30 * time.Minute,
			MaxRetries:         2,
			RetryDelay:         5 * time.Second,
			Services:           cfg.Services,
		})

		// Start Scheduler
		if err := schedulerSvc.Start(ctx); err != nil {
			return fmt.Errorf("failed to start scheduler: %w", err)
		}
		defer schedulerSvc.Stop()

		// Create Scheduler Handler
		schedulerHandler := api.NewSchedulerHandler(schedulerSvc)

		// Create Decision Repository and Handler

		// Create Memory Repository and Handler

		// Create Event Repository and Handler

		// Create System Repository and Handler

		// Create Notification Repository and Handler

		// Create Profile Repository and Handler
		profileRepo := repository.NewProfileWebRepository(db)
		profileHandler := api.NewProfileHandler(profileRepo)
		notificationRepo := repository.NewNotificationWebRepository(db)
		notificationHandler := api.NewNotificationHandler(notificationRepo)
		systemRepo := repository.NewSystemWebRepository(db)
		systemHandler := api.NewSystemHandler(systemRepo)
		eventRepo := repository.NewEventWebRepository(db)
		eventHandler := api.NewEventHandler(eventRepo)
		memoryRepo := repository.NewMemoryWebRepository(db)
		memoryHandler := api.NewMemoryHandler(memoryRepo)
		
		// RFC 009: 启动 Memory GC 服务（每日 04:00 清理历史记录）
		gcService := service.NewMemoryGCService(db)
		go gcService.RunPeriodically(ctx)
		
		decisionRepo := repository.NewDecisionWebRepository(db)
		decisionHandler := api.NewDecisionHandler(decisionRepo)
		registryRepo := repository.NewRegistryWebRepository(db)
		registryHandler := api.NewRegistryHandler(registryRepo)

		// RFC 010: 启动心跳监控器（60s 检查间隔，60s 超时阈值）
		heartbeatMonitor := service.NewHeartbeatMonitor(
			registryRepo,
			60*time.Second,  // checkInterval
			60*time.Second,  // timeoutThreshold
			nil,             // use default logger
		)
		go func() {
			if err := heartbeatMonitor.Start(ctx); err != nil {
				logger.L().Error("Heartbeat monitor stopped", logger.String("error", err.Error()))
			}
		}()

		// Create HTTP server
		server := api.NewHTTPServer(svc, skillHandler, schedulerHandler, decisionHandler, memoryHandler, eventHandler, systemHandler, notificationHandler, profileHandler, registryHandler)

		// Start HTTP server in goroutine
		addr := fmt.Sprintf("%s:%d", host, port)
		go func() {
			fmt.Printf("🚀 Agent OS API Server starting on http://%s\n", addr)
			fmt.Printf("📚 API endpoints:\n")
			fmt.Printf("   POST   /api/v1/notifications/send\n")
			fmt.Printf("   GET    /api/v1/profile\n")
			fmt.Printf("   PUT    /api/v1/profile\n")
			fmt.Printf("   GET    /api/v1/profile/api-keys\n")
			fmt.Printf("   GET    /api/v1/profile/activity\n")
			fmt.Printf("   GET    /api/v1/notifications/channels\n")
			fmt.Printf("   GET    /api/v1/notifications/logs\n")
			fmt.Printf("   GET    /api/v1/notifications/providers\n")
			fmt.Printf("   GET    /api/v1/skills\n")
			fmt.Printf("   GET    /api/v1/skills/{id}\n")
			fmt.Printf("   POST   /api/v1/skills\n")
			fmt.Printf("   PUT    /api/v1/skills/{id}\n")
			fmt.Printf("   DELETE /api/v1/skills/{id}\n")
			fmt.Printf("   POST   /api/v1/scheduler/tasks\n")
			fmt.Printf("   GET    /api/v1/scheduler/tasks\n")
			fmt.Printf("   GET    /api/v1/scheduler/tasks/{id}\n")
			fmt.Printf("   PUT    /api/v1/scheduler/tasks/{id}\n")
			fmt.Printf("   DELETE /api/v1/scheduler/tasks/{id}\n")
			fmt.Printf("   POST   /api/v1/scheduler/tasks/{id}/trigger\n")
			fmt.Printf("   GET    /api/v1/scheduler/executions\n")
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
