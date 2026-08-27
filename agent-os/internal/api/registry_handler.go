package api

import (
	"net/http"

	"github.com/gorilla/mux"
	"github.com/pi-investment/agent-os/internal/domain"
	"github.com/pi-investment/agent-os/internal/repository"
)

// RegistryHandler Agent 注册表处理器
type RegistryHandler struct {
	repo repository.RegistryWebRepository
}

// NewRegistryHandler 创建注册表处理器
func NewRegistryHandler(repo repository.RegistryWebRepository) *RegistryHandler {
	return &RegistryHandler{repo: repo}
}

// Register 注册 Agent（POST /api/v1/registry/agents/register）
func (h *RegistryHandler) Register(w http.ResponseWriter, r *http.Request) {
	var req domain.AgentRegisterRequest
	if err := parseJSON(r, &req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request body: "+err.Error())
		return
	}
	if req.AgentID == "" {
		respondError(w, http.StatusBadRequest, "agent_id is required")
		return
	}
	if req.Type == "" {
		respondError(w, http.StatusBadRequest, "type is required")
		return
	}

	agent, err := h.repo.Upsert(r.Context(), req)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to register agent: "+err.Error())
		return
	}
	respondJSON(w, http.StatusCreated, agent)
}

// Heartbeat 心跳（POST /api/v1/registry/agents/heartbeat）
func (h *RegistryHandler) Heartbeat(w http.ResponseWriter, r *http.Request) {
	var req domain.AgentHeartbeatRequest
	if err := parseJSON(r, &req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request body: "+err.Error())
		return
	}
	if req.AgentID == "" {
		respondError(w, http.StatusBadRequest, "agent_id is required")
		return
	}

	if err := h.repo.Heartbeat(r.Context(), req); err != nil {
		respondError(w, http.StatusInternalServerError, "failed to update heartbeat: "+err.Error())
		return
	}
	respondJSON(w, http.StatusOK, map[string]interface{}{"success": true})
}

// UpdateStatus 更新状态（POST /api/v1/registry/agents/update-status）
func (h *RegistryHandler) UpdateStatus(w http.ResponseWriter, r *http.Request) {
	var req domain.AgentStatusUpdateRequest
	if err := parseJSON(r, &req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request body: "+err.Error())
		return
	}
	if req.AgentID == "" {
		respondError(w, http.StatusBadRequest, "agent_id is required")
		return
	}
	if req.Status == "" {
		respondError(w, http.StatusBadRequest, "status is required")
		return
	}

	if err := h.repo.UpdateStatus(r.Context(), req); err != nil {
		respondError(w, http.StatusInternalServerError, "failed to update status: "+err.Error())
		return
	}
	respondJSON(w, http.StatusOK, map[string]interface{}{"success": true})
}

// Unregister 注销（POST /api/v1/registry/agents/unregister）
func (h *RegistryHandler) Unregister(w http.ResponseWriter, r *http.Request) {
	var req domain.AgentUnregisterRequest
	if err := parseJSON(r, &req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request body: "+err.Error())
		return
	}
	if req.AgentID == "" {
		respondError(w, http.StatusBadRequest, "agent_id is required")
		return
	}

	if err := h.repo.Unregister(r.Context(), req.AgentID); err != nil {
		respondError(w, http.StatusInternalServerError, "failed to unregister agent: "+err.Error())
		return
	}
	respondJSON(w, http.StatusOK, map[string]interface{}{"success": true})
}

// ListAvailable 列出可用 Agent（GET /api/v1/registry/agents/available）
// RFC 010: 支持 role 和 status 过滤
func (h *RegistryHandler) ListAvailable(w http.ResponseWriter, r *http.Request) {
	capability := r.URL.Query().Get("capability")
	role := r.URL.Query().Get("role")
	status := r.URL.Query().Get("status")

	var agents []*domain.AgentWeb
	var err error

	// RFC 010: 优先按 role 查询（新功能）
	if role != "" {
		agents, err = h.repo.ListByRole(r.Context(), role, status)
	} else {
		// 保持向后兼容：按 capability 查询
		agents, err = h.repo.ListActive(r.Context(), capability)
	}

	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to list agents: "+err.Error())
		return
	}
	respondJSON(w, http.StatusOK, agents)
}

// Get 查询单个 Agent（GET /api/v1/registry/agents/{id}）
func (h *RegistryHandler) Get(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	agentID := vars["id"]
	if agentID == "" {
		respondError(w, http.StatusBadRequest, "agent id is required")
		return
	}

	agent, err := h.repo.GetByAgentID(r.Context(), agentID)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to get agent: "+err.Error())
		return
	}
	respondJSON(w, http.StatusOK, agent)
}
