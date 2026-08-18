package domain

import (
	"time"
)

// Agent represents a registered agent in the system
type Agent struct {
	ID              string                 `json:"id"`
	AgentID         string                 `json:"agent_id"`
	SessionID       string                 `json:"session_id"`
	AgentType       string                 `json:"agent_type"`
	Status          AgentStatus            `json:"status"`
	LastHeartbeatAt time.Time              `json:"last_heartbeat_at"`
	CreatedAt       time.Time              `json:"created_at"`
	UpdatedAt       time.Time              `json:"updated_at"`
	Metadata        map[string]interface{} `json:"metadata,omitempty"`
	Capabilities    []string               `json:"capabilities,omitempty"`
}

// AgentStatus represents the current status of an agent
type AgentStatus string

const (
	AgentStatusIdle    AgentStatus = "idle"
	AgentStatusBusy    AgentStatus = "busy"
	AgentStatusOffline AgentStatus = "offline"
	AgentStatusError   AgentStatus = "error"
)

// AgentCapability represents a capability that an agent supports
type AgentCapability struct {
	ID         string    `json:"id"`
	AgentID    string    `json:"agent_id"`
	Capability string    `json:"capability"`
	CreatedAt  time.Time `json:"created_at"`
}

// AgentHeartbeat represents a heartbeat record
type AgentHeartbeat struct {
	ID          string                 `json:"id"`
	AgentID     string                 `json:"agent_id"`
	Status      AgentStatus            `json:"status"`
	HeartbeatAt time.Time              `json:"heartbeat_at"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
}

// RegisterAgentRequest represents a request to register an agent
type RegisterAgentRequest struct {
	AgentID      string                 `json:"agent_id"`
	SessionID    string                 `json:"session_id"`
	AgentType    string                 `json:"agent_type"`
	Capabilities []string               `json:"capabilities,omitempty"`
	Metadata     map[string]interface{} `json:"metadata,omitempty"`
}

// HeartbeatRequest represents a heartbeat request
type HeartbeatRequest struct {
	AgentID  string                 `json:"agent_id"`
	Status   AgentStatus            `json:"status"`
	Metadata map[string]interface{} `json:"metadata,omitempty"`
}

// UpdateStatusRequest represents a request to update agent status
type UpdateStatusRequest struct {
	AgentID string      `json:"agent_id"`
	Status  AgentStatus `json:"status"`
}
