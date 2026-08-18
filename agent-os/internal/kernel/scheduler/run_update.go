package scheduler

import (
	"context"
	"fmt"

	"github.com/google/uuid"
	"github.com/pi-investment/agent-os/pkg/types"
)

// parseRunStatus validates a status string against the TaskStatus contract.
func parseRunStatus(s string) (types.TaskStatus, bool) {
	status := types.TaskStatus(s)
	switch status {
	case types.TaskStatusPending,
		types.TaskStatusRunning,
		types.TaskStatusSuccess,
		types.TaskStatusFailed,
		types.TaskStatusTimeout,
		types.TaskStatusCanceled:
		return status, true
	}
	return "", false
}

// isTerminalRunStatus reports whether the status ends the run
// (sets finished_at / duration via Complete).
func isTerminalRunStatus(s types.TaskStatus) bool {
	switch s {
	case types.TaskStatusSuccess,
		types.TaskStatusFailed,
		types.TaskStatusTimeout,
		types.TaskStatusCanceled:
		return true
	}
	return false
}

// GetTaskRun retrieves a single task run by ID.
func (s *Scheduler) GetTaskRun(ctx context.Context, runID uuid.UUID) (*types.TaskRun, error) {
	return s.taskRunRepo.GetByID(ctx, runID)
}

// UpdateTaskRunResult applies an externally reported result to a task run.
//
// Used by webhook receivers (e.g. quantsys-v2 WP-15) to report the real
// job outcome: the scheduler's own run record only tracks "webhook call
// succeeded", which for async receivers means "job accepted", not "job
// finished". Terminal statuses complete the run (finished_at, duration);
// non-terminal statuses just update the status column.
func (s *Scheduler) UpdateTaskRunResult(ctx context.Context, runID uuid.UUID, statusStr, output, errMsg string) (*types.TaskRun, error) {
	status, ok := parseRunStatus(statusStr)
	if !ok {
		return nil, fmt.Errorf("invalid status: %q", statusStr)
	}

	// Ensure the run exists (404 semantics for the API layer)
	if _, err := s.taskRunRepo.GetByID(ctx, runID); err != nil {
		return nil, fmt.Errorf("task run not found: %s", runID)
	}

	if isTerminalRunStatus(status) {
		if err := s.taskRunRepo.Complete(ctx, runID, status, output, errMsg); err != nil {
			return nil, fmt.Errorf("failed to complete task run: %w", err)
		}
	} else {
		if err := s.taskRunRepo.UpdateStatus(ctx, runID, status); err != nil {
			return nil, fmt.Errorf("failed to update task run status: %w", err)
		}
	}

	return s.taskRunRepo.GetByID(ctx, runID)
}
