package service

import (
	"context"
	"time"

	"go.uber.org/zap"
)

// HealthChecker periodically checks agent health and marks stale agents offline
type HealthChecker struct {
	registryService RegistryService
	logger          *zap.Logger
	checkInterval   time.Duration
	heartbeatTimeout time.Duration
	stopCh          chan struct{}
}

// NewHealthChecker creates a new health checker
func NewHealthChecker(
	registryService RegistryService,
	logger *zap.Logger,
	checkInterval time.Duration,
	heartbeatTimeout time.Duration,
) *HealthChecker {
	return &HealthChecker{
		registryService:  registryService,
		logger:           logger,
		checkInterval:    checkInterval,
		heartbeatTimeout: heartbeatTimeout,
		stopCh:           make(chan struct{}),
	}
}

// Start begins the health check loop
func (h *HealthChecker) Start(ctx context.Context) {
	ticker := time.NewTicker(h.checkInterval)
	defer ticker.Stop()

	h.logger.Info("Health checker started",
		zap.Duration("check_interval", h.checkInterval),
		zap.Duration("heartbeat_timeout", h.heartbeatTimeout),
	)

	for {
		select {
		case <-ctx.Done():
			h.logger.Info("Health checker stopped (context cancelled)")
			return
		case <-h.stopCh:
			h.logger.Info("Health checker stopped")
			return
		case <-ticker.C:
			h.checkHealth()
		}
	}
}

// Stop stops the health checker
func (h *HealthChecker) Stop() {
	close(h.stopCh)
}

// checkHealth performs a health check
func (h *HealthChecker) checkHealth() {
	count, err := h.registryService.MarkStaleAgentsOffline(h.heartbeatTimeout)
	if err != nil {
		h.logger.Error("Failed to mark stale agents offline", zap.Error(err))
		return
	}

	if count > 0 {
		h.logger.Warn("Marked stale agents offline",
			zap.Int("count", count),
			zap.Duration("timeout", h.heartbeatTimeout),
		)
	}
}
