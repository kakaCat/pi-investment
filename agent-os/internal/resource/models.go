package resource

import (
	"time"

	"github.com/google/uuid"
)

// Namespace represents an agent namespace
type Namespace struct {
	ID          uuid.UUID              `json:"id"`
	Name        string                 `json:"name"`
	Description string                 `json:"description"`
	CreatedAt   time.Time              `json:"created_at"`
	Metadata    map[string]interface{} `json:"metadata"`
}

// ResourceQuota represents a resource quota for a namespace
type ResourceQuota struct {
	ID           uuid.UUID `json:"id"`
	NamespaceID  uuid.UUID `json:"namespace_id"`
	ResourceType string    `json:"resource_type"` // cpu, memory, api_calls, tokens
	LimitValue   int64     `json:"limit_value"`
	UsedValue    int64     `json:"used_value"`
	Unit         string    `json:"unit"` // cores, mb, count, tokens
	CreatedAt    time.Time `json:"created_at"`
	UpdatedAt    time.Time `json:"updated_at"`
}

// UsagePercent calculates the usage percentage
func (q *ResourceQuota) UsagePercent() float64 {
	if q.LimitValue == 0 {
		return 0
	}
	return float64(q.UsedValue) / float64(q.LimitValue) * 100
}

// IsExceeded checks if the quota is exceeded
func (q *ResourceQuota) IsExceeded() bool {
	return q.UsedValue >= q.LimitValue
}

// CanAllocate checks if a given amount can be allocated
func (q *ResourceQuota) CanAllocate(amount int64) bool {
	return q.UsedValue+amount <= q.LimitValue
}

// ResourceUsageLog represents a historical usage log entry
type ResourceUsageLog struct {
	ID           uuid.UUID              `json:"id"`
	NamespaceID  uuid.UUID              `json:"namespace_id"`
	ResourceType string                 `json:"resource_type"`
	Amount       int64                  `json:"amount"`
	Operation    string                 `json:"operation"` // allocate, release
	TaskRunID    *uuid.UUID             `json:"task_run_id,omitempty"`
	CreatedAt    time.Time              `json:"created_at"`
	Metadata     map[string]interface{} `json:"metadata"`
}

// QuotaUsageView represents the quota_usage view
type QuotaUsageView struct {
	Namespace    string  `json:"namespace"`
	ResourceType string  `json:"resource_type"`
	LimitValue   int64   `json:"limit_value"`
	UsedValue    int64   `json:"used_value"`
	UsagePercent float64 `json:"usage_percent"`
	Unit         string  `json:"unit"`
}
