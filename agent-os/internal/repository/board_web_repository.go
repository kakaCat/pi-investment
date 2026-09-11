package repository

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/pi-investment/agent-os/internal/domain"
	"github.com/pi-investment/agent-os/internal/timeutil"
)

// BoardWebRepository 公告板仓储接口（RFC 014 独立存储）
type BoardWebRepository interface {
	List(ctx context.Context, req domain.BoardListRequest) ([]*domain.BoardPost, error)
	GetByID(ctx context.Context, id string) (*domain.BoardPost, error)
	Create(ctx context.Context, req domain.BoardCreateRequest) (*domain.BoardPost, error)
	Update(ctx context.Context, id string, req domain.BoardUpdateRequest) (*domain.BoardPost, string, error)
}

type boardWebRepository struct {
	db *sql.DB
}

// NewBoardWebRepository 创建公告板仓储
func NewBoardWebRepository(db *sql.DB) BoardWebRepository {
	return &boardWebRepository{db: db}
}

const boardColumns = `id, title, content, display_title, kind, status, author, assignee,
	revision, claim_count, claimed_at, closed_at, status_reason, drop_reason,
	moderation_log, created_at, updated_at`

func scanBoardPost(row interface{ Scan(...interface{}) error }) (*domain.BoardPost, error) {
	var p domain.BoardPost
	err := row.Scan(
		&p.ID, &p.Title, &p.Content, &p.DisplayTitle, &p.Kind, &p.Status,
		&p.Author, &p.Assignee, &p.Revision, &p.ClaimCount,
		&p.ClaimedAt, &p.ClosedAt, &p.StatusReason, &p.DropReason,
		&p.ModerationLog, &p.CreatedAt, &p.UpdatedAt,
	)
	if err != nil {
		return nil, err
	}
	return &p, nil
}

// List 查询帖子（服务端精确过滤，无语义搜索泄漏）
func (r *boardWebRepository) List(ctx context.Context, req domain.BoardListRequest) ([]*domain.BoardPost, error) {
	query := "SELECT " + boardColumns + " FROM board_posts WHERE 1=1"
	args := []interface{}{}
	argIndex := 1

	switch req.Status {
	case "", "active":
		query += " AND status IN ('open','claimed','paused','blocked')"
	case "all":
		// 不过滤
	default:
		query += fmt.Sprintf(" AND status = $%d", argIndex)
		args = append(args, req.Status)
		argIndex++
	}
	if req.Kind != "" {
		query += fmt.Sprintf(" AND kind = $%d", argIndex)
		args = append(args, req.Kind)
		argIndex++
	}
	if req.Assignee != "" {
		query += fmt.Sprintf(" AND assignee = $%d", argIndex)
		args = append(args, req.Assignee)
		argIndex++
	}
	query += " ORDER BY created_at DESC"
	limit := req.Limit
	if limit <= 0 || limit > 500 {
		limit = 100
	}
	query += fmt.Sprintf(" LIMIT $%d", argIndex)
	args = append(args, limit)

	rows, err := r.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to query board posts: %w", err)
	}
	defer rows.Close()

	posts := []*domain.BoardPost{}
	for rows.Next() {
		p, err := scanBoardPost(rows)
		if err != nil {
			return nil, fmt.Errorf("failed to scan board post: %w", err)
		}
		posts = append(posts, p)
	}
	return posts, rows.Err()
}

// GetByID 按 ID 取帖（含终态，交由调用方判断可操作性）
func (r *boardWebRepository) GetByID(ctx context.Context, id string) (*domain.BoardPost, error) {
	row := r.db.QueryRowContext(ctx,
		"SELECT "+boardColumns+" FROM board_posts WHERE id = $1", id)
	p, err := scanBoardPost(row)
	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("board post not found: %s", id)
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get board post: %w", err)
	}
	return p, nil
}

// Create 发帖：needs_action=true→open（悬赏池），false→done（纯记录）
func (r *boardWebRepository) Create(ctx context.Context, req domain.BoardCreateRequest) (*domain.BoardPost, error) {
	status := "done"
	note := "创建记录（已完成）"
	if req.NeedsAction {
		status = "open"
		note = "创建并进悬赏池"
	}
	kind := req.Kind
	if kind == "" {
		kind = "finding"
	}
	logEntry := domain.ModerationLogEntry{
		// 2026-09-11（w-f4aa1f6a）：原为 UTC，项目时间统一北京时间
		Timestamp: timeutil.RFC3339Nano(time.Now()),
		Action:    "create",
		Actor:     req.Author,
		Note:      note,
	}
	logJSON, _ := json.Marshal([]domain.ModerationLogEntry{logEntry})

	var author *string
	if req.Author != "" {
		author = &req.Author
	}

	row := r.db.QueryRowContext(ctx, `
		INSERT INTO board_posts (title, content, kind, status, author, moderation_log)
		VALUES ($1, $2, $3, $4, $5, $6)
		RETURNING `+boardColumns,
		req.Title, req.Content, kind, status, author, logJSON)
	p, err := scanBoardPost(row)
	if err != nil {
		return nil, fmt.Errorf("failed to create board post: %w", err)
	}
	return p, nil
}

