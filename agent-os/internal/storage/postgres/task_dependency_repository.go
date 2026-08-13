package postgres

import (
	"context"
	"fmt"

	"github.com/google/uuid"
	"github.com/pi-investment/agent-os/pkg/types"
)

// TaskDependencyRepository handles task dependency-related database operations
type TaskDependencyRepository struct {
	pool Querier
}

// NewTaskDependencyRepository creates a new TaskDependencyRepository
func NewTaskDependencyRepository() *TaskDependencyRepository {
	return &TaskDependencyRepository{
		pool: GetPool(),
	}
}

// Create creates a new task dependency
func (r *TaskDependencyRepository) Create(ctx context.Context, dep *types.TaskDependency) error {
	query := `
		INSERT INTO task_dependencies (task_id, depends_on_task_id)
		VALUES ($1, $2)
		RETURNING id, created_at
	`

	err := r.pool.QueryRow(ctx, query, dep.TaskID, dep.DependsOnTaskID).Scan(&dep.ID, &dep.CreatedAt)
	if err != nil {
		return fmt.Errorf("failed to create task dependency: %w", err)
	}

	return nil
}

// Delete deletes a task dependency
func (r *TaskDependencyRepository) Delete(ctx context.Context, taskID, dependsOnTaskID uuid.UUID) error {
	query := `DELETE FROM task_dependencies WHERE task_id = $1 AND depends_on_task_id = $2`

	tag, err := r.pool.Exec(ctx, query, taskID, dependsOnTaskID)
	if err != nil {
		return fmt.Errorf("failed to delete task dependency: %w", err)
	}

	if tag.RowsAffected() == 0 {
		return fmt.Errorf("task dependency not found")
	}

	return nil
}

// GetDependencies retrieves all dependencies for a task (tasks that this task depends on)
func (r *TaskDependencyRepository) GetDependencies(ctx context.Context, taskID uuid.UUID) ([]uuid.UUID, error) {
	query := `
		SELECT depends_on_task_id
		FROM task_dependencies
		WHERE task_id = $1
		ORDER BY created_at
	`

	rows, err := r.pool.Query(ctx, query, taskID)
	if err != nil {
		return nil, fmt.Errorf("failed to get dependencies: %w", err)
	}
	defer rows.Close()

	var deps []uuid.UUID
	for rows.Next() {
		var depID uuid.UUID
		if err := rows.Scan(&depID); err != nil {
			return nil, fmt.Errorf("failed to scan dependency: %w", err)
		}
		deps = append(deps, depID)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating dependencies: %w", err)
	}

	return deps, nil
}

// GetDependents retrieves all tasks that depend on this task
func (r *TaskDependencyRepository) GetDependents(ctx context.Context, taskID uuid.UUID) ([]uuid.UUID, error) {
	query := `
		SELECT task_id
		FROM task_dependencies
		WHERE depends_on_task_id = $1
		ORDER BY created_at
	`

	rows, err := r.pool.Query(ctx, query, taskID)
	if err != nil {
		return nil, fmt.Errorf("failed to get dependents: %w", err)
	}
	defer rows.Close()

	var deps []uuid.UUID
	for rows.Next() {
		var depID uuid.UUID
		if err := rows.Scan(&depID); err != nil {
			return nil, fmt.Errorf("failed to scan dependent: %w", err)
		}
		deps = append(deps, depID)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating dependents: %w", err)
	}

	return deps, nil
}

// GetAllDependencies retrieves all task dependencies
func (r *TaskDependencyRepository) GetAllDependencies(ctx context.Context) ([]*types.TaskDependency, error) {
	query := `
		SELECT id, task_id, depends_on_task_id, created_at
		FROM task_dependencies
		ORDER BY created_at
	`

	rows, err := r.pool.Query(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("failed to get all dependencies: %w", err)
	}
	defer rows.Close()

	var deps []*types.TaskDependency
	for rows.Next() {
		var dep types.TaskDependency
		if err := rows.Scan(&dep.ID, &dep.TaskID, &dep.DependsOnTaskID, &dep.CreatedAt); err != nil {
			return nil, fmt.Errorf("failed to scan dependency: %w", err)
		}
		deps = append(deps, &dep)
	}

	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("error iterating dependencies: %w", err)
	}

	return deps, nil
}

// HasCircularDependency checks if adding a dependency would create a circular dependency
func (r *TaskDependencyRepository) HasCircularDependency(ctx context.Context, taskID, dependsOnTaskID uuid.UUID) (bool, error) {
	// Use a recursive CTE to check for circular dependencies
	query := `
		WITH RECURSIVE dep_chain AS (
			-- Base case: direct dependencies of the task we want to depend on
			SELECT depends_on_task_id as task_id, 1 as depth
			FROM task_dependencies
			WHERE task_id = $1

			UNION ALL

			-- Recursive case: follow the dependency chain
			SELECT td.depends_on_task_id, dc.depth + 1
			FROM task_dependencies td
			JOIN dep_chain dc ON td.task_id = dc.task_id
			WHERE dc.depth < 100  -- Prevent infinite recursion
		)
		SELECT EXISTS (
			SELECT 1 FROM dep_chain WHERE task_id = $2
		)
	`

	var hasCircular bool
	err := r.pool.QueryRow(ctx, query, dependsOnTaskID, taskID).Scan(&hasCircular)
	if err != nil {
		return false, fmt.Errorf("failed to check circular dependency: %w", err)
	}

	return hasCircular, nil
}
