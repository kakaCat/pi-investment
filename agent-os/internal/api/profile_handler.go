package api

import (
	"net/http"
	"strconv"

	"github.com/pi-investment/agent-os/internal/domain"
	"github.com/pi-investment/agent-os/internal/repository"
)

// ProfileHandler 用户配置处理器
type ProfileHandler struct {
	repo repository.ProfileWebRepository
}

// NewProfileHandler 创建用户配置处理器
func NewProfileHandler(repo repository.ProfileWebRepository) *ProfileHandler {
	return &ProfileHandler{repo: repo}
}

// GetProfile 获取用户配置
func (h *ProfileHandler) GetProfile(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	
	// 简化版：使用固定用户名 admin
	username := "admin"
	
	profile, err := h.repo.GetProfile(ctx, username)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to get profile: "+err.Error())
		return
	}
	
	respondJSON(w, http.StatusOK, profile)
}

// UpdateProfile 更新用户配置
func (h *ProfileHandler) UpdateProfile(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	
	var req domain.UpdateProfileRequest
	if err := parseJSON(r, &req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request body: "+err.Error())
		return
	}
	
	// 简化版：使用固定用户名 admin
	username := "admin"
	
	if err := h.repo.UpdateProfile(ctx, username, req); err != nil {
		respondError(w, http.StatusInternalServerError, "failed to update profile: "+err.Error())
		return
	}
	
	respondJSON(w, http.StatusOK, map[string]interface{}{
		"success": true,
		"message": "profile updated successfully",
	})
}

// GetAPIKeys 获取 API 密钥列表
func (h *ProfileHandler) GetAPIKeys(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	
	// 简化版：使用固定用户名 admin
	username := "admin"
	
	keys, err := h.repo.GetAPIKeys(ctx, username)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to get api keys: "+err.Error())
		return
	}
	
	respondJSON(w, http.StatusOK, map[string]interface{}{
		"keys": keys,
	})
}

// GetActivityLogs 获取活动日志
func (h *ProfileHandler) GetActivityLogs(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	
	req := domain.ActivityLogsRequest{}
	
	if limitStr := r.URL.Query().Get("limit"); limitStr != "" {
		limit, err := strconv.Atoi(limitStr)
		if err == nil {
			req.Limit = limit
		}
	}
	
	// 简化版：使用固定用户名 admin
	username := "admin"
	
	logs, err := h.repo.GetActivityLogs(ctx, username, req)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to get activity logs: "+err.Error())
		return
	}
	
	respondJSON(w, http.StatusOK, map[string]interface{}{
		"logs":  logs,
		"total": len(logs),
	})
}
