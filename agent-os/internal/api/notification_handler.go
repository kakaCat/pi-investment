package api

import (
	"net/http"
	"strconv"

	"github.com/pi-investment/agent-os/internal/domain"
	"github.com/pi-investment/agent-os/internal/repository"
)

// NotificationHandler 通知处理器
type NotificationHandler struct {
	repo repository.NotificationWebRepository
}

// NewNotificationHandler 创建通知处理器
func NewNotificationHandler(repo repository.NotificationWebRepository) *NotificationHandler {
	return &NotificationHandler{repo: repo}
}

// GetChannels 获取通知渠道列表
func (h *NotificationHandler) GetChannels(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	
	channels, err := h.repo.GetChannels(ctx)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to get channels: "+err.Error())
		return
	}
	
	respondJSON(w, http.StatusOK, map[string]interface{}{
		"channels": channels,
	})
}

// GetProviders 获取通知提供商列表
func (h *NotificationHandler) GetProviders(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	
	providers, err := h.repo.GetProviders(ctx)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to get providers: "+err.Error())
		return
	}
	
	respondJSON(w, http.StatusOK, map[string]interface{}{
		"providers": providers,
	})
}

// GetLogs 获取通知日志
func (h *NotificationHandler) GetLogs(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	
	req := domain.NotificationLogsRequest{
		Status: r.URL.Query().Get("status"),
	}
	
	if limitStr := r.URL.Query().Get("limit"); limitStr != "" {
		limit, err := strconv.Atoi(limitStr)
		if err == nil {
			req.Limit = limit
		}
	}
	
	logs, err := h.repo.GetLogs(ctx, req)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to get logs: "+err.Error())
		return
	}
	
	respondJSON(w, http.StatusOK, map[string]interface{}{
		"logs":  logs,
		"total": len(logs),
	})
}

// SendNotification 发送通知
func (h *NotificationHandler) SendNotification(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	
	var req domain.SendNotificationRequest
	if err := parseJSON(r, &req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request body: "+err.Error())
		return
	}
	
	// 验证必填字段
	if req.Channel == "" || req.Title == "" {
		respondError(w, http.StatusBadRequest, "channel and title are required")
		return
	}
	
	if err := h.repo.SendNotification(ctx, req); err != nil {
		respondError(w, http.StatusInternalServerError, "failed to send notification: "+err.Error())
		return
	}
	
	respondJSON(w, http.StatusOK, map[string]interface{}{
		"success": true,
		"message": "notification sent successfully",
	})
}
