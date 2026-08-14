package service

import (
	"context"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/pi-investment/agent-os/internal/domain"
	"github.com/pi-investment/agent-os/internal/provider"
	"github.com/pi-investment/agent-os/internal/repository"
)

type NotificationService struct {
	repo *repository.NotificationRepository
}

func NewNotificationService(repo *repository.NotificationRepository) *NotificationService {
	return &NotificationService{
		repo: repo,
	}
}

// Send sends a notification to the specified channel
func (s *NotificationService) Send(ctx context.Context, req *domain.SendRequest) (*domain.SendResult, error) {
	// 1. Get channel from database
	channel, err := s.repo.GetChannelByCode(ctx, req.Channel)
	if err != nil {
		return nil, fmt.Errorf("failed to get channel: %w", err)
	}
	if channel == nil {
		return &domain.SendResult{
			Success: false,
			Error:   fmt.Sprintf("channel '%s' not found or disabled", req.Channel),
		}, nil
	}

	// 2. Get provider config
	providerConfig, err := s.repo.GetProvider(ctx, channel.ProviderID)
	if err != nil {
		return nil, fmt.Errorf("failed to get provider: %w", err)
	}
	if providerConfig == nil {
		return &domain.SendResult{
			Success: false,
			Error:   "provider not found or disabled",
		}, nil
	}

	// 3. Get provider from registry
	providerImpl, err := provider.Get(providerConfig.Code)
	if err != nil {
		return &domain.SendResult{
			Success: false,
			Error:   fmt.Sprintf("provider '%s' not registered: %v", providerConfig.Code, err),
		}, nil
	}

	// 4. Create log entry
	logID := uuid.New().String()
	log := &domain.NotificationLog{
		ID:        logID,
		ChannelID: channel.ID,
		Title:     req.Title,
		Content:   req.Content,
		Status:    "pending",
		Metadata:  req.Metadata,
		CreatedAt: time.Now(),
	}

	if err := s.repo.CreateLog(ctx, log); err != nil {
		return nil, fmt.Errorf("failed to create log: %w", err)
	}

	// 5. Build message
	msg := &provider.Message{
		Title:    req.Title,
		Content:  req.Content,
		Format:   "markdown",
		Priority: req.Urgency,
		Color:    req.Color,
		Metadata: req.Metadata,
	}

	// 6. Send via provider
	result, err := providerImpl.Send(ctx, channel.Config, msg)
	if err != nil {
		s.repo.UpdateLog(ctx, logID, "failed", "", err.Error(), nil)
		return &domain.SendResult{
			LogID:   logID,
			Success: false,
			Error:   err.Error(),
		}, nil
	}

	if !result.Success {
		errorMsg := ""
		if result.Error != nil {
			errorMsg = result.Error.Error()
		}
		s.repo.UpdateLog(ctx, logID, "failed", "", errorMsg, nil)
		return &domain.SendResult{
			LogID:   logID,
			Success: false,
			Error:   errorMsg,
		}, nil
	}

	// 7. Update log as success
	now := time.Now()
	s.repo.UpdateLog(ctx, logID, "sent", result.MessageID, "", &now)

	return &domain.SendResult{
		LogID:     logID,
		Success:   true,
		MessageID: result.MessageID,
	}, nil
}

// ListChannels lists all available channels
func (s *NotificationService) ListChannels(ctx context.Context) ([]*domain.NotificationChannel, error) {
	return s.repo.ListChannels(ctx)
}

// GetRecentLogs retrieves recent notification logs
func (s *NotificationService) GetRecentLogs(ctx context.Context, limit int) ([]*domain.NotificationLog, error) {
	return s.repo.GetRecentLogs(ctx, limit)
}
