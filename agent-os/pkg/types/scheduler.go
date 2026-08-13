package types

import (
	"time"

	"github.com/google/uuid"
)

// TaskStatus represents the status of a task execution
type TaskStatus string

const (
	TaskStatusPending TaskStatus = "pending"
	TaskStatusRunning TaskStatus = "running"
	TaskStatusSuccess TaskStatus = "success"
	TaskStatusFailed  TaskStatus = "failed"
	TaskStatusTimeout TaskStatus = "timeout"
	TaskStatusCanceled TaskStatus = "canceled"
)

// TriggerSource represents who triggered the task
type TriggerSource string

const (
	TriggerSourceScheduler TriggerSource = "scheduler"
	TriggerSourceManual    TriggerSource = "manual"
	TriggerSourceWebhook   TriggerSource = "webhook"
	TriggerSourceDependency TriggerSource = "dependency"
)

// Task represents a task definition
type Task struct {
	ID          uuid.UUID              `json:"id"`
	Name        string                 `json:"name"`
	Description string                 `json:"description,omitempty"`
	Schedule    string                 `json:"schedule,omitempty"` // Cron expression
	Command     string                 `json:"command"`
	Enabled     bool                   `json:"enabled"`
	CreatedAt   time.Time              `json:"created_at"`
	UpdatedAt   time.Time              `json:"updated_at"`
	CreatedBy   string                 `json:"created_by,omitempty"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`

	// Runtime fields (not stored in DB)
	Dependencies []uuid.UUID `json:"dependencies,omitempty"`
}

// TaskRun represents a task execution
type TaskRun struct {
	ID          uuid.UUID              `json:"id"`
	TaskID      uuid.UUID              `json:"task_id"`
	Status      TaskStatus             `json:"status"`
	StartedAt   time.Time              `json:"started_at"`
	FinishedAt  *time.Time             `json:"finished_at,omitempty"`
	DurationMs  *int64                 `json:"duration_ms,omitempty"`
	Output      string                 `json:"output,omitempty"`
	Error       string                 `json:"error,omitempty"`
	TriggeredBy TriggerSource          `json:"triggered_by"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
}

// TaskDependency represents a dependency between tasks
type TaskDependency struct {
	ID             uuid.UUID `json:"id"`
	TaskID         uuid.UUID `json:"task_id"`
	DependsOnTaskID uuid.UUID `json:"depends_on_task_id"`
	CreatedAt      time.Time `json:"created_at"`
}

// TaskWithStats represents a task with execution statistics
type TaskWithStats struct {
	Task
	TotalRuns      int        `json:"total_runs"`
	LastRunAt      *time.Time `json:"last_run_at,omitempty"`
	LastRunStatus  *TaskStatus `json:"last_run_status,omitempty"`
	SuccessRate    float64    `json:"success_rate"`
	AvgDurationMs  *int64     `json:"avg_duration_ms,omitempty"`
}

// SchedulerConfig represents scheduler configuration
type SchedulerConfig struct {
	MaxConcurrentTasks int           `json:"max_concurrent_tasks"`
	DefaultTimeout     time.Duration `json:"default_timeout"`
	MaxRetries         int           `json:"max_retries"`
	RetryDelay         time.Duration `json:"retry_delay"`
}
