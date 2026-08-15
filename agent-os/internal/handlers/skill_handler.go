package handlers

import (
	"encoding/json"
	"net/http"

	"github.com/gorilla/mux"
	"github.com/pi-investment/agent-os/internal/services"
)

type SkillHandler struct {
	service *services.SkillService
}

func NewSkillHandler(service *services.SkillService) *SkillHandler {
	return &SkillHandler{service: service}
}

func (h *SkillHandler) RegisterRoutes(r *mux.Router) {
	r.HandleFunc("/skills", h.ListSkills).Methods("GET")
	r.HandleFunc("/skills/{id}", h.GetSkill).Methods("GET")
	r.HandleFunc("/skills", h.CreateSkill).Methods("POST")
	r.HandleFunc("/skills/{id}", h.UpdateSkill).Methods("PUT")
	r.HandleFunc("/skills/{id}", h.DeleteSkill).Methods("DELETE")
}

// GET /api/v1/skills
func (h *SkillHandler) ListSkills(w http.ResponseWriter, r *http.Request) {
	owner := r.URL.Query().Get("owner")
	status := r.URL.Query().Get("status")

	skills, err := h.service.ListSkills(r.Context(), owner, status)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"skills": skills,
	})
}

// GET /api/v1/skills/{id}
func (h *SkillHandler) GetSkill(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]

	skill, err := h.service.GetSkill(r.Context(), id)
	if err != nil {
		http.Error(w, err.Error(), http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(skill)
}

// POST /api/v1/skills
func (h *SkillHandler) CreateSkill(w http.ResponseWriter, r *http.Request) {
	var req struct {
		Name        string                 `json:"name"`
		Description string                 `json:"description"`
		Category    string                 `json:"category"`
		Owner       string                 `json:"owner"`
		Content     string                 `json:"content"`
		Author      string                 `json:"author"`
		Metadata    map[string]interface{} `json:"metadata"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	// Validate required fields
	if req.Name == "" || req.Owner == "" || req.Content == "" {
		http.Error(w, "name, owner, and content are required", http.StatusBadRequest)
		return
	}

	skill, err := h.service.CreateSkill(
		r.Context(),
		req.Name,
		req.Description,
		req.Category,
		req.Owner,
		req.Content,
		req.Author,
		req.Metadata,
	)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(skill)
}

// PUT /api/v1/skills/{id}
func (h *SkillHandler) UpdateSkill(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]

	var req struct {
		Content       string `json:"content"`
		Author        string `json:"author"`
		CommitMessage string `json:"commit_message"`
	}

	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}

	// Validate required fields
	if req.Content == "" {
		http.Error(w, "content is required", http.StatusBadRequest)
		return
	}

	version, err := h.service.UpdateSkill(r.Context(), id, req.Content, req.Author, req.CommitMessage)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(version)
}

// DELETE /api/v1/skills/{id}
func (h *SkillHandler) DeleteSkill(w http.ResponseWriter, r *http.Request) {
	vars := mux.Vars(r)
	id := vars["id"]

	if err := h.service.DeleteSkill(r.Context(), id); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"success": true,
		"message": "Skill deleted successfully",
	})
}
