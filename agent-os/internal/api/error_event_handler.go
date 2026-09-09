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

// List GET /api/v1/scheduler/error-events?status=&source=&limit=
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
	events, err := h.repo.List(r.Context(), req)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to list error events: "+err.Error())
		return
	}
	if events == nil {
		events = []*domain.ErrorEvent{}
	}
	respondJSON(w, http.StatusOK, map[string]interface{}{
		"success": true,
		"total":   len(events),
		"events":  events,
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
