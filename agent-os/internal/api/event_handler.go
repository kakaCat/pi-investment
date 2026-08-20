package api

import (
	"net/http"
	"strconv"

	"github.com/gorilla/mux"
	"github.com/pi-investment/agent-os/internal/domain"
	"github.com/pi-investment/agent-os/internal/repository"
)

// EventHandler 事件处理器
type EventHandler struct {
	repo repository.EventWebRepository
}

// NewEventHandler 创建事件处理器
func NewEventHandler(repo repository.EventWebRepository) *EventHandler {
	return &EventHandler{repo: repo}
}

// GetHistory 获取事件历史
func (h *EventHandler) GetHistory(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	
	req := domain.EventHistoryRequest{
		Type:  r.URL.Query().Get("type"),
		Start: r.URL.Query().Get("start"),
		End:   r.URL.Query().Get("end"),
	}
	
	if limitStr := r.URL.Query().Get("limit"); limitStr != "" {
		limit, err := strconv.Atoi(limitStr)
		if err == nil {
			req.Limit = limit
		}
	}
	
	events, err := h.repo.GetHistory(ctx, req)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to get event history: "+err.Error())
		return
	}
	
	respondJSON(w, http.StatusOK, map[string]interface{}{
		"events": events,
		"total":  len(events),
	})
}

// GetAlertRules 获取告警规则列表
func (h *EventHandler) GetAlertRules(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	
	rules, err := h.repo.GetAlertRules(ctx)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to get alert rules: "+err.Error())
		return
	}
	
	respondJSON(w, http.StatusOK, map[string]interface{}{
		"rules": rules,
	})
}

// CreateAlertRule 创建告警规则
func (h *EventHandler) CreateAlertRule(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	
	var req domain.AlertRuleCreateRequest
	if err := parseJSON(r, &req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request body: "+err.Error())
		return
	}
	
	// 验证必填字段
	if req.Name == "" || req.EventType == "" || req.Condition == "" || req.Level == "" {
		respondError(w, http.StatusBadRequest, "name, event_type, condition, and level are required")
		return
	}
	
	if err := h.repo.CreateAlertRule(ctx, req); err != nil {
		respondError(w, http.StatusInternalServerError, "failed to create alert rule: "+err.Error())
		return
	}
	
	respondJSON(w, http.StatusOK, map[string]interface{}{
		"success": true,
		"message": "alert rule created successfully",
	})
}

// DeleteAlertRule 删除告警规则
func (h *EventHandler) DeleteAlertRule(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	vars := mux.Vars(r)
	id := vars["id"]
	
	if id == "" {
		respondError(w, http.StatusBadRequest, "alert rule id is required")
		return
	}
	
	if err := h.repo.DeleteAlertRule(ctx, id); err != nil {
		respondError(w, http.StatusInternalServerError, "failed to delete alert rule: "+err.Error())
		return
	}
	
	respondJSON(w, http.StatusOK, map[string]interface{}{
		"success": true,
		"message": "alert rule deleted successfully",
	})
}

// UpdateAlertRuleEnabled 更新告警规则启用状态
func (h *EventHandler) UpdateAlertRuleEnabled(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	vars := mux.Vars(r)
	id := vars["id"]

	if id == "" {
		respondError(w, http.StatusBadRequest, "alert rule id is required")
		return
	}

	var req struct {
		Enabled bool `json:"enabled"`
	}
	if err := parseJSON(r, &req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request body: "+err.Error())
		return
	}

	if err := h.repo.UpdateAlertRuleEnabled(ctx, id, req.Enabled); err != nil {
		respondError(w, http.StatusInternalServerError, "failed to update alert rule: "+err.Error())
		return
	}

	respondJSON(w, http.StatusOK, map[string]interface{}{
		"success": true,
		"message": "alert rule updated successfully",
	})
}
