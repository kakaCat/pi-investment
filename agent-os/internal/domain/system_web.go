package domain

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

// SystemLog 系统日志
type SystemLog struct {
	ID        uuid.UUID       `json:"id" db:"id"`
	Level     string          `json:"level" db:"level"`
	Source    string          `json:"source" db:"source"`
	Message   string          `json:"message" db:"message"`
	Details   json.RawMessage `json:"details,omitempty" db:"details"`
	Timestamp time.Time       `json:"timestamp" db:"timestamp"`
}

// Namespace 命名空间
type Namespace struct {
	Name        string    `json:"name" db:"name"`
	Description *string   `json:"description,omitempty" db:"description"`
	Status      string    `json:"status" db:"status"`
	CreatedAt   time.Time `json:"created_at" db:"created_at"`
	UpdatedAt   time.Time `json:"updated_at" db:"updated_at"`
}

// ResourceQuota 资源配额
type ResourceQuota struct {
	ID           uuid.UUID `json:"id" db:"id"`
	Namespace    string    `json:"namespace" db:"namespace"`
	ResourceType string    `json:"resource_type" db:"resource_type"`
	Limit        float64   `json:"limit" db:"limit_value"`
	Used         float64   `json:"used" db:"used_value"`
	Unit         *string   `json:"unit,omitempty" db:"unit"`
	CreatedAt    time.Time `json:"created_at" db:"created_at"`
	UpdatedAt    time.Time `json:"updated_at" db:"updated_at"`
}

// SystemStatus 系统状态
type SystemStatus struct {
	Status     string                   `json:"status"`
	Uptime     int64                    `json:"uptime"`
	Version    string                   `json:"version"`
	Components []map[string]interface{} `json:"components"`
}

// SystemLogsRequest 系统日志请求
type SystemLogsRequest struct {
	Level  string `json:"level"`
	Source string `json:"source"`
	Limit  int    `json:"limit"`
}
