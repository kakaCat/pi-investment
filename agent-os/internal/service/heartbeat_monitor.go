package service

import (
	"context"
	"fmt"
	"time"

	"github.com/pi-investment/agent-os/internal/domain"
	"github.com/pi-investment/agent-os/internal/logger"
	"github.com/pi-investment/agent-os/internal/repository"
)

// HeartbeatMonitor 心跳监控器（RFC 010）
// 定期扫描超时窗口，标记为 timeout 并触发告警
type HeartbeatMonitor struct {
	repo             repository.RegistryWebRepository
	checkInterval    time.Duration
	timeoutThreshold time.Duration
	logger           logger.Logger
}

// NewHeartbeatMonitor 创建心跳监控器
func NewHeartbeatMonitor(
	repo repository.RegistryWebRepository,
	checkInterval time.Duration,
	timeoutThreshold time.Duration,
	log logger.Logger,
) *HeartbeatMonitor {
	if checkInterval == 0 {
		checkInterval = 60 * time.Second // 默认 60 秒检查一次
	}
	if timeoutThreshold == 0 {
		timeoutThreshold = 60 * time.Second // 默认 60 秒超时
	}
	if log == nil {
		log = logger.L()
	}

	return &HeartbeatMonitor{
		repo:             repo,
		checkInterval:    checkInterval,
		timeoutThreshold: timeoutThreshold,
		logger:           log,
	}
}

// Start 启动监控（阻塞）
func (m *HeartbeatMonitor) Start(ctx context.Context) error {
	m.logger.Info("Started heartbeat monitor",
		logger.String("check_interval", m.checkInterval.String()),
		logger.String("timeout_threshold", m.timeoutThreshold.String()),
	)

	ticker := time.NewTicker(m.checkInterval)
	defer ticker.Stop()

	// 启动后立即执行一次
	if err := m.check(ctx); err != nil {
		m.logger.Error("Initial check failed", logger.Error(err))
	}

	for {
		select {
		case <-ctx.Done():
			m.logger.Info("Heartbeat monitor stopped")
			return ctx.Err()
		case <-ticker.C:
			if err := m.check(ctx); err != nil {
				m.logger.Error("Check failed", logger.Error(err))
			}
		}
	}
}

// check 执行一次超时检查
func (m *HeartbeatMonitor) check(ctx context.Context) error {
	// 查询所有非 offline/timeout 的 agent
	agents, err := m.repo.ListActive(ctx, "")
	if err != nil {
		return fmt.Errorf("failed to list active agents: %w", err)
	}

	now := time.Now()
	timeoutCount := 0

	for _, agent := range agents {
		// 跳过已经 offline/timeout 的
		if agent.Status == "offline" || agent.Status == "timeout" {
			continue
		}

		// 检查心跳是否超时
		timeSinceHeartbeat := now.Sub(agent.LastHeartbeatAt)
		if timeSinceHeartbeat > m.timeoutThreshold {
			m.logger.Warn("Timeout detected",
				logger.String("agent_id", agent.AgentID),
				logger.String("role", agent.AgentType),
				logger.String("duration", timeSinceHeartbeat.String()),
			)

			// 标记为 timeout
			if err := m.repo.MarkTimeout(ctx, agent.AgentID); err != nil {
				m.logger.Error("Failed to mark timeout",
					logger.String("agent_id", agent.AgentID),
					logger.Error(err),
				)
				continue
			}

			timeoutCount++

			// TODO: 发送飞书告警
			// m.sendAlert(agent)
		}
	}

	if timeoutCount > 0 {
		m.logger.Info("Marked agents as timeout", logger.Int("count", timeoutCount))
	}

	return nil
}

// sendAlert 发送告警（TODO: 集成 notification service）
func (m *HeartbeatMonitor) sendAlert(agent *domain.AgentWeb) {
	// 预留：发送飞书告警
	m.logger.Warn("Heartbeat timeout alert",
		logger.String("agent_id", agent.AgentID),
		logger.String("role", agent.AgentType),
	)
}
