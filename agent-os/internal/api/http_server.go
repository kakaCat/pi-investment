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
	service          *service.NotificationService
	skillHandler     *handlers.SkillHandler
	schedulerHandler *SchedulerHandler
	server           *http.Server
	decisionHandler  *DecisionHandler
	memoryHandler    *MemoryHandler
	eventHandler     *EventHandler
	systemHandler    *SystemHandler
	notificationHandler *NotificationHandler
	profileHandler      *ProfileHandler
	registryHandler     *RegistryHandler
	evolutionHandler    *EvolutionHandler
}
func NewHTTPServer(service *service.NotificationService, skillHandler *handlers.SkillHandler, schedulerHandler *SchedulerHandler, decisionHandler *DecisionHandler, memoryHandler *MemoryHandler, eventHandler *EventHandler, systemHandler *SystemHandler, notificationHandler *NotificationHandler, profileHandler *ProfileHandler, registryHandler *RegistryHandler, evolutionHandler *EvolutionHandler) *HTTPServer {
	return &HTTPServer{
		service:          service,
		skillHandler:     skillHandler,
		schedulerHandler: schedulerHandler,
		decisionHandler:  decisionHandler,
		profileHandler:      profileHandler,
		notificationHandler: notificationHandler,
		systemHandler:    systemHandler,
		eventHandler:     eventHandler,
		memoryHandler:    memoryHandler,
		registryHandler:  registryHandler,
		evolutionHandler: evolutionHandler,
	}
}

// Start starts the HTTP server
func (s *HTTPServer) Start(addr string) error {
	router := mux.NewRouter()

	// Health check
	router.HandleFunc("/health", s.handleHealth).Methods("GET")

	// API v1
	api := router.PathPrefix("/api/v1").Subrouter()


	// Skill endpoints
	if s.skillHandler != nil {
		s.skillHandler.RegisterRoutes(api)
	}

	// Scheduler endpoints
	if s.schedulerHandler != nil {
		s.schedulerHandler.RegisterRoutes(api)
	}

	// Decision endpoints
	if s.decisionHandler != nil {
		api.HandleFunc("/decisions/statistics", s.decisionHandler.GetStatistics).Methods("GET")
		api.HandleFunc("/decisions", s.decisionHandler.List).Methods("GET")
		api.HandleFunc("/decisions/{id}", s.decisionHandler.Get).Methods("GET")
	}

	// Memory endpoints
	if s.memoryHandler != nil {
		api.HandleFunc("/memory", s.memoryHandler.List).Methods("GET")
		api.HandleFunc("/memory", s.memoryHandler.Create).Methods("POST")
		api.HandleFunc("/memory/search", s.memoryHandler.Search).Methods("GET")
		api.HandleFunc("/memory/tags", s.memoryHandler.GetTags).Methods("GET")
		api.HandleFunc("/memory/tags", s.memoryHandler.CreateTag).Methods("POST")
		api.HandleFunc("/memory/tags/{name}", s.memoryHandler.DeleteTag).Methods("DELETE")
	}

	// Event endpoints
	if s.eventHandler != nil {
		api.HandleFunc("/events/history", s.eventHandler.GetHistory).Methods("GET")
		api.HandleFunc("/events/alerts", s.eventHandler.GetAlertRules).Methods("GET")
		api.HandleFunc("/events/alerts", s.eventHandler.CreateAlertRule).Methods("POST")
		api.HandleFunc("/events/alerts/{id}", s.eventHandler.DeleteAlertRule).Methods("DELETE")
		api.HandleFunc("/events/alerts/{id}", s.eventHandler.UpdateAlertRuleEnabled).Methods("PUT")
	}

	// System endpoints
	if s.systemHandler != nil {
		api.HandleFunc("/system/status", s.systemHandler.GetStatus).Methods("GET")
		api.HandleFunc("/system/quotas", s.systemHandler.GetQuotas).Methods("GET")
		api.HandleFunc("/system/logs", s.systemHandler.GetLogs).Methods("GET")
		api.HandleFunc("/system/namespaces", s.systemHandler.GetNamespaces).Methods("GET")
		api.HandleFunc("/system/namespaces", s.systemHandler.CreateNamespace).Methods("POST")
		api.HandleFunc("/system/namespaces/{name}", s.systemHandler.DeleteNamespace).Methods("DELETE")
	}

	// Notification endpoints
	if s.notificationHandler != nil {
		api.HandleFunc("/notifications/channels", s.notificationHandler.GetChannels).Methods("GET")
		api.HandleFunc("/notifications/channels", s.notificationHandler.CreateChannel).Methods("POST")
		api.HandleFunc("/notifications/channels/{id}", s.notificationHandler.DeleteChannel).Methods("DELETE")
		api.HandleFunc("/notifications/providers", s.notificationHandler.GetProviders).Methods("GET")
		api.HandleFunc("/notifications/logs", s.notificationHandler.GetLogs).Methods("GET")
		api.HandleFunc("/notifications/send", s.notificationHandler.SendNotification).Methods("POST")
	}

	// Profile endpoints
	if s.profileHandler != nil {
		api.HandleFunc("/profile", s.profileHandler.GetProfile).Methods("GET")
		api.HandleFunc("/profile", s.profileHandler.UpdateProfile).Methods("PUT")
		api.HandleFunc("/profile/api-keys", s.profileHandler.GetAPIKeys).Methods("GET")
		api.HandleFunc("/profile/activity", s.profileHandler.GetActivityLogs).Methods("GET")
	}

	// Registry endpoints
	if s.registryHandler != nil {
		api.HandleFunc("/registry/agents/register", s.registryHandler.Register).Methods("POST")
		api.HandleFunc("/registry/agents/heartbeat", s.registryHandler.Heartbeat).Methods("POST")
		api.HandleFunc("/registry/agents/update-status", s.registryHandler.UpdateStatus).Methods("POST")
		api.HandleFunc("/registry/agents/unregister", s.registryHandler.Unregister).Methods("POST")
		api.HandleFunc("/registry/agents/available", s.registryHandler.ListAvailable).Methods("GET")
		api.HandleFunc("/registry/agents/{id}", s.registryHandler.Get).Methods("GET")
	}

	// Evolution endpoints
	if s.evolutionHandler != nil {
		api.HandleFunc("/evolution/run", s.evolutionHandler.Run).Methods("POST")
		api.HandleFunc("/evolution/leaderboard", s.evolutionHandler.Leaderboard).Methods("GET")
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
