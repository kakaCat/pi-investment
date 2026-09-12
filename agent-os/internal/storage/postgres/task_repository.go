package postgres

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgconn"
	"github.com/pi-investment/agent-os/pkg/types"
)

// TaskRepository handles task-related database operations
type TaskRepository struct {
	pool Querier
}

// Querier interface for database operations (allows mocking)
type Querier interface {
	Query(ctx context.Context, sql string, args ...interface{}) (pgx.Rows, error)
	QueryRow(ctx context.Context, sql string, args ...interface{}) pgx.Row
	Exec(ctx context.Context, sql string, args ...interface{}) (pgconn.CommandTag, error)
}

// NewTaskRepository creates a new TaskRepository
func NewTaskRepository() *TaskRepository {
	return &TaskRepository{
		pool: GetPool(),
	}
}

// Create creates a new task
func (r *TaskRepository) Create(ctx context.Context, task *types.Task) error {
	metadataJSON, err := json.Marshal(task.Metadata)
	if err != nil {
		return fmt.Errorf("failed to marshal metadata: %w", err)
	}

	payloadJSON, err := json.Marshal(task.Payload)
	if err != nil {
		return fmt.Errorf("failed to marshal payload: %w", err)
	}

	query := `
		INSERT INTO tasks (
			name, owner, description, schedule, cron, command,
			webhook_url, service_name, payload, timeout, retry_count, enabled,
			created_by, metadata
		)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
		RETURNING id, created_at, updated_at
	`

	err = r.pool.QueryRow(ctx, query,
		task.Name,
		task.Owner,
		task.Description,
		task.Schedule,
		task.Cron,
		task.Command,
		task.WebhookURL,
		task.ServiceName,
		payloadJSON,
		task.Timeout,
		task.RetryCount,
		task.Enabled,
		task.CreatedBy,
		metadataJSON,
	).Scan(&task.ID, &task.CreatedAt, &task.UpdatedAt)

	if err != nil {
		return fmt.Errorf("failed to create task: %w", err)
	}

	return nil
}

// GetByID retrieves a task by ID
func (r *TaskRepository) GetByID(ctx context.Context, id uuid.UUID) (*types.Task, error) {
	query := `
		SELECT id, name, owner, COALESCE(description, ''), COALESCE(schedule, ''), COALESCE(cron, ''),
		       COALESCE(command, ''), COALESCE(webhook_url, ''), COALESCE(service_name, ''),
		       COALESCE(payload, '{}'::jsonb), COALESCE(timeout, 3600), COALESCE(retry_count, 0), enabled,
		       created_at, updated_at, COALESCE(created_by, ''), COALESCE(metadata, '{}'::jsonb),
		       COALESCE(agent_line, '')
		FROM tasks
		WHERE id = $1
	`

	var task types.Task
	var metadataJSON []byte
	var payloadJSON []byte

	err := r.pool.QueryRow(ctx, query, id).Scan(
		&task.ID,
		&task.Name,
		&task.Owner,
		&task.Description,
		&task.Schedule,
		&task.Cron,
		&task.Command,
		&task.WebhookURL,
		&task.ServiceName,
		&payloadJSON,
		&task.Timeout,
		&task.RetryCount,
		&task.Enabled,
		&task.CreatedAt,
		&task.UpdatedAt,
		&task.CreatedBy,
		&metadataJSON,
		&task.AgentLine,
	)

	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, fmt.Errorf("task not found")
		}
		return nil, fmt.Errorf("failed to get task: %w", err)
	}

	if err := json.Unmarshal(metadataJSON, &task.Metadata); err != nil {
		return nil, fmt.Errorf("failed to unmarshal metadata: %w", err)
	}

	if err := json.Unmarshal(payloadJSON, &task.Payload); err != nil {
		return nil, fmt.Errorf("failed to unmarshal payload: %w", err)
	}

	return &task, nil
}

