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
	Owner       string                 `json:"owner"`                        // Agent owner ID
	Description string                 `json:"description,omitempty"`
	Schedule    string                 `json:"schedule,omitempty"`           // Cron expression (deprecated, use Cron)
	Cron        string                 `json:"cron,omitempty"`               // Cron expression
	Command     string                 `json:"command,omitempty"`            // Shell command (optional if webhook_url is set)
	WebhookURL  string                 `json:"webhook_url,omitempty"`        // HTTP webhook URL
	ServiceName string                 `json:"service_name,omitempty"`       // Bound local service (e.g. quantsys-v2); ensured running before execution
	Payload     map[string]interface{} `json:"payload,omitempty"`            // Task payload sent to webhook
	Timeout     int                    `json:"timeout,omitempty"`            // Timeout in seconds
	RetryCount  int                    `json:"retry_count,omitempty"`        // Max retry count on failure
	Enabled     bool                   `json:"enabled"`
	CreatedAt   time.Time              `json:"created_at"`
	UpdatedAt   time.Time              `json:"updated_at"`
	CreatedBy   string                 `json:"created_by,omitempty"`         // Deprecated, use Owner
	Metadata    map[string]interface{} `json:"metadata,omitempty"`           // Additional metadata

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
	MaxConcurrentTasks int                          `json:"max_concurrent_tasks"`
	DefaultTimeout     time.Duration                `json:"default_timeout"`
	MaxRetries         int                          `json:"max_retries"`
	RetryDelay         time.Duration                `json:"retry_delay"`
	// Services is the registry of local services a task can bind to via
	// Task.ServiceName. Entries override the built-in defaults by name.
	Services           map[string]ServiceDefinition `json:"services,omitempty"`
}

// ServiceDefinition describes a local service that scheduled tasks can
// depend on. The scheduler health-checks the service before executing a
// bound task and starts it (via StartCommand) when it is not running.
type ServiceDefinition struct {
	// HealthURL is an HTTP endpoint; a 2xx response means the service is up.
	HealthURL string `json:"health_url" mapstructure:"health_url" yaml:"health_url"`
	// StartCommand is a shell command used to start the service when the
	// health check fails. It is launched detached (new process group) so it
	// survives after Agent OS returns. Empty means "never auto-start".
	StartCommand string `json:"start_command,omitempty" mapstructure:"start_command" yaml:"start_command"`
	// WorkDir is the working directory for StartCommand.
	WorkDir string `json:"work_dir,omitempty" mapstructure:"work_dir" yaml:"work_dir"`
	// StartupTimeoutSeconds bounds how long to wait for the service to
	// become healthy after starting it (default 60).
	StartupTimeoutSeconds int `json:"startup_timeout_seconds,omitempty" mapstructure:"startup_timeout_seconds" yaml:"startup_timeout_seconds"`
}
