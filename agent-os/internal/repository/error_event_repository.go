package repository

import (
	"context"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/pi-investment/agent-os/internal/domain"
)

// ErrorEventRepository 错误事件仓储接口
type ErrorEventRepository interface {
	// Upsert 指纹去重写入：存在则 occurrence_count+1 并刷新 last_seen_at；
	// resolved/ignored 状态的事件复现时自动复开（status 回 open、清 resolution 字段）。
	Upsert(ctx context.Context, in domain.ErrorEventUpsertInput) (*domain.ErrorEvent, bool, error)
	// List 返回 (events, total, error)：total 为满足过滤条件的总数（供分页）。
	List(ctx context.Context, req domain.ErrorEventListRequest) ([]*domain.ErrorEvent, int, error)
	GetByID(ctx context.Context, id string) (*domain.ErrorEvent, error)
	// ApplyAction 状态流转：claim→processing(置 assignee)；resolve→resolved(置 resolved_at/note)；
	// ignore→ignored(置 note)；reopen→open(清 resolution)。返回 (event, message, error)。
	ApplyAction(ctx context.Context, id string, req domain.ErrorEventActionRequest) (*domain.ErrorEvent, string, error)
	Stats(ctx context.Context) (*domain.ErrorEventStats, error)
}

type errorEventRepository struct {
	db *sql.DB
}

// NewErrorEventRepository 创建错误事件仓储
func NewErrorEventRepository(db *sql.DB) ErrorEventRepository {
	return &errorEventRepository{db: db}
}

const errorEventColumns = "id, source, task_id, task_name, level, msg, detail, fingerprint, status, occurrence_count, first_seen_at, last_seen_at, assignee, dispatched_session, resolved_at, resolution_note, metadata, created_at, updated_at"

func scanErrorEvent(row interface{ Scan(...interface{}) error }) (*domain.ErrorEvent, error) {
	var e domain.ErrorEvent
	var metadata []byte
	err := row.Scan(
		&e.ID, &e.Source, &e.TaskID, &e.TaskName, &e.Level, &e.Msg, &e.Detail, &e.Fingerprint,
		&e.Status, &e.OccurrenceCount, &e.FirstSeenAt, &e.LastSeenAt,
		&e.Assignee, &e.DispatchedSession, &e.ResolvedAt, &e.ResolutionNote,
		&metadata, &e.CreatedAt, &e.UpdatedAt,
	)
	if err != nil {
		return nil, err
	}
	if len(metadata) > 0 && string(metadata) != "null" {
		e.Metadata = json.RawMessage(metadata)
	} else {
		e.Metadata = json.RawMessage("{}")
	}
	return &e, nil
}

// Upsert 指纹去重写入。返回 (event, isNew, error)。
func (r *errorEventRepository) Upsert(ctx context.Context, in domain.ErrorEventUpsertInput) (*domain.ErrorEvent, bool, error) {
	if in.Source == "" {
		in.Source = string(domain.ErrorSourceOS)
	}
	if in.Level == "" {
		in.Level = "error"
	}
	if in.Fingerprint == "" {
		in.Fingerprint = FingerprintOf(in.Source, in.TaskID, in.Msg)
	}
	metaJSON := []byte("{}")
	if len(in.Metadata) > 0 {
		b, err := json.Marshal(in.Metadata)
		if err == nil {
			metaJSON = b
		}
	}
	var taskID, taskName, detail *string
	if in.TaskID != "" {
		taskID = &in.TaskID
	}
	if in.TaskName != "" {
		taskName = &in.TaskName
	}
	if in.Detail != "" {
		detail = &in.Detail
	}

	// 先查同指纹记录，命中则走更新路径
	var existingID string
	var existingStatus string
	err := r.db.QueryRowContext(ctx, "SELECT id, status FROM error_events WHERE fingerprint = $1", in.Fingerprint).Scan(&existingID, &existingStatus)
	if err == nil {
		// 已存在：count+1，刷新 last_seen_at；resolved/ignored 复现 → 自动复开 open
		newStatus := existingStatus
		resetClause := ""
		if existingStatus == string(domain.ErrorStatusResolved) || existingStatus == string(domain.ErrorStatusIgnored) {
			newStatus = string(domain.ErrorStatusOpen)
			resetClause = ", resolved_at = NULL, resolution_note = NULL, assignee = NULL, dispatched_session = NULL"
		}
		var query string
		if newStatus != existingStatus {
			query = "UPDATE error_events SET occurrence_count = occurrence_count + 1, last_seen_at = NOW(), status = $2" + resetClause + ", updated_at = NOW() WHERE fingerprint = $1 RETURNING " + errorEventColumns
			row := r.db.QueryRowContext(ctx, query, in.Fingerprint, newStatus)
			e, err2 := scanErrorEvent(row)
			if err2 != nil {
				return nil, false, fmt.Errorf("failed to update existing error event: %w", err2)
			}
			return e, false, nil
		}
		query = "UPDATE error_events SET occurrence_count = occurrence_count + 1, last_seen_at = NOW(), updated_at = NOW() WHERE fingerprint = $1 RETURNING " + errorEventColumns
		row := r.db.QueryRowContext(ctx, query, in.Fingerprint)
		e, err2 := scanErrorEvent(row)
		if err2 != nil {
			return nil, false, fmt.Errorf("failed to update existing error event: %w", err2)
		}
		return e, false, nil
	}
	if err != sql.ErrNoRows {
		return nil, false, fmt.Errorf("failed to check existing error event: %w", err)
	}

	// 不存在：插入
	insertSQL := "INSERT INTO error_events (source, task_id, task_name, level, msg, detail, fingerprint, metadata) VALUES ($1, $2, $3, $4, $5, $6, $7, $8) RETURNING " + errorEventColumns
	row := r.db.QueryRowContext(ctx, insertSQL,
		in.Source, taskID, taskName, in.Level, in.Msg, detail, in.Fingerprint, metaJSON)
	e, err := scanErrorEvent(row)
	if err != nil {
		// 并发唯一键冲突 → 幂等成功
		if strings.Contains(err.Error(), "uq_error_events_fingerprint") || strings.Contains(err.Error(), "duplicate key") {
			return nil, false, nil
		}
		return nil, false, fmt.Errorf("failed to create error event: %w", err)
	}
	return e, true, nil
}

