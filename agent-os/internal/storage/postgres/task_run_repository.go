package postgres

import (
	"context"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/pi-investment/agent-os/pkg/types"
)

// TaskRunRepository handles task run-related database operations
type TaskRunRepository struct {
	pool Querier
}

// NewTaskRunRepository creates a new TaskRunRepository
func NewTaskRunRepository() *TaskRunRepository {
	return &TaskRunRepository{
		pool: GetPool(),
	}
}

// Create creates a new task run
func (r *TaskRunRepository) Create(ctx context.Context, run *types.TaskRun) error {
	metadataJSON, err := json.Marshal(run.Metadata)
	if err != nil {
		return fmt.Errorf("failed to marshal metadata: %w", err)
	}

	query := `
		INSERT INTO task_runs (task_id, status, triggered_by, metadata)
		VALUES ($1, $2, $3, $4)
		RETURNING id, started_at
	`

	err = r.pool.QueryRow(ctx, query,
		run.TaskID,
		run.Status,
		run.TriggeredBy,
		metadataJSON,
	).Scan(&run.ID, &run.StartedAt)

	if err != nil {
		return fmt.Errorf("failed to create task run: %w", err)
	}

	return nil
}

// GetByID retrieves a task run by ID
func (r *TaskRunRepository) GetByID(ctx context.Context, id uuid.UUID) (*types.TaskRun, error) {
	query := `
		SELECT id, task_id, status, started_at, finished_at, duration_ms,
		       output, error, triggered_by, metadata
		FROM task_runs
		WHERE id = $1
	`

	var run types.TaskRun
	var metadataJSON []byte

	err := r.pool.QueryRow(ctx, query, id).Scan(
		&run.ID,
		&run.TaskID,
		&run.Status,
		&run.StartedAt,
		&run.FinishedAt,
		&run.DurationMs,
		&run.Output,
		&run.Error,
		&run.TriggeredBy,
		&metadataJSON,
	)

	if err == pgx.ErrNoRows {
		return nil, fmt.Errorf("task run not found: %s", id)
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get task run: %w", err)
	}

	if err := json.Unmarshal(metadataJSON, &run.Metadata); err != nil {
		return nil, fmt.Errorf("failed to unmarshal metadata: %w", err)
	}

	return &run, nil
}

// ListByTaskID retrieves all runs for a specific task
func (r *TaskRunRepository) ListByTaskID(ctx context.Context, taskID uuid.UUID, limit int) ([]*types.TaskRun, error) {
	query := `
		SELECT id, task_id, status, started_at, finished_at, duration_ms,
		       output, error, triggered_by, metadata
		FROM task_runs
		WHERE task_id = $1
		ORDER BY started_at DESC
	`

	if limit > 0 {
		query += fmt.Sprintf(" LIMIT %d", limit)
	}

	rows, err := r.pool.Query(ctx, query, taskID)
	if err != nil {
		return nil, fmt.Errorf("failed to list task runs: %w", err)
	}
	defer rows.Close()

	var runs []*types.TaskRun
	for rows.Next() {
		var run types.TaskRun
		var metadataJSON []byte

		err := rows.Scan(
			&run.ID,
			&run.TaskID,
			&run.Status,
			&run.StartedAt,
			&run.FinishedAt,
			&run.DurationMs,
			&run.Output,
			&run.Error,
			&run.TriggeredBy,
			&metadataJSON,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan task run: %w", err)
		}

		if err := json.Unmarshal(metadataJSON, &run.Metadata); err != nil {
			return nil, fmt.Errorf("failed to unmarshal metadata: %w", err)
		}

		runs = append(runs, &run)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating task runs: %w", err)
	}

	return runs, nil
}

// UpdateStatus updates the status of a task run
func (r *TaskRunRepository) UpdateStatus(ctx context.Context, id uuid.UUID, status types.TaskStatus) error {
	query := `
		UPDATE task_runs
		SET status = $1
		WHERE id = $2
	`

	tag, err := r.pool.Exec(ctx, query, status, id)
	if err != nil {
		return fmt.Errorf("failed to update task run status: %w", err)
	}

	if tag.RowsAffected() == 0 {
		return fmt.Errorf("task run not found: %s", id)
	}

	return nil
}

