package scheduler

import (
	"context"
	"time"

	"github.com/google/uuid"
	"github.com/pi-investment/agent-os/internal/kernel/scheduler/types"
	"github.com/pi-investment/agent-os/pkg/logger"
)

// OrphanedTask represents a task that exists in database but not in scheduler
type OrphanedTask struct {
	ID               uuid.UUID  `json:"id"`
	Name             string     `json:"name"`
	ScheduleExpr     string     `json:"scheduleExpr"`
	LastRunAt        *time.Time `json:"lastRunAt"`
	CreatedAt        time.Time  `json:"createdAt"`
	InScheduler      bool       `json:"inScheduler"`
	InDatabase       bool       `json:"inDatabase"`
	DaysSinceLastRun int        `json:"daysSinceLastRun"`
	Enabled          bool       `json:"enabled"`
	Reason           string     `json:"reason"`
	WebhookURL       string     `json:"webhookUrl,omitempty"`
}

// DetectOrphanedTasks finds tasks in database that are not loaded in scheduler
func (s *Scheduler) DetectOrphanedTasks(ctx context.Context) ([]*OrphanedTask, error) {
	// 1. Get all tasks from database (including disabled)
	allTasks, err := s.taskRepo.List(ctx, false)
	if err != nil {
		return nil, err
	}

	// 2. Get scheduled task IDs from scheduler
	s.mu.RLock()
	scheduledIDs := make(map[uuid.UUID]bool)
	for id := range s.tasks {
		scheduledIDs[id] = true
	}
	s.mu.RUnlock()

	// 3. Find orphaned tasks (in DB but not in scheduler)
	var orphaned []*OrphanedTask
	now := time.Now()

	for _, task := range allTasks {
		inScheduler := scheduledIDs[task.ID]

		// Skip if task is in scheduler
		if inScheduler {
			continue
		}

		// This is an orphaned task
		var lastRunAt *time.Time
		var daysSince int

		// Try to get last run time (use GetLatestRunByTaskID)
		lastRun, err := s.taskRunRepo.GetLatestRunByTaskID(ctx, task.ID)
		if err == nil && lastRun != nil {
			lastRunAt = &lastRun.StartedAt
			daysSince = int(now.Sub(lastRun.StartedAt).Hours() / 24)
		} else {
			// Never executed, calculate days since creation
			daysSince = int(now.Sub(task.CreatedAt).Hours() / 24)
		}

		reason := determineOrphanedReason(task)

		orphaned = append(orphaned, &OrphanedTask{
			ID:               task.ID,
			Name:             task.Name,
			ScheduleExpr:     task.Cron,
			LastRunAt:        lastRunAt,
			CreatedAt:        task.CreatedAt,
			InScheduler:      false,
			InDatabase:       true,
			DaysSinceLastRun: daysSince,
			Enabled:          task.Enabled,
			Reason:           reason,
			WebhookURL:       task.WebhookURL,
		})
	}

	logger.Info("Orphaned tasks detected",
		"count", len(orphaned),
		"total_tasks", len(allTasks),
		"scheduled_tasks", len(scheduledIDs))

	return orphaned, nil
}

// determineOrphanedReason determines why a task is orphaned
func determineOrphanedReason(task *types.Task) string {
	if !task.Enabled {
		return "任务已禁用"
	}
	if task.Cron == "" {
		return "缺少 cron 表达式"
	}
	if task.WebhookURL != "" {
		return "webhook URL 可能不可达"
	}
	if task.Command == "" {
		return "缺少执行命令"
	}
	return "加载失败或配置错误"
}

// CleanupOrphanedTask deletes an orphaned task from database
func (s *Scheduler) CleanupOrphanedTask(ctx context.Context, taskID uuid.UUID) error {
	// Verify task is not in scheduler (safety check)
	s.mu.RLock()
	_, inScheduler := s.tasks[taskID]
	s.mu.RUnlock()

	if inScheduler {
		return logger.ErrorReturn("cannot delete task that is in scheduler", "task_id", taskID)
	}

	// Delete from database
	if err := s.taskRepo.Delete(ctx, taskID); err != nil {
		return err
	}

	logger.Info("Orphaned task cleaned up", "task_id", taskID)
	return nil
}
