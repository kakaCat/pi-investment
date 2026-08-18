package repository

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/lib/pq"
	"github.com/pi-investment/agent-os/internal/domain"
)

// RegistryWebRepository Agent 注册表仓储接口
type RegistryWebRepository interface {
	Upsert(ctx context.Context, req domain.AgentRegisterRequest) (*domain.AgentWeb, error)
	Heartbeat(ctx context.Context, req domain.AgentHeartbeatRequest) error
	UpdateStatus(ctx context.Context, req domain.AgentStatusUpdateRequest) error
	Unregister(ctx context.Context, agentID string) error
	ListActive(ctx context.Context, capability string) ([]*domain.AgentWeb, error)
	GetByAgentID(ctx context.Context, agentID string) (*domain.AgentWeb, error)
}

type registryWebRepository struct {
	db *sql.DB
}

// NewRegistryWebRepository 创建 Agent 注册表仓储
func NewRegistryWebRepository(db *sql.DB) RegistryWebRepository {
	return &registryWebRepository{db: db}
}

// Upsert 注册（agent_id 已存在时更新）
func (r *registryWebRepository) Upsert(ctx context.Context, req domain.AgentRegisterRequest) (*domain.AgentWeb, error) {
	status := "idle"
	if req.Status != nil && *req.Status != "" {
		status = *req.Status
	}

	query := `INSERT INTO agents (agent_id, session_id, agent_type, status, host, port, pid, version, capabilities, metadata)
	          VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
	          ON CONFLICT (agent_id) DO UPDATE SET
	            session_id = EXCLUDED.session_id,
	            agent_type = EXCLUDED.agent_type,
	            status = EXCLUDED.status,
	            host = EXCLUDED.host,
	            port = EXCLUDED.port,
	            pid = EXCLUDED.pid,
	            version = EXCLUDED.version,
	            capabilities = EXCLUDED.capabilities,
	            metadata = EXCLUDED.metadata,
	            updated_at = NOW()
	          RETURNING id, agent_id, session_id, agent_type, status, host, port, pid, version,
	                    capabilities, metadata, registered_at, last_heartbeat_at`

	var a domain.AgentWeb
	var metadata []byte
	err := r.db.QueryRowContext(ctx, query,
		req.AgentID, req.SessionID, req.Type, status,
		req.Host, req.Port, req.Pid, req.Version,
		pq.Array(req.Capabilities), req.Metadata,
	).Scan(
		&a.ID, &a.AgentID, &a.SessionID, &a.AgentType, &a.Status,
		&a.Host, &a.Port, &a.Pid, &a.Version,
		pq.Array(&a.Capabilities), &metadata,
		&a.RegisteredAt, &a.LastHeartbeatAt,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to upsert agent: %w", err)
	}
	a.Metadata = metadata
	return &a, nil
}

// Heartbeat 更新心跳时间与状态
func (r *registryWebRepository) Heartbeat(ctx context.Context, req domain.AgentHeartbeatRequest) error {
	status := req.Status
	if status == "" {
		status = "idle"
	}

	query := `UPDATE agents SET status = $2, last_heartbeat_at = NOW(), updated_at = NOW()
	          WHERE agent_id = $1`
	res, err := r.db.ExecContext(ctx, query, req.AgentID, status)
	if err != nil {
		return fmt.Errorf("failed to update heartbeat: %w", err)
	}
	affected, err := res.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to read affected rows: %w", err)
	}
	if affected == 0 {
		return fmt.Errorf("agent not found: %s", req.AgentID)
	}
	return nil
}

// UpdateStatus 更新 Agent 状态
func (r *registryWebRepository) UpdateStatus(ctx context.Context, req domain.AgentStatusUpdateRequest) error {
	query := `UPDATE agents SET status = $2, updated_at = NOW() WHERE agent_id = $1`
	res, err := r.db.ExecContext(ctx, query, req.AgentID, req.Status)
	if err != nil {
		return fmt.Errorf("failed to update agent status: %w", err)
	}
	affected, err := res.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to read affected rows: %w", err)
	}
	if affected == 0 {
		return fmt.Errorf("agent not found: %s", req.AgentID)
	}
	return nil
}

// Unregister 注销 Agent
func (r *registryWebRepository) Unregister(ctx context.Context, agentID string) error {
	query := `DELETE FROM agents WHERE agent_id = $1`
	res, err := r.db.ExecContext(ctx, query, agentID)
	if err != nil {
		return fmt.Errorf("failed to unregister agent: %w", err)
	}
	affected, err := res.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to read affected rows: %w", err)
	}
	if affected == 0 {
		return fmt.Errorf("agent not found: %s", agentID)
	}
	return nil
}

// ListActive 列出活跃 Agent（可选按 capability 过滤）
func (r *registryWebRepository) ListActive(ctx context.Context, capability string) ([]*domain.AgentWeb, error) {
	query := `SELECT id, agent_id, session_id, agent_type, status, host, port, pid, version,
	                 capabilities, metadata, registered_at, last_heartbeat_at
	          FROM agents WHERE status != 'offline'`
	args := []interface{}{}

	if capability != "" {
		query += fmt.Sprintf(" AND $%d = ANY(capabilities)", len(args)+1)
		args = append(args, capability)
	}
	query += " ORDER BY last_heartbeat_at DESC"

	rows, err := r.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to list agents: %w", err)
	}
	defer rows.Close()

	var agents []*domain.AgentWeb
	for rows.Next() {
		var a domain.AgentWeb
		var metadata []byte
		err := rows.Scan(
			&a.ID, &a.AgentID, &a.SessionID, &a.AgentType, &a.Status,
			&a.Host, &a.Port, &a.Pid, &a.Version,
			pq.Array(&a.Capabilities), &metadata,
			&a.RegisteredAt, &a.LastHeartbeatAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan agent: %w", err)
		}
		a.Metadata = metadata
		agents = append(agents, &a)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows iteration error: %w", err)
	}
	return agents, nil
}

// GetByAgentID 按 agent_id 查询
func (r *registryWebRepository) GetByAgentID(ctx context.Context, agentID string) (*domain.AgentWeb, error) {
	query := `SELECT id, agent_id, session_id, agent_type, status, host, port, pid, version,
	                 capabilities, metadata, registered_at, last_heartbeat_at
	          FROM agents WHERE agent_id = $1`

	var a domain.AgentWeb
	var metadata []byte
	err := r.db.QueryRowContext(ctx, query, agentID).Scan(
		&a.ID, &a.AgentID, &a.SessionID, &a.AgentType, &a.Status,
		&a.Host, &a.Port, &a.Pid, &a.Version,
		pq.Array(&a.Capabilities), &metadata,
		&a.RegisteredAt, &a.LastHeartbeatAt,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to get agent: %w", err)
	}
	a.Metadata = metadata
	return &a, nil
}
