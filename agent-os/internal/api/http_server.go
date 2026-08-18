package api

import (
	"context"
	"encoding/json"
	"net/http"
	"strconv"
	"time"

	"github.com/gorilla/mux"
	"github.com/pi-investment/agent-os/internal/domain"
	"github.com/pi-investment/agent-os/internal/handlers"
	"github.com/pi-investment/agent-os/internal/provider"
	"github.com/pi-investment/agent-os/internal/service"
)

type HTTPServer struct {
	service         *service.NotificationService
	skillHandler    *handlers.SkillHandler
	registryHandler *handlers.RegistryHandler
	server          *http.Server
}

func NewHTTPServer(service *service.NotificationService, skillHandler *handlers.SkillHandler, registryHandler *handlers.RegistryHandler) *HTTPServer {
	return &HTTPServer{
		service:         service,
		skillHandler:    skillHandler,
		registryHandler: registryHandler,
	}
}

// Start starts the HTTP server
func (s *HTTPServer) Start(addr string) error {
	router := mux.NewRouter()

	// Health check
	router.HandleFunc("/health", s.handleHealth).Methods("GET")

	// API v1
	api := router.PathPrefix("/api/v1").Subrouter()

	// Notification endpoints
	api.HandleFunc("/notifications/send", s.handleSend).Methods("POST")
	api.HandleFunc("/notifications/channels", s.handleListChannels).Methods("GET")
	api.HandleFunc("/notifications/logs", s.handleGetLogs).Methods("GET")
	api.HandleFunc("/notifications/providers", s.handleListProviders).Methods("GET")

	// Skill endpoints
	if s.skillHandler != nil {
		s.skillHandler.RegisterRoutes(api)
	}

	// Registry endpoints
	if s.registryHandler != nil {
		s.registryHandler.RegisterRoutes(api)
	}

	s.server = &http.Server{
		Addr:         addr,
		Handler:      router,
		ReadTimeout:  15 * time.Second,
		WriteTimeout: 15 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	return s.server.ListenAndServe()
}

// Stop stops the HTTP server
func (s *HTTPServer) Stop(ctx context.Context) error {
	if s.server != nil {
		return s.server.Shutdown(ctx)
	}
	return nil
}

// handleHealth handles health check
func (s *HTTPServer) handleHealth(w http.ResponseWriter, r *http.Request) {
	respondJSON(w, http.StatusOK, map[string]string{
		"status": "ok",
		"time":   time.Now().Format(time.RFC3339),
	})
}

// handleSend handles notification send request
func (s *HTTPServer) handleSend(w http.ResponseWriter, r *http.Request) {
	var req domain.SendRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request body: "+err.Error())
		return
	}

	// Validate required fields
	if req.Channel == "" {
		respondError(w, http.StatusBadRequest, "channel is required")
		return
	}
	if req.Title == "" {
		respondError(w, http.StatusBadRequest, "title is required")
		return
	}
	if req.Content == "" {
		respondError(w, http.StatusBadRequest, "content is required")
		return
	}

	// Send notification
	result, err := s.service.Send(r.Context(), &req)
	if err != nil {
		respondError(w, http.StatusInternalServerError, err.Error())
		return
	}

	respondJSON(w, http.StatusOK, result)
}

// handleListChannels handles list channels request
func (s *HTTPServer) handleListChannels(w http.ResponseWriter, r *http.Request) {
	channels, err := s.service.ListChannels(r.Context())
	if err != nil {
		respondError(w, http.StatusInternalServerError, err.Error())
		return
	}

	respondJSON(w, http.StatusOK, channels)
}

// handleGetLogs handles get logs request
func (s *HTTPServer) handleGetLogs(w http.ResponseWriter, r *http.Request) {
	limitStr := r.URL.Query().Get("limit")
	limit := 10
	if limitStr != "" {
		if l, err := strconv.Atoi(limitStr); err == nil && l > 0 {
			limit = l
		}
	}

	logs, err := s.service.GetRecentLogs(r.Context(), limit)
	if err != nil {
		respondError(w, http.StatusInternalServerError, err.Error())
		return
	}

	respondJSON(w, http.StatusOK, logs)
}

// handleListProviders handles list providers request
func (s *HTTPServer) handleListProviders(w http.ResponseWriter, r *http.Request) {
	providers := provider.List()
	respondJSON(w, http.StatusOK, map[string]interface{}{
		"providers": providers,
	})
}

func respondJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

func respondError(w http.ResponseWriter, status int, message string) {
	respondJSON(w, status, map[string]string{"error": message})
}
