package api

import (
	"net/http"
	"strconv"

	"github.com/gorilla/mux"
	"github.com/pi-investment/agent-os/internal/domain"
	"github.com/pi-investment/agent-os/internal/repository"
)

// DecisionHandler 决策处理器
type DecisionHandler struct {
	repo repository.DecisionWebRepository
}

// NewDecisionHandler 创建决策处理器
func NewDecisionHandler(repo repository.DecisionWebRepository) *DecisionHandler {
	return &DecisionHandler{repo: repo}
}

// List 获取决策列表
func (h *DecisionHandler) List(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	
	// 解析查询参数
	req := domain.DecisionListRequest{
		Action: r.URL.Query().Get("action"),
		Status: r.URL.Query().Get("status"),
	}
	
	if limitStr := r.URL.Query().Get("limit"); limitStr != "" {
		limit, err := strconv.Atoi(limitStr)
		if err == nil {
			req.Limit = limit
		}
	}
	
	// 获取决策列表
	decisions, err := h.repo.List(ctx, req)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to get decisions: "+err.Error())
		return
	}
	
	respondJSON(w, http.StatusOK, map[string]interface{}{
		"decisions": decisions,
		"total":     len(decisions),
	})
}

// Get 获取单个决策详情
func (h *DecisionHandler) Get(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	vars := mux.Vars(r)
	id := vars["id"]
	
	if id == "" {
		respondError(w, http.StatusBadRequest, "decision id is required")
		return
	}
	
	decision, err := h.repo.GetByID(ctx, id)
	if err != nil {
		if err.Error() == "decision not found: "+id {
			respondError(w, http.StatusNotFound, "decision not found")
			return
		}
		respondError(w, http.StatusInternalServerError, "failed to get decision: "+err.Error())
		return
	}
	
	respondJSON(w, http.StatusOK, map[string]interface{}{
		"decision": decision,
	})
}

// GetStatistics 获取决策统计
func (h *DecisionHandler) GetStatistics(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	
	stats, err := h.repo.GetStatistics(ctx)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to get statistics: "+err.Error())
		return
	}
	
	respondJSON(w, http.StatusOK, map[string]interface{}{
		"stats": stats,
	})
}
