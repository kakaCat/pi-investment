package postgres

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/pi-investment/agent-os/internal/config"
	"github.com/pi-investment/agent-os/pkg/logger"
)

var (
	pool *pgxpool.Pool
	once sync.Once
)

// InitPool initializes the database connection pool
func InitPool(ctx context.Context) error {
	var initErr error
	once.Do(func() {
		cfg := config.Get()
		connStr := fmt.Sprintf(
			"host=%s port=%d user=%s password=%s dbname=%s sslmode=%s",
			cfg.Database.Host,
			cfg.Database.Port,
			cfg.Database.User,
			cfg.Database.Password,
			cfg.Database.DBName,
			cfg.Database.SSLMode,
		)

		poolConfig, err := pgxpool.ParseConfig(connStr)
		if err != nil {
			initErr = fmt.Errorf("failed to parse connection string: %w", err)
			return
		}

		// Configure pool
		poolConfig.MaxConns = 25
		poolConfig.MinConns = 5
		poolConfig.MaxConnLifetime = time.Hour
		poolConfig.MaxConnIdleTime = 30 * time.Minute
		poolConfig.HealthCheckPeriod = time.Minute

		pool, err = pgxpool.NewWithConfig(ctx, poolConfig)
		if err != nil {
			initErr = fmt.Errorf("failed to create connection pool: %w", err)
			return
		}

		// Test connection
		if err := pool.Ping(ctx); err != nil {
			pool.Close()
			pool = nil
			initErr = fmt.Errorf("failed to ping database: %w", err)
			return
		}

		logger.Info("Database connection pool initialized",
			"host", cfg.Database.Host,
			"port", cfg.Database.Port,
			"dbname", cfg.Database.DBName)
	})

	return initErr
}

// GetPool returns the database connection pool
func GetPool() *pgxpool.Pool {
	if pool == nil {
		panic("database pool not initialized. Call InitPool first")
	}
	return pool
}

// Close closes the database connection pool
func Close() {
	if pool != nil {
		pool.Close()
		logger.Info("Database connection pool closed")
	}
}
