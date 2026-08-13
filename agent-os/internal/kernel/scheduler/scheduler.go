package scheduler

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/pi-investment/agent-os/internal/storage/postgres"
	"github.com/pi-investment/agent-os/pkg/logger"
	"github.com/pi-investment/agent-os/pkg/types"
	"github.com/robfig/cron/v3"
)

// Scheduler manages task scheduling and execution
type Scheduler struct {
	taskRepo       *postgres.TaskRepository
	taskRunRepo    *postgres.TaskRunRepository
	depRepo        *postgres.TaskDependencyRepository
	executor       *Executor
	cron           *cron.Cron
	dag            *DAG
	config         *types.SchedulerConfig
	mu             sync.RWMutex
	cronEntries    map[uuid.UUID]cron.EntryID // taskID -> cronEntryID
	running        bool
	ctx            context.Context
	cancel         context.CancelFunc
}

// New creates a new Scheduler
func New(config *types.SchedulerConfig) *Scheduler {
	if config == nil {
		config = &types.SchedulerConfig{
			MaxConcurrentTasks: 5,
			DefaultTimeout:     30 * time.Minute,
			MaxRetries:         2,
			RetryDelay:         5 * time.Second,
		}
	}

	return &Scheduler{
		taskRepo:    postgres.NewTaskRepository(),
		taskRunRepo: postgres.NewTaskRunRepository(),
		depRepo:     postgres.NewTaskDependencyRepository(),
		executor:    NewExecutor(config),
		cron:        cron.New(cron.WithSeconds()),
		dag:         NewDAG(),
		config:      config,
		cronEntries: make(map[uuid.UUID]cron.EntryID),
	}
}

// Start starts the scheduler
func (s *Scheduler) Start(ctx context.Context) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.running {
		return fmt.Errorf("scheduler already running")
	}

	s.ctx, s.cancel = context.WithCancel(ctx)

	// Load tasks and dependencies from database
	if err := s.loadTasksAndDependencies(); err != nil {
		return fmt.Errorf("failed to load tasks: %w", err)
	}

	// Start cron scheduler
	s.cron.Start()
	s.running = true

	logger.Info("Scheduler started",
		"max_concurrent_tasks", s.config.MaxConcurrentTasks,
		"default_timeout", s.config.DefaultTimeout,
		"max_retries", s.config.MaxRetries)

	return nil
}

// Stop stops the scheduler
func (s *Scheduler) Stop() error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if !s.running {
		return fmt.Errorf("scheduler not running")
	}

	// Stop cron scheduler
	ctx := s.cron.Stop()
	<-ctx.Done()

	// Cancel context
	s.cancel()
	s.running = false

	logger.Info("Scheduler stopped")

	return nil
}

// RegisterTask registers a new task
func (s *Scheduler) RegisterTask(ctx context.Context, task *types.Task) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	// Create task in database
	if err := s.taskRepo.Create(ctx, task); err != nil {
		return fmt.Errorf("failed to register task: %w", err)
	}

	// Add to DAG
	s.dag.AddTask(task.ID)

	// Add dependencies if specified
	for _, depID := range task.Dependencies {
		if err := s.AddDependency(ctx, task.ID, depID); err != nil {
			return fmt.Errorf("failed to add dependency: %w", err)
		}
	}

	// Schedule if has cron expression and is enabled
	if task.Enabled && task.Schedule != "" {
		if err := s.scheduleTask(task); err != nil {
			return fmt.Errorf("failed to schedule task: %w", err)
		}
	}

	logger.Info("Task registered",
		"task_id", task.ID,
		"task_name", task.Name,
		"schedule", task.Schedule)

	return nil
}

