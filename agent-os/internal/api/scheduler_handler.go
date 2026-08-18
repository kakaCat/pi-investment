package api

import (
	"encoding/json"
	"net/http"
	"strconv"
	"strings"

	"github.com/google/uuid"
	"github.com/gorilla/mux"
	"github.com/pi-investment/agent-os/internal/dto"
	"github.com/pi-investment/agent-os/internal/kernel/scheduler"
	"github.com/pi-investment/agent-os/internal/validator"
	"github.com/pi-investment/agent-os/pkg/types"
)

// SchedulerHandler handles scheduler HTTP requests
type SchedulerHandler struct {
	scheduler *scheduler.Scheduler
}

// NewSchedulerHandler creates a new scheduler handler
func NewSchedulerHandler(sched *scheduler.Scheduler) *SchedulerHandler {
	return &SchedulerHandler{
		scheduler: sched,
	}
}

// RegisterRoutes registers scheduler routes
func (h *SchedulerHandler) RegisterRoutes(router *mux.Router) {
	// Tasks - 注意：具体路径要在通配路径之前注册
	router.HandleFunc("/scheduler/tasks", h.handleRegisterTask).Methods("POST")
	router.HandleFunc("/scheduler/tasks", h.handleListTasks).Methods("GET")
	// Stats 必须在 /{id} 之前注册，否则 "stats" 会被当成 id
	router.HandleFunc("/scheduler/tasks/stats", h.handleGetTasksWithStats).Methods("GET")
	router.HandleFunc("/scheduler/tasks/{id}", h.handleGetTask).Methods("GET")
	router.HandleFunc("/scheduler/tasks/{id}", h.handleUpdateTask).Methods("PUT")
	router.HandleFunc("/scheduler/tasks/{id}", h.handleDeleteTask).Methods("DELETE")
	router.HandleFunc("/scheduler/tasks/{id}/trigger", h.handleTriggerTask).Methods("POST")
	router.HandleFunc("/scheduler/tasks/{id}/pause", h.handlePauseTask).Methods("POST")
	router.HandleFunc("/scheduler/tasks/{id}/resume", h.handleResumeTask).Methods("POST")

	// Executions (TaskRuns)
	router.HandleFunc("/scheduler/executions", h.handleListExecutions).Methods("GET")
	router.HandleFunc("/scheduler/executions/{id}", h.handleGetExecution).Methods("GET")
	router.HandleFunc("/scheduler/executions/{id}", h.handleUpdateExecution).Methods("PUT")
}

// handleRegisterTask registers a new task
// POST /api/v1/scheduler/tasks
func (h *SchedulerHandler) handleRegisterTask(w http.ResponseWriter, r *http.Request) {
	var req dto.CreateTaskRequest

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request body: "+err.Error())
		return
	}

	// Validate request
	if err := validator.Validate(&req); err != nil {
		respondError(w, http.StatusBadRequest, err.Error())
		return
	}

	// Create task
	task := &types.Task{
		ID:          uuid.New(),
		Name:        req.Name,
		Owner:       req.Owner,
		Description: req.Description,
		Cron:        req.Cron,
		Schedule:    req.Cron, // For backward compatibility
		WebhookURL:  req.WebhookURL,
		Payload:     req.Payload,
		Timeout:     req.Timeout,
		RetryCount:  req.RetryCount,
		Enabled:     req.Enabled,
	}

	// Set defaults
	if task.Timeout == 0 {
		task.Timeout = 3600 // 1 hour default
	}

	// Register task
	if err := h.scheduler.RegisterTask(r.Context(), task); err != nil {
		respondError(w, http.StatusInternalServerError, "failed to register task: "+err.Error())
		return
	}

	respondJSON(w, http.StatusCreated, task)
}

// handleListTasks lists all tasks
// GET /api/v1/scheduler/tasks?enabled_only=false
func (h *SchedulerHandler) handleListTasks(w http.ResponseWriter, r *http.Request) {
	enabledOnlyStr := r.URL.Query().Get("enabled_only")
	enabledOnly := enabledOnlyStr == "true"

	tasks, err := h.scheduler.ListTasks(r.Context(), enabledOnly)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to list tasks: "+err.Error())
		return
	}

	respondJSON(w, http.StatusOK, map[string]interface{}{
		"tasks": tasks,
		"count": len(tasks),
	})
}

