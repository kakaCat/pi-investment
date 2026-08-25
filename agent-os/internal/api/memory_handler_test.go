package api

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/google/uuid"
	"github.com/gorilla/mux"
	"github.com/pi-investment/agent-os/internal/domain"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"
	"github.com/stretchr/testify/require"
)

// MockMemoryWebRepository is a mock for MemoryWebRepository
type MockMemoryWebRepository struct {
	mock.Mock
}

func (m *MockMemoryWebRepository) List(ctx context.Context, req domain.MemoryListRequest) ([]*domain.MemoryWeb, error) {
	args := m.Called(ctx, req)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]*domain.MemoryWeb), args.Error(1)
}

func (m *MockMemoryWebRepository) Search(ctx context.Context, req domain.MemorySearchRequest) ([]*domain.MemoryWeb, error) {
	args := m.Called(ctx, req)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]*domain.MemoryWeb), args.Error(1)
}

func (m *MockMemoryWebRepository) Create(ctx context.Context, req domain.MemoryCreateRequest) (*domain.MemoryWeb, error) {
	args := m.Called(ctx, req)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(*domain.MemoryWeb), args.Error(1)
}

func (m *MockMemoryWebRepository) GetTags(ctx context.Context) ([]*domain.Tag, error) {
	args := m.Called(ctx)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]*domain.Tag), args.Error(1)
}

func (m *MockMemoryWebRepository) CreateTag(ctx context.Context, name string) error {
	args := m.Called(ctx, name)
	return args.Error(0)
}

func (m *MockMemoryWebRepository) DeleteTag(ctx context.Context, name string) error {
	args := m.Called(ctx, name)
	return args.Error(0)
}

func (m *MockMemoryWebRepository) Update(ctx context.Context, id string, req domain.MemoryUpdateRequest) (*domain.MemoryWeb, error) {
	args := m.Called(ctx, id, req)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(*domain.MemoryWeb), args.Error(1)
}

func (m *MockMemoryWebRepository) Delete(ctx context.Context, id string, req domain.MemoryDeleteRequest) error {
	args := m.Called(ctx, id, req)
	return args.Error(0)
}

func TestMemoryHandler_List(t *testing.T) {
	tests := []struct {
		name           string
		queryParams    string
		mockReturn     []*domain.MemoryWeb
		mockError      error
		expectedStatus int
		checkResponse  func(t *testing.T, resp *http.Response)
	}{
		{
			name:        "success - list all memories",
			queryParams: "",
			mockReturn: []*domain.MemoryWeb{
				{ID: uuid.New(), Title: "Memory 1", Content: "Content 1", Category: "knowledge"},
				{ID: uuid.New(), Title: "Memory 2", Content: "Content 2", Category: "experience"},
			},
			mockError:      nil,
			expectedStatus: http.StatusOK,
			checkResponse: func(t *testing.T, resp *http.Response) {
				var result map[string]interface{}
				require.NoError(t, json.NewDecoder(resp.Body).Decode(&result))
				assert.Equal(t, float64(2), result["total"])
				memories := result["memories"].([]interface{})
				assert.Len(t, memories, 2)
			},
		},
		{
			name:           "success - filter by category",
			queryParams:    "?category=knowledge",
			mockReturn:     []*domain.MemoryWeb{{ID: uuid.New(), Category: "knowledge"}},
			mockError:      nil,
			expectedStatus: http.StatusOK,
			checkResponse: func(t *testing.T, resp *http.Response) {
				var result map[string]interface{}
				require.NoError(t, json.NewDecoder(resp.Body).Decode(&result))
				assert.Equal(t, float64(1), result["total"])
			},
		},
		{
			name:           "success - with limit",
			queryParams:    "?limit=10",
			mockReturn:     []*domain.MemoryWeb{},
			mockError:      nil,
			expectedStatus: http.StatusOK,
			checkResponse:  func(t *testing.T, resp *http.Response) {},
		},
		{
			name:           "error - repository fails",
			queryParams:    "",
			mockReturn:     nil,
			mockError:      errors.New("database error"),
			expectedStatus: http.StatusInternalServerError,
			checkResponse: func(t *testing.T, resp *http.Response) {
				var result map[string]interface{}
				require.NoError(t, json.NewDecoder(resp.Body).Decode(&result))
				assert.Contains(t, result["message"], "failed to get memories")
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			mockRepo := new(MockMemoryWebRepository)
			mockRepo.On("List", mock.Anything, mock.Anything).Return(tt.mockReturn, tt.mockError)

			handler := NewMemoryHandler(mockRepo)

			req := httptest.NewRequest(http.MethodGet, "/api/v1/memory"+tt.queryParams, nil)
			w := httptest.NewRecorder()

			handler.List(w, req)

			assert.Equal(t, tt.expectedStatus, w.Code)
			tt.checkResponse(t, w.Result())
			mockRepo.AssertExpectations(t)
		})
	}
}

