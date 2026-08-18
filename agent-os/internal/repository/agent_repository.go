package repository

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/pi-investment/agent-os/internal/domain"
)

// AgentRepository defines the interface for agent data access
type AgentRepository interface {
	Create(agent *domain.Agent) error
	Update(agent *domain.Agent) error
	Delete(agentID string) error
	GetByAgentID(agentID string) (*domain.Agent, error)
	List() ([]*domain.Agent, error)
	ListByStatus(status domain.AgentStatus) ([]*domain.Agent, error)
	ListByType(agentType string) ([]*domain.Agent, error)
	FindAvailableAgents(capabilities []string) ([]*domain.Agent, error)
	UpdateStatus(agentID string, status domain.AgentStatus) error
	UpdateHeartbeat(agentID string) error
	AddCapabilities(agentID string, capabilities []string) error
	GetCapabilities(agentID string) ([]string, error)
	RecordHeartbeat(heartbeat *domain.AgentHeartbeat) error
	GetStaleAgents(timeout time.Duration) ([]*domain.Agent, error)
}

type agentRepository struct {
	db *sql.DB
}

// NewAgentRepository creates a new agent repository
func NewAgentRepository(db *sql.DB) AgentRepository {
	return &agentRepository{db: db}
}

// Create inserts a new agent into the database
func (r *agentRepository) Create(agent *domain.Agent) error {
	tx, err := r.db.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	// Insert agent
	query := `
		INSERT INTO agents (id, agent_id, session_id, agent_type, status, last_heartbeat_at, created_at, updated_at, metadata)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
	`

	if agent.ID == "" {
		agent.ID = uuid.New().String()
	}

	now := time.Now()
	if agent.CreatedAt.IsZero() {
		agent.CreatedAt = now
	}
	if agent.UpdatedAt.IsZero() {
		agent.UpdatedAt = now
	}
	if agent.LastHeartbeatAt.IsZero() {
		agent.LastHeartbeatAt = now
	}

	metadataJSON, err := json.Marshal(agent.Metadata)
	if err != nil {
		return fmt.Errorf("failed to marshal metadata: %w", err)
	}

	_, err = tx.Exec(query,
		agent.ID,
		agent.AgentID,
		agent.SessionID,
		agent.AgentType,
		agent.Status,
		agent.LastHeartbeatAt,
		agent.CreatedAt,
		agent.UpdatedAt,
		metadataJSON,
	)
	if err != nil {
		return fmt.Errorf("failed to create agent: %w", err)
	}

	// Insert capabilities
	if len(agent.Capabilities) > 0 {
		if err := r.addCapabilitiesTx(tx, agent.AgentID, agent.Capabilities); err != nil {
			return err
		}
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	return nil
}

// Update updates an existing agent
func (r *agentRepository) Update(agent *domain.Agent) error {
	query := `
		UPDATE agents
		SET session_id = $1, agent_type = $2, status = $3, updated_at = $4, metadata = $5
		WHERE agent_id = $6
	`

	agent.UpdatedAt = time.Now()

	metadataJSON, err := json.Marshal(agent.Metadata)
	if err != nil {
		return fmt.Errorf("failed to marshal metadata: %w", err)
	}

	result, err := r.db.Exec(query,
		agent.SessionID,
		agent.AgentType,
		agent.Status,
		agent.UpdatedAt,
		metadataJSON,
		agent.AgentID,
	)
	if err != nil {
		return fmt.Errorf("failed to update agent: %w", err)
	}

	rows, _ := result.RowsAffected()
	if rows == 0 {
		return fmt.Errorf("agent not found: %s", agent.AgentID)
	}

	return nil
}

// Delete removes an agent from the database
func (r *agentRepository) Delete(agentID string) error {
	query := `DELETE FROM agents WHERE agent_id = $1`

	result, err := r.db.Exec(query, agentID)
	if err != nil {
		return fmt.Errorf("failed to delete agent: %w", err)
	}

	rows, _ := result.RowsAffected()
	if rows == 0 {
		return fmt.Errorf("agent not found: %s", agentID)
	}

	return nil
}

// GetByAgentID retrieves an agent by agent ID
func (r *agentRepository) GetByAgentID(agentID string) (*domain.Agent, error) {
	query := `
		SELECT id, agent_id, session_id, agent_type, status, last_heartbeat_at, created_at, updated_at, metadata
		FROM agents
		WHERE agent_id = $1
	`

	agent := &domain.Agent{}
	var metadataJSON []byte

	err := r.db.QueryRow(query, agentID).Scan(
		&agent.ID,
		&agent.AgentID,
		&agent.SessionID,
		&agent.AgentType,
		&agent.Status,
		&agent.LastHeartbeatAt,
		&agent.CreatedAt,
		&agent.UpdatedAt,
		&metadataJSON,
	)

	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("agent not found: %s", agentID)
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get agent: %w", err)
	}

	if metadataJSON != nil {
		if err := json.Unmarshal(metadataJSON, &agent.Metadata); err != nil {
			return nil, fmt.Errorf("failed to unmarshal metadata: %w", err)
		}
	}

	// Load capabilities
	capabilities, err := r.GetCapabilities(agentID)
	if err != nil {
		return nil, err
	}
	agent.Capabilities = capabilities

	return agent, nil
}

