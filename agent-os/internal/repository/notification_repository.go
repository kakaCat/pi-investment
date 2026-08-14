package repository

import (
	"context"
	"database/sql"
	"encoding/json"
	"time"

	"github.com/pi-investment/agent-os/internal/domain"
)

type NotificationRepository struct {
	db *sql.DB
}

func NewNotificationRepository(db *sql.DB) *NotificationRepository {
	return &NotificationRepository{db: db}
}

// GetChannelByCode retrieves a channel by its code
func (r *NotificationRepository) GetChannelByCode(ctx context.Context, code string) (*domain.NotificationChannel, error) {
	query := `
		SELECT
			c.id, c.provider_id, c.code, c.name, c.description,
			c.enabled, c.config, c.metadata, c.created_at, c.updated_at,
			p.code as provider_code, p.name as provider_name
		FROM notification_channels c
		JOIN notification_providers p ON c.provider_id = p.id
		WHERE c.code = $1 AND c.enabled = true
	`

	var channel domain.NotificationChannel
	var configJSON, metadataJSON []byte

	err := r.db.QueryRowContext(ctx, query, code).Scan(
		&channel.ID,
		&channel.ProviderID,
		&channel.Code,
		&channel.Name,
		&channel.Description,
		&channel.Enabled,
		&configJSON,
		&metadataJSON,
		&channel.CreatedAt,
		&channel.UpdatedAt,
		&channel.ProviderCode,
		&channel.ProviderName,
	)

	if err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, err
	}

	if err := json.Unmarshal(configJSON, &channel.Config); err != nil {
		return nil, err
	}
	if err := json.Unmarshal(metadataJSON, &channel.Metadata); err != nil {
		return nil, err
	}

	return &channel, nil
}

// GetProvider retrieves a provider by its ID
func (r *NotificationRepository) GetProvider(ctx context.Context, id string) (*domain.NotificationProvider, error) {
	query := `
		SELECT id, code, name, enabled, config, created_at, updated_at
		FROM notification_providers
		WHERE id = $1 AND enabled = true
	`

	var provider domain.NotificationProvider
	var configJSON []byte

	err := r.db.QueryRowContext(ctx, query, id).Scan(
		&provider.ID,
		&provider.Code,
		&provider.Name,
		&provider.Enabled,
		&configJSON,
		&provider.CreatedAt,
		&provider.UpdatedAt,
	)

	if err != nil {
		if err == sql.ErrNoRows {
			return nil, nil
		}
		return nil, err
	}

	if err := json.Unmarshal(configJSON, &provider.Config); err != nil {
		return nil, err
	}

	return &provider, nil
}

// CreateLog creates a new notification log entry
func (r *NotificationRepository) CreateLog(ctx context.Context, log *domain.NotificationLog) error {
	query := `
		INSERT INTO notification_logs
		(id, channel_id, title, content, status, metadata, created_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7)
	`

	metadataJSON, err := json.Marshal(log.Metadata)
	if err != nil {
		return err
	}

	_, err = r.db.ExecContext(ctx, query,
		log.ID,
		log.ChannelID,
		log.Title,
		log.Content,
		log.Status,
		metadataJSON,
		log.CreatedAt,
	)

	return err
}

// UpdateLog updates a notification log entry
func (r *NotificationRepository) UpdateLog(ctx context.Context, id, status, messageID, errorMsg string, sentAt *time.Time) error {
	query := `
		UPDATE notification_logs
		SET status = $2, message_id = $3, error = $4, sent_at = $5
		WHERE id = $1
	`

	_, err := r.db.ExecContext(ctx, query, id, status, messageID, errorMsg, sentAt)
	return err
}

// ListChannels retrieves all enabled channels
func (r *NotificationRepository) ListChannels(ctx context.Context) ([]*domain.NotificationChannel, error) {
	query := `
		SELECT
			c.id, c.provider_id, c.code, c.name, c.description,
			c.enabled, c.config, c.metadata, c.created_at, c.updated_at,
			p.code as provider_code, p.name as provider_name
		FROM notification_channels c
		JOIN notification_providers p ON c.provider_id = p.id
		WHERE c.enabled = true
		ORDER BY c.code
	`

	rows, err := r.db.QueryContext(ctx, query)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var channels []*domain.NotificationChannel

	for rows.Next() {
		var channel domain.NotificationChannel
		var configJSON, metadataJSON []byte

		err := rows.Scan(
			&channel.ID,
			&channel.ProviderID,
			&channel.Code,
			&channel.Name,
			&channel.Description,
			&channel.Enabled,
			&configJSON,
			&metadataJSON,
			&channel.CreatedAt,
			&channel.UpdatedAt,
			&channel.ProviderCode,
			&channel.ProviderName,
		)
		if err != nil {
			return nil, err
		}

		if err := json.Unmarshal(configJSON, &channel.Config); err != nil {
			return nil, err
		}
		if err := json.Unmarshal(metadataJSON, &channel.Metadata); err != nil {
			return nil, err
		}

		channels = append(channels, &channel)
	}

	return channels, rows.Err()
}

// GetRecentLogs retrieves recent notification logs
func (r *NotificationRepository) GetRecentLogs(ctx context.Context, limit int) ([]*domain.NotificationLog, error) {
	query := `
		SELECT id, channel_id, title, content, status, message_id, error, metadata, sent_at, created_at
		FROM notification_logs
		ORDER BY created_at DESC
		LIMIT $1
	`

	rows, err := r.db.QueryContext(ctx, query, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var logs []*domain.NotificationLog

	for rows.Next() {
		var log domain.NotificationLog
		var metadataJSON []byte
		var messageID, errorMsg sql.NullString
		var sentAt sql.NullTime

		err := rows.Scan(
			&log.ID,
			&log.ChannelID,
			&log.Title,
			&log.Content,
			&log.Status,
			&messageID,
			&errorMsg,
			&metadataJSON,
			&sentAt,
			&log.CreatedAt,
		)
		if err != nil {
			return nil, err
		}

		if messageID.Valid {
			log.MessageID = messageID.String
		}
		if errorMsg.Valid {
			log.Error = errorMsg.String
		}
		if sentAt.Valid {
			log.SentAt = &sentAt.Time
		}

		if err := json.Unmarshal(metadataJSON, &log.Metadata); err != nil {
			return nil, err
		}

		logs = append(logs, &log)
	}

	return logs, rows.Err()
}