// List 查询错误事件（status/source 过滤，按 last_seen_at DESC；Offset/Limit 分页）
// 返回 (events, total, error)：total 为满足过滤条件的 DB 总数（COUNT 同条件查询）。
func (r *errorEventRepository) List(ctx context.Context, req domain.ErrorEventListRequest) ([]*domain.ErrorEvent, int, error) {
	// 1) 组装 WHERE
	where := " WHERE 1=1"
	args := []interface{}{}
	argIndex := 1
	if req.Status != "" {
		where += fmt.Sprintf(" AND status = $%d", argIndex)
		args = append(args, req.Status)
		argIndex++
	}
	if req.Source != "" {
		where += fmt.Sprintf(" AND source = $%d", argIndex)
		args = append(args, req.Source)
		argIndex++
	}

	// 2) COUNT 同条件总数
	var total int
	if err := r.db.QueryRowContext(ctx, "SELECT COUNT(*) FROM error_events"+where, args...).Scan(&total); err != nil {
		return nil, 0, fmt.Errorf("failed to count error events: %w", err)
	}

	// 3) 分页查询
	limit := req.Limit
	if limit <= 0 {
		limit = 50
	}
	if limit > 500 {
		limit = 500
	}
	offset := req.Offset
	if offset < 0 {
		offset = 0
	}
	if offset > 100000 {
		offset = 100000
	}
	query := "SELECT " + errorEventColumns + " FROM error_events" + where +
		fmt.Sprintf(" ORDER BY last_seen_at DESC LIMIT $%d OFFSET $%d", argIndex, argIndex+1)
	args = append(args, limit, offset)

	rows, err := r.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, 0, fmt.Errorf("failed to list error events: %w", err)
	}
	defer rows.Close()

	var out []*domain.ErrorEvent
	for rows.Next() {
		e, err := scanErrorEvent(rows)
		if err != nil {
			return nil, 0, fmt.Errorf("failed to scan error event: %w", err)
		}
		out = append(out, e)
	}
	if err := rows.Err(); err != nil {
		return nil, 0, err
	}
	return out, total, nil
}

// GetByID 按 ID 查询
func (r *errorEventRepository) GetByID(ctx context.Context, id string) (*domain.ErrorEvent, error) {
	row := r.db.QueryRowContext(ctx, "SELECT "+errorEventColumns+" FROM error_events WHERE id = $1", id)
	e, err := scanErrorEvent(row)
	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("error event not found: %s", id)
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get error event: %w", err)
	}
	return e, nil
}