// List retrieves all agents
func (r *agentRepository) List() ([]*domain.Agent, error) {
	query := `
		SELECT id, agent_id, session_id, agent_type, status, last_heartbeat_at, created_at, updated_at, metadata
		FROM agents
		ORDER BY created_at DESC
	`

	rows, err := r.db.Query(query)
	if err != nil {
		return nil, fmt.Errorf("failed to list agents: %w", err)
	}
	defer rows.Close()

	return r.scanAgents(rows)
}

// ListByStatus retrieves agents by status
func (r *agentRepository) ListByStatus(status domain.AgentStatus) ([]*domain.Agent, error) {
	query := `
		SELECT id, agent_id, session_id, agent_type, status, last_heartbeat_at, created_at, updated_at, metadata
		FROM agents
		WHERE status = $1
		ORDER BY created_at DESC
	`

	rows, err := r.db.Query(query, status)
	if err != nil {
		return nil, fmt.Errorf("failed to list agents by status: %w", err)
	}
	defer rows.Close()

	return r.scanAgents(rows)
}

// ListByType retrieves agents by type
func (r *agentRepository) ListByType(agentType string) ([]*domain.Agent, error) {
	query := `
		SELECT id, agent_id, session_id, agent_type, status, last_heartbeat_at, created_at, updated_at, metadata
		FROM agents
		WHERE agent_type = $1
		ORDER BY created_at DESC
	`

	rows, err := r.db.Query(query, agentType)
	if err != nil {
		return nil, fmt.Errorf("failed to list agents by type: %w", err)
	}
	defer rows.Close()

	return r.scanAgents(rows)
}

// FindAvailableAgents finds agents with specified capabilities
func (r *agentRepository) FindAvailableAgents(capabilities []string) ([]*domain.Agent, error) {
	if len(capabilities) == 0 {
		return r.ListByStatus(domain.AgentStatusIdle)
	}

	query := `
		SELECT DISTINCT a.id, a.agent_id, a.session_id, a.agent_type, a.status, 
		       a.last_heartbeat_at, a.created_at, a.updated_at, a.metadata
		FROM agents a
		INNER JOIN agent_capabilities ac ON a.agent_id = ac.agent_id
		WHERE a.status = $1 AND ac.capability = ANY($2)
		GROUP BY a.id, a.agent_id, a.session_id, a.agent_type, a.status, 
		         a.last_heartbeat_at, a.created_at, a.updated_at, a.metadata
		HAVING COUNT(DISTINCT ac.capability) = $3
		ORDER BY a.last_heartbeat_at DESC
	`

	rows, err := r.db.Query(query, domain.AgentStatusIdle, capabilities, len(capabilities))
	if err != nil {
		return nil, fmt.Errorf("failed to find available agents: %w", err)
	}
	defer rows.Close()

	return r.scanAgents(rows)
}

// UpdateStatus updates the status of an agent
func (r *agentRepository) UpdateStatus(agentID string, status domain.AgentStatus) error {
	query := `
		UPDATE agents
		SET status = $1, updated_at = $2
		WHERE agent_id = $3
	`

	result, err := r.db.Exec(query, status, time.Now(), agentID)
	if err != nil {
		return fmt.Errorf("failed to update agent status: %w", err)
	}

	rows, _ := result.RowsAffected()
	if rows == 0 {
		return fmt.Errorf("agent not found: %s", agentID)
	}

	return nil
}

// UpdateHeartbeat updates the last heartbeat time
func (r *agentRepository) UpdateHeartbeat(agentID string) error {
	query := `
		UPDATE agents
		SET last_heartbeat_at = $1, updated_at = $2
		WHERE agent_id = $3
	`

	result, err := r.db.Exec(query, time.Now(), time.Now(), agentID)
	if err != nil {
		return fmt.Errorf("failed to update heartbeat: %w", err)
	}

	rows, _ := result.RowsAffected()
	if rows == 0 {
		return fmt.Errorf("agent not found: %s", agentID)
	}

	return nil
}

