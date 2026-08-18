package api

import (
	"net/http"
	"strconv"

	"github.com/gorilla/mux"
	"github.com/pi-investment/agent-os/internal/domain"
	"github.com/pi-investment/agent-os/internal/repository"
)

// MemoryHandler 记忆处理器
type MemoryHandler struct {
	repo repository.MemoryWebRepository
}

// NewMemoryHandler 创建记忆处理器
func NewMemoryHandler(repo repository.MemoryWebRepository) *MemoryHandler {
	return &MemoryHandler{repo: repo}
}

// List 获取记忆列表
func (h *MemoryHandler) List(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	
	req := domain.MemoryListRequest{
		Category: r.URL.Query().Get("category"),
		Tag:      r.URL.Query().Get("tag"),
	}
	
	if limitStr := r.URL.Query().Get("limit"); limitStr != "" {
		limit, err := strconv.Atoi(limitStr)
		if err == nil {
			req.Limit = limit
		}
	}
	
	memories, err := h.repo.List(ctx, req)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to get memories: "+err.Error())
		return
	}
	
	respondJSON(w, http.StatusOK, map[string]interface{}{
		"memories": memories,
		"total":    len(memories),
	})
}

// Search 搜索记忆
func (h *MemoryHandler) Search(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	
	query := r.URL.Query().Get("q")
	if query == "" {
		respondError(w, http.StatusBadRequest, "query parameter 'q' is required")
		return
	}
	
	req := domain.MemorySearchRequest{
		Query: query,
	}
	
	if limitStr := r.URL.Query().Get("limit"); limitStr != "" {
		limit, err := strconv.Atoi(limitStr)
		if err == nil {
			req.Limit = limit
		}
	}
	
	memories, err := h.repo.Search(ctx, req)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to search memories: "+err.Error())
		return
	}
	
	respondJSON(w, http.StatusOK, map[string]interface{}{
		"memories": memories,
		"total":    len(memories),
	})
}

// Create 写入记忆
func (h *MemoryHandler) Create(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()

	var req domain.MemoryCreateRequest
	if err := parseJSON(r, &req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request body: "+err.Error())
		return
	}

	if req.Content == "" {
		respondError(w, http.StatusBadRequest, "content is required")
		return
	}

	// 分类默认值：knowledge / experience / decision / data
	if req.Category == "" {
		req.Category = "knowledge"
	}
	validCategories := map[string]bool{"knowledge": true, "experience": true, "decision": true, "data": true}
	if !validCategories[req.Category] {
		respondError(w, http.StatusBadRequest, "invalid category: "+req.Category)
		return
	}

	if req.Title == "" {
		req.Title = req.Category
	}

	memory, err := h.repo.Create(ctx, req)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to create memory: "+err.Error())
		return
	}

	respondJSON(w, http.StatusCreated, map[string]interface{}{
		"success": true,
		"memory":  memory,
	})
}

// GetTags 获取标签列表
func (h *MemoryHandler) GetTags(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	
	tags, err := h.repo.GetTags(ctx)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to get tags: "+err.Error())
		return
	}
	
	respondJSON(w, http.StatusOK, map[string]interface{}{
		"tags": tags,
	})
}

// CreateTag 创建标签
func (h *MemoryHandler) CreateTag(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	
	var req struct {
		Name string `json:"name"`
	}
	
	if err := parseJSON(r, &req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request body: "+err.Error())
		return
	}
	
	if req.Name == "" {
		respondError(w, http.StatusBadRequest, "tag name is required")
		return
	}
	
	if err := h.repo.CreateTag(ctx, req.Name); err != nil {
		respondError(w, http.StatusInternalServerError, "failed to create tag: "+err.Error())
		return
	}
	
	respondJSON(w, http.StatusOK, map[string]interface{}{
		"success": true,
		"message": "tag created successfully",
	})
}

// DeleteTag 删除标签
func (h *MemoryHandler) DeleteTag(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	vars := mux.Vars(r)
	name := vars["name"]
	
	if name == "" {
		respondError(w, http.StatusBadRequest, "tag name is required")
		return
	}
	
	if err := h.repo.DeleteTag(ctx, name); err != nil {
		respondError(w, http.StatusInternalServerError, "failed to delete tag: "+err.Error())
		return
	}
	
	respondJSON(w, http.StatusOK, map[string]interface{}{
		"success": true,
		"message": "tag deleted successfully",
	})
}
