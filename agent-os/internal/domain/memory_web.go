package domain

import (
	"time"

	"github.com/google/uuid"
)

// MemoryWeb Web API 记忆视图
type MemoryWeb struct {
	ID        uuid.UUID `json:"id" db:"id"`
	Title     string    `json:"title" db:"title"`
	Content   string    `json:"content" db:"content"`
	Category  string    `json:"category" db:"category"`
	Tags      []string  `json:"tags" db:"tags"`
	AgentID   *string   `json:"agent_id,omitempty" db:"agent_id"`
	CreatedAt time.Time `json:"created_at" db:"created_at"`
	UpdatedAt time.Time `json:"updated_at" db:"updated_at"`
}

// Tag 标签
type Tag struct {
	Name      string    `json:"name" db:"name"`
	Count     int       `json:"count" db:"count"`
	CreatedAt time.Time `json:"created_at" db:"created_at"`
}

// MemoryListRequest 记忆列表请求
type MemoryListRequest struct {
	Category string `json:"category"`
	Tag      string `json:"tag"`
	Limit    int    `json:"limit"`
}

// MemorySearchRequest 记忆搜索请求
type MemorySearchRequest struct {
	Query string `json:"query"`
	Limit int    `json:"limit"`
}

// MemoryCreateRequest 记忆写入请求（POST /api/v1/memory）
type MemoryCreateRequest struct {
	Title    string   `json:"title"`
	Content  string   `json:"content"`
	Category string   `json:"category"`
	Tags     []string `json:"tags"`
	AgentID  *string  `json:"agent_id,omitempty"`
}
