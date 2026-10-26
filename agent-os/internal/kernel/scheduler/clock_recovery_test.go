package scheduler

import (
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/pi-investment/agent-os/pkg/types"
	"github.com/robfig/cron/v3"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func TestWallClockJumpDetectorSleepAndClockChanges(t *testing.T) {
	base := time.Date(2026, 10, 26, 1, 0, 0, 0, time.Local)
	detector := newWallClockJumpDetector(base, 90*time.Second)

	delta, jumped := detector.Check(base.Add(30 * time.Second))
	assert.False(t, jumped)
	assert.Equal(t, 30*time.Second, delta)

	// 故障注入：合盖两小时后第一次滴答必须检测到墙钟跳变。
	delta, jumped = detector.Check(base.Add(2 * time.Hour))
	assert.True(t, jumped)
	assert.Equal(t, 2*time.Hour-30*time.Second, delta)

	// 同一跳变只能触发一次；下一次正常滴答不得反复重建。
	_, jumped = detector.Check(base.Add(2*time.Hour + 30*time.Second))
	assert.False(t, jumped)

	// NTP/人工回拨同样会使旧排程失真，不能只看正向跳变。
	delta, jumped = detector.Check(base.Add(30 * time.Minute))
	assert.True(t, jumped)
	assert.Negative(t, delta)
}

func newClockRecoveryTestScheduler(running bool) *Scheduler {
	return &Scheduler{
		cron:        cron.New(cron.WithSeconds()),
		cronEntries: make(map[uuid.UUID]cron.EntryID),
		running:     running,
	}
}

func TestRebuildCronLockedStartsFromCurrentWallClock(t *testing.T) {
	s := newClockRecoveryTestScheduler(true)
	oldTask := &types.Task{ID: uuid.New(), Name: "old-future", Schedule: "0 0 22 * * *", Enabled: true}
	require.NoError(t, s.scheduleTask(oldTask))
	oldCron := s.cron

	newTask := &types.Task{ID: uuid.New(), Name: "new-future", Schedule: "0 0 23 * * *", Enabled: true}
	require.NoError(t, s.rebuildCronLocked([]*types.Task{newTask}, "injected sleep"))
	t.Cleanup(func() {
		ctx := s.cron.Stop()
		<-ctx.Done()
	})

	assert.NotSame(t, oldCron, s.cron)
	require.Len(t, s.cron.Entries(), 1)
	entry := s.cron.Entries()[0]
	assert.True(t, entry.Next.After(time.Now()), "重建后必须只排未来时点，不得立即补跑历史槽位")
	_, hasOld := s.cronEntries[oldTask.ID]
	assert.False(t, hasOld)
	_, hasNew := s.cronEntries[newTask.ID]
	assert.True(t, hasNew)
}

func TestRebuildCronLockedInvalidTaskPreservesOldScheduler(t *testing.T) {
	s := newClockRecoveryTestScheduler(false)
	valid := &types.Task{ID: uuid.New(), Name: "valid", Schedule: "0 0 22 * * *", Enabled: true}
	require.NoError(t, s.scheduleTask(valid))
	oldCron := s.cron
	oldEntries := s.cronEntries

	invalid := &types.Task{ID: uuid.New(), Name: "broken", Schedule: "not-a-cron", Enabled: true}
	err := s.rebuildCronLocked([]*types.Task{invalid}, "injected invalid cron")
	require.Error(t, err)
	assert.Same(t, oldCron, s.cron, "任何任务解析失败都必须保留旧调度器")
	assert.Equal(t, oldEntries, s.cronEntries)
}
