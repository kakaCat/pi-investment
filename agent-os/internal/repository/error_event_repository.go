package repository

import (
	"context"
	"crypto/sha256"
	"database/sql"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"path"
	"regexp"
	"strings"
	"unicode/utf8"

	"github.com/pi-investment/agent-os/internal/domain"
	"github.com/pi-investment/agent-os/internal/timeutil"
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
		in.Fingerprint = FingerprintOfWithDetail(in.Source, in.TaskID, in.Msg, in.Detail)
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
			r.applyEnvNoisePolicy(ctx, e)
			return e, false, nil
		}
		query = "UPDATE error_events SET occurrence_count = occurrence_count + 1, last_seen_at = NOW(), updated_at = NOW() WHERE fingerprint = $1 RETURNING " + errorEventColumns
		row := r.db.QueryRowContext(ctx, query, in.Fingerprint)
		e, err2 := scanErrorEvent(row)
		if err2 != nil {
			return nil, false, fmt.Errorf("failed to update existing error event: %w", err2)
		}
		r.applyEnvNoisePolicy(ctx, e)
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
	r.applyEnvNoisePolicy(ctx, e)
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

// validateActionNote P1（2026-09-10 w-f4aa1f6a）：resolve/ignore 必须带结构化处置结论 note（≥10 字），
// 防止"我解决了"式空话占位——结论供页面展示，也是复开判伪的责任依据。
func validateActionNote(action, note string) error {
	if action != "resolve" && action != "ignore" {
		return nil
	}
	n := strings.TrimSpace(note)
	what := "处置结论（格式：根因+动作+证据，如：根因=3.13移除timeout参数；动作=thread_pool.py改cancel_futures；证据=go test PASS）"
	if action == "ignore" {
		what = "忽略理由（为何误报/无需处置）"
	}
	if utf8.RuneCountInString(n) < 10 {
		return fmt.Errorf("note 校验失败：%s 必须填写%s（≥10 字，当前 %d 字）", action, what, utf8.RuneCountInString(n))
	}
	return nil
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
		if err := validateActionNote("resolve", req.Note); err != nil {
			return nil, "", err
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
		if err := validateActionNote("ignore", req.Note); err != nil {
			return nil, "", err
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
	stats.UpdatedAt = timeutil.Now() // 2026-09-11（w-f4aa1f6a）统一北京时间
	return stats, nil
}

// 指纹归一化（P0，2026-09-10 w-f4aa1f6a）：与 quantsys-v2 infrastructure/error_reporting/
// agent_os_reporter.py normalize_msg 同规则——抹掉 trace_id/timestamp/uuid 等易变段，
// 使同根因错误同指纹（此前 msg 原文哈希导致同根因多行、resolved 复现自动复开失效）。
var (
	reUUID    = regexp.MustCompile(`[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}`)
	reISOTs   = regexp.MustCompile(`\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:?\d{2})?`)
	reHexLong = regexp.MustCompile(`(^|[^0-9a-zA-Z])[0-9a-fA-F]{16,}([^0-9a-zA-Z]|$)`)
	reHex8    = regexp.MustCompile(`(^|[^0-9a-zA-Z])[0-9a-fA-F]{8}([^0-9a-zA-Z]|$)`)
	reNumber  = regexp.MustCompile(`\d+(?:\.\d+)*(?:\.[A-Za-z]{2,4})?`)
	// reLoggerPrefix：纯文本日志的 logger 前缀（与 Python 端 _RE_LOGGER_PREFIX 同规则）
	reLoggerPrefix = regexp.MustCompile(`^[a-z_][a-z0-9_]*(?:\.[a-z0-9_]+)+:\s+`)
)

var volatileJSONKeys = []string{"trace_id", "timestamp", "ts", "time", "request_id", "span_id", "run_id"}

// jsonEssenceKeys 结构化日志的「根因文本」字段（按优先级）。
// 2026-09-11（w-8f2c4cc5）：JSON 通道与文本通道此前指纹不同——同一异常经 structlog JSON
// 落盘时指纹取「去掉易变键后的整段 JSON」，经纯文本 logger 落盘时取「剥掉 logger 前缀的
// 事件文案」，两者天然不等，于是一次异常生成 2 条事件（实测 2026-09-11 00:52
// SchedulerService.add_task TypeError：f5341905 JSON 行 + 9e7070cc 文本行）。
// 现统一取事件文案本身作为根因文本，使同一异常的不同落盘通道归并到同一指纹。
var jsonEssenceKeys = []string{"event", "message", "msg", "error", "exception", "detail"}

// NormalizeMsg 归一化错误消息：同根因错误 → 同指纹。供 FingerprintOf 与测试使用。
func NormalizeMsg(msg string) string {
	s := strings.TrimSpace(msg)
	if strings.HasPrefix(s, "{") {
		var obj map[string]any
		if err := json.Unmarshal([]byte(s), &obj); err == nil {
			for _, k := range volatileJSONKeys {
				delete(obj, k)
			}
			if essence, ok := jsonEssenceText(obj); ok {
				s = essence
			} else if b, err := json.Marshal(obj); err == nil {
				// Go Marshal 转义 <>& 为 \\u003c 等，Python ensure_ascii=False 不转义——反转义对齐
				s = strings.NewReplacer("\\u003c", "<", "\\u003e", ">", "\\u0026", "&").Replace(string(b))
			}
		}
	}
	// 纯文本通道的 logger 前缀（模块路径形态，至少含一个点且小写开头）：
	// "adapters.inbound.fastapi_app.shared: API错误: ..." → "API错误: ..."。
	// 限定「模块路径」形态是为了不误伤 "TypeError: xxx" 这类异常名开头（无点、首字母大写）。
	s = reLoggerPrefix.ReplaceAllString(s, "")
	s = reUUID.ReplaceAllString(s, "<uuid>")
	s = reISOTs.ReplaceAllString(s, "<ts>")
	s = reHexLong.ReplaceAllString(s, "${1}<hex>${2}")
	s = reHex8.ReplaceAllString(s, "${1}<hex8>${2}")
	s = reNumber.ReplaceAllString(s, "<num>")
	return s
}

// jsonEssenceText 取结构化日志的根因文本（event/message/msg），无则返回 false。
// 语义键的值按顺序拼接（不丢弃任何已出现的根因文本）：只取 event 会漏掉
// 「event 是通用标签、error 才是根因」的日志形态；拼接既保持通道间可比，
// 又避免不同故障因共用标签而被合并。
func jsonEssenceText(obj map[string]any) (string, bool) {
	parts := make([]string, 0, len(jsonEssenceKeys))
	for _, k := range jsonEssenceKeys {
		if v, ok := obj[k]; ok {
			if text, ok := v.(string); ok && strings.TrimSpace(text) != "" {
				parts = append(parts, text)
			}
		}
	}
	if len(parts) == 0 {
		return "", false
	}
	return strings.Join(parts, "|"), true
}

// traceback 帧：File "path", line N, in func（与 Python 端 _RE_TB_FRAME 同规则）
var reTbFrame = regexp.MustCompile(`File "([^"]+)", line \d+, in (\w+)`)

// StackFramesOf 从 detail 的 traceback 提取帧序列（basename:func，不含行号——
// 代码微调行号变但根因相同应合并）。无堆栈返回空串。
func StackFramesOf(detail string) string {
	if detail == "" {
		return ""
	}
	matches := reTbFrame.FindAllStringSubmatch(detail, -1)
	if len(matches) == 0 {
		return ""
	}
	frames := make([]string, 0, len(matches))
	for _, m := range matches {
		frames = append(frames, path.Base(m[1])+":"+m[2])
	}
	return strings.Join(frames, "|")
}

// FingerprintOf 生成去重指纹（sha256(source|task_id|归一化 msg) hex 前 40 位）
func FingerprintOf(source, taskID, msg string) string {
	return FingerprintOfWithDetail(source, taskID, msg, "")
}

// FingerprintOfWithDetail 分层指纹（2026-09-10 重构，与 v2 端 _fingerprint 同规则）：
// ①detail 有 traceback → 按堆栈帧序列取指纹（同根因异入参天然合并，不过拟合）；
// ②无堆栈 → msg 通用参数化兜底（uuid/hex/ISO时间 + 通用数字 \d+(\.\d+)*(\.[A-Za-z]{2,4})?）。
func FingerprintOfWithDetail(source, taskID, msg, detail string) string {
	base := source + "|" + taskID + "|"
	if stack := StackFramesOf(detail); stack != "" {
		base += "stack|" + stack
	} else {
		base += NormalizeMsg(msg)
	}
	sum := sha256.Sum256([]byte(base))
	return hex.EncodeToString(sum[:])[:40]
}
