package service

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"

	"github.com/google/uuid"
	"github.com/pi-investment/agent-os/internal/domain"
	"github.com/pi-investment/agent-os/internal/repository"
)

type NotificationService struct {
	repo   *repository.NotificationRepository
	client *http.Client
}

func NewNotificationService(repo *repository.NotificationRepository) *NotificationService {
	return &NotificationService{
		repo: repo,
		client: &http.Client{
			Timeout: 10 * time.Second,
		},
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

	// 2. Get provider
	provider, err := s.repo.GetProvider(ctx, channel.ProviderID)
	if err != nil {
		return nil, fmt.Errorf("failed to get provider: %w", err)
	}
	if provider == nil {
		return &domain.SendResult{
			Success: false,
			Error:   "provider not found or disabled",
		}, nil
	}

	// 3. Create log entry
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

	// 4. Send message based on provider type
	var messageID string
	var sendErr error

	switch provider.Code {
	case "feishu":
		messageID, sendErr = s.sendFeishu(channel.Config, req)
	default:
		sendErr = fmt.Errorf("unsupported provider: %s", provider.Code)
	}

	// 5. Update log
	now := time.Now()
	if sendErr != nil {
		s.repo.UpdateLog(ctx, logID, "failed", "", sendErr.Error(), nil)
		return &domain.SendResult{
			LogID:   logID,
			Success: false,
			Error:   sendErr.Error(),
		}, nil
	}

	s.repo.UpdateLog(ctx, logID, "sent", messageID, "", &now)
	return &domain.SendResult{
		LogID:     logID,
		Success:   true,
		MessageID: messageID,
	}, nil
}

// sendFeishu sends a message to Feishu via webhook
func (s *NotificationService) sendFeishu(config map[string]interface{}, req *domain.SendRequest) (string, error) {
	webhook, ok := config["webhook"].(string)
	if !ok || webhook == "" {
		return "", fmt.Errorf("webhook URL not configured")
	}

	// Color mapping
	colorMap := map[string]string{
		"blue":   "blue",
		"green":  "green",
		"red":    "red",
		"orange": "orange",
		"grey":   "grey",
		"purple": "purple",
	}
	color := colorMap[req.Color]
	if color == "" {
		color = "blue"
	}

	// Build Feishu card
	card := map[string]interface{}{
		"msg_type": "interactive",
		"card": map[string]interface{}{
			"header": map[string]interface{}{
				"title": map[string]interface{}{
					"tag":     "plain_text",
					"content": req.Title,
				},
				"template": color,
			},
			"elements": []map[string]interface{}{
				{
					"tag": "div",
					"text": map[string]interface{}{
						"tag":     "lark_md",
						"content": req.Content,
					},
				},
			},
		},
	}

	// Marshal to JSON
	body, err := json.Marshal(card)
	if err != nil {
		return "", fmt.Errorf("failed to marshal card: %w", err)
	}

	// Send HTTP request
	resp, err := s.client.Post(webhook, "application/json", bytes.NewBuffer(body))
	if err != nil {
		return "", fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	// Read response
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("failed to read response: %w", err)
	}

	// Parse response
	var result map[string]interface{}
	if err := json.Unmarshal(respBody, &result); err != nil {
		return "", fmt.Errorf("failed to parse response: %w", err)
	}

	// Check result
	code, _ := result["code"].(float64)
	if code != 0 {
		msg, _ := result["msg"].(string)
		return "", fmt.Errorf("feishu error (code=%v): %s", code, msg)
	}

	// Extract message ID if available
	var messageID string
	if data, ok := result["data"].(map[string]interface{}); ok {
		if msgID, ok := data["message_id"].(string); ok {
			messageID = msgID
		}
	}

	return messageID, nil
}

// ListChannels lists all available channels
func (s *NotificationService) ListChannels(ctx context.Context) ([]*domain.NotificationChannel, error) {
	return s.repo.ListChannels(ctx)
}

// GetRecentLogs retrieves recent notification logs
func (s *NotificationService) GetRecentLogs(ctx context.Context, limit int) ([]*domain.NotificationLog, error) {
	return s.repo.GetRecentLogs(ctx, limit)
}
