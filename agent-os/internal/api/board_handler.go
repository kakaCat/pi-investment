package api

import (
	"net/http"
	"strconv"
	"strings"

	"github.com/gorilla/mux"
	"github.com/pi-investment/agent-os/internal/domain"
	"github.com/pi-investment/agent-os/internal/repository"
)

// BoardHandler 公告板处理器（RFC 014 独立存储）
type BoardHandler struct {
	repo repository.BoardWebRepository
}

// NewBoardHandler 创建公告板处理器
func NewBoardHandler(repo repository.BoardWebRepository) *BoardHandler {
	return &BoardHandler{repo: repo}
}

// List 查询帖子（GET /api/v1/board/posts?status=&kind=&assignee=&limit=）
func (h *BoardHandler) List(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	req := domain.BoardListRequest{
		Status:   r.URL.Query().Get("status"),
		Kind:     r.URL.Query().Get("kind"),
		Assignee: r.URL.Query().Get("assignee"),
	}
	if limitStr := r.URL.Query().Get("limit"); limitStr != "" {
		if limit, err := strconv.Atoi(limitStr); err == nil {
			req.Limit = limit
		}
	}
	posts, err := h.repo.List(ctx, req)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to list board posts: "+err.Error())
		return
	}
	respondJSON(w, http.StatusOK, map[string]interface{}{
		"posts": posts,
		"total": len(posts),
	})
}

// GetByID 按 ID 取帖（GET /api/v1/board/posts/{id}）
func (h *BoardHandler) GetByID(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	id := mux.Vars(r)["id"]
	if id == "" {
		respondError(w, http.StatusBadRequest, "post id is required")
		return
	}
	post, err := h.repo.GetByID(ctx, id)
	if err != nil {
		if strings.Contains(err.Error(), "not found") {
			respondError(w, http.StatusNotFound, err.Error())
			return
		}
		respondError(w, http.StatusInternalServerError, "failed to get board post: "+err.Error())
		return
	}
	respondJSON(w, http.StatusOK, post)
}

// Create 发帖（POST /api/v1/board/posts）
func (h *BoardHandler) Create(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	var req domain.BoardCreateRequest
	if err := parseJSON(r, &req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request body: "+err.Error())
		return
	}
	if strings.TrimSpace(req.Title) == "" {
		respondError(w, http.StatusBadRequest, "title is required")
		return
	}
	if strings.TrimSpace(req.Content) == "" {
		respondError(w, http.StatusBadRequest, "content is required")
		return
	}
	post, err := h.repo.Create(ctx, req)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to create board post: "+err.Error())
		return
	}
	respondJSON(w, http.StatusCreated, map[string]interface{}{
		"success": true,
		"post":    post,
	})
}

// Update 状态流转（PATCH /api/v1/board/posts/{id}）
func (h *BoardHandler) Update(w http.ResponseWriter, r *http.Request) {
	ctx := r.Context()
	id := mux.Vars(r)["id"]
	if id == "" {
		respondError(w, http.StatusBadRequest, "post id is required")
		return
	}
	var req domain.BoardUpdateRequest
	if err := parseJSON(r, &req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request body: "+err.Error())
		return
	}
	if req.Action == "" {
		respondError(w, http.StatusBadRequest, "action is required")
		return
	}
	post, message, err := h.repo.Update(ctx, id, req)
	if err != nil {
		switch {
		case strings.Contains(err.Error(), "revision conflict"):
			respondError(w, http.StatusConflict, err.Error())
		case strings.Contains(err.Error(), "permission denied"):
			respondError(w, http.StatusForbidden, err.Error())
		case strings.Contains(err.Error(), "not found"):
			respondError(w, http.StatusNotFound, err.Error())
		case strings.Contains(err.Error(), "illegal transition"),
			strings.Contains(err.Error(), "requires note"),
			strings.Contains(err.Error(), "requires content"),
			strings.Contains(err.Error(), "unknown action"):
			respondError(w, http.StatusBadRequest, err.Error())
		default:
			respondError(w, http.StatusInternalServerError, "failed to update board post: "+err.Error())
		}
		return
	}
	respondJSON(w, http.StatusOK, map[string]interface{}{
		"success":    true,
		"post":       post,
		"new_status": post.Status,
		"revision":   post.Revision,
		"message":    message,
	})
}
