package repository

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"github.com/lib/pq"
	"github.com/pi-investment/agent-os/internal/domain"
)

// EventWebRepository Web API 事件仓储接口
type EventWebRepository interface {
	GetHistory(ctx context.Context, req domain.EventHistoryRequest) ([]*domain.EventWeb, error)
	GetAlertRules(ctx context.Context) ([]*domain.AlertRule, error)
	CreateAlertRule(ctx context.Context, req domain.AlertRuleCreateRequest) error
	DeleteAlertRule(ctx context.Context, id string) error
}

type eventWebRepository struct {
	db *sql.DB
}

// NewEventWebRepository 创建 Web API 事件仓储
func NewEventWebRepository(db *sql.DB) EventWebRepository {
	return &eventWebRepository{db: db}
}

// GetHistory 获取事件历史
func (r *eventWebRepository) GetHistory(ctx context.Context, req domain.EventHistoryRequest) ([]*domain.EventWeb, error) {
	query := `SELECT id, type, message, agent_id, data, timestamp
	          FROM events WHERE 1=1`
	
	args := []interface{}{}
	argIndex := 1
	
	if req.Type != "" {
		query += fmt.Sprintf(" AND type = $%d", argIndex)
		args = append(args, req.Type)
		argIndex++
	}
	
	if req.Start != "" {
		startTime, err := time.Parse(time.RFC3339, req.Start)
		if err == nil {
			query += fmt.Sprintf(" AND timestamp >= $%d", argIndex)
			args = append(args, startTime)
			argIndex++
		}
	}
	
	if req.End != "" {
		endTime, err := time.Parse(time.RFC3339, req.End)
		if err == nil {
			query += fmt.Sprintf(" AND timestamp <= $%d", argIndex)
			args = append(args, endTime)
			argIndex++
		}
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
		return nil, fmt.Errorf("failed to query events: %w", err)
	}
	defer rows.Close()
	
	var events []*domain.EventWeb
	for rows.Next() {
		var e domain.EventWeb
		err := rows.Scan(
			&e.ID, &e.Type, &e.Message, &e.AgentID,
			&e.Data, &e.Timestamp,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan event: %w", err)
		}
		events = append(events, &e)
	}
	
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows iteration error: %w", err)
	}
	
	return events, nil
}

// GetAlertRules 获取所有告警规则
func (r *eventWebRepository) GetAlertRules(ctx context.Context) ([]*domain.AlertRule, error) {
	query := `SELECT id, name, event_type, condition, level, channels, enabled,
	                 triggered_count, last_triggered_at, created_at, updated_at
	          FROM alert_rules
	          ORDER BY created_at DESC`
	
	rows, err := r.db.QueryContext(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("failed to query alert rules: %w", err)
	}
	defer rows.Close()
	
	var rules []*domain.AlertRule
	for rows.Next() {
		var r domain.AlertRule
		err := rows.Scan(
			&r.ID, &r.Name, &r.EventType, &r.Condition, &r.Level,
			pq.Array(&r.Channels), &r.Enabled,
			&r.TriggeredCount, &r.LastTriggeredAt,
			&r.CreatedAt, &r.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan alert rule: %w", err)
		}
		rules = append(rules, &r)
	}
	
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows iteration error: %w", err)
	}
	
	return rules, nil
}

// CreateAlertRule 创建告警规则
func (r *eventWebRepository) CreateAlertRule(ctx context.Context, req domain.AlertRuleCreateRequest) error {
	query := `INSERT INTO alert_rules (name, event_type, condition, level, channels)
	          VALUES ($1, $2, $3, $4, $5)`
	
	_, err := r.db.ExecContext(ctx, query,
		req.Name, req.EventType, req.Condition, req.Level, pq.Array(req.Channels))
	if err != nil {
		return fmt.Errorf("failed to create alert rule: %w", err)
	}
	
	return nil
}

// DeleteAlertRule 删除告警规则
func (r *eventWebRepository) DeleteAlertRule(ctx context.Context, id string) error {
	query := `DELETE FROM alert_rules WHERE id = $1`
	
	_, err := r.db.ExecContext(ctx, query, id)
	if err != nil {
		return fmt.Errorf("failed to delete alert rule: %w", err)
	}
	
	return nil
}
