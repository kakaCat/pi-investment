package repository

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"

	"github.com/lib/pq"
	"github.com/pi-investment/agent-os/internal/domain"
)

// DecisionWebRepository Web API 决策仓储接口
type DecisionWebRepository interface {
	List(ctx context.Context, req domain.DecisionListRequest) ([]*domain.DecisionWeb, error)
	GetByID(ctx context.Context, id string) (*domain.DecisionWeb, error)
	GetStatistics(ctx context.Context) (*domain.DecisionStatistics, error)
}

type decisionWebRepository struct {
	db *sql.DB
}

// NewDecisionWebRepository 创建 Web API 决策仓储
func NewDecisionWebRepository(db *sql.DB) DecisionWebRepository {
	return &decisionWebRepository{db: db}
}

// List 获取决策列表
func (r *decisionWebRepository) List(ctx context.Context, req domain.DecisionListRequest) ([]*domain.DecisionWeb, error) {
	query := `SELECT id, agent_id, action, targets, target, confidence, status, reason, 
	                 context, outcome, created_at, executed_at, pnl, timeline, data, updated_at
	          FROM decisions WHERE 1=1`
	
	args := []interface{}{}
	argIndex := 1
	
	if req.Action != "" {
		query += fmt.Sprintf(" AND action = $%d", argIndex)
		args = append(args, req.Action)
		argIndex++
	}
	
	if req.Status != "" {
		query += fmt.Sprintf(" AND status = $%d", argIndex)
		args = append(args, req.Status)
		argIndex++
	}
	
	query += " ORDER BY created_at DESC"
	
	if req.Limit > 0 {
		query += fmt.Sprintf(" LIMIT $%d", argIndex)
		args = append(args, req.Limit)
	} else {
		query += " LIMIT 100"
	}
	
	rows, err := r.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to query decisions: %w", err)
	}
	defer rows.Close()
	
	var decisions []*domain.DecisionWeb
	for rows.Next() {
		var d domain.DecisionWeb
		var contextBytes, outcomeBytes []byte
		
		err := rows.Scan(
			&d.ID, &d.AgentID, &d.Action, pq.Array(&d.Targets), &d.Target,
			&d.Confidence, &d.Status, &d.Reason,
			&contextBytes, &outcomeBytes, &d.CreatedAt, &d.ExecutedAt,
			&d.PnL, &d.Timeline, &d.Data, &d.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan decision: %w", err)
		}
		
		// 解析 JSONB 字段
		if len(contextBytes) > 0 {
			json.Unmarshal(contextBytes, &d.Context)
		}
		if len(outcomeBytes) > 0 {
			json.Unmarshal(outcomeBytes, &d.Outcome)
		}
		
		decisions = append(decisions, &d)
	}
	
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows iteration error: %w", err)
	}
	
	return decisions, nil
}

// GetByID 根据ID获取决策
func (r *decisionWebRepository) GetByID(ctx context.Context, id string) (*domain.DecisionWeb, error) {
	query := `SELECT id, agent_id, action, targets, target, confidence, status, reason,
	                 context, outcome, created_at, executed_at, pnl, timeline, data, updated_at
	          FROM decisions WHERE id = $1`
	
	var d domain.DecisionWeb
	var contextBytes, outcomeBytes []byte
	
	err := r.db.QueryRowContext(ctx, query, id).Scan(
		&d.ID, &d.AgentID, &d.Action, pq.Array(&d.Targets), &d.Target,
		&d.Confidence, &d.Status, &d.Reason,
		&contextBytes, &outcomeBytes, &d.CreatedAt, &d.ExecutedAt,
		&d.PnL, &d.Timeline, &d.Data, &d.UpdatedAt,
	)
	
	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("decision not found: %s", id)
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get decision: %w", err)
	}
	
	// 解析 JSONB 字段
	if len(contextBytes) > 0 {
		json.Unmarshal(contextBytes, &d.Context)
	}
	if len(outcomeBytes) > 0 {
		json.Unmarshal(outcomeBytes, &d.Outcome)
	}
	
	return &d, nil
}

// GetStatistics 获取决策统计
func (r *decisionWebRepository) GetStatistics(ctx context.Context) (*domain.DecisionStatistics, error) {
	stats := &domain.DecisionStatistics{
		TypeDistribution:   []domain.DistributionItem{},
		StatusDistribution: []domain.DistributionItem{},
	}
	
	// 总数和基本统计
	query := `SELECT 
	            COUNT(*) as total,
	            COUNT(CASE WHEN status = 'executed' THEN 1 END) as executed,
	            COUNT(CASE WHEN status = 'pending' THEN 1 END) as pending,
	            COALESCE(AVG(confidence) * 100, 0) as avg_confidence
	          FROM decisions`
	
	err := r.db.QueryRowContext(ctx, query).Scan(
		&stats.Total, &stats.Executed, &stats.Pending, &stats.AvgConfidence,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to get decision statistics: %w", err)
	}
	
	// 按动作类型分布
	typeQuery := `SELECT action as name, COUNT(*) as value 
	              FROM decisions 
	              GROUP BY action`
	
	rows, err := r.db.QueryContext(ctx, typeQuery)
	if err != nil {
		return nil, fmt.Errorf("failed to get type distribution: %w", err)
	}
	defer rows.Close()
	
	for rows.Next() {
		var item domain.DistributionItem
		if err := rows.Scan(&item.Name, &item.Value); err != nil {
			return nil, fmt.Errorf("failed to scan type distribution: %w", err)
		}
		stats.TypeDistribution = append(stats.TypeDistribution, item)
	}
	
	// 按状态分布
	statusQuery := `SELECT status as name, COUNT(*) as value 
	                FROM decisions 
	                WHERE status IS NOT NULL
	                GROUP BY status`
	
	rows, err = r.db.QueryContext(ctx, statusQuery)
	if err != nil {
		return nil, fmt.Errorf("failed to get status distribution: %w", err)
	}
	defer rows.Close()
	
	for rows.Next() {
		var item domain.DistributionItem
		if err := rows.Scan(&item.Name, &item.Value); err != nil {
			return nil, fmt.Errorf("failed to scan status distribution: %w", err)
		}
		stats.StatusDistribution = append(stats.StatusDistribution, item)
	}
	
	return stats, nil
}
