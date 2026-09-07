package domain

import (
	"encoding/json"
	"time"
)

// RFC 014: 公告板独立存储领域模型（脱离 memory 复用）

// BoardPost 公告板帖子
type BoardPost struct {
	ID            string          `json:"id"`
	Title         string          `json:"title"`
	Content       string          `json:"content"`
	DisplayTitle  *string         `json:"display_title,omitempty"`
	Kind          string          `json:"kind"`
	Status        string          `json:"status"`
	Author        *string         `json:"author"`
	Assignee      *string         `json:"assignee"`
	Revision      int             `json:"revision"`
	ClaimCount    int             `json:"claim_count"`
	ClaimedAt     *time.Time      `json:"claimed_at,omitempty"`
	ClosedAt      *time.Time      `json:"closed_at,omitempty"`
	StatusReason  *string         `json:"status_reason,omitempty"`
	DropReason    *string         `json:"drop_reason,omitempty"`
	ModerationLog json.RawMessage `json:"moderation_log"`
	CreatedAt     time.Time       `json:"created_at"`
	UpdatedAt     time.Time       `json:"updated_at"`
}

// ModerationLogEntry 审计日志条目
type ModerationLogEntry struct {
	Timestamp string `json:"timestamp"`
	Action    string `json:"action"`
	Actor     string `json:"actor"`
	Note      string `json:"note,omitempty"`
}

// BoardCreateRequest 发帖请求（POST /api/v1/board/posts）
type BoardCreateRequest struct {
	Title       string `json:"title"`
	Content     string `json:"content"`
	Kind        string `json:"kind"`
	NeedsAction bool   `json:"needs_action"`
	Author      string `json:"author"`
}

// BoardListRequest 列表查询（GET /api/v1/board/posts）
type BoardListRequest struct {
	Status   string // active=open/claimed/paused/blocked; done; dropped; all=全部
	Kind     string
	Assignee string
	Limit    int
}

// BoardUpdateRequest 状态流转（PATCH /api/v1/board/posts/{id}）
type BoardUpdateRequest struct {
	Action           string `json:"action"` // edit/claim/pause/blocked/complete/drop
	Note             string `json:"note"`
	Title            string `json:"title"`
	Content          string `json:"content"`
	ExpectedRevision *int   `json:"expected_revision"`
	Actor            string `json:"actor"`
}

// BoardStateMachine 状态机（与旧 board-tools.ts STATE_MACHINE 一致）
var BoardStateMachine = map[string][]string{
	"open":     {"claim", "drop"},
	"claimed":  {"pause", "blocked", "complete", "drop"},
	"paused":   {"claim", "drop"},
	"blocked":  {"claim", "complete", "drop"},
	"done":     {}, // 终态
	"dropped":  {}, // 终态
	"archived": {}, // 终态
}

// BoardActiveStatuses 活跃状态集合（status=active 口径）
var BoardActiveStatuses = []string{"open", "claimed", "paused", "blocked"}