// AddCapabilities adds capabilities to an agent
func (r *agentRepository) AddCapabilities(agentID string, capabilities []string) error {
	tx, err := r.db.Begin()
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback()

	if err := r.addCapabilitiesTx(tx, agentID, capabilities); err != nil {
		return err
	}

	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	return nil
}

// addCapabilitiesTx adds capabilities within a transaction
func (r *agentRepository) addCapabilitiesTx(tx *sql.Tx, agentID string, capabilities []string) error {
	query := `
		INSERT INTO agent_capabilities (id, agent_id, capability, created_at)
		VALUES ($1, $2, $3, $4)
		ON CONFLICT (agent_id, capability) DO NOTHING
	`

	for _, capability := range capabilities {
		_, err := tx.Exec(query, uuid.New().String(), agentID, capability, time.Now())
		if err != nil {
			return fmt.Errorf("failed to add capability: %w", err)
		}
	}

	return nil
}

// GetCapabilities retrieves capabilities for an agent
func (r *agentRepository) GetCapabilities(agentID string) ([]string, error) {
	query := `
		SELECT capability
		FROM agent_capabilities
		WHERE agent_id = $1
		ORDER BY capability
	`

	rows, err := r.db.Query(query, agentID)
	if err != nil {
		return nil, fmt.Errorf("failed to get capabilities: %w", err)
	}
	defer rows.Close()

	var capabilities []string
	for rows.Next() {
		var capability string
		if err := rows.Scan(&capability); err != nil {
			return nil, fmt.Errorf("failed to scan capability: %w", err)
		}
		capabilities = append(capabilities, capability)
	}

	return capabilities, rows.Err()
}

// RecordHeartbeat records a heartbeat in the history table
func (r *agentRepository) RecordHeartbeat(heartbeat *domain.AgentHeartbeat) error {
	query := `
		INSERT INTO agent_heartbeats (id, agent_id, status, heartbeat_at, metadata)
		VALUES ($1, $2, $3, $4, $5)
	`

	if heartbeat.ID == "" {
		heartbeat.ID = uuid.New().String()
	}

	if heartbeat.HeartbeatAt.IsZero() {
		heartbeat.HeartbeatAt = time.Now()
	}

	metadataJSON, err := json.Marshal(heartbeat.Metadata)
	if err != nil {
		return fmt.Errorf("failed to marshal metadata: %w", err)
	}

	_, err = r.db.Exec(query,
		heartbeat.ID,
		heartbeat.AgentID,
		heartbeat.Status,
		heartbeat.HeartbeatAt,
		metadataJSON,
	)
	if err != nil {
		return fmt.Errorf("failed to record heartbeat: %w", err)
	}

	return nil
}

// GetStaleAgents retrieves agents whose last heartbeat is older than the timeout
func (r *agentRepository) GetStaleAgents(timeout time.Duration) ([]*domain.Agent, error) {
	query := `
		SELECT id, agent_id, session_id, agent_type, status, last_heartbeat_at, created_at, updated_at, metadata
		FROM agents
		WHERE status != $1 AND last_heartbeat_at < $2
		ORDER BY last_heartbeat_at ASC
	`

	cutoff := time.Now().Add(-timeout)
	rows, err := r.db.Query(query, domain.AgentStatusOffline, cutoff)
	if err != nil {
		return nil, fmt.Errorf("failed to get stale agents: %w", err)
	}
	defer rows.Close()

	return r.scanAgents(rows)
}

// scanAgents scans multiple agents from rows
func (r *agentRepository) scanAgents(rows *sql.Rows) ([]*domain.Agent, error) {
	var agents []*domain.Agent

	for rows.Next() {
		agent := &domain.Agent{}
		var metadataJSON []byte

		err := rows.Scan(
			&agent.ID,
			&agent.AgentID,
			&agent.SessionID,
			&agent.AgentType,
			&agent.Status,
			&agent.LastHeartbeatAt,
			&agent.CreatedAt,
			&agent.UpdatedAt,
			&metadataJSON,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan agent: %w", err)
		}

		if metadataJSON != nil {
			if err := json.Unmarshal(metadataJSON, &agent.Metadata); err != nil {
				return nil, fmt.Errorf("failed to unmarshal metadata: %w", err)
			}
		}

		// Load capabilities
		capabilities, err := r.GetCapabilities(agent.AgentID)
		if err != nil {
			return nil, err
		}
		agent.Capabilities = capabilities

		agents = append(agents, agent)
	}

	return agents, rows.Err()
}
