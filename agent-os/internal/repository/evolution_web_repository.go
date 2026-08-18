package repository

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"github.com/pi-investment/agent-os/internal/domain"
)

// EvolutionWebRepository 进化记录仓储接口
type EvolutionWebRepository interface {
	CreateRun(ctx context.Context, run *domain.EvolutionRun) error
	UpdateRunStatus(ctx context.Context, id string, status string, fitness float64, improvement float64, proposals, bestParams []byte) error
	GetLeaderboard(ctx context.Context, limit int) ([]*domain.EvolutionLeaderboardEntry, error)
}

type evolutionWebRepository struct {
	db *sql.DB
}

// NewEvolutionWebRepository 创建进化记录仓储
func NewEvolutionWebRepository(db *sql.DB) EvolutionWebRepository {
	return &evolutionWebRepository{db: db}
}

// CreateRun 创建进化运行记录
func (r *evolutionWebRepository) CreateRun(ctx context.Context, run *domain.EvolutionRun) error {
	query := `INSERT INTO evolution_runs (id, strategy_id, mode, generations, status)
	          VALUES ($1, $2, $3, $4, $5)`
	_, err := r.db.ExecContext(ctx, query,
		run.ID, run.StrategyID, run.Mode, run.Generations, run.Status,
	)
	if err != nil {
		return fmt.Errorf("failed to create evolution run: %w", err)
	}
	return nil
}

// UpdateRunStatus 完成/失败时回填结果
func (r *evolutionWebRepository) UpdateRunStatus(ctx context.Context, id string, status string, fitness float64, improvement float64, proposals, bestParams []byte) error {
	query := `UPDATE evolution_runs
	          SET status = $2, fitness = $3, fitness_improvement = $4,
	              proposals = $5, best_params = $6, completed_at = $7
	          WHERE id = $1`
	_, err := r.db.ExecContext(ctx, query,
		id, status, fitness, improvement, proposals, bestParams, time.Now(),
	)
	if err != nil {
		return fmt.Errorf("failed to update evolution run: %w", err)
	}
	return nil
}

// GetLeaderboard 按策略最新 fitness 降序排行
func (r *evolutionWebRepository) GetLeaderboard(ctx context.Context, limit int) ([]*domain.EvolutionLeaderboardEntry, error) {
	query := `SELECT DISTINCT ON (strategy_id) strategy_id, fitness, id, mode, completed_at
	          FROM evolution_runs
	          WHERE status = 'completed'
	          ORDER BY strategy_id, completed_at DESC
	          LIMIT $1`

	if limit <= 0 {
		limit = 10
	}

	rows, err := r.db.QueryContext(ctx, query, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to query evolution leaderboard: %w", err)
	}
	defer rows.Close()

	var entries []*domain.EvolutionLeaderboardEntry
	for rows.Next() {
		var e domain.EvolutionLeaderboardEntry
		var completedAt sql.NullTime
		err := rows.Scan(&e.StrategyID, &e.Fitness, &e.RunID, &e.Mode, &completedAt)
		if err != nil {
			return nil, fmt.Errorf("failed to scan leaderboard entry: %w", err)
		}
		if completedAt.Valid {
			e.UpdatedAt = completedAt.Time
		}
		entries = append(entries, &e)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows iteration error: %w", err)
	}
	return entries, nil
}