// ApplyAction 状态流转（事务内 SELECT FOR UPDATE → 状态机校验 → 更新）
func (r *errorEventRepository) ApplyAction(ctx context.Context, id string, req domain.ErrorEventActionRequest) (*domain.ErrorEvent, string, error) {
	tx, err := r.db.BeginTx(ctx, nil)
	if err != nil {
		return nil, "", fmt.Errorf("failed to begin tx: %w", err)
	}
	defer tx.Rollback()

	row := tx.QueryRowContext(ctx, "SELECT "+errorEventColumns+" FROM error_events WHERE id = $1 FOR UPDATE", id)
	e, err := scanErrorEvent(row)
	if err == sql.ErrNoRows {
		return nil, "", fmt.Errorf("error event not found: %s", id)
	}
	if err != nil {
		return nil, "", fmt.Errorf("failed to lock error event: %w", err)
	}

	var msg string
	switch req.Action {
	case "claim":
		if e.Status != string(domain.ErrorStatusOpen) {
			return nil, "", fmt.Errorf("状态机不允许：当前状态 %s 不可 claim（仅 open 可认领）", e.Status)
		}
		var actor *string
		if req.Actor != "" {
			actor = &req.Actor
		}
		if _, err := tx.ExecContext(ctx, "UPDATE error_events SET status = $1, assignee = $2, updated_at = NOW() WHERE id = $3",
			string(domain.ErrorStatusProcessing), actor, id); err != nil {
			return nil, "", fmt.Errorf("failed to claim error event: %w", err)
		}
		msg = "已认领（处理中）"
	case "resolve":
		if e.Status != string(domain.ErrorStatusProcessing) && e.Status != string(domain.ErrorStatusOpen) {
			return nil, "", fmt.Errorf("状态机不允许：当前状态 %s 不可 resolve（仅 open/processing 可解决）", e.Status)
		}
		var note *string
		if req.Note != "" {
			note = &req.Note
		}
		if _, err := tx.ExecContext(ctx, "UPDATE error_events SET status = $1, resolved_at = NOW(), resolution_note = $2, updated_at = NOW() WHERE id = $3",
			string(domain.ErrorStatusResolved), note, id); err != nil {
			return nil, "", fmt.Errorf("failed to resolve error event: %w", err)
		}
		msg = "已解决"
	case "ignore":
		if e.Status == string(domain.ErrorStatusResolved) {
			return nil, "", fmt.Errorf("状态机不允许：已解决事件不可忽略")
		}
		var note *string
		if req.Note != "" {
			note = &req.Note
		}
		if _, err := tx.ExecContext(ctx, "UPDATE error_events SET status = $1, resolved_at = NOW(), resolution_note = $2, updated_at = NOW() WHERE id = $3",
			string(domain.ErrorStatusIgnored), note, id); err != nil {
			return nil, "", fmt.Errorf("failed to ignore error event: %w", err)
		}
		msg = "已忽略"
	case "reopen":
		if e.Status != string(domain.ErrorStatusResolved) && e.Status != string(domain.ErrorStatusIgnored) {
			return nil, "", fmt.Errorf("状态机不允许：当前状态 %s 不可 reopen（仅 resolved/ignored 可复开）", e.Status)
		}
		if _, err := tx.ExecContext(ctx, "UPDATE error_events SET status = $1, resolved_at = NULL, resolution_note = NULL, assignee = NULL, dispatched_session = NULL, updated_at = NOW() WHERE id = $2",
			string(domain.ErrorStatusOpen), id); err != nil {
			return nil, "", fmt.Errorf("failed to reopen error event: %w", err)
		}
		msg = "已复开"
	default:
		return nil, "", fmt.Errorf("未知动作: %s（支持 claim/resolve/ignore/reopen）", req.Action)
	}

	// 重查返回更新后记录
	row2 := tx.QueryRowContext(ctx, "SELECT "+errorEventColumns+" FROM error_events WHERE id = $1", id)
	e2, err := scanErrorEvent(row2)
	if err != nil {
		return nil, "", fmt.Errorf("failed to reload error event: %w", err)
	}
	if err := tx.Commit(); err != nil {
		return nil, "", fmt.Errorf("failed to commit tx: %w", err)
	}
	return e2, msg, nil
}

// Stats 按状态/来源统计
func (r *errorEventRepository) Stats(ctx context.Context) (*domain.ErrorEventStats, error) {
	stats := &domain.ErrorEventStats{
		ByStatus: map[string]int{},
		BySource: map[string]int{},
	}

	rows, err := r.db.QueryContext(ctx, "SELECT status, COUNT(*) FROM error_events GROUP BY status")
	if err != nil {
		return nil, fmt.Errorf("failed to query status stats: %w", err)
	}
	for rows.Next() {
		var s string
		var c int
		if err := rows.Scan(&s, &c); err != nil {
			rows.Close()
			return nil, err
		}
		stats.ByStatus[s] = c
		stats.Total += c
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return nil, err
	}

	rows2, err := r.db.QueryContext(ctx, "SELECT source, COUNT(*) FROM error_events GROUP BY source")
	if err != nil {
		return nil, fmt.Errorf("failed to query source stats: %w", err)
	}
	defer rows2.Close()
	for rows2.Next() {
		var s string
		var c int
		if err := rows2.Scan(&s, &c); err != nil {
			return nil, err
		}
		stats.BySource[s] = c
	}
	if err := rows2.Err(); err != nil {
		return nil, err
	}

	stats.OpenCount = stats.ByStatus[string(domain.ErrorStatusOpen)] + stats.ByStatus[string(domain.ErrorStatusProcessing)]
	stats.UpdatedAt = time.Now().UTC()
	return stats, nil
}

// FingerprintOf 生成去重指纹（sha256(source|task_id|msg) hex 前 40 位）
func FingerprintOf(source, taskID, msg string) string {
	base := source + "|" + taskID + "|" + strings.TrimSpace(msg)
	sum := sha256.Sum256([]byte(base))
	return hex.EncodeToString(sum[:])[:40]
}
