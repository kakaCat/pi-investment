package repository

import (
	"context"

	"github.com/pi-investment/agent-os/internal/domain"
)

// applyEnvNoisePolicy 对"环境类噪声"事件执行归档策略。
//
// 只作用于 open 状态：resolved 是人处置过的结论、processing 已被认领，都不应被自动改写。
// 命中规则且未触发速率安全阀 → 归档为 ignored（带说明）；触发安全阀 → 保持 open 并写明速率原因。
// 任何 DB 写失败都不影响本次采集（事件仍以原状态落库，下一轮复发会再次评估）。
func (r *errorEventRepository) applyEnvNoisePolicy(ctx context.Context, e *domain.ErrorEvent) {
	if e == nil || e.Status != string(domain.ErrorStatusOpen) {
		return
	}
	detail := ""
	if e.Detail != nil {
		detail = *e.Detail
	}
	rule := matchEnvNoise(e.Msg, detail)
	if rule == nil {
		return
	}

	// 速率安全阀：短窗口内密集复发不归档，避免把"真退化"当噪声掩盖
	if escalated, reason := envNoiseEscalated(e.OccurrenceCount, e.FirstSeenAt, e.LastSeenAt); escalated {
		note := escalationNote(rule, reason)
		if _, err := r.db.ExecContext(ctx,
			"UPDATE error_events SET resolution_note = $2, updated_at = NOW() WHERE id = $1",
			e.ID, note); err == nil {
			e.ResolutionNote = &note
		}
		return
	}

	note := autoArchiveNote(rule, e.OccurrenceCount, e.FirstSeenAt, e.LastSeenAt)
	row := r.db.QueryRowContext(ctx,
		"UPDATE error_events SET status = $2, resolution_note = $3, resolved_at = NULL, assignee = NULL, dispatched_session = NULL, updated_at = NOW() WHERE id = $1 RETURNING "+errorEventColumns,
		e.ID, string(domain.ErrorStatusIgnored), note)
	if updated, err := scanErrorEvent(row); err == nil {
		*e = *updated
	}
}