// UpdateTask updates an existing task
func (s *Scheduler) UpdateTask(ctx context.Context, task *types.Task) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	// Get existing task
	existing, err := s.taskRepo.GetByID(ctx, task.ID)
	if err != nil {
		return fmt.Errorf("failed to get existing task: %w", err)
	}

	// Update in database
	if err := s.taskRepo.Update(ctx, task); err != nil {
		return fmt.Errorf("failed to update task: %w", err)
	}

	// Reschedule if schedule changed
	if existing.Schedule != task.Schedule || existing.Enabled != task.Enabled {
		// Remove old schedule
		if entryID, exists := s.cronEntries[task.ID]; exists {
			s.cron.Remove(entryID)
			delete(s.cronEntries, task.ID)
		}

		// Add new schedule if enabled
		if task.Enabled && task.Schedule != "" {
			if err := s.scheduleTask(task); err != nil {
				return fmt.Errorf("failed to reschedule task: %w", err)
			}
		}
	}

	logger.Info("Task updated",
		"task_id", task.ID,
		"task_name", task.Name)

	return nil
}

// DeleteTask deletes a task
func (s *Scheduler) DeleteTask(ctx context.Context, taskID uuid.UUID) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	// Remove from cron if scheduled
	if entryID, exists := s.cronEntries[taskID]; exists {
		s.cron.Remove(entryID)
		delete(s.cronEntries, taskID)
	}

	// Delete from database (cascades to dependencies and runs)
	if err := s.taskRepo.Delete(ctx, taskID); err != nil {
		return fmt.Errorf("failed to delete task: %w", err)
	}

	logger.Info("Task deleted", "task_id", taskID)

	return nil
}

// TriggerTask manually triggers a task
func (s *Scheduler) TriggerTask(ctx context.Context, taskID uuid.UUID) (*types.TaskRun, error) {
	// Get task
	task, err := s.taskRepo.GetByID(ctx, taskID)
	if err != nil {
		return nil, fmt.Errorf("failed to get task: %w", err)
	}

	if !task.Enabled {
		return nil, fmt.Errorf("task is disabled: %s", task.Name)
	}

	logger.Info("Manually triggering task",
		"task_id", task.ID,
		"task_name", task.Name)

	// Execute task
	return s.executeTask(ctx, task, types.TriggerSourceManual)
}

// AddDependency adds a dependency between tasks
func (s *Scheduler) AddDependency(ctx context.Context, taskID, dependsOnTaskID uuid.UUID) error {
	// Check if both tasks exist
	if _, err := s.taskRepo.GetByID(ctx, taskID); err != nil {
		return fmt.Errorf("task not found: %s", taskID)
	}
	if _, err := s.taskRepo.GetByID(ctx, dependsOnTaskID); err != nil {
		return fmt.Errorf("dependency task not found: %s", dependsOnTaskID)
	}

	// Check for circular dependency
	hasCircular, err := s.depRepo.HasCircularDependency(ctx, taskID, dependsOnTaskID)
	if err != nil {
		return fmt.Errorf("failed to check circular dependency: %w", err)
	}
	if hasCircular {
		return fmt.Errorf("circular dependency detected")
	}

	// Add to database
	dep := &types.TaskDependency{
		TaskID:          taskID,
		DependsOnTaskID: dependsOnTaskID,
	}
	if err := s.depRepo.Create(ctx, dep); err != nil {
		return fmt.Errorf("failed to create dependency: %w", err)
	}

	// Add to DAG
	if err := s.dag.AddDependency(taskID, dependsOnTaskID); err != nil {
		return fmt.Errorf("failed to add dependency to DAG: %w", err)
	}

	logger.Info("Dependency added",
		"task_id", taskID,
		"depends_on", dependsOnTaskID)

	return nil
}

// RemoveDependency removes a dependency between tasks
func (s *Scheduler) RemoveDependency(ctx context.Context, taskID, dependsOnTaskID uuid.UUID) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	// Remove from database
	if err := s.depRepo.Delete(ctx, taskID, dependsOnTaskID); err != nil {
		return fmt.Errorf("failed to delete dependency: %w", err)
	}

	// Remove from DAG
	s.dag.RemoveDependency(taskID, dependsOnTaskID)

	logger.Info("Dependency removed",
		"task_id", taskID,
		"depends_on", dependsOnTaskID)

	return nil
}

// GetTask retrieves a task by ID
func (s *Scheduler) GetTask(ctx context.Context, taskID uuid.UUID) (*types.Task, error) {
	return s.taskRepo.GetByID(ctx, taskID)
}

