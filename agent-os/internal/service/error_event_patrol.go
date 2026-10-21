package service

import (
	"context"
	"time"

	"github.com/pi-investment/agent-os/internal/logger"
	"github.com/pi-investment/agent-os/internal/repository"
)

// ErrorEventPatrol 错误事件僵尸回收巡检（P1 兜底，2026-10-21 w-6224baac）。
//
// 背景：P0（claimTransitionAllowed）让「processing ∧ 无责任人」可被认领，
// 但认领仍依赖有人看板；本巡检保证该组合**最终自动消失**：静默超阈值即回落
// open（含 metadata 留痕），把「任何状态都有出口」的不变式从靠注意力变成靠机器。
//
// 口径与安全边界：
//
//	· 只处理 assignee 为空的 processing —— 有责任人的一律不碰（人正在处理）；
//	· 回落 open 而非 resolve/ignore —— 不伪造处置结论；
//	· 单条 UPDATE 批量完成，失败只记日志，绝不影响宿主启动/其它组件。
type ErrorEventPatrol struct {
	repo      repository.ErrorEventRepository
	threshold time.Duration
	interval  time.Duration
}

// NewErrorEventPatrol 创建巡检（threshold<=0 用默认 2h；interval<=0 用 30min）。
func NewErrorEventPatrol(repo repository.ErrorEventRepository, threshold, interval time.Duration) *ErrorEventPatrol {
	if threshold <= 0 {
		threshold = repository.DefaultZombieThreshold
	}
	if interval <= 0 {
		interval = 30 * time.Minute
	}
	return &ErrorEventPatrol{repo: repo, threshold: threshold, interval: interval}
}

// Run 执行一轮回收，返回回收条数。
func (p *ErrorEventPatrol) Run(ctx context.Context) (int64, error) {
	n, err := p.repo.ReclaimZombieProcessing(ctx, p.threshold)
	if err != nil {
		return 0, err
	}
	return n, nil
}

// RunPeriodically 周期巡检（启动 1 分钟后先跑一轮，随后按 interval）。永不返回错误。
func (p *ErrorEventPatrol) RunPeriodically(ctx context.Context) {
	logger.L().Info("error event zombie patrol started",
		logger.String("threshold", p.threshold.String()),
		logger.String("interval", p.interval.String()))
	// 启动即跑一轮：回收存量僵尸（历史遗留，如 a6780ec3 形态）
	select {
	case <-time.After(time.Minute):
		p.runOnce(ctx)
	case <-ctx.Done():
		return
	}
	ticker := time.NewTicker(p.interval)
	defer ticker.Stop()
	for {
		select {
		case <-ticker.C:
			p.runOnce(ctx)
		case <-ctx.Done():
			return
		}
	}
}

func (p *ErrorEventPatrol) runOnce(ctx context.Context) {
	n, err := p.Run(ctx)
	if err != nil {
		logger.L().Error("error event zombie patrol failed", logger.Error(err))
		return
	}
	if n > 0 {
		logger.L().Info("zombie processing events reclaimed", logger.Int64("count", n))
	}
}
