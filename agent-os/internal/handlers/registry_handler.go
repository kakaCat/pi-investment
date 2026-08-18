package handlers

import (
	"encoding/json"
	"net/http"

	"github.com/gorilla/mux"
	"go.uber.org/zap"

	"github.com/pi-investment/agent-os/internal/domain"
	"github.com/pi-investment/agent-os/internal/service"
)

type RegistryHandler struct {
	service service.RegistryService
	logger  *zap.Logger
}

func NewRegistryHandler(service service.RegistryService, logger *zap.Logger) *RegistryHandler {
	return &RegistryHandler{
		service: service,
		logger:  logger,
	}
}

func (h *RegistryHandler) RegisterRoutes(r *mux.Router) {
	r.HandleFunc("/registry/agents/register", h.Register).Methods("POST")
	r.HandleFunc("/registry/agents/unregister", h.Unregister).Methods("POST")
	r.HandleFunc("/registry/agents/heartbeat", h.Heartbeat).Methods("POST")
	r.HandleFunc("/registry/agents/update-status", h.UpdateStatus).Methods("POST")
	r.HandleFunc("/registry/agents/{agent_id}", h.GetAgent).Methods("GET")
	r.HandleFunc("/registry/agents", h.ListAgents).Methods("GET")
	r.HandleFunc("/registry/agents/available", h.FindAvailableAgents).Methods("GET")
}

// POST /api/v1/registry/agents/register
func (h *RegistryHandler) Register(w http.ResponseWriter, r *http.Request) {
	var req domain.RegisterAgentRequest

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.logger.Error("Failed to decode register request", zap.Error(err))
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	agent, err := h.service.Register(&req)
	if err != nil {
		h.logger.Error("Failed to register agent",
			zap.String("agent_id", req.AgentID),
			zap.Error(err),
		)
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	h.logger.Info("Agent registered",
		zap.String("agent_id", agent.AgentID),
		zap.String("session_id", agent.SessionID),
		zap.String("agent_type", agent.AgentType),
	)

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(map[string]interface{}{
		"success": true,
		"agent":   agent,
	})
}

// POST /api/v1/registry/agents/unregister
func (h *RegistryHandler) Unregister(w http.ResponseWriter, r *http.Request) {
	var req struct {
		AgentID string `json:"agent_id"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.logger.Error("Failed to decode unregister request", zap.Error(err))
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	if err := h.service.Unregister(req.AgentID); err != nil {
		h.logger.Error("Failed to unregister agent",
			zap.String("agent_id", req.AgentID),
			zap.Error(err),
		)
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	h.logger.Info("Agent unregistered", zap.String("agent_id", req.AgentID))

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"success": true,
		"message": "Agent unregistered successfully",
	})
}

// POST /api/v1/registry/agents/heartbeat
func (h *RegistryHandler) Heartbeat(w http.ResponseWriter, r *http.Request) {
	var req domain.HeartbeatRequest

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.logger.Error("Failed to decode heartbeat request", zap.Error(err))
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	if err := h.service.Heartbeat(&req); err != nil {
		h.logger.Error("Failed to process heartbeat",
			zap.String("agent_id", req.AgentID),
			zap.Error(err),
		)
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"success": true,
		"message": "Heartbeat received",
	})
}

// POST /api/v1/registry/agents/update-status
func (h *RegistryHandler) UpdateStatus(w http.ResponseWriter, r *http.Request) {
	var req domain.UpdateStatusRequest

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.logger.Error("Failed to decode update status request", zap.Error(err))
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	if err := h.service.UpdateStatus(&req); err != nil {
		h.logger.Error("Failed to update status",
			zap.String("agent_id", req.AgentID),
			zap.String("status", string(req.Status)),
			zap.Error(err),
		)
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	h.logger.Info("Agent status updated",
		zap.String("agent_id", req.AgentID),
		zap.String("status", string(req.Status)),
	)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"success": true,
		"message": "Status updated successfully",
	})
}

// GET /api/v1/registry/agents/{agent_id}
func (h *RegistryHandler) GetAgent(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	agentID := vars["agent_id"]

	agent, err := h.service.GetAgent(agentID)
	if err != nil {
		h.logger.Error("Failed to get agent",
			zap.String("agent_id", agentID),
			zap.Error(err),
		)
		http.Error(w, err.Error(), http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(agent)
}

// GET /api/v1/registry/agents
func (h *RegistryHandler) ListAgents(w http.ResponseWriter, r *http.Request) {
	status := r.URL.Query().Get("status")

	var agents []*domain.Agent
	var err error

	if status != "" {
		agents, err = h.service.ListAgentsByStatus(domain.AgentStatus(status))
	} else {
		agents, err = h.service.ListAgents()
	}

	if err != nil {
		h.logger.Error("Failed to list agents", zap.Error(err))
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"agents": agents,
		"count":  len(agents),
	})
}

// GET /api/v1/registry/agents/available
func (h *RegistryHandler) FindAvailableAgents(w http.ResponseWriter, r *http.Request) {
	// Parse capabilities from query parameter (comma-separated)
	capabilitiesParam := r.URL.Query().Get("capabilities")
	var capabilities []string
	if capabilitiesParam != "" {
		// Simple split by comma - could be enhanced with proper parsing
		for _, cap := range splitByComma(capabilitiesParam) {
			if cap != "" {
				capabilities = append(capabilities, cap)
			}
		}
	}

	agents, err := h.service.FindAvailableAgents(capabilities)
	if err != nil {
		h.logger.Error("Failed to find available agents",
			zap.Strings("capabilities", capabilities),
			zap.Error(err),
		)
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"agents": agents,
		"count":  len(agents),
	})
}

// Helper function to split comma-separated string
func splitByComma(s string) []string {
	var result []string
	current := ""
	for _, ch := range s {
		if ch == ',' {
			if current != "" {
				result = append(result, current)
				current = ""
			}
		} else if ch != ' ' {
			current += string(ch)
		}
	}
	if current != "" {
		result = append(result, current)
	}
	return result
}