func TestMemoryHandler_Search(t *testing.T) {
	tests := []struct {
		name           string
		queryParams    string
		mockReturn     []*domain.MemoryWeb
		mockError      error
		expectedStatus int
		checkResponse  func(t *testing.T, resp *http.Response)
	}{
		{
			name:        "success - search with query",
			queryParams: "?q=test",
			mockReturn: []*domain.MemoryWeb{
				{ID: uuid.New(), Title: "Test Memory", Content: "Test content"},
			},
			mockError:      nil,
			expectedStatus: http.StatusOK,
			checkResponse: func(t *testing.T, resp *http.Response) {
				var result map[string]interface{}
				require.NoError(t, json.NewDecoder(resp.Body).Decode(&result))
				assert.Equal(t, float64(1), result["total"])
			},
		},
		{
			name:           "error - missing query parameter",
			queryParams:    "",
			mockReturn:     nil,
			mockError:      nil,
			expectedStatus: http.StatusBadRequest,
			checkResponse: func(t *testing.T, resp *http.Response) {
				var result map[string]interface{}
				require.NoError(t, json.NewDecoder(resp.Body).Decode(&result))
				assert.Contains(t, result["message"], "query parameter 'q' is required")
			},
		},
		{
			name:           "error - search fails",
			queryParams:    "?q=test",
			mockReturn:     nil,
			mockError:      errors.New("search error"),
			expectedStatus: http.StatusInternalServerError,
			checkResponse: func(t *testing.T, resp *http.Response) {
				var result map[string]interface{}
				require.NoError(t, json.NewDecoder(resp.Body).Decode(&result))
				assert.Contains(t, result["message"], "failed to search memories")
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			mockRepo := new(MockMemoryWebRepository)
			if tt.queryParams != "" {
				mockRepo.On("Search", mock.Anything, mock.Anything).Return(tt.mockReturn, tt.mockError)
			}

			handler := NewMemoryHandler(mockRepo)

			req := httptest.NewRequest(http.MethodGet, "/api/v1/memory/search"+tt.queryParams, nil)
			w := httptest.NewRecorder()

			handler.Search(w, req)

			assert.Equal(t, tt.expectedStatus, w.Code)
			tt.checkResponse(t, w.Result())

			if tt.queryParams != "" {
				mockRepo.AssertExpectations(t)
			}
		})
	}
}

