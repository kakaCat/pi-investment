package api

import (
	"bytes"
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gorilla/mux"
	"github.com/pi-investment/agent-os/internal/domain"
)

// mockMemoryWebRepository 用于测试的 mock repository
type mockMemoryWebRepository struct {
	memories map[string]*domain.MemoryWeb
}

func newMockMemoryWebRepository() *mockMemoryWebRepository {
	return &mockMemoryWebRepository{
		memories: make(map[string]*domain.MemoryWeb),
	}
}

func (m *mockMemoryWebRepository) List(ctx context.Context, req domain.MemoryListRequest) ([]*domain.MemoryWeb, error) {
	var result []*domain.MemoryWeb
	for _, mem := range m.memories {
		result = append(result, mem)
	}
	return result, nil
}

func (m *mockMemoryWebRepository) Search(ctx context.Context, req domain.MemorySearchRequest) ([]*domain.MemoryWeb, error) {
	return []*domain.MemoryWeb{}, nil
}

func (m *mockMemoryWebRepository) Create(ctx context.Context, req domain.MemoryCreateRequest) (*domain.MemoryWeb, error) {
	mem := &domain.MemoryWeb{
		Title:   req.Title,
		Content: req.Content,
	}
	return mem, nil
}

func (m *mockMemoryWebRepository) Update(ctx context.Context, id string, req domain.MemoryUpdateRequest) (*domain.MemoryWeb, error) {
	mem, exists := m.memories[id]
	if !exists {
		mem = &domain.MemoryWeb{Title: "test", Content: "original"}
		m.memories[id] = mem
	}
	
	if req.Content != nil {
		mem.Content = *req.Content
	}
	
	return mem, nil
}

func (m *mockMemoryWebRepository) Delete(ctx context.Context, id string, req domain.MemoryDeleteRequest) error {
	delete(m.memories, id)
	return nil
}

func (m *mockMemoryWebRepository) GetTags(ctx context.Context) ([]*domain.Tag, error) {
	return []*domain.Tag{}, nil
}

func (m *mockMemoryWebRepository) CreateTag(ctx context.Context, name string) error {
	return nil
}

func (m *mockMemoryWebRepository) DeleteTag(ctx context.Context, name string) error {
	return nil
}

// TestMemoryUpdate 测试 PATCH /memory/{id}
func TestMemoryUpdate(t *testing.T) {
	repo := newMockMemoryWebRepository()
	handler := NewMemoryHandler(repo)
	
	router := mux.NewRouter()
	router.HandleFunc("/memory/{id}", handler.Update).Methods("PATCH")
	
	newContent := "updated content"
	reqBody := domain.MemoryUpdateRequest{
		Content: &newContent,
	}
	bodyBytes, _ := json.Marshal(reqBody)
	
	req := httptest.NewRequest("PATCH", "/memory/test-id", bytes.NewReader(bodyBytes))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	
	router.ServeHTTP(w, req)
	
	if w.Code != http.StatusOK {
		t.Errorf("Expected status 200, got %d: %s", w.Code, w.Body.String())
	}
	
	var resp map[string]interface{}
	json.NewDecoder(w.Body).Decode(&resp)
	
	if !resp["success"].(bool) {
		t.Error("Expected success=true")
	}
}

// TestMemoryDelete 测试 DELETE /memory/{id}
func TestMemoryDelete(t *testing.T) {
	repo := newMockMemoryWebRepository()
	handler := NewMemoryHandler(repo)
	
	router := mux.NewRouter()
	router.HandleFunc("/memory/{id}", handler.Delete).Methods("DELETE")
	
	reqBody := domain.MemoryDeleteRequest{
		Reason: "test deletion",
	}
	bodyBytes, _ := json.Marshal(reqBody)
	
	req := httptest.NewRequest("DELETE", "/memory/test-id", bytes.NewReader(bodyBytes))
	req.Header.Set("Content-Type", "application/json")
	w := httptest.NewRecorder()
	
	router.ServeHTTP(w, req)
	
	if w.Code != http.StatusOK {
		t.Errorf("Expected status 200, got %d: %s", w.Code, w.Body.String())
	}
	
	var resp map[string]interface{}
	json.NewDecoder(w.Body).Decode(&resp)
	
	if !resp["success"].(bool) {
		t.Error("Expected success=true")
	}
	
	if resp["message"].(string) != "memory deleted successfully" {
		t.Errorf("Expected success message, got %s", resp["message"])
	}
}

// TestMemoryListWithIncludeClosed 测试 include_closed 参数
func TestMemoryListWithIncludeClosed(t *testing.T) {
	repo := newMockMemoryWebRepository()
	handler := NewMemoryHandler(repo)
	
	router := mux.NewRouter()
	router.HandleFunc("/memory", handler.List).Methods("GET")
	
	// Test without include_closed (default false)
	req := httptest.NewRequest("GET", "/memory", nil)
	w := httptest.NewRecorder()
	router.ServeHTTP(w, req)
	
	if w.Code != http.StatusOK {
		t.Errorf("Expected status 200, got %d", w.Code)
	}
	
	// Test with include_closed=true
	req = httptest.NewRequest("GET", "/memory?include_closed=true", nil)
	w = httptest.NewRecorder()
	router.ServeHTTP(w, req)
	
	if w.Code != http.StatusOK {
		t.Errorf("Expected status 200, got %d", w.Code)
	}
}
