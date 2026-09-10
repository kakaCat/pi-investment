package scheduler

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"os/exec"
	"strings"
	"syscall"
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
			delay := RetryDelayFor(attempt, lastErr, e.config.RetryDelay)
			logger.Info("Retrying task execution",
				"task_id", task.ID,
				"task_name", task.Name,
				"run_id", run.ID,
				"attempt", attempt,
				"delay", delay.String(),
				"connection_failure", IsConnectionFailure(lastErr))
			time.Sleep(delay)
		}

		// Update status to running
		if err := e.taskRunRepo.UpdateStatus(ctx, run.ID, types.TaskStatusRunning); err != nil {
			logger.Error("Failed to update task run status to running",
				"run_id", run.ID,
				"error", err)
		}

		// Execute the task (webhook or command)
		var output string
		var err error

		if task.WebhookURL != "" {
			output, err = e.executeWebhook(ctx, task, run)
		} else if task.Command != "" {
			output, err = e.executeCommand(ctx, task.Command, e.config.DefaultTimeout)
		} else {
			err = fmt.Errorf("task has neither webhook_url nor command")
		}

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

// buildWebhookPayload constructs the webhook request body following the
// WP-15 receiver contract (e.g. quantsys-v2 /internal/scheduler/webhook):
// job_id, job_name, trigger_time and metadata are all required top-level
// fields; the task payload and run context travel inside metadata.
func buildWebhookPayload(task *types.Task, run *types.TaskRun) map[string]interface{} {
	metadata := make(map[string]interface{}, len(task.Payload)+3)
	for k, v := range task.Payload {
		metadata[k] = v
	}
	metadata["run_id"] = run.ID.String()
	metadata["owner"] = task.Owner
	metadata["triggered_by"] = string(run.TriggeredBy)

	return map[string]interface{}{
		"job_id":       task.ID.String(),
		"job_name":     task.Name,
		"trigger_time": time.Now().UTC().Format(time.RFC3339),
		"metadata":     metadata,
	}
}

// executeWebhook executes a task by calling its webhook URL
func (e *Executor) executeWebhook(ctx context.Context, task *types.Task, run *types.TaskRun) (string, error) {
	// Determine timeout
	timeout := e.config.DefaultTimeout
	if task.Timeout > 0 {
		timeout = time.Duration(task.Timeout) * time.Second
	}

	// Create context with timeout
	execCtx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	// Construct webhook payload (WP-15 receiver contract)
	payload := buildWebhookPayload(task, run)

	// Marshal payload to JSON
	payloadBytes, err := json.Marshal(payload)
	if err != nil {
		return "", fmt.Errorf("failed to marshal webhook payload: %w", err)
	}

	// Create HTTP request
	req, err := http.NewRequestWithContext(execCtx, "POST", task.WebhookURL, bytes.NewBuffer(payloadBytes))
	if err != nil {
		return "", fmt.Errorf("failed to create webhook request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("User-Agent", "Agent-OS-Scheduler/1.0")

	// Send request
	logger.Info("Sending webhook request",
		"task_id", task.ID,
		"task_name", task.Name,
		"webhook_url", task.WebhookURL,
		"run_id", run.ID)

	client := &http.Client{
		Timeout: timeout,
	}

	resp, err := client.Do(req)
	if err != nil {
		if execCtx.Err() == context.DeadlineExceeded {
			return "", fmt.Errorf("webhook timeout after %v", timeout)
		}
		return "", fmt.Errorf("webhook request failed: %w", err)
	}
	defer resp.Body.Close()

	// Read response body
	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return "", fmt.Errorf("failed to read webhook response: %w", err)
	}

	output := string(respBody)

	// Check response status
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return output, fmt.Errorf("webhook returned non-2xx status: %d (body: %s)", resp.StatusCode, output)
	}

	logger.Info("Webhook executed successfully",
		"task_id", task.ID,
		"task_name", task.Name,
		"webhook_url", task.WebhookURL,
		"status_code", resp.StatusCode,
		"run_id", run.ID)

	return output, nil
}

// IsConnectionFailure reports whether err looks like the downstream endpoint
// was unreachable (as opposed to returning a bad response).
//
// Rationale (2026-09-11): scheduled agent-webhook tasks talk to long-running
// local services (e.g. the DSH instance on 127.0.0.1:13080). While such a
// service restarts, the port is closed and the call fails with
// "dial tcp 127.0.0.1:13080: connect: connection refused". agent-os stderr
// between 2026-08-27 and 2026-09-11 contains 96 such failures across 10+
// agent-brain-* routines, each one silently losing that run of the routine.
func IsConnectionFailure(err error) bool {
	if err == nil {
		return false
	}
	if errors.Is(err, syscall.ECONNREFUSED) ||
		errors.Is(err, syscall.ECONNRESET) ||
		errors.Is(err, syscall.EHOSTUNREACH) ||
		errors.Is(err, syscall.ENETUNREACH) {
		return true
	}
	var netErr net.Error
	if errors.As(err, &netErr) && netErr.Timeout() {
		return true
	}
	// Fallback for wrapped errors whose errno got stringified along the way.
	msg := strings.ToLower(err.Error())
	for _, marker := range []string{
		"connection refused",
		"connection reset",
		"no route to host",
		"network is unreachable",
		"i/o timeout",
		"connection timed out",
	} {
		if strings.Contains(msg, marker) {
			return true
		}
	}
	return false
}

// RetryDelayFor returns the wait before the given retry attempt.
//
// Connection failures get an escalating backoff so the retry window covers a
// service restart, while ordinary failures keep the configured fixed delay.
// With the default RetryDelay of 5s the total window grows from ~10s
// (5s + 5s) to ~90s (30s + 60s), which is longer than a DSH instance restart.
func RetryDelayFor(attempt int, lastErr error, base time.Duration) time.Duration {
	if attempt <= 0 {
		return 0
	}
	if !IsConnectionFailure(lastErr) {
		return base
	}
	if base <= 0 {
		base = 5 * time.Second
	}
	delay := base * time.Duration(6*attempt)
	if maxDelay := 2 * time.Minute; delay > maxDelay {
		delay = maxDelay
	}
	return delay
}