// Update 状态流转：事务内 SELECT FOR UPDATE → 乐观锁/权限/状态机校验 → 更新。
// 返回 (post, message, error)；message 用于幂等成功说明。
func (r *boardWebRepository) Update(ctx context.Context, id string, req domain.BoardUpdateRequest) (*domain.BoardPost, string, error) {
	tx, err := r.db.BeginTx(ctx, nil)
	if err != nil {
		return nil, "", fmt.Errorf("failed to begin tx: %w", err)
	}
	defer tx.Rollback()

	row := tx.QueryRowContext(ctx,
		"SELECT "+boardColumns+" FROM board_posts WHERE id = $1 FOR UPDATE", id)
	p, err := scanBoardPost(row)
	if err == sql.ErrNoRows {
		return nil, "", fmt.Errorf("board post not found: %s", id)
	}
	if err != nil {
		return nil, "", fmt.Errorf("failed to lock board post: %w", err)
	}

	// 乐观锁
	if req.ExpectedRevision != nil && *req.ExpectedRevision != p.Revision {
		return nil, "", fmt.Errorf("revision conflict: expected %d, actual %d", *req.ExpectedRevision, p.Revision)
	}

	// 权限（作者/认领人；claim 任何人可执行）
	author := ""
	if p.Author != nil {
		author = *p.Author
	}
	assignee := ""
	if p.Assignee != nil {
		assignee = *p.Assignee
	}
	if req.Action != "claim" && req.Action != "edit" {
		if req.Actor != author && req.Actor != assignee {
			return nil, "", fmt.Errorf("permission denied: only author/assignee can %s (author=%s, assignee=%s)", req.Action, author, assignee)
		}
	}

	// 幂等：重复 complete/drop 已关闭帖 → 幂等成功
	if req.Action == "complete" && p.Status == "done" {
		return p, "幂等操作：帖子已经是 done 状态", nil
	}
	if req.Action == "drop" && p.Status == "dropped" {
		return p, "幂等操作：帖子已经是 dropped 状态", nil
	}

	// 状态机
	if req.Action != "edit" {
		allowed := domain.BoardStateMachine[p.Status]
		ok := false
		for _, a := range allowed {
			if a == req.Action {
				ok = true
				break
			}
		}
		if !ok {
			return nil, "", fmt.Errorf("illegal transition: status %s does not allow %s (allowed: %s)", p.Status, req.Action, strings.Join(allowed, ","))
		}
	}

	// closed 类动作必须有 note
	if (req.Action == "complete" || req.Action == "drop") && strings.TrimSpace(req.Note) == "" {
		return nil, "", fmt.Errorf("%s requires note (关闭原因)", req.Action)
	}
	if req.Action == "edit" && strings.TrimSpace(req.Content) == "" && strings.TrimSpace(req.Title) == "" {
		return nil, "", fmt.Errorf("edit requires content or title")
	}

	// 计算新状态与字段
	newStatus := p.Status
	setClauses := []string{"revision = revision + 1", "updated_at = NOW()"}
	args := []interface{}{}
	argIndex := 1
	addSet := func(clause string, val interface{}) {
		setClauses = append(setClauses, fmt.Sprintf(clause, argIndex))
		args = append(args, val)
		argIndex++
	}
	var noteForField *string
	if req.Note != "" {
		noteForField = &req.Note
	}

	switch req.Action {
	case "edit":
		if strings.TrimSpace(req.Content) != "" {
			addSet("content = $%d", req.Content)
		}
		if strings.TrimSpace(req.Title) != "" {
			addSet("display_title = $%d", req.Title)
		}
	case "claim":
		newStatus = "claimed"
		addSet("status = $%d", newStatus)
		addSet("assignee = $%d", req.Actor)
		setClauses = append(setClauses, "claimed_at = NOW()", "claim_count = claim_count + 1")
	case "pause":
		newStatus = "paused"
		addSet("status = $%d", newStatus)
		addSet("status_reason = $%d", req.Note)
	case "blocked":
		newStatus = "blocked"
		addSet("status = $%d", newStatus)
		addSet("status_reason = $%d", req.Note)
	case "complete":
		newStatus = "done"
		addSet("status = $%d", newStatus)
		addSet("status_reason = $%d", req.Note)
		setClauses = append(setClauses, "closed_at = NOW()")
	case "drop":
		newStatus = "dropped"
		addSet("status = $%d", newStatus)
		addSet("drop_reason = $%d", req.Note)
		setClauses = append(setClauses, "closed_at = NOW()")
	default:
		return nil, "", fmt.Errorf("unknown action: %s", req.Action)
	}

	// 追加 moderation_log
	var log []domain.ModerationLogEntry
	if len(p.ModerationLog) > 0 {
		_ = json.Unmarshal(p.ModerationLog, &log)
	}
	log = append(log, domain.ModerationLogEntry{
		Timestamp: timeutil.RFC3339Nano(time.Now()), // 2026-09-11（w-f4aa1f6a）统一北京时间
		Action:    req.Action,
		Actor:     req.Actor,
		Note:      req.Note,
	})
	logJSON, _ := json.Marshal(log)
	addSet("moderation_log = $%d", logJSON)

	query := fmt.Sprintf("UPDATE board_posts SET %s WHERE id = $%d RETURNING %s",
		strings.Join(setClauses, ", "), argIndex, boardColumns)
	args = append(args, id)

	updated, err := scanBoardPost(tx.QueryRowContext(ctx, query, args...))
	if err != nil {
		return nil, "", fmt.Errorf("failed to update board post: %w", err)
	}
	if err := tx.Commit(); err != nil {
		return nil, "", fmt.Errorf("failed to commit: %w", err)
	}
	_ = noteForField
	return updated, fmt.Sprintf("已执行 %s，状态: %s → %s", req.Action, p.Status, newStatus), nil
}