// ListTasks lists all tasks
func (s *Scheduler) ListTasks(ctx context.Context, enabledOnly bool) ([]*types.Task, error) {
	return s.taskRepo.List(ctx, enabledOnly)
}

// GetTaskRuns retrieves runs for a task
func (s *Scheduler) GetTaskRuns(ctx context.Context, taskID uuid.UUID, limit int) ([]*types.TaskRun, error) {
	return s.taskRunRepo.ListByTaskID(ctx, taskID, limit)
}

// GetTasksWithStats retrieves tasks with execution statistics
func (s *Scheduler) GetTasksWithStats(ctx context.Context) ([]*types.TaskWithStats, error) {
	return s.taskRepo.GetTasksWithStats(ctx)
}

// scheduleTask schedules a task with cron
func (s *Scheduler) scheduleTask(task *types.Task) error {
	entryID, err := s.cron.AddFunc(task.Schedule, func() {
		ctx := context.Background()
		_, err := s.executeTask(ctx, task, types.TriggerSourceScheduler)
		if err != nil {
			logger.Error("Scheduled task execution failed",
				"task_id", task.ID,
				"task_name", task.Name,
				"error", err)
		}
	})

	if err != nil {
		return fmt.Errorf("failed to add cron job: %w", err)
	}

	s.cronEntries[task.ID] = entryID

	logger.Info("Task scheduled",
		"task_id", task.ID,
		"task_name", task.Name,
		"schedule", task.Schedule)

	return nil
}

// executeTask executes a task, checking dependencies first
func (s *Scheduler) executeTask(ctx context.Context, task *types.Task, triggeredBy types.TriggerSource) (*types.TaskRun, error) {
	// Check dependencies
	deps := s.dag.GetDependencies(task.ID)
	if len(deps) > 0 {
		// Check if all dependencies completed successfully
		completedTasks := make(map[uuid.UUID]bool)
		for _, depID := range deps {
			latestRun, err := s.taskRunRepo.GetLatestRunByTaskID(ctx, depID)
			if err != nil {
				return nil, fmt.Errorf("failed to check dependency status: %w", err)
			}
			if latestRun == nil || latestRun.Status != types.TaskStatusSuccess {
				return nil, fmt.Errorf("dependency not satisfied: task %s has not completed successfully", depID)
			}
			completedTasks[depID] = true
		}

		if !s.dag.CanExecute(task.ID, completedTasks) {
			return nil, fmt.Errorf("dependencies not satisfied")
		}
	}

	// Execute task
	return s.executor.Execute(ctx, task, triggeredBy)
}

// loadTasksAndDependencies loads tasks and dependencies from database
func (s *Scheduler) loadTasksAndDependencies() error {
	ctx := context.Background()

	// Load scheduled tasks
	tasks, err := s.taskRepo.GetScheduledTasks(ctx)
	if err != nil {
		return fmt.Errorf("failed to load scheduled tasks: %w", err)
	}

	// Add tasks to DAG
	for _, task := range tasks {
		s.dag.AddTask(task.ID)
	}

	// Load dependencies
	deps, err := s.depRepo.GetAllDependencies(ctx)
	if err != nil {
		return fmt.Errorf("failed to load dependencies: %w", err)
	}

	// Add dependencies to DAG
	for _, dep := range deps {
		if err := s.dag.AddDependency(dep.TaskID, dep.DependsOnTaskID); err != nil {
			logger.Error("Failed to add dependency to DAG",
				"task_id", dep.TaskID,
				"depends_on", dep.DependsOnTaskID,
				"error", err)
		}
	}

	// Schedule tasks
	for _, task := range tasks {
		if err := s.scheduleTask(task); err != nil {
			logger.Error("Failed to schedule task",
				"task_id", task.ID,
				"task_name", task.Name,
				"error", err)
		}
	}

	logger.Info("Tasks and dependencies loaded",
		"task_count", len(tasks),
		"dependency_count", len(deps))

	return nil
}

// IsRunning returns true if the scheduler is running
func (s *Scheduler) IsRunning() bool {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.running
}
