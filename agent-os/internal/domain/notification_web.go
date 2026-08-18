package domain

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

// NotificationChannelWeb 通知渠道 Web 视图
type NotificationChannelWeb struct {
	ID          uuid.UUID       `json:"id" db:"id"`
	ProviderID  uuid.UUID       `json:"provider_id" db:"provider_id"`
	Code        string          `json:"code" db:"code"`
	Name        string          `json:"name" db:"name"`
	Description *string         `json:"description,omitempty" db:"description"`
	Enabled     bool            `json:"enabled" db:"enabled"`
	Config      json.RawMessage `json:"config" db:"config"`
	CreatedAt   time.Time       `json:"created_at" db:"created_at"`
	UpdatedAt   time.Time       `json:"updated_at" db:"updated_at"`
}

// NotificationProviderWeb 通知提供商 Web 视图
// NotificationProviderWeb 通知提供商 Web 视图
type NotificationProviderWeb struct {
	ID        uuid.UUID `json:"id" db:"id"`
	Code      string    `json:"code" db:"code"`
	Name      string    `json:"name" db:"name"`
	Enabled   bool      `json:"enabled" db:"enabled"`
	CreatedAt time.Time `json:"created_at" db:"created_at"`
	UpdatedAt time.Time `json:"updated_at" db:"updated_at"`
}

// NotificationLogWeb 通知日志 Web 视图
type NotificationLogWeb struct {
	ID        uuid.UUID       `json:"id" db:"id"`
	ChannelID uuid.UUID       `json:"channel_id" db:"channel_id"`
	Status    string          `json:"status" db:"status"`
	Title     *string         `json:"title,omitempty" db:"title"`
	Content   *string         `json:"content,omitempty" db:"content"`
	MessageID *string         `json:"message_id,omitempty" db:"message_id"`
	Error     *string         `json:"error,omitempty" db:"error"`
	Metadata  json.RawMessage `json:"metadata,omitempty" db:"metadata"`
	SentAt    *time.Time      `json:"sent_at,omitempty" db:"sent_at"`
	CreatedAt time.Time       `json:"created_at" db:"created_at"`
}

// NotificationLogsRequest 通知日志请求
type NotificationLogsRequest struct {
	Status string `json:"status"`
	Limit  int    `json:"limit"`
}

// SendNotificationRequest 发送通知请求
type SendNotificationRequest struct {
	Channel string `json:"channel"`
	Title   string `json:"title"`
	Content string `json:"content"`
}
