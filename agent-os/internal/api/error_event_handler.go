package api

import (
	"encoding/json"
	"net/http"
	"strconv"
	"strings"

	"github.com/gorilla/mux"
	"github.com/pi-investment/agent-os/internal/domain"
	"github.com/pi-investment/agent-os/internal/repository"
)

// ErrorEventHandler 错误事件收集与处置 HTTP 处理器
type ErrorEventHandler struct {
	repo repository.ErrorEventRepository
}

// NewErrorEventHandler 创建错误事件处理器
func NewErrorEventHandler(repo repository.ErrorEventRepository) *ErrorEventHandler {
	return &ErrorEventHandler{repo: repo}
}

// List GET /api/v1/scheduler/error-events?status=&source=&limit=&offset=
// 分页：limit=每页条数（默认50，上限500）、offset=偏移（默认0）；total=满足过滤条件的 DB 总数（供翻页）。
func (h *ErrorEventHandler) List(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query()
	req := domain.ErrorEventListRequest{
		Status: q.Get("status"),
		Source: q.Get("source"),
	}
	if v := q.Get("limit"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			req.Limit = n
		}
	}
	if v := q.Get("offset"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			req.Offset = n
		}
	}
	events, total, err := h.repo.List(r.Context(), req)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to list error events: "+err.Error())
		return
	}
	if events == nil {
		events = []*domain.ErrorEvent{}
	}
	respondJSON(w, http.StatusOK, map[string]interface{}{
		"success": true,
		"total":   total,
		"events":  events,
	})
}

// errorEventIngestRequest 结构化上报体（外部系统如 quantsys-v2 主动推送）
type errorEventIngestRequest struct {
	Source      string                 `json:"source"` // os/v2/dsh（缺省 v2）
	TaskID      string                 `json:"task_id"`
	TaskName    string                 `json:"task_name"`
	Level       string                 `json:"level"`       // 缺省 error
	Msg         string                 `json:"msg"`         // 必填：错误一句话
	Detail      string                 `json:"detail"`      // 完整堆栈/上下文
	Fingerprint string                 `json:"fingerprint"` // 可选：自定义指纹（缺省按 source|task_id|msg 计算）
	Metadata    map[string]interface{} `json:"metadata"`    // 附加信息（log_path/组件等）
}

// Create POST /api/v1/scheduler/error-events（结构化错误上报：新事件收录 / 同指纹去重计数）
func (h *ErrorEventHandler) Create(w http.ResponseWriter, r *http.Request) {
	var req errorEventIngestRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request body: "+err.Error())
		return
	}
	if strings.TrimSpace(req.Msg) == "" {
		respondError(w, http.StatusBadRequest, "msg 必填（错误一句话）")
		return
	}
	in := domain.ErrorEventUpsertInput{
		Source:      req.Source,
		TaskID:      req.TaskID,
		TaskName:    req.TaskName,
		Level:       req.Level,
		Msg:         req.Msg,
		Detail:      req.Detail,
		Fingerprint: req.Fingerprint,
		Metadata:    req.Metadata,
	}
	if in.Source == "" {
		in.Source = string(domain.ErrorSourceV2)
	}
	event, isNew, err := h.repo.Upsert(r.Context(), in)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to ingest error event: "+err.Error())
		return
	}
	message := "已收录（新事件）"
	if !isNew {
		message = "已合并去重（同指纹 occurrence_count+1）"
	}
	respondJSON(w, http.StatusCreated, map[string]interface{}{
		"success": true,
		"message": message,
		"created": isNew,
		"event":   event,
	})
}

// GetStats GET /api/v1/scheduler/error-events/stats
func (h *ErrorEventHandler) GetStats(w http.ResponseWriter, r *http.Request) {
	stats, err := h.repo.Stats(r.Context())
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to get error event stats: "+err.Error())
		return
	}
	respondJSON(w, http.StatusOK, map[string]interface{}{
		"success": true,
		"stats":   stats,
	})
}

// Update PATCH /api/v1/scheduler/error-events/{id}
// body: {"action":"claim|resolve|ignore|reopen","actor":"...","session":"...","note":"..."}
func (h *ErrorEventHandler) Update(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]

	var req domain.ErrorEventActionRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request body: "+err.Error())
		return
	}
	if strings.TrimSpace(req.Action) == "" {
		respondError(w, http.StatusBadRequest, "action 必填（claim/resolve/ignore/reopen）")
		return
	}

	event, msg, err := h.repo.ApplyAction(r.Context(), id, req)
	if err != nil {
		status := http.StatusInternalServerError
		lower := strings.ToLower(err.Error())
		if strings.Contains(lower, "not found") {
			status = http.StatusNotFound
		} else if strings.Contains(lower, "状态机") || strings.Contains(lower, "未知动作") {
			status = http.StatusConflict
		}
		respondError(w, status, err.Error())
		return
	}
	respondJSON(w, http.StatusOK, map[string]interface{}{
		"success": true,
		"message": msg,
		"event":   event,
	})
}
