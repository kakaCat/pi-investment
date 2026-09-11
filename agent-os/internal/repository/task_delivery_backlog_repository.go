package repository

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"time"
)

// TaskDeliveryBacklogEntry 一条待补投的任务投递记录。
type TaskDeliveryBacklogEntry struct {
	ID            int64           // 自增序号（DB 为 UUID，此字段仅用于日志/排序时填充）
	UUID          string          // 行主键
	TaskID        string
	TaskName      string
	WebhookURL    string
	Payload       json.RawMessage
	Attempts      int
	MaxAttempts   int
	NextAttemptAt time.Time
	LastError     string
}

// TaskDeliveryBacklogRepository 任务投递积压队列（持久化重投，2026-09-11 w-f4aa1f6a）。
//
// 设计意图：把"投递不进去"从"内存重试耗尽即丢弃"改为"落库 + 后台补投"，
// 因为对端（DSH）不可达时长可能远超任何内存重试窗口（实测 2026-09-11 达 90 分钟以上）。
type TaskDeliveryBacklogRepository struct {
	db *sql.DB
}

func NewTaskDeliveryBacklogRepository(db *sql.DB) *TaskDeliveryBacklogRepository {
	return &TaskDeliveryBacklogRepository{db: db}
}

// Enqueue 落库一条待补投记录（attempts=0，next_attempt_at=now+首次延迟）。
func (r *TaskDeliveryBacklogRepository) Enqueue(
	ctx context.Context,
	taskID, taskName, webhookURL string,
	payload json.RawMessage,
	firstDelay time.Duration,
	maxAttempts int,
	lastErr string,
) error {
	if maxAttempts <= 0 {
		maxAttempts = 10
	}
	_, err := r.db.ExecContext(ctx, `
		INSERT INTO task_delivery_backlog
			(task_id, task_name, webhook_url, payload, attempts, max_attempts, next_attempt_at, last_error)
		VALUES ($1, $2, $3, $4, 0, $5, NOW() + ($6 || ' seconds')::interval, $7)
	`, nullableUUID(taskID), taskName, webhookURL, string(payload), maxAttempts, int(firstDelay.Seconds()), lastErr)
	if err != nil {
		return fmt.Errorf("enqueue delivery backlog: %w", err)
	}
	return nil
}

// ListDue 取出到期的待补投记录（供 worker 补投）。
func (r *TaskDeliveryBacklogRepository) ListDue(ctx context.Context, limit int) ([]*TaskDeliveryBacklogEntry, error) {
	if limit <= 0 {
		limit = 20
	}
	rows, err := r.db.QueryContext(ctx, `
		SELECT id::text, COALESCE(task_id::text, ''), COALESCE(task_name, ''), webhook_url,
		       payload, attempts, max_attempts, next_attempt_at, COALESCE(last_error, '')
		  FROM task_delivery_backlog
		 WHERE status = 'pending'
		   AND next_attempt_at <= NOW()
		   AND attempts < max_attempts
		 ORDER BY next_attempt_at
		 LIMIT $1
	`, limit)
	if err != nil {
		return nil, fmt.Errorf("list due deliveries: %w", err)
	}
	defer rows.Close()

	var out []*TaskDeliveryBacklogEntry
	for rows.Next() {
		e := &TaskDeliveryBacklogEntry{}
		var raw []byte
		if err := rows.Scan(&e.UUID, &e.TaskID, &e.TaskName, &e.WebhookURL, &raw,
			&e.Attempts, &e.MaxAttempts, &e.NextAttemptAt, &e.LastError); err != nil {
			return nil, fmt.Errorf("scan delivery backlog: %w", err)
		}
		e.Payload = json.RawMessage(raw)
		out = append(out, e)
	}
	return out, rows.Err()
}

// MarkDelivered 标记补投成功。
func (r *TaskDeliveryBacklogRepository) MarkDelivered(ctx context.Context, id string) error {
	_, err := r.db.ExecContext(ctx, `
		UPDATE task_delivery_backlog
		   SET status = 'delivered', delivered_at = NOW(), updated_at = NOW(), last_error = NULL
		 WHERE id = $1::uuid
	`, id)
	return err
}

// MarkAttemptFailed 记录一次失败并安排下次尝试；超过上限则置 failed。
func (r *TaskDeliveryBacklogRepository) MarkAttemptFailed(
	ctx context.Context, id string, attempts int, nextAt time.Time, lastErr string,
) error {
	_, err := r.db.ExecContext(ctx, `
		UPDATE task_delivery_backlog
		   SET attempts = $2,
		       next_attempt_at = $3,
		       last_error = $4,
		       status = CASE WHEN $2 >= max_attempts THEN 'failed' ELSE 'pending' END,
		       updated_at = NOW()
		 WHERE id = $1::uuid
	`, id, attempts, nextAt, lastErr)
	return err
}

// CountPending 返回待补投条数（启动/巡检时的可见性）。
func (r *TaskDeliveryBacklogRepository) CountPending(ctx context.Context) (int, error) {
	var n int
	err := r.db.QueryRowContext(ctx,
		`SELECT COUNT(*) FROM task_delivery_backlog WHERE status = 'pending'`).Scan(&n)
	return n, err
}

func nullableUUID(s string) interface{} {
	if s == "" {
		return nil
	}
	return s
}
