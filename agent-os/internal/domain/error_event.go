package domain

import (
	"encoding/json"
	"time"
)

// Agent OS 错误事件收集与处置领域模型
// 来源：① scheduler 任务执行失败（executor 挂钩）② 三端日志（v2/os/dsh）tail 采集器
// 指纹去重：同 fingerprint 反复出现只 occurrence_count+1；resolved 后同指纹复现自动复开（status 回 open）。

// ErrorEventSource 错误来源
type ErrorEventSource string

const (
	ErrorSourceOS  ErrorEventSource = "os"
	ErrorSourceV2  ErrorEventSource = "v2"
	ErrorSourceDSH ErrorEventSource = "dsh"
)

// ErrorEventStatus 状态机：open→processing(claim/dispatch)→resolved/ignored；resolved/ignored 为终态（复开除外）
type ErrorEventStatus string

const (
	ErrorStatusOpen       ErrorEventStatus = "open"
	ErrorStatusProcessing ErrorEventStatus = "processing"
	ErrorStatusResolved   ErrorEventStatus = "resolved"
	ErrorStatusIgnored    ErrorEventStatus = "ignored"
)

// ErrorEvent 错误事件
type ErrorEvent struct {
	ID                string          `json:"id"`
	Source            string          `json:"source"`
	TaskID            *string         `json:"task_id"`
	TaskName          *string         `json:"task_name"`
	Level             string          `json:"level"`
	Msg               string          `json:"msg"`
	Detail            *string         `json:"detail"`
	Fingerprint       string          `json:"fingerprint"`
	Status            string          `json:"status"`
	OccurrenceCount   int             `json:"occurrence_count"`
	FirstSeenAt       time.Time       `json:"first_seen_at"`
	LastSeenAt        time.Time       `json:"last_seen_at"`
	Assignee          *string         `json:"assignee"`
	DispatchedSession *string         `json:"dispatched_session"`
	ResolvedAt        *time.Time      `json:"resolved_at"`
	ResolutionNote    *string         `json:"resolution_note"`
	Metadata          json.RawMessage `json:"metadata"`
	CreatedAt         time.Time       `json:"created_at"`
	UpdatedAt         time.Time       `json:"updated_at"`
}

// ErrorEventUpsertInput 采集写入（executor 挂钩 / 日志采集器共用）
type ErrorEventUpsertInput struct {
	Source      string
	TaskID      string
	TaskName    string
	Level       string
	Msg         string
	Detail      string
	Fingerprint string
	Metadata    map[string]interface{}
}

// ErrorEventListRequest 列表查询（GET /api/v1/scheduler/error-events）
// Offset 分页偏移（配合 Limit 使用）；返回体 total 为满足过滤条件的 DB 总数（非本次条数）。
type ErrorEventListRequest struct {
	Status string
	Source string
	Limit  int
	Offset int
}

// ErrorEventActionRequest 状态流转（PATCH /api/v1/scheduler/error-events/{id}）
// action: claim(认领→processing) / resolve(解决) / ignore(忽略) / reopen(复开)
type ErrorEventActionRequest struct {
	Action  string `json:"action"`
	Actor   string `json:"actor"`
	Session string `json:"session"`
	Note    string `json:"note"`
}

// ErrorEventStats 统计（GET /api/v1/scheduler/error-events/stats）
type ErrorEventStats struct {
	Total     int            `json:"total"`
	ByStatus  map[string]int `json:"by_status"`
	BySource  map[string]int `json:"by_source"`
	OpenCount int            `json:"open_count"`
	UpdatedAt time.Time      `json:"updated_at"`
}