// Complete marks a task run as completed (success or failed)
func (r *TaskRunRepository) Complete(ctx context.Context, id uuid.UUID, status types.TaskStatus, output, errMsg string) error {
	now := time.Now()

	query := `
		UPDATE task_runs
		SET status = $1,
		    finished_at = $2,
		    duration_ms = EXTRACT(EPOCH FROM ($2 - started_at)) * 1000,
		    output = $3,
		    error = $4
		WHERE id = $5
	`

	tag, err := r.pool.Exec(ctx, query, status, now, output, errMsg, id)
	if err != nil {
		return fmt.Errorf("failed to complete task run: %w", err)
	}

	if tag.RowsAffected() == 0 {
		return fmt.Errorf("task run not found: %s", id)
	}

	return nil
}

// GetRunningRuns retrieves all currently running task runs
func (r *TaskRunRepository) GetRunningRuns(ctx context.Context) ([]*types.TaskRun, error) {
	query := `
		SELECT id, task_id, status, started_at, finished_at, duration_ms,
		       output, error, triggered_by, metadata
		FROM task_runs
		WHERE status = $1
		ORDER BY started_at
	`

	rows, err := r.pool.Query(ctx, query, types.TaskStatusRunning)
	if err != nil {
		return nil, fmt.Errorf("failed to get running task runs: %w", err)
	}
	defer rows.Close()

	var runs []*types.TaskRun
	for rows.Next() {
		var run types.TaskRun
		var metadataJSON []byte

		err := rows.Scan(
			&run.ID,
			&run.TaskID,
			&run.Status,
			&run.StartedAt,
			&run.FinishedAt,
			&run.DurationMs,
			&run.Output,
			&run.Error,
			&run.TriggeredBy,
			&metadataJSON,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan task run: %w", err)
		}

		if err := json.Unmarshal(metadataJSON, &run.Metadata); err != nil {
			return nil, fmt.Errorf("failed to unmarshal metadata: %w", err)
		}

		runs = append(runs, &run)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating task runs: %w", err)
	}

	return runs, nil
}

// GetLatestRunByTaskID retrieves the most recent run for a task
func (r *TaskRunRepository) GetLatestRunByTaskID(ctx context.Context, taskID uuid.UUID) (*types.TaskRun, error) {
	query := `
		SELECT id, task_id, status, started_at, finished_at, duration_ms,
		       output, error, triggered_by, metadata
		FROM task_runs
		WHERE task_id = $1
		ORDER BY started_at DESC
		LIMIT 1
	`

	var run types.TaskRun
	var metadataJSON []byte

	err := r.pool.QueryRow(ctx, query, taskID).Scan(
		&run.ID,
		&run.TaskID,
		&run.Status,
		&run.StartedAt,
		&run.FinishedAt,
		&run.DurationMs,
		&run.Output,
		&run.Error,
		&run.TriggeredBy,
		&metadataJSON,
	)

	if err == pgx.ErrNoRows {
		return nil, nil // No runs found, not an error
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get latest task run: %w", err)
	}

	if err := json.Unmarshal(metadataJSON, &run.Metadata); err != nil {
		return nil, fmt.Errorf("failed to unmarshal metadata: %w", err)
	}

	return &run, nil
}

// DeleteOldRuns deletes task runs older than the specified duration
func (r *TaskRunRepository) DeleteOldRuns(ctx context.Context, olderThan time.Duration) (int64, error) {
	query := `
		DELETE FROM task_runs
		WHERE started_at < $1
	`

	cutoff := time.Now().Add(-olderThan)
	tag, err := r.pool.Exec(ctx, query, cutoff)
	if err != nil {
		return 0, fmt.Errorf("failed to delete old task runs: %w", err)
	}

	return tag.RowsAffected(), nil
}
