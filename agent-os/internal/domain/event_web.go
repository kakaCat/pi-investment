package domain

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

// EventWeb Web API 事件视图
type EventWeb struct {
	ID        uuid.UUID       `json:"id" db:"id"`
	Type      string          `json:"type" db:"type"`
	Message   string          `json:"message" db:"message"`
	AgentID   *string         `json:"agent_id,omitempty" db:"agent_id"`
	Data      json.RawMessage `json:"data,omitempty" db:"data"`
	Timestamp time.Time       `json:"timestamp" db:"timestamp"`
}

// AlertRule 告警规则
type AlertRule struct {
	ID               uuid.UUID  `json:"id" db:"id"`
	Name             string     `json:"name" db:"name"`
	EventType        string     `json:"event_type" db:"event_type"`
	Condition        string     `json:"condition" db:"condition"`
	Level            string     `json:"level" db:"level"`
	Channels         []string   `json:"channels" db:"channels"`
	Enabled          bool       `json:"enabled" db:"enabled"`
	TriggeredCount   int        `json:"triggered_count" db:"triggered_count"`
	LastTriggeredAt  *time.Time `json:"last_triggered_at,omitempty" db:"last_triggered_at"`
	CreatedAt        time.Time  `json:"created_at" db:"created_at"`
	UpdatedAt        time.Time  `json:"updated_at" db:"updated_at"`
}

// EventHistoryRequest 事件历史请求
type EventHistoryRequest struct {
	Type  string `json:"type"`
	Start string `json:"start"`
	End   string `json:"end"`
	Limit int    `json:"limit"`
}

// AlertRuleCreateRequest 创建告警规则请求
type AlertRuleCreateRequest struct {
	Name      string   `json:"name"`
	EventType string   `json:"event_type"`
	Condition string   `json:"condition"`
	Level     string   `json:"level"`
	Channels  []string `json:"channels"`
}