func TestMemoryHandler_Create(t *testing.T) {
	tests := []struct {
		name           string
		requestBody    interface{}
		mockReturn     *domain.MemoryWeb
		mockError      error
		expectedStatus int
		checkResponse  func(t *testing.T, resp *http.Response)
	}{
		{
			name: "success - create memory",
			requestBody: domain.MemoryCreateRequest{
				Title:    "New Memory",
				Content:  "Memory content",
				Category: "knowledge",
			},
			mockReturn: &domain.MemoryWeb{
				ID:       uuid.New(),
				Title:    "New Memory",
				Content:  "Memory content",
				Category: "knowledge",
			},
			mockError:      nil,
			expectedStatus: http.StatusCreated,
			checkResponse: func(t *testing.T, resp *http.Response) {
				var result map[string]interface{}
				require.NoError(t, json.NewDecoder(resp.Body).Decode(&result))
				assert.True(t, result["success"].(bool))
				assert.NotNil(t, result["memory"])
			},
		},
		{
			name: "success - default category",
			requestBody: domain.MemoryCreateRequest{
				Content: "Memory content",
			},
			mockReturn: &domain.MemoryWeb{
				ID:       uuid.New(),
				Content:  "Memory content",
				Category: "knowledge",
			},
			mockError:      nil,
			expectedStatus: http.StatusCreated,
			checkResponse:  func(t *testing.T, resp *http.Response) {},
		},
		{
			name: "error - empty content",
			requestBody: domain.MemoryCreateRequest{
				Title: "No content",
			},
			mockReturn:     nil,
			mockError:      nil,
			expectedStatus: http.StatusBadRequest,
			checkResponse: func(t *testing.T, resp *http.Response) {
				var result map[string]interface{}
				require.NoError(t, json.NewDecoder(resp.Body).Decode(&result))
				assert.Contains(t, result["message"], "content is required")
			},
		},
		{
			name: "error - invalid category",
			requestBody: domain.MemoryCreateRequest{
				Content:  "Memory content",
				Category: "invalid",
			},
			mockReturn:     nil,
			mockError:      nil,
			expectedStatus: http.StatusBadRequest,
			checkResponse: func(t *testing.T, resp *http.Response) {
				var result map[string]interface{}
				require.NoError(t, json.NewDecoder(resp.Body).Decode(&result))
				assert.Contains(t, result["message"], "invalid category")
			},
		},
		{
			name:           "error - invalid JSON",
			requestBody:    "invalid json",
			mockReturn:     nil,
			mockError:      nil,
			expectedStatus: http.StatusBadRequest,
			checkResponse: func(t *testing.T, resp *http.Response) {
				var result map[string]interface{}
				require.NoError(t, json.NewDecoder(resp.Body).Decode(&result))
				assert.Contains(t, result["message"], "invalid request body")
			},
		},
		{
			name: "error - repository fails",
			requestBody: domain.MemoryCreateRequest{
				Content:  "Memory content",
				Category: "knowledge",
			},
			mockReturn:     nil,
			mockError:      errors.New("database error"),
			expectedStatus: http.StatusInternalServerError,
			checkResponse: func(t *testing.T, resp *http.Response) {
				var result map[string]interface{}
				require.NoError(t, json.NewDecoder(resp.Body).Decode(&result))
				assert.Contains(t, result["message"], "failed to create memory")
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			mockRepo := new(MockMemoryWebRepository)

			// Only set mock expectation if we expect the repo to be called
			if tt.expectedStatus == http.StatusCreated || tt.expectedStatus == http.StatusInternalServerError {
				mockRepo.On("Create", mock.Anything, mock.Anything).Return(tt.mockReturn, tt.mockError)
			}

			handler := NewMemoryHandler(mockRepo)

			var body []byte
			if str, ok := tt.requestBody.(string); ok {
				body = []byte(str)
			} else {
				body, _ = json.Marshal(tt.requestBody)
			}

			req := httptest.NewRequest(http.MethodPost, "/api/v1/memory", bytes.NewReader(body))
			req.Header.Set("Content-Type", "application/json")
			w := httptest.NewRecorder()

			handler.Create(w, req)

			assert.Equal(t, tt.expectedStatus, w.Code)
			tt.checkResponse(t, w.Result())

			if tt.expectedStatus == http.StatusCreated || tt.expectedStatus == http.StatusInternalServerError {
				mockRepo.AssertExpectations(t)
			}
		})
	}
}

func TestMemoryHandler_GetTags(t *testing.T) {
	tests := []struct {
		name           string
		mockReturn     []*domain.Tag
		mockError      error
		expectedStatus int
		checkResponse  func(t *testing.T, resp *http.Response)
	}{
		{
			name:           "success - get tags",
			mockReturn:     []*domain.Tag{{Name: "tag1"}, {Name: "tag2"}, {Name: "tag3"}},
			mockError:      nil,
			expectedStatus: http.StatusOK,
			checkResponse: func(t *testing.T, resp *http.Response) {
				var result map[string]interface{}
				require.NoError(t, json.NewDecoder(resp.Body).Decode(&result))
				tags := result["tags"].([]interface{})
				assert.Len(t, tags, 3)
			},
		},
		{
			name:           "error - repository fails",
			mockReturn:     nil,
			mockError:      errors.New("database error"),
			expectedStatus: http.StatusInternalServerError,
			checkResponse: func(t *testing.T, resp *http.Response) {
				var result map[string]interface{}
				require.NoError(t, json.NewDecoder(resp.Body).Decode(&result))
				assert.Contains(t, result["message"], "failed to get tags")
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			mockRepo := new(MockMemoryWebRepository)
			mockRepo.On("GetTags", mock.Anything).Return(tt.mockReturn, tt.mockError)

			handler := NewMemoryHandler(mockRepo)

			req := httptest.NewRequest(http.MethodGet, "/api/v1/memory/tags", nil)
			w := httptest.NewRecorder()

			handler.GetTags(w, req)

			assert.Equal(t, tt.expectedStatus, w.Code)
			tt.checkResponse(t, w.Result())
			mockRepo.AssertExpectations(t)
		})
	}
}