// GetByName retrieves a task by name
func (r *TaskRepository) GetByName(ctx context.Context, name string) (*types.Task, error) {
	query := `
		SELECT id, name, owner, COALESCE(description, ''), COALESCE(schedule, ''), COALESCE(cron, ''),
		       COALESCE(command, ''), COALESCE(webhook_url, ''), COALESCE(service_name, ''),
		       COALESCE(payload, '{}'::jsonb), COALESCE(timeout, 3600), COALESCE(retry_count, 0), enabled,
		       created_at, updated_at, COALESCE(created_by, ''), COALESCE(metadata, '{}'::jsonb),
		       COALESCE(agent_line, '')
		FROM tasks
		WHERE name = $1
	`

	var task types.Task
	var metadataJSON []byte
	var payloadJSON []byte

	err := r.pool.QueryRow(ctx, query, name).Scan(
		&task.ID,
		&task.Name,
		&task.Owner,
		&task.Description,
		&task.Schedule,
		&task.Cron,
		&task.Command,
		&task.WebhookURL,
		&task.ServiceName,
		&payloadJSON,
		&task.Timeout,
		&task.RetryCount,
		&task.Enabled,
		&task.CreatedAt,
		&task.UpdatedAt,
		&task.CreatedBy,
		&metadataJSON,
		&task.AgentLine,
	)

	if err == pgx.ErrNoRows {
		return nil, fmt.Errorf("task not found: %s", name)
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get task: %w", err)
	}

	if err := json.Unmarshal(metadataJSON, &task.Metadata); err != nil {
		return nil, fmt.Errorf("failed to unmarshal metadata: %w", err)
	}

	if err := json.Unmarshal(payloadJSON, &task.Payload); err != nil {
		return nil, fmt.Errorf("failed to unmarshal payload: %w", err)
	}

	return &task, nil
}

// List retrieves all tasks with optional filters
func (r *TaskRepository) List(ctx context.Context, enabledOnly bool) ([]*types.Task, error) {
	query := `
		SELECT id, name, owner, COALESCE(description, ''), COALESCE(schedule, ''), COALESCE(cron, ''),
		       COALESCE(command, ''), COALESCE(webhook_url, ''), COALESCE(service_name, ''),
		       COALESCE(payload, '{}'::jsonb), COALESCE(timeout, 3600), COALESCE(retry_count, 0), enabled,
		       created_at, updated_at, COALESCE(created_by, ''), COALESCE(metadata, '{}'::jsonb),
		       COALESCE(agent_line, '')
		FROM tasks
	`
	if enabledOnly {
		query += " WHERE enabled = true"
	}
	query += " ORDER BY name"

	rows, err := r.pool.Query(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("failed to list tasks: %w", err)
	}
	defer rows.Close()

	var tasks []*types.Task
	for rows.Next() {
		var task types.Task
		var metadataJSON []byte
		var payloadJSON []byte

		err := rows.Scan(
			&task.ID,
			&task.Name,
			&task.Owner,
			&task.Description,
			&task.Schedule,
			&task.Cron,
			&task.Command,
			&task.WebhookURL,
			&task.ServiceName,
			&payloadJSON,
			&task.Timeout,
			&task.RetryCount,
			&task.Enabled,
			&task.CreatedAt,
			&task.UpdatedAt,
			&task.CreatedBy,
			&metadataJSON,
			&task.AgentLine,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan task: %w", err)
		}

		if err := json.Unmarshal(metadataJSON, &task.Metadata); err != nil {
			return nil, fmt.Errorf("failed to unmarshal metadata: %w", err)
		}

		if err := json.Unmarshal(payloadJSON, &task.Payload); err != nil {
			return nil, fmt.Errorf("failed to unmarshal payload: %w", err)
		}

		tasks = append(tasks, &task)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("failed to iterate tasks: %w", err)
	}

	return tasks, nil
}

// Update updates a task
func (r *TaskRepository) Update(ctx context.Context, task *types.Task) error {
	metadataJSON, err := json.Marshal(task.Metadata)
	if err != nil {
		return fmt.Errorf("failed to marshal metadata: %w", err)
	}

	payloadJSON, err := json.Marshal(task.Payload)
	if err != nil {
		return fmt.Errorf("failed to marshal payload: %w", err)
	}

	query := `
		UPDATE tasks
		SET description = $1, schedule = $2, cron = $3, command = $4,
		    webhook_url = $5, service_name = $6, payload = $7, timeout = $8,
		    retry_count = $9, enabled = $10, metadata = $11
		WHERE id = $12
		RETURNING updated_at
	`

	err = r.pool.QueryRow(ctx, query,
		task.Description,
		task.Schedule,
		task.Cron,
		task.Command,
		task.WebhookURL,
		task.ServiceName,
		payloadJSON,
		task.Timeout,
		task.RetryCount,
		task.Enabled,
		metadataJSON,
		task.ID,
	).Scan(&task.UpdatedAt)

	if err == pgx.ErrNoRows {
		return fmt.Errorf("task not found: %s", task.ID)
	}
	if err != nil {
		return fmt.Errorf("failed to update task: %w", err)
	}

	return nil
}

// Delete deletes a task
func (r *TaskRepository) Delete(ctx context.Context, id uuid.UUID) error {
	query := `DELETE FROM tasks WHERE id = $1`

	tag, err := r.pool.Exec(ctx, query, id)
	if err != nil {
		return fmt.Errorf("failed to delete task: %w", err)
	}

	if tag.RowsAffected() == 0 {
		return fmt.Errorf("task not found: %s", id)
	}

	return nil
}

