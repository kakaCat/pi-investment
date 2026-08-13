package resource

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"

	"github.com/google/uuid"
)

// Repository handles database operations for resource management
type Repository struct {
	db *sql.DB
}

// NewRepository creates a new resource repository
func NewRepository(db *sql.DB) *Repository {
	return &Repository{db: db}
}

// ============================================================================
// NAMESPACE OPERATIONS
// ============================================================================

// GetNamespaceByName retrieves a namespace by name
func (r *Repository) GetNamespaceByName(ctx context.Context, name string) (*Namespace, error) {
	query := `
		SELECT id, name, description, created_at, metadata
		FROM namespaces
		WHERE name = $1
	`

	var ns Namespace
	var metadataJSON []byte

	err := r.db.QueryRowContext(ctx, query, name).Scan(
		&ns.ID,
		&ns.Name,
		&ns.Description,
		&ns.CreatedAt,
		&metadataJSON,
	)

	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("namespace not found: %s", name)
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get namespace: %w", err)
	}

	if err := json.Unmarshal(metadataJSON, &ns.Metadata); err != nil {
		return nil, fmt.Errorf("failed to unmarshal metadata: %w", err)
	}

	return &ns, nil
}

// ListNamespaces retrieves all namespaces
func (r *Repository) ListNamespaces(ctx context.Context) ([]*Namespace, error) {
	query := `
		SELECT id, name, description, created_at, metadata
		FROM namespaces
		ORDER BY name
	`

	rows, err := r.db.QueryContext(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("failed to list namespaces: %w", err)
	}
	defer rows.Close()

	var namespaces []*Namespace
	for rows.Next() {
		var ns Namespace
		var metadataJSON []byte

		if err := rows.Scan(&ns.ID, &ns.Name, &ns.Description, &ns.CreatedAt, &metadataJSON); err != nil {
			return nil, fmt.Errorf("failed to scan namespace: %w", err)
		}

		if err := json.Unmarshal(metadataJSON, &ns.Metadata); err != nil {
			return nil, fmt.Errorf("failed to unmarshal metadata: %w", err)
		}

		namespaces = append(namespaces, &ns)
	}

	return namespaces, rows.Err()
}

// ============================================================================
// QUOTA OPERATIONS
// ============================================================================

// GetQuotasByNamespace retrieves all quotas for a namespace
func (r *Repository) GetQuotasByNamespace(ctx context.Context, namespaceID uuid.UUID) ([]*ResourceQuota, error) {
	query := `
		SELECT id, namespace_id, resource_type, limit_value, used_value, unit, created_at, updated_at
		FROM resource_quotas
		WHERE namespace_id = $1
		ORDER BY resource_type
	`

	rows, err := r.db.QueryContext(ctx, query, namespaceID)
	if err != nil {
		return nil, fmt.Errorf("failed to get quotas: %w", err)
	}
	defer rows.Close()

	var quotas []*ResourceQuota
	for rows.Next() {
		var q ResourceQuota
		if err := rows.Scan(&q.ID, &q.NamespaceID, &q.ResourceType, &q.LimitValue, &q.UsedValue, &q.Unit, &q.CreatedAt, &q.UpdatedAt); err != nil {
			return nil, fmt.Errorf("failed to scan quota: %w", err)
		}
		quotas = append(quotas, &q)
	}

	return quotas, rows.Err()
}

// GetQuota retrieves a specific quota for a namespace and resource type
func (r *Repository) GetQuota(ctx context.Context, namespaceID uuid.UUID, resourceType string) (*ResourceQuota, error) {
	query := `
		SELECT id, namespace_id, resource_type, limit_value, used_value, unit, created_at, updated_at
		FROM resource_quotas
		WHERE namespace_id = $1 AND resource_type = $2
	`

	var q ResourceQuota
	err := r.db.QueryRowContext(ctx, query, namespaceID, resourceType).Scan(
		&q.ID,
		&q.NamespaceID,
		&q.ResourceType,
		&q.LimitValue,
		&q.UsedValue,
		&q.Unit,
		&q.CreatedAt,
		&q.UpdatedAt,
	)

	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("quota not found for resource type: %s", resourceType)
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get quota: %w", err)
	}

	return &q, nil
}

