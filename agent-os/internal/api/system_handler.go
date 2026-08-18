package api

import (
	"net/http"
	"strconv"

	"github.com/pi-investment/agent-os/internal/domain"
	"github.com/pi-investment/agent-os/internal/repository"
)

// SystemHandler 系统处理器
type SystemHandler struct {
	repo repository.SystemWebRepository
}

// NewSystemHandler 创建系统处理器
func NewSystemHandler(repo repository.SystemWebRepository) *SystemHandler {
	return &SystemHandler{repo: repo}
}

// GetStatus 获取系统状态
func (h *SystemHandler) GetStatus(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	
	status, err := h.repo.GetStatus(ctx)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to get system status: "+err.Error())
		return
	}
	
	respondJSON(w, http.StatusOK, status)
}

// GetQuotas 获取资源配额
func (h *SystemHandler) GetQuotas(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	
	quotas, err := h.repo.GetQuotas(ctx)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to get resource quotas: "+err.Error())
		return
	}
	
	respondJSON(w, http.StatusOK, map[string]interface{}{
		"quotas": quotas,
	})
}

// GetLogs 获取系统日志
func (h *SystemHandler) GetLogs(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	
	req := domain.SystemLogsRequest{
		Level:  r.URL.Query().Get("level"),
		Source: r.URL.Query().Get("source"),
	}
	
	if limitStr := r.URL.Query().Get("limit"); limitStr != "" {
		limit, err := strconv.Atoi(limitStr)
		if err == nil {
			req.Limit = limit
		}
	}
	
	logs, err := h.repo.GetLogs(ctx, req)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to get system logs: "+err.Error())
		return
	}
	
	respondJSON(w, http.StatusOK, map[string]interface{}{
		"logs":  logs,
		"total": len(logs),
	})
}

// GetNamespaces 获取命名空间列表
func (h *SystemHandler) GetNamespaces(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	
	namespaces, err := h.repo.GetNamespaces(ctx)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to get namespaces: "+err.Error())
		return
	}
	
	respondJSON(w, http.StatusOK, map[string]interface{}{
		"namespaces": namespaces,
	})
}
