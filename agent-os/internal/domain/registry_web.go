package domain

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

// AgentWeb 注册到 Agent OS 的 Agent 视图
// RFC 010: AgentID = Window ID, AgentType = Role
type AgentWeb struct {
	ID              uuid.UUID       `json:"id"`
	AgentID         string          `json:"agent_id"`          // Window ID (w-29882338)
	SessionID       *string         `json:"session_id,omitempty"`
	AgentType       string          `json:"agent_type"`        // Role (investor, market_analyst)
	Name            *string         `json:"name,omitempty"`    // Window name (PI投资脑)
	Instance        *string         `json:"instance,omitempty"` // Instance name (investment)
	Status          string          `json:"status"`            // online, offline, timeout, idle, active
	Host            *string         `json:"host,omitempty"`
	Port            *int            `json:"port,omitempty"`
	Pid             *int            `json:"pid,omitempty"`
	Version         *string         `json:"version,omitempty"`
	Capabilities    []string        `json:"capabilities,omitempty"`
	Metadata        json.RawMessage `json:"metadata,omitempty"`
	RegisteredAt    time.Time       `json:"registered_at"`
	LastHeartbeatAt time.Time       `json:"last_heartbeat_at"`
	OfflineAt       *time.Time      `json:"offline_at,omitempty"` // Timestamp when went offline/timeout
}

// AgentRegisterRequest 注册请求（POST /api/v1/registry/agents/register）
// RFC 010: AgentID = Window ID, Type = Role
type AgentRegisterRequest struct {
	AgentID      string          `json:"agent_id"`          // Window ID (w-29882338)
	SessionID    *string         `json:"session_id,omitempty"`
	Type         string          `json:"type"`              // Role (investor)
	Name         *string         `json:"name,omitempty"`    // Window name (PI投资脑)
	Instance     *string         `json:"instance,omitempty"` // Instance name (investment)
	Capabilities []string        `json:"capabilities"`
	Status       *string         `json:"status,omitempty"`
	Host         *string         `json:"host,omitempty"`
	Port         *int            `json:"port,omitempty"`
	Pid          *int            `json:"pid,omitempty"`
	Version      *string         `json:"version,omitempty"`
	Metadata     json.RawMessage `json:"metadata,omitempty"`
}

// AgentHeartbeatRequest 心跳请求（POST /api/v1/registry/agents/heartbeat）
type AgentHeartbeatRequest struct {
	AgentID       string          `json:"agent_id"`
	Status        string          `json:"status"`
	Load          *float64        `json:"load,omitempty"`
	CurrentTaskID *string         `json:"current_task_id,omitempty"`
	Metadata      json.RawMessage `json:"metadata,omitempty"`
}

// AgentStatusUpdateRequest 状态更新请求（POST /api/v1/registry/agents/update-status）
type AgentStatusUpdateRequest struct {
	AgentID  string          `json:"agent_id"`
	Status   string          `json:"status"`
	Message  *string         `json:"message,omitempty"`
	Metadata json.RawMessage `json:"metadata,omitempty"`
}

// AgentUnregisterRequest 注销请求（POST /api/v1/registry/agents/unregister）
type AgentUnregisterRequest struct {
	AgentID string `json:"agent_id"`
}
