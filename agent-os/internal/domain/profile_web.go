package domain

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

// UserProfile 用户配置
type UserProfile struct {
	ID          uuid.UUID       `json:"id" db:"id"`
	Username    string          `json:"username" db:"username"`
	Email       *string         `json:"email,omitempty" db:"email"`
	AvatarURL   *string         `json:"avatar_url,omitempty" db:"avatar_url"`
	DisplayName *string         `json:"display_name,omitempty" db:"display_name"`
	Bio         *string         `json:"bio,omitempty" db:"bio"`
	Preferences json.RawMessage `json:"preferences,omitempty" db:"preferences"`
	CreatedAt   time.Time       `json:"created_at" db:"created_at"`
	UpdatedAt   time.Time       `json:"updated_at" db:"updated_at"`
}

// APIKey API 密钥
type APIKey struct {
	ID          uuid.UUID  `json:"id" db:"id"`
	Name        string     `json:"name" db:"name"`
	KeyPrefix   string     `json:"key_prefix" db:"key_prefix"`
	UserID      uuid.UUID  `json:"user_id" db:"user_id"`
	Permissions []string   `json:"permissions" db:"permissions"`
	ExpiresAt   *time.Time `json:"expires_at,omitempty" db:"expires_at"`
	LastUsedAt  *time.Time `json:"last_used_at,omitempty" db:"last_used_at"`
	CreatedAt   time.Time  `json:"created_at" db:"created_at"`
}

// UserActivityLog 用户活动日志
type UserActivityLog struct {
	ID        uuid.UUID       `json:"id" db:"id"`
	UserID    uuid.UUID       `json:"user_id" db:"user_id"`
	Action    string          `json:"action" db:"action"`
	Resource  *string         `json:"resource,omitempty" db:"resource"`
	Details   json.RawMessage `json:"details,omitempty" db:"details"`
	IPAddress *string         `json:"ip_address,omitempty" db:"ip_address"`
	UserAgent *string         `json:"user_agent,omitempty" db:"user_agent"`
	Timestamp time.Time       `json:"timestamp" db:"timestamp"`
}

// UpdateProfileRequest 更新用户配置请求
type UpdateProfileRequest struct {
	Email       *string         `json:"email"`
	DisplayName *string         `json:"display_name"`
	Bio         *string         `json:"bio"`
	Preferences json.RawMessage `json:"preferences"`
}

// ActivityLogsRequest 活动日志请求
type ActivityLogsRequest struct {
	Limit int `json:"limit"`
}
