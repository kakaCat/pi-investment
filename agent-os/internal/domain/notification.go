package domain

import "time"

// NotificationProvider represents a notification provider (e.g., Feishu, Slack)
type NotificationProvider struct {
	ID        string                 `json:"id"`
	Code      string                 `json:"code"`
	Name      string                 `json:"name"`
	Enabled   bool                   `json:"enabled"`
	Config    map[string]interface{} `json:"config"`
	CreatedAt time.Time              `json:"created_at"`
	UpdatedAt time.Time              `json:"updated_at"`
}

// NotificationChannel represents a notification channel (e.g., trading, alerts)
type NotificationChannel struct {
	ID           string                 `json:"id"`
	ProviderID   string                 `json:"provider_id"`
	Code         string                 `json:"code"`
	Name         string                 `json:"name"`
	Description  string                 `json:"description"`
	Enabled      bool                   `json:"enabled"`
	Config       map[string]interface{} `json:"config"`
	Metadata     map[string]interface{} `json:"metadata"`
	CreatedAt    time.Time              `json:"created_at"`
	UpdatedAt    time.Time              `json:"updated_at"`
	ProviderCode string                 `json:"provider_code,omitempty"` // Joined field
	ProviderName string                 `json:"provider_name,omitempty"` // Joined field
}

// NotificationLog represents a notification sending log
type NotificationLog struct {
	ID        string                 `json:"id"`
	ChannelID string                 `json:"channel_id"`
	Title     string                 `json:"title"`
	Content   string                 `json:"content"`
	Status    string                 `json:"status"` // pending, sent, failed
	MessageID string                 `json:"message_id,omitempty"`
	Error     string                 `json:"error,omitempty"`
	Metadata  map[string]interface{} `json:"metadata"`
	SentAt    *time.Time             `json:"sent_at,omitempty"`
	CreatedAt time.Time              `json:"created_at"`
}

// SendRequest represents a notification send request
type SendRequest struct {
	Channel  string                 `json:"channel"`
	Title    string                 `json:"title"`
	Content  string                 `json:"content"`
	Color    string                 `json:"color,omitempty"`
	Urgency  string                 `json:"urgency,omitempty"`
	Metadata map[string]interface{} `json:"metadata,omitempty"`
}

// SendResult represents the result of a notification send operation
type SendResult struct {
	LogID     string `json:"log_id"`
	Success   bool   `json:"success"`
	Error     string `json:"error,omitempty"`
	MessageID string `json:"message_id,omitempty"`
}
