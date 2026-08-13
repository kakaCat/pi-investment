package scheduler

import (
	"context"
	"fmt"
	"os/exec"
	"strings"
	"time"

	"github.com/pi-investment/agent-os/internal/storage/postgres"
	"github.com/pi-investment/agent-os/pkg/logger"
	"github.com/pi-investment/agent-os/pkg/types"
)

// Executor handles task execution with timeout, retry, and concurrency control
type Executor struct {
	taskRunRepo *postgres.TaskRunRepository
	config      *types.SchedulerConfig
	semaphore   chan struct{} // Semaphore for concurrency control
}

// NewExecutor creates a new Executor
func NewExecutor(config *types.SchedulerConfig) *Executor {
	return &Executor{
		taskRunRepo: postgres.NewTaskRunRepository(),
		config:      config,
		semaphore:   make(chan struct{}, config.MaxConcurrentTasks),
	}
}

// Execute executes a task with timeout and retry logic
func (e *Executor) Execute(ctx context.Context, task *types.Task, triggeredBy types.TriggerSource) (*types.TaskRun, error) {
	// Acquire semaphore (concurrency control)
	select {
	case e.semaphore <- struct{}{}:
		defer func() { <-e.semaphore }()
	case <-ctx.Done():
		return nil, fmt.Errorf("context canceled while waiting for execution slot")
	}

	// Create task run record
	run := &types.TaskRun{
		TaskID:      task.ID,
		Status:      types.TaskStatusPending,
		TriggeredBy: triggeredBy,
		Metadata:    make(map[string]interface{}),
	}

	if err := e.taskRunRepo.Create(ctx, run); err != nil {
		return nil, fmt.Errorf("failed to create task run: %w", err)
	}

	logger.Info("Task execution started",
		"task_id", task.ID,
		"task_name", task.Name,
		"run_id", run.ID,
		"triggered_by", triggeredBy)

	// Execute with retries
	var lastErr error
	for attempt := 0; attempt <= e.config.MaxRetries; attempt++ {
		if attempt > 0 {
			logger.Info("Retrying task execution",
				"task_id", task.ID,
				"task_name", task.Name,
				"run_id", run.ID,
				"attempt", attempt)
			time.Sleep(e.config.RetryDelay)
		}

		// Update status to running
		if err := e.taskRunRepo.UpdateStatus(ctx, run.ID, types.TaskStatusRunning); err != nil {
			logger.Error("Failed to update task run status to running",
				"run_id", run.ID,
				"error", err)
		}

		// Execute the task
		output, err := e.executeCommand(ctx, task.Command, e.config.DefaultTimeout)

		if err == nil {
			// Success
			if err := e.taskRunRepo.Complete(ctx, run.ID, types.TaskStatusSuccess, output, ""); err != nil {
				logger.Error("Failed to mark task run as completed",
					"run_id", run.ID,
					"error", err)
			}

			logger.Info("Task execution succeeded",
				"task_id", task.ID,
				"task_name", task.Name,
				"run_id", run.ID,
				"attempts", attempt+1)

			run.Status = types.TaskStatusSuccess
			run.Output = output
			now := time.Now()
			run.FinishedAt = &now

			return run, nil
		}

		lastErr = err

		// Check if it's a timeout error
		if ctx.Err() == context.DeadlineExceeded {
			if err := e.taskRunRepo.Complete(ctx, run.ID, types.TaskStatusTimeout, output, err.Error()); err != nil {
				logger.Error("Failed to mark task run as timeout",
					"run_id", run.ID,
					"error", err)
			}

			logger.Error("Task execution timeout",
				"task_id", task.ID,
				"task_name", task.Name,
				"run_id", run.ID,
				"timeout", e.config.DefaultTimeout)

			run.Status = types.TaskStatusTimeout
			run.Error = err.Error()
			now := time.Now()
			run.FinishedAt = &now

			return run, fmt.Errorf("task execution timeout: %w", err)
		}

		logger.Error("Task execution failed",
			"task_id", task.ID,
			"task_name", task.Name,
			"run_id", run.ID,
			"attempt", attempt+1,
			"error", err)
	}

	// All retries failed
	if err := e.taskRunRepo.Complete(ctx, run.ID, types.TaskStatusFailed, "", lastErr.Error()); err != nil {
		logger.Error("Failed to mark task run as failed",
			"run_id", run.ID,
			"error", err)
	}

	logger.Error("Task execution failed after all retries",
		"task_id", task.ID,
		"task_name", task.Name,
		"run_id", run.ID,
		"max_retries", e.config.MaxRetries)

	run.Status = types.TaskStatusFailed
	run.Error = lastErr.Error()
	now := time.Now()
	run.FinishedAt = &now

	return run, fmt.Errorf("task execution failed after %d retries: %w", e.config.MaxRetries, lastErr)
}

// executeCommand executes a shell command with timeout
func (e *Executor) executeCommand(ctx context.Context, command string, timeout time.Duration) (string, error) {
	// Create context with timeout
	execCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	// Parse command (split by spaces, respecting quotes)
	args := parseCommand(command)
	if len(args) == 0 {
		return "", fmt.Errorf("empty command")
	}

	// Create command
	cmd := exec.CommandContext(execCtx, args[0], args[1:]...)

	// Execute command
	output, err := cmd.CombinedOutput()

	if execCtx.Err() == context.DeadlineExceeded {
		return string(output), fmt.Errorf("command timeout after %v", timeout)
	}

	if err != nil {
		return string(output), fmt.Errorf("command failed: %w (output: %s)", err, string(output))
	}

	return string(output), nil
}

// parseCommand parses a command string into args, respecting quotes
func parseCommand(command string) []string {
	var args []string
	var current strings.Builder
	inQuote := false
	quoteChar := rune(0)

	for _, r := range command {
		switch {
		case r == '"' || r == '\'':
			if inQuote {
				if r == quoteChar {
					inQuote = false
					quoteChar = 0
				} else {
					current.WriteRune(r)
				}
			} else {
				inQuote = true
				quoteChar = r
			}
		case r == ' ' && !inQuote:
			if current.Len() > 0 {
				args = append(args, current.String())
				current.Reset()
			}
		default:
			current.WriteRune(r)
		}
	}

	if current.Len() > 0 {
		args = append(args, current.String())
	}

	return args
}

// GetRunningCount returns the number of currently running tasks
func (e *Executor) GetRunningCount() int {
	return len(e.semaphore)
}

// GetAvailableSlots returns the number of available execution slots
func (e *Executor) GetAvailableSlots() int {
	return e.config.MaxConcurrentTasks - e.GetRunningCount()
}
