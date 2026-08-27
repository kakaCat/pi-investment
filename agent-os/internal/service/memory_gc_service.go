package service

import (
	"context"
	"database/sql"
	"fmt"
	"time"

	"github.com/pi-investment/agent-os/internal/logger"
)

// MemoryGCService 记忆垃圾回收服务
type MemoryGCService struct {
	db *sql.DB
}

// NewMemoryGCService 创建 GC 服务
func NewMemoryGCService(db *sql.DB) *MemoryGCService {
	return &MemoryGCService{
		db: db,
	}
}

// Run 执行一次完整的 GC 周期
// RFC 009 两阶段 GC:
// 1. done/dropped 超 30 天 → archived
// 2. archived 超 180 天 → 硬删
func (s *MemoryGCService) Run(ctx context.Context) error {
	logger.L().Info("Starting memory GC cycle")
	
	// 阶段 1: done/dropped → archived (30 天)
	archivedCount, err := s.archiveClosedMemories(ctx)
	if err != nil {
		return fmt.Errorf("failed to archive closed memories: %w", err)
	}
	
	// 阶段 2: archived → 硬删 (180 天)
	deletedCount, err := s.deleteArchivedMemories(ctx)
	if err != nil {
		return fmt.Errorf("failed to delete archived memories: %w", err)
	}
	
	logger.L().Info("Memory GC cycle completed", logger.Int64("archived", archivedCount), logger.Int64("deleted", deletedCount))
	
	return nil
}

// archiveClosedMemories 将 done/dropped 状态超过 30 天的记忆标记为 archived
func (s *MemoryGCService) archiveClosedMemories(ctx context.Context) (int64, error) {
	query := `
		UPDATE memories
		SET metadata = jsonb_set(
			COALESCE(metadata, '{}'::jsonb),
			'{board_status}',
			'"archived"'
		)
		WHERE metadata->>'board_status' IN ('done', 'dropped')
		  AND (metadata->>'closed_at')::timestamp < NOW() - INTERVAL '30 days'
	`
	
	result, err := s.db.ExecContext(ctx, query)
	if err != nil {
		return 0, fmt.Errorf("failed to execute archive query: %w", err)
	}
	
	count, _ := result.RowsAffected()
	if count > 0 {
		logger.L().Info("Archived closed memories", logger.Int64("count", count))
	}
	
	return count, nil
}

// deleteArchivedMemories 硬删除 archived 状态超过 180 天的记忆
func (s *MemoryGCService) deleteArchivedMemories(ctx context.Context) (int64, error) {
	// 分批删除，避免长事务锁表
	const batchSize = 1000
	totalDeleted := int64(0)
	
	for {
		query := `
			DELETE FROM memories
			WHERE id IN (
				SELECT id FROM memories
				WHERE metadata->>'board_status' = 'archived'
				  AND (metadata->>'closed_at')::timestamp < NOW() - INTERVAL '180 days'
				LIMIT $1
			)
		`
		
		result, err := s.db.ExecContext(ctx, query, batchSize)
		if err != nil {
			return totalDeleted, fmt.Errorf("failed to execute delete query: %w", err)
		}
		
		count, _ := result.RowsAffected()
		totalDeleted += count
		
		if count == 0 {
			break // 没有更多记录需要删除
		}
		
		// 短暂休眠，避免对数据库造成压力
		if count == batchSize {
			time.Sleep(100 * time.Millisecond)
		}
	}
	
	if totalDeleted > 0 {
		logger.L().Info("Deleted archived memories", logger.Int64("count", totalDeleted))
	}
	
	return totalDeleted, nil
}

// RunPeriodically 定期运行 GC（每日 04:00）
func (s *MemoryGCService) RunPeriodically(ctx context.Context) {
	ticker := time.NewTicker(24 * time.Hour)
	defer ticker.Stop()
	
	// 计算到下一个 04:00 的延迟
	now := time.Now()
	next := time.Date(now.Year(), now.Month(), now.Day(), 4, 0, 0, 0, now.Location())
	if now.After(next) {
		next = next.Add(24 * time.Hour)
	}
	initialDelay := next.Sub(now)
	
	logger.L().Info("Memory GC scheduled", logger.String("next_run", next.Format(time.RFC3339)))
	
	// 首次延迟到 04:00
	select {
	case <-time.After(initialDelay):
		if err := s.Run(ctx); err != nil {
			logger.L().Error("Memory GC failed", logger.Error(err))
		}
	case <-ctx.Done():
		return
	}
	
	// 之后每 24 小时运行一次
	for {
		select {
		case <-ticker.C:
			if err := s.Run(ctx); err != nil {
				logger.L().Error("Memory GC failed", logger.Error(err))
			}
		case <-ctx.Done():
			logger.L().Info("Memory GC stopped")
			return
		}
	}
}
