package repository

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/google/uuid"
	"github.com/pi-investment/agent-os/internal/domain"
)

// NotificationWebRepository Web API 通知仓储接口
type NotificationWebRepository interface {
	GetChannels(ctx context.Context) ([]*domain.NotificationChannelWeb, error)
	GetProviders(ctx context.Context) ([]*domain.NotificationProviderWeb, error)
	GetLogs(ctx context.Context, req domain.NotificationLogsRequest) ([]*domain.NotificationLogWeb, error)
	SendNotification(ctx context.Context, req domain.SendNotificationRequest) error
}

type notificationWebRepository struct {
	db *sql.DB
}

// NewNotificationWebRepository 创建 Web API 通知仓储
func NewNotificationWebRepository(db *sql.DB) NotificationWebRepository {
	return &notificationWebRepository{db: db}
}

// GetChannels 获取所有通知渠道
func (r *notificationWebRepository) GetChannels(ctx context.Context) ([]*domain.NotificationChannelWeb, error) {
	query := `SELECT id, provider_id, code, name, description, enabled, config, created_at, updated_at
	          FROM notification_channels
	          ORDER BY created_at`
	
	rows, err := r.db.QueryContext(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("failed to query channels: %w", err)
	}
	defer rows.Close()
	
	var channels []*domain.NotificationChannelWeb
	for rows.Next() {
		var c domain.NotificationChannelWeb
		err := rows.Scan(
			&c.ID, &c.ProviderID, &c.Code, &c.Name, &c.Description,
			&c.Enabled, &c.Config, &c.CreatedAt, &c.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan channel: %w", err)
		}
		channels = append(channels, &c)
	}
	
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows iteration error: %w", err)
	}
	
	return channels, nil
}

// GetProviders 获取所有通知提供商
func (r *notificationWebRepository) GetProviders(ctx context.Context) ([]*domain.NotificationProviderWeb, error) {
	query := `SELECT id, code, name, enabled, created_at, updated_at
	          FROM notification_providers
	          ORDER BY created_at`
	
	rows, err := r.db.QueryContext(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("failed to query providers: %w", err)
	}
	defer rows.Close()
	
	var providers []*domain.NotificationProviderWeb
	for rows.Next() {
		var p domain.NotificationProviderWeb
		err := rows.Scan(&p.ID, &p.Code, &p.Name, &p.Enabled, &p.CreatedAt, &p.UpdatedAt)
		if err != nil {
			return nil, fmt.Errorf("failed to scan provider: %w", err)
		}
		providers = append(providers, &p)
	}
	
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows iteration error: %w", err)
	}
	
	return providers, nil
}

// GetLogs 获取通知日志
func (r *notificationWebRepository) GetLogs(ctx context.Context, req domain.NotificationLogsRequest) ([]*domain.NotificationLogWeb, error) {
	query := `SELECT id, channel_id, status, title, content, message_id, error, metadata, sent_at, created_at
	          FROM notification_logs WHERE 1=1`
	
	args := []interface{}{}
	argIndex := 1
	
	if req.Status != "" {
		query += fmt.Sprintf(" AND status = $%d", argIndex)
		args = append(args, req.Status)
		argIndex++
	}
	
	query += " ORDER BY created_at DESC"
	
	if req.Limit > 0 {
		query += fmt.Sprintf(" LIMIT $%d", argIndex)
		args = append(args, req.Limit)
	} else {
		query += " LIMIT 100"
	}
	
	rows, err := r.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to query logs: %w", err)
	}
	defer rows.Close()
	
	var logs []*domain.NotificationLogWeb
	for rows.Next() {
		var l domain.NotificationLogWeb
		err := rows.Scan(
			&l.ID, &l.ChannelID, &l.Status, &l.Title, &l.Content,
			&l.MessageID, &l.Error, &l.Metadata, &l.SentAt, &l.CreatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan log: %w", err)
		}
		logs = append(logs, &l)
	}
	
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows iteration error: %w", err)
	}
	
	return logs, nil
}

// SendNotification 发送通知（记录到日志）
func (r *notificationWebRepository) SendNotification(ctx context.Context, req domain.SendNotificationRequest) error {
	// 查找渠道
	var channelID uuid.UUID
	err := r.db.QueryRowContext(ctx,
		"SELECT id FROM notification_channels WHERE code = $1 AND enabled = true",
		req.Channel,
	).Scan(&channelID)
	
	if err == sql.ErrNoRows {
		return fmt.Errorf("channel not found or disabled: %s", req.Channel)
	}
	if err != nil {
		return fmt.Errorf("failed to find channel: %w", err)
	}
	
	// 插入日志（pending 状态）
	_, err = r.db.ExecContext(ctx,
		`INSERT INTO notification_logs (channel_id, status, title, content)
		 VALUES ($1, 'pending', $2, $3)`,
		channelID, req.Title, req.Content,
	)
	if err != nil {
		return fmt.Errorf("failed to create notification log: %w", err)
	}
	
	return nil
}