// UpdateQuotaUsage updates the used value of a quota
func (r *Repository) UpdateQuotaUsage(ctx context.Context, namespaceID uuid.UUID, resourceType string, delta int64) error {
	query := `
		UPDATE resource_quotas
		SET used_value = used_value + $1
		WHERE namespace_id = $2 AND resource_type = $3
	`

	result, err := r.db.ExecContext(ctx, query, delta, namespaceID, resourceType)
	if err != nil {
		return fmt.Errorf("failed to update quota usage: %w", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rows == 0 {
		return fmt.Errorf("no quota found to update")
	}

	return nil
}

// SetQuotaLimit updates the limit value of a quota
func (r *Repository) SetQuotaLimit(ctx context.Context, namespaceID uuid.UUID, resourceType string, limitValue int64) error {
	query := `
		UPDATE resource_quotas
		SET limit_value = $1
		WHERE namespace_id = $2 AND resource_type = $3
	`

	result, err := r.db.ExecContext(ctx, query, limitValue, namespaceID, resourceType)
	if err != nil {
		return fmt.Errorf("failed to set quota limit: %w", err)
	}

	rows, err := result.RowsAffected()
	if err != nil {
		return fmt.Errorf("failed to get rows affected: %w", err)
	}

	if rows == 0 {
		return fmt.Errorf("no quota found to update")
	}

	return nil
}

// ResetQuotaUsage resets the used value of a quota to zero
func (r *Repository) ResetQuotaUsage(ctx context.Context, namespaceID uuid.UUID, resourceType string) error {
	query := `
		UPDATE resource_quotas
		SET used_value = 0
		WHERE namespace_id = $1 AND resource_type = $2
	`

	_, err := r.db.ExecContext(ctx, query, namespaceID, resourceType)
	if err != nil {
		return fmt.Errorf("failed to reset quota usage: %w", err)
	}

	return nil
}

// ============================================================================
// USAGE LOG OPERATIONS
// ============================================================================

// LogUsage records a resource usage event
func (r *Repository) LogUsage(ctx context.Context, log *ResourceUsageLog) error {
	query := `
		INSERT INTO resource_usage_log (id, namespace_id, resource_type, amount, operation, task_run_id, metadata)
		VALUES ($1, $2, $3, $4, $5, $6, $7)
	`

	metadataJSON, err := json.Marshal(log.Metadata)
	if err != nil {
		return fmt.Errorf("failed to marshal metadata: %w", err)
	}

	if log.ID == uuid.Nil {
		log.ID = uuid.New()
	}

	_, err = r.db.ExecContext(ctx, query,
		log.ID,
		log.NamespaceID,
		log.ResourceType,
		log.Amount,
		log.Operation,
		log.TaskRunID,
		metadataJSON,
	)

	if err != nil {
		return fmt.Errorf("failed to log usage: %w", err)
	}

	return nil
}

// GetUsageHistory retrieves usage history for a namespace
func (r *Repository) GetUsageHistory(ctx context.Context, namespaceID uuid.UUID, limit int) ([]*ResourceUsageLog, error) {
	query := `
		SELECT id, namespace_id, resource_type, amount, operation, task_run_id, created_at, metadata
		FROM resource_usage_log
		WHERE namespace_id = $1
		ORDER BY created_at DESC
		LIMIT $2
	`

	rows, err := r.db.QueryContext(ctx, query, namespaceID, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to get usage history: %w", err)
	}
	defer rows.Close()

	var logs []*ResourceUsageLog
	for rows.Next() {
		var log ResourceUsageLog
		var metadataJSON []byte
		var taskRunID sql.NullString

		if err := rows.Scan(&log.ID, &log.NamespaceID, &log.ResourceType, &log.Amount, &log.Operation, &taskRunID, &log.CreatedAt, &metadataJSON); err != nil {
			return nil, fmt.Errorf("failed to scan usage log: %w", err)
		}

		if taskRunID.Valid {
			id, _ := uuid.Parse(taskRunID.String)
			log.TaskRunID = &id
		}

		if err := json.Unmarshal(metadataJSON, &log.Metadata); err != nil {
			return nil, fmt.Errorf("failed to unmarshal metadata: %w", err)
		}

		logs = append(logs, &log)
	}

	return logs, rows.Err()
}

// ============================================================================
// QUOTA USAGE VIEW
// ============================================================================

// GetQuotaUsageView retrieves the quota usage view
func (r *Repository) GetQuotaUsageView(ctx context.Context) ([]*QuotaUsageView, error) {
	query := `
		SELECT namespace, resource_type, limit_value, used_value, usage_percent, unit
		FROM quota_usage
		ORDER BY usage_percent DESC NULLS LAST
	`

	rows, err := r.db.QueryContext(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("failed to get quota usage view: %w", err)
	}
	defer rows.Close()

	var views []*QuotaUsageView
	for rows.Next() {
		var v QuotaUsageView
		var usagePercent sql.NullFloat64

		if err := rows.Scan(&v.Namespace, &v.ResourceType, &v.LimitValue, &v.UsedValue, &usagePercent, &v.Unit); err != nil {
			return nil, fmt.Errorf("failed to scan quota usage view: %w", err)
		}

		if usagePercent.Valid {
			v.UsagePercent = usagePercent.Float64
		}

		views = append(views, &v)
	}

	return views, rows.Err()
}