func TestMemoryHandler_CreateTag(t *testing.T) {
	tests := []struct {
		name           string
		requestBody    interface{}
		mockError      error
		expectedStatus int
		checkResponse  func(t *testing.T, resp *http.Response)
	}{
		{
			name: "success - create tag",
			requestBody: map[string]string{
				"name": "new-tag",
			},
			mockError:      nil,
			expectedStatus: http.StatusOK,
			checkResponse: func(t *testing.T, resp *http.Response) {
				var result map[string]interface{}
				require.NoError(t, json.NewDecoder(resp.Body).Decode(&result))
				assert.True(t, result["success"].(bool))
			},
		},
		{
			name: "error - empty tag name",
			requestBody: map[string]string{
				"name": "",
			},
			mockError:      nil,
			expectedStatus: http.StatusBadRequest,
			checkResponse: func(t *testing.T, resp *http.Response) {
				var result map[string]interface{}
				require.NoError(t, json.NewDecoder(resp.Body).Decode(&result))
				assert.Contains(t, result["message"], "tag name is required")
			},
		},
		{
			name:           "error - invalid JSON",
			requestBody:    "invalid",
			mockError:      nil,
			expectedStatus: http.StatusBadRequest,
			checkResponse: func(t *testing.T, resp *http.Response) {
				var result map[string]interface{}
				require.NoError(t, json.NewDecoder(resp.Body).Decode(&result))
				assert.Contains(t, result["message"], "invalid request body")
			},
		},
		{
			name: "error - repository fails",
			requestBody: map[string]string{
				"name": "new-tag",
			},
			mockError:      errors.New("database error"),
			expectedStatus: http.StatusInternalServerError,
			checkResponse: func(t *testing.T, resp *http.Response) {
				var result map[string]interface{}
				require.NoError(t, json.NewDecoder(resp.Body).Decode(&result))
				assert.Contains(t, result["message"], "failed to create tag")
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			mockRepo := new(MockMemoryWebRepository)

			if tt.expectedStatus == http.StatusOK || tt.expectedStatus == http.StatusInternalServerError {
				mockRepo.On("CreateTag", mock.Anything, mock.Anything).Return(tt.mockError)
			}

			handler := NewMemoryHandler(mockRepo)

			var body []byte
			if str, ok := tt.requestBody.(string); ok {
				body = []byte(str)
			} else {
				body, _ = json.Marshal(tt.requestBody)
			}

			req := httptest.NewRequest(http.MethodPost, "/api/v1/memory/tags", bytes.NewReader(body))
			req.Header.Set("Content-Type", "application/json")
			w := httptest.NewRecorder()

			handler.CreateTag(w, req)

			assert.Equal(t, tt.expectedStatus, w.Code)
			tt.checkResponse(t, w.Result())

			if tt.expectedStatus == http.StatusOK || tt.expectedStatus == http.StatusInternalServerError {
				mockRepo.AssertExpectations(t)
			}
		})
	}
}

func TestMemoryHandler_DeleteTag(t *testing.T) {
	tests := []struct {
		name           string
		tagName        string
		mockError      error
		expectedStatus int
		checkResponse  func(t *testing.T, resp *http.Response)
	}{
		{
			name:           "success - delete tag",
			tagName:        "tag-to-delete",
			mockError:      nil,
			expectedStatus: http.StatusOK,
			checkResponse: func(t *testing.T, resp *http.Response) {
				var result map[string]interface{}
				require.NoError(t, json.NewDecoder(resp.Body).Decode(&result))
				assert.True(t, result["success"].(bool))
			},
		},
		{
			name:           "error - empty tag name",
			tagName:        "",
			mockError:      nil,
			expectedStatus: http.StatusBadRequest,
			checkResponse: func(t *testing.T, resp *http.Response) {
				var result map[string]interface{}
				require.NoError(t, json.NewDecoder(resp.Body).Decode(&result))
				assert.Contains(t, result["message"], "tag name is required")
			},
		},
		{
			name:           "error - repository fails",
			tagName:        "tag-to-delete",
			mockError:      errors.New("database error"),
			expectedStatus: http.StatusInternalServerError,
			checkResponse: func(t *testing.T, resp *http.Response) {
				var result map[string]interface{}
				require.NoError(t, json.NewDecoder(resp.Body).Decode(&result))
				assert.Contains(t, result["message"], "failed to delete tag")
			},
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			mockRepo := new(MockMemoryWebRepository)

			if tt.expectedStatus == http.StatusOK || tt.expectedStatus == http.StatusInternalServerError {
				mockRepo.On("DeleteTag", mock.Anything, tt.tagName).Return(tt.mockError)
			}

			handler := NewMemoryHandler(mockRepo)

			req := httptest.NewRequest(http.MethodDelete, "/api/v1/memory/tags/"+tt.tagName, nil)
			req = mux.SetURLVars(req, map[string]string{"name": tt.tagName})
			w := httptest.NewRecorder()

			handler.DeleteTag(w, req)

			assert.Equal(t, tt.expectedStatus, w.Code)
			tt.checkResponse(t, w.Result())

			if tt.expectedStatus == http.StatusOK || tt.expectedStatus == http.StatusInternalServerError {
				mockRepo.AssertExpectations(t)
			}
		})
	}
}