// handleGetTask gets a task by ID
// GET /api/v1/scheduler/tasks/{id}
func (h *SchedulerHandler) handleGetTask(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	taskID, err := uuid.Parse(vars["id"])
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid task ID")
		return
	}

	task, err := h.scheduler.GetTask(r.Context(), taskID)
	if err != nil {
		respondError(w, http.StatusNotFound, "task not found")
		return
	}

	respondJSON(w, http.StatusOK, task)
}

// handleUpdateTask updates a task
// PUT /api/v1/scheduler/tasks/{id}
func (h *SchedulerHandler) handleUpdateTask(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	taskID, err := uuid.Parse(vars["id"])
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid task ID")
		return
	}

	// Get existing task
	existingTask, err := h.scheduler.GetTask(r.Context(), taskID)
	if err != nil {
		respondError(w, http.StatusNotFound, "task not found")
		return
	}

	// Decode update request
	var req struct {
		Name        *string                 `json:"name,omitempty"`
		Description *string                 `json:"description,omitempty"`
		Cron        *string                 `json:"cron,omitempty"`
		WebhookURL  *string                 `json:"webhook_url,omitempty"`
		Payload     *map[string]interface{} `json:"payload,omitempty"`
		Timeout     *int                    `json:"timeout,omitempty"`
		RetryCount  *int                    `json:"retry_count,omitempty"`
		Enabled     *bool                   `json:"enabled,omitempty"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request body: "+err.Error())
		return
	}

	// Apply updates
	if req.Name != nil {
		existingTask.Name = *req.Name
	}
	if req.Description != nil {
		existingTask.Description = *req.Description
	}
	if req.Cron != nil {
		existingTask.Cron = *req.Cron
		existingTask.Schedule = *req.Cron // Backward compat
	}
	if req.WebhookURL != nil {
		existingTask.WebhookURL = *req.WebhookURL
	}
	if req.Payload != nil {
		existingTask.Payload = *req.Payload
	}
	if req.Timeout != nil {
		existingTask.Timeout = *req.Timeout
	}
	if req.RetryCount != nil {
		existingTask.RetryCount = *req.RetryCount
	}
	if req.Enabled != nil {
		existingTask.Enabled = *req.Enabled
	}

	// Update task
	if err := h.scheduler.UpdateTask(r.Context(), existingTask); err != nil {
		respondError(w, http.StatusInternalServerError, "failed to update task: "+err.Error())
		return
	}

	respondJSON(w, http.StatusOK, existingTask)
}

// handleDeleteTask deletes a task
// DELETE /api/v1/scheduler/tasks/{id}
func (h *SchedulerHandler) handleDeleteTask(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	taskID, err := uuid.Parse(vars["id"])
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid task ID")
		return
	}

	if err := h.scheduler.DeleteTask(r.Context(), taskID); err != nil {
		respondError(w, http.StatusInternalServerError, "failed to delete task: "+err.Error())
		return
	}

	respondJSON(w, http.StatusOK, map[string]string{
		"message": "task deleted successfully",
	})
}

// handleTriggerTask manually triggers a task
// POST /api/v1/scheduler/tasks/{id}/trigger
func (h *SchedulerHandler) handleTriggerTask(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	taskID, err := uuid.Parse(vars["id"])
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid task ID")
		return
	}

	taskRun, err := h.scheduler.TriggerTask(r.Context(), taskID)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to trigger task: "+err.Error())
		return
	}

	respondJSON(w, http.StatusOK, taskRun)
}

// handlePauseTask pauses a task (disables it)
// POST /api/v1/scheduler/tasks/{id}/pause
func (h *SchedulerHandler) handlePauseTask(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	taskID, err := uuid.Parse(vars["id"])
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid task ID")
		return
	}

	task, err := h.scheduler.GetTask(r.Context(), taskID)
	if err != nil {
		respondError(w, http.StatusNotFound, "task not found")
		return
	}

	task.Enabled = false
	if err := h.scheduler.UpdateTask(r.Context(), task); err != nil {
		respondError(w, http.StatusInternalServerError, "failed to pause task: "+err.Error())
		return
	}

	respondJSON(w, http.StatusOK, map[string]string{
		"message": "task paused successfully",
	})
}

// handleResumeTask resumes a task (enables it)
// POST /api/v1/scheduler/tasks/{id}/resume
func (h *SchedulerHandler) handleResumeTask(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	taskID, err := uuid.Parse(vars["id"])
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid task ID")
		return
	}

	task, err := h.scheduler.GetTask(r.Context(), taskID)
	if err != nil {
		respondError(w, http.StatusNotFound, "task not found")
		return
	}

	task.Enabled = true
	if err := h.scheduler.UpdateTask(r.Context(), task); err != nil {
		respondError(w, http.StatusInternalServerError, "failed to resume task: "+err.Error())
		return
	}

	respondJSON(w, http.StatusOK, map[string]string{
		"message": "task resumed successfully",
	})
}

// handleListExecutions lists task executions
// GET /api/v1/scheduler/executions?task_id=xxx&limit=10
func (h *SchedulerHandler) handleListExecutions(w http.ResponseWriter, r *http.Request) {
	taskIDStr := r.URL.Query().Get("task_id")
	limitStr := r.URL.Query().Get("limit")

	limit := 100
	if limitStr != "" {
		if l, err := strconv.Atoi(limitStr); err == nil && l > 0 {
			limit = l
		}
	}

	if taskIDStr == "" {
		respondError(w, http.StatusBadRequest, "task_id is required")
		return
	}

	taskID, err := uuid.Parse(taskIDStr)
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid task_id")
		return
	}

	runs, err := h.scheduler.GetTaskRuns(r.Context(), taskID, limit)
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to list executions: "+err.Error())
		return
	}

	respondJSON(w, http.StatusOK, map[string]interface{}{
		"executions": runs,
		"count":      len(runs),
	})
}

// handleGetExecution gets a single execution by ID
// GET /api/v1/scheduler/executions/{id}
func (h *SchedulerHandler) handleGetExecution(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	executionID, err := uuid.Parse(vars["id"])
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid execution ID")
		return
	}

	run, err := h.scheduler.GetTaskRun(r.Context(), executionID)
	if err != nil {
		respondError(w, http.StatusNotFound, "execution not found: "+err.Error())
		return
	}

	respondJSON(w, http.StatusOK, run)
}

// handleUpdateExecution updates an execution status
// PUT /api/v1/scheduler/executions/{id}
func (h *SchedulerHandler) handleUpdateExecution(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	executionID, err := uuid.Parse(vars["id"])
	if err != nil {
		respondError(w, http.StatusBadRequest, "invalid execution ID")
		return
	}

	var req struct {
		Status string `json:"status"`
		Output string `json:"output,omitempty"`
		Error  string `json:"error,omitempty"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		respondError(w, http.StatusBadRequest, "invalid request body: "+err.Error())
		return
	}

	if req.Status == "" {
		respondError(w, http.StatusBadRequest, "status is required")
		return
	}

	run, err := h.scheduler.UpdateTaskRunResult(r.Context(), executionID, req.Status, req.Output, req.Error)
	if err != nil {
		if strings.Contains(err.Error(), "not found") {
			respondError(w, http.StatusNotFound, err.Error())
			return
		}
		if strings.Contains(err.Error(), "invalid status") {
			respondError(w, http.StatusBadRequest, err.Error())
			return
		}
		respondError(w, http.StatusInternalServerError, "failed to update execution: "+err.Error())
		return
	}

	respondJSON(w, http.StatusOK, run)
}

// handleGetTasksWithStats gets tasks with execution statistics
// GET /api/v1/scheduler/tasks/stats
func (h *SchedulerHandler) handleGetTasksWithStats(w http.ResponseWriter, r *http.Request) {
	tasksWithStats, err := h.scheduler.GetTasksWithStats(r.Context())
	if err != nil {
		respondError(w, http.StatusInternalServerError, "failed to get tasks with stats: "+err.Error())
		return
	}

	respondJSON(w, http.StatusOK, map[string]interface{}{
		"tasks": tasksWithStats,
		"count": len(tasksWithStats),
	})
}
