package scheduler

import (
	"context"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/pi-investment/agent-os/pkg/logger"
	"github.com/pi-investment/agent-os/pkg/types"
	"github.com/robfig/cron/v3"
)

const (
	clockCheckInterval = 30 * time.Second
	clockJumpThreshold = 90 * time.Second
)

// wallClockJumpDetector 只比较墙钟。time.Time 自带的单调时钟在 macOS 睡眠期间会暂停，
// 直接用 time.Since 可能漏掉数小时的合盖睡眠；Round(0) 会去掉单调时钟读数。
type wallClockJumpDetector struct {
	lastWall  time.Time
	threshold time.Duration
}

func newWallClockJumpDetector(start time.Time, threshold time.Duration) *wallClockJumpDetector {
	return &wallClockJumpDetector{lastWall: start.Round(0), threshold: threshold}
}

func (d *wallClockJumpDetector) Check(now time.Time) (time.Duration, bool) {
	currentWall := now.Round(0)
	delta := currentWall.Sub(d.lastWall)
	d.lastWall = currentWall
	return delta, delta > d.threshold || delta < -d.threshold
}

// startClockJumpMonitor 在时钟跳变后恢复未来排程，不在这里执行历史槽位。
// 历史补偿由 scripts/scheduler_watchdog.py 按 catchup 策略单一执行，避免双执行器重复补跑。
func (s *Scheduler) startClockJumpMonitor(ctx context.Context) {
	ticker := time.NewTicker(clockCheckInterval)
	go func() {
		defer ticker.Stop()
		detector := newWallClockJumpDetector(time.Now(), clockJumpThreshold)
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				delta, jumped := detector.Check(time.Now())
				if !jumped {
					continue
				}
				logger.Warn("Wall clock jump detected; rebuilding future cron schedule",
					"delta", delta.String(), "threshold", clockJumpThreshold.String())
				if err := s.recoverFutureSchedule(ctx, fmt.Sprintf("wall clock jump %s", delta)); err != nil {
					logger.Error("Failed to rebuild cron schedule after clock jump", "error", err)
				}
			}
		}
	}()
}

// recoverFutureSchedule 重新读取启用任务并原子替换 cron。只有全部表达式解析成功才切换，
// 否则保留旧调度器；不得把一次恢复动作变成全量任务消失。
func (s *Scheduler) recoverFutureSchedule(ctx context.Context, reason string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if !s.running {
		return nil
	}
	tasks, err := s.taskRepo.GetScheduledTasks(ctx)
	if err != nil {
		return fmt.Errorf("load scheduled tasks for clock recovery: %w", err)
	}
	return s.rebuildCronLocked(tasks, reason)
}

// rebuildCronLocked 的调用者必须持有 s.mu。它不补跑历史槽位，只让新 cron 从当前时间计算下一次执行。
func (s *Scheduler) rebuildCronLocked(tasks []*types.Task, reason string) error {
	fresh := cron.New(cron.WithSeconds())
	freshEntries := make(map[uuid.UUID]cron.EntryID, len(tasks))
	for _, task := range tasks {
		cronExpr := normalizeCronExpression(task.Schedule)
		if cronExpr == "" {
			cronExpr = normalizeCronExpression(task.Cron)
		}
		entryID, err := fresh.AddFunc(cronExpr, s.scheduledTaskCallback(task))
		if err != nil {
			return fmt.Errorf("rebuild cron for task %s (%s): %w", task.Name, task.ID, err)
		}
		freshEntries[task.ID] = entryID
	}

	old := s.cron
	if old != nil {
		// Stop 只阻止旧 cron 继续派生任务；不等待正在执行的任务，避免恢复被长任务卡住。
		old.Stop()
	}
	s.cron = fresh
	s.cronEntries = freshEntries
	if s.running {
		fresh.Start()
	}
	logger.Info("Future cron schedule rebuilt", "reason", reason, "task_count", len(tasks))
	return nil
}
