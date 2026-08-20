package repository

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"github.com/pi-investment/agent-os/internal/domain"
)

// SystemWebRepository Web API 系统仓储接口
type SystemWebRepository interface {
	GetStatus(ctx context.Context) (*domain.SystemStatus, error)
	GetQuotas(ctx context.Context) ([]*domain.ResourceQuota, error)
	GetLogs(ctx context.Context, req domain.SystemLogsRequest) ([]*domain.SystemLog, error)
	GetNamespaces(ctx context.Context) ([]*domain.Namespace, error)
	CreateNamespace(ctx context.Context, req domain.NamespaceCreateRequest) error
	DeleteNamespace(ctx context.Context, name string) error
}

type systemWebRepository struct {
	db        *sql.DB
	startTime time.Time
}

// NewSystemWebRepository 创建 Web API 系统仓储
func NewSystemWebRepository(db *sql.DB) SystemWebRepository {
	return &systemWebRepository{
		db:        db,
		startTime: time.Now(),
	}
}

// GetStatus 获取系统状态
func (r *systemWebRepository) GetStatus(ctx context.Context) (*domain.SystemStatus, error) {
	uptime := int64(time.Since(r.startTime).Seconds())
	
	status := &domain.SystemStatus{
		Status:  "ok",
		Uptime:  uptime,
		Version: "1.0.0",
		Components: []map[string]interface{}{
			{"name": "API Server", "status": "healthy"},
			{"name": "Scheduler", "status": "healthy"},
			{"name": "Database", "status": "healthy"},
			{"name": "Redis", "status": "healthy"},
		},
	}
	
	return status, nil
}

// GetQuotas 获取资源配额
func (r *systemWebRepository) GetQuotas(ctx context.Context) ([]*domain.ResourceQuota, error) {
	query := `SELECT id, namespace, resource_type, limit_value, used_value, unit, created_at, updated_at
	          FROM resource_quotas
	          ORDER BY namespace, resource_type`
	
	rows, err := r.db.QueryContext(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("failed to query resource quotas: %w", err)
	}
	defer rows.Close()
	
	var quotas []*domain.ResourceQuota
	for rows.Next() {
		var q domain.ResourceQuota
		err := rows.Scan(
			&q.ID, &q.Namespace, &q.ResourceType,
			&q.Limit, &q.Used, &q.Unit,
			&q.CreatedAt, &q.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan resource quota: %w", err)
		}
		quotas = append(quotas, &q)
	}
	
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows iteration error: %w", err)
	}
	
	return quotas, nil
}

// GetLogs 获取系统日志
func (r *systemWebRepository) GetLogs(ctx context.Context, req domain.SystemLogsRequest) ([]*domain.SystemLog, error) {
	query := `SELECT id, level, source, message, details, timestamp
	          FROM system_logs WHERE 1=1`
	
	args := []interface{}{}
	argIndex := 1
	
	if req.Level != "" {
		query += fmt.Sprintf(" AND level = $%d", argIndex)
		args = append(args, req.Level)
		argIndex++
	}
	
	if req.Source != "" {
		query += fmt.Sprintf(" AND source = $%d", argIndex)
		args = append(args, req.Source)
		argIndex++
	}
	
	query += " ORDER BY timestamp DESC"
	
	if req.Limit > 0 {
		query += fmt.Sprintf(" LIMIT $%d", argIndex)
		args = append(args, req.Limit)
	} else {
		query += " LIMIT 100"
	}
	
	rows, err := r.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to query system logs: %w", err)
	}
	defer rows.Close()
	
	var logs []*domain.SystemLog
	for rows.Next() {
		var l domain.SystemLog
		err := rows.Scan(
			&l.ID, &l.Level, &l.Source, &l.Message,
			&l.Details, &l.Timestamp,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan system log: %w", err)
		}
		logs = append(logs, &l)
	}
	
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows iteration error: %w", err)
	}
	
	return logs, nil
}

// GetNamespaces 获取命名空间列表
func (r *systemWebRepository) GetNamespaces(ctx context.Context) ([]*domain.Namespace, error) {
	query := `SELECT name, description, status, created_at, updated_at
	          FROM namespaces
	          ORDER BY created_at`
	
	rows, err := r.db.QueryContext(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("failed to query namespaces: %w", err)
	}
	defer rows.Close()
	
	var namespaces []*domain.Namespace
	for rows.Next() {
		var n domain.Namespace
		err := rows.Scan(&n.Name, &n.Description, &n.Status, &n.CreatedAt, &n.UpdatedAt)
		if err != nil {
			return nil, fmt.Errorf("failed to scan namespace: %w", err)
		}
		namespaces = append(namespaces, &n)
	}
	
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows iteration error: %w", err)
	}
	
	return namespaces, nil
}

// CreateNamespace 创建命名空间
func (r *systemWebRepository) CreateNamespace(ctx context.Context, req domain.NamespaceCreateRequest) error {
	query := `INSERT INTO namespaces (name, description, status)
	          VALUES ($1, $2, $3)`
	
	_, err := r.db.ExecContext(ctx, query, req.Name, req.Description, "active")
	if err != nil {
		return fmt.Errorf("failed to create namespace: %w", err)
	}
	
	return nil
}

// DeleteNamespace 删除命名空间
func (r *systemWebRepository) DeleteNamespace(ctx context.Context, name string) error {
	result, err := r.db.ExecContext(ctx,
		"DELETE FROM namespaces WHERE name = $1", name)
	if err != nil {
		return fmt.Errorf("failed to delete namespace: %w", err)
	}
	affected, _ := result.RowsAffected()
	if affected == 0 {
		return fmt.Errorf("namespace not found: %s", name)
	}
	return nil
}