// GetScheduledTasks retrieves all enabled tasks with schedules
func (r *TaskRepository) GetScheduledTasks(ctx context.Context) ([]*types.Task, error) {
	// 2026-09-11（w-f4aa1f6a）：可空列一律 COALESCE。
	// 事故：一条未填 command/schedule 的任务（INSERT 时省略）会让本查询在
	// rows.Scan 处报 "cannot scan NULL into *string (col: description)"，
	// 进而 failed to load tasks → **agent-os 整个起不来**（实测确认）。
	// 调度器启动路径不允许因单条脏数据而全盘失败。
	query := `
		SELECT id, name, owner, COALESCE(description, ''), COALESCE(schedule, ''), COALESCE(cron, ''),
		       COALESCE(command, ''), COALESCE(webhook_url, ''), COALESCE(service_name, ''),
		       COALESCE(payload, '{}'::jsonb), COALESCE(timeout, 3600), COALESCE(retry_count, 0), enabled,
		       created_at, updated_at, COALESCE(created_by, ''), COALESCE(metadata, '{}'::jsonb),
		       COALESCE(agent_line, '')
		FROM tasks
		WHERE enabled = true AND (
			(schedule IS NOT NULL AND schedule != '') OR
			(cron IS NOT NULL AND cron != '')
		)
		ORDER BY name
	`

	rows, err := r.pool.Query(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("failed to get scheduled tasks: %w", err)
	}
	defer rows.Close()

	var tasks []*types.Task
	for rows.Next() {
		var task types.Task
		var metadataJSON []byte
		var payloadJSON []byte

		err := rows.Scan(
			&task.ID,
			&task.Name,
			&task.Owner,
			&task.Description,
			&task.Schedule,
			&task.Cron,
			&task.Command,
			&task.WebhookURL,
			&task.ServiceName,
			&payloadJSON,
			&task.Timeout,
			&task.RetryCount,
			&task.Enabled,
			&task.CreatedAt,
			&task.UpdatedAt,
			&task.CreatedBy,
			&metadataJSON,
			&task.AgentLine,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan task: %w", err)
		}

		if err := json.Unmarshal(metadataJSON, &task.Metadata); err != nil {
			return nil, fmt.Errorf("failed to unmarshal metadata: %w", err)
		}

		if err := json.Unmarshal(payloadJSON, &task.Payload); err != nil {
			return nil, fmt.Errorf("failed to unmarshal payload: %w", err)
		}

		tasks = append(tasks, &task)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating tasks: %w", err)
	}

	return tasks, nil
}

// GetTasksWithStats retrieves tasks with execution statistics
func (r *TaskRepository) GetTasksWithStats(ctx context.Context) ([]*types.TaskWithStats, error) {
	query := `
		SELECT
			t.id, t.name, t.description, t.schedule, t.command, t.service_name, t.enabled,
			t.created_at, t.updated_at, t.created_by, t.metadata,
			COUNT(tr.id) as total_runs,
			MAX(tr.started_at) as last_run_at,
			(SELECT status FROM task_runs WHERE task_id = t.id ORDER BY started_at DESC LIMIT 1) as last_run_status,
			ROUND(
				COALESCE(
					(COUNT(CASE WHEN tr.status = 'success' THEN 1 END)::float / NULLIF(COUNT(tr.id), 0) * 100),
					0
				)::numeric,
				2
			) as success_rate,
			AVG(tr.duration_ms)::bigint as avg_duration_ms
		FROM tasks t
		LEFT JOIN task_runs tr ON t.id = tr.task_id
		GROUP BY t.id
		ORDER BY t.name
	`

	rows, err := r.pool.Query(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("failed to get tasks with stats: %w", err)
	}
	defer rows.Close()

	var tasks []*types.TaskWithStats
	for rows.Next() {
		var task types.TaskWithStats
		var metadataJSON []byte
		var lastRunStatus *string

		err := rows.Scan(
			&task.ID,
			&task.Name,
			&task.Description,
			&task.Schedule,
			&task.Command,
			&task.ServiceName,
			&task.Enabled,
			&task.CreatedAt,
			&task.UpdatedAt,
			&task.CreatedBy,
			&metadataJSON,
			&task.TotalRuns,
			&task.LastRunAt,
			&lastRunStatus,
			&task.SuccessRate,
			&task.AvgDurationMs,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan task: %w", err)
		}

		if err := json.Unmarshal(metadataJSON, &task.Metadata); err != nil {
			return nil, fmt.Errorf("failed to unmarshal metadata: %w", err)
		}

		if lastRunStatus != nil {
			status := types.TaskStatus(*lastRunStatus)
			task.LastRunStatus = &status
		}

		tasks = append(tasks, &task)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating tasks: %w", err)
	}

	return tasks, nil
}
