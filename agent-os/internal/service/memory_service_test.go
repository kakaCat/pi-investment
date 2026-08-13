package service_test

import (
	"testing"

	"github.com/google/uuid"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"

	"github.com/pi-investment/agent-os/internal/domain"
	"github.com/pi-investment/agent-os/internal/service"
)

// mockMemoryRepository is a simple in-memory implementation for testing
type mockMemoryRepository struct {
	memories map[uuid.UUID]*domain.Memory
	tags     map[uuid.UUID][]string
}

func newMockMemoryRepository() *mockMemoryRepository {
	return &mockMemoryRepository{
		memories: make(map[uuid.UUID]*domain.Memory),
		tags:     make(map[uuid.UUID][]string),
	}
}

func (m *mockMemoryRepository) Create(memory *domain.Memory) error {
	if memory.ID == uuid.Nil {
		memory.ID = uuid.New()
	}
	m.memories[memory.ID] = memory
	if len(memory.Tags) > 0 {
		m.tags[memory.ID] = memory.Tags
	}
	return nil
}

func (m *mockMemoryRepository) Update(memory *domain.Memory) error {
	m.memories[memory.ID] = memory
	return nil
}

func (m *mockMemoryRepository) Delete(id uuid.UUID) error {
	delete(m.memories, id)
	delete(m.tags, id)
	return nil
}

func (m *mockMemoryRepository) GetByID(id uuid.UUID) (*domain.Memory, error) {
	memory, ok := m.memories[id]
	if !ok {
		return nil, domain.ErrMemoryNotFound
	}
	if tags, ok := m.tags[id]; ok {
		memory.Tags = tags
	}
	return memory, nil
}

func (m *mockMemoryRepository) List(namespaceID uuid.UUID, limit, offset int) ([]*domain.Memory, error) {
	var result []*domain.Memory
	for _, mem := range m.memories {
		if mem.NamespaceID == namespaceID {
			result = append(result, mem)
		}
	}
	return result, nil
}

func (m *mockMemoryRepository) Search(query *domain.SearchQuery) ([]*domain.SearchResult, error) {
	return nil, nil
}

func (m *mockMemoryRepository) SearchBM25(query *domain.SearchQuery) ([]*domain.SearchResult, error) {
	var results []*domain.SearchResult
	for _, mem := range m.memories {
		if mem.NamespaceID == query.NamespaceID {
			results = append(results, &domain.SearchResult{
				Memory: mem,
				Score:  1.0,
				Source: "bm25",
			})
		}
	}
	return results, nil
}

func (m *mockMemoryRepository) SearchVector(query *domain.SearchQuery, embedding []float64) ([]*domain.SearchResult, error) {
	var results []*domain.SearchResult
	for _, mem := range m.memories {
		if mem.NamespaceID == query.NamespaceID && mem.Embedding != nil {
			results = append(results, &domain.SearchResult{
				Memory: mem,
				Score:  0.8,
				Source: "vector",
			})
		}
	}
	return results, nil
}

func (m *mockMemoryRepository) AddTags(memoryID uuid.UUID, tags []string) error {
	existing := m.tags[memoryID]
	m.tags[memoryID] = append(existing, tags...)
	return nil
}

func (m *mockMemoryRepository) RemoveTags(memoryID uuid.UUID, tags []string) error {
	existing := m.tags[memoryID]
	var filtered []string
	for _, t := range existing {
		remove := false
		for _, rt := range tags {
			if t == rt {
				remove = true
				break
			}
		}
		if !remove {
			filtered = append(filtered, t)
		}
	}
	m.tags[memoryID] = filtered
	return nil
}

func (m *mockMemoryRepository) GetByTags(namespaceID uuid.UUID, tags []string, limit int) ([]*domain.Memory, error) {
	return nil, nil
}

func (m *mockMemoryRepository) IncrementAccessCount(id uuid.UUID) error {
	if mem, ok := m.memories[id]; ok {
		mem.AccessedCount++
	}
	return nil
}

func TestMemoryService_Write(t *testing.T) {
	repo := newMockMemoryRepository()
	embedding := service.NewMockEmbeddingService()
	svc := service.NewMemoryService(repo, embedding)

	namespaceID := uuid.New()

	tests := []struct {
		name        string
		content     string
		category    string
		importance  float64
		tags        []string
		metadata    map[string]any
		expectError bool
	}{
		{
			name:        "valid memory",
			content:     "Test memory content",
			category:    "project",
			importance:  0.8,
			tags:        []string{"test", "example"},
			metadata:    map[string]any{"source": "test"},
			expectError: false,
		},
		{
			name:        "empty content",
			content:     "",
			category:    "project",
			importance:  0.5,
			expectError: true,
		},
		{
			name:        "invalid importance (too high)",
			content:     "Test",
			category:    "project",
			importance:  1.5,
			expectError: true,
		},
		{
			name:        "invalid importance (negative)",
			content:     "Test",
			category:    "project",
			importance:  -0.1,
			expectError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			memory, err := svc.Write(namespaceID, tt.content, tt.category, tt.importance, tt.tags, tt.metadata)

			if tt.expectError {
				assert.Error(t, err)
				assert.Nil(t, memory)
			} else {
				require.NoError(t, err)
				require.NotNil(t, memory)
				assert.NotEqual(t, uuid.Nil, memory.ID)
				assert.Equal(t, namespaceID, memory.NamespaceID)
				assert.Equal(t, tt.content, memory.Content)
				assert.Equal(t, tt.category, memory.Category)
				assert.Equal(t, tt.importance, memory.Importance)
				assert.Equal(t, tt.tags, memory.Tags)
				assert.NotNil(t, memory.Embedding) // Mock embedding service generates embeddings
			}
		})
	}
}

func TestMemoryService_Read(t *testing.T) {
	repo := newMockMemoryRepository()
	embedding := service.NewMockEmbeddingService()
	svc := service.NewMemoryService(repo, embedding)

	namespaceID := uuid.New()

	// Create a memory
	memory, err := svc.Write(namespaceID, "Test content", "project", 0.7, []string{"test"}, nil)
	require.NoError(t, err)

	// Read it back
	retrieved, err := svc.Read(memory.ID)
	require.NoError(t, err)
	assert.Equal(t, memory.ID, retrieved.ID)
	assert.Equal(t, memory.Content, retrieved.Content)

	// Read non-existent memory
	_, err = svc.Read(uuid.New())
	assert.Error(t, err)
}

func TestMemoryService_Update(t *testing.T) {
	repo := newMockMemoryRepository()
	embedding := service.NewMockEmbeddingService()
	svc := service.NewMemoryService(repo, embedding)

	namespaceID := uuid.New()

	// Create a memory
	memory, err := svc.Write(namespaceID, "Original content", "project", 0.5, nil, nil)
	require.NoError(t, err)

	// Update it
	err = svc.Update(memory.ID, "Updated content", 0.9)
	require.NoError(t, err)

	// Verify update
	updated, err := svc.Read(memory.ID)
	require.NoError(t, err)
	assert.Equal(t, "Updated content", updated.Content)
	assert.Equal(t, 0.9, updated.Importance)
}

func TestMemoryService_Delete(t *testing.T) {
	repo := newMockMemoryRepository()
	embedding := service.NewMockEmbeddingService()
	svc := service.NewMemoryService(repo, embedding)

	namespaceID := uuid.New()

	// Create a memory
	memory, err := svc.Write(namespaceID, "Test content", "project", 0.5, nil, nil)
	require.NoError(t, err)

	// Delete it
	err = svc.Delete(memory.ID)
	require.NoError(t, err)

	// Verify deletion
	_, err = svc.Read(memory.ID)
	assert.Error(t, err)
}

func TestMemoryService_Search(t *testing.T) {
	repo := newMockMemoryRepository()
	embedding := service.NewMockEmbeddingService()
	svc := service.NewMemoryService(repo, embedding)

	namespaceID := uuid.New()

	// Create some test memories
	_, err := svc.Write(namespaceID, "Machine learning basics", "project", 0.8, []string{"ml", "ai"}, nil)
	require.NoError(t, err)

	_, err = svc.Write(namespaceID, "Python programming guide", "reference", 0.6, []string{"python", "code"}, nil)
	require.NoError(t, err)

	// Search
	query := &domain.SearchQuery{
		Query:       "machine learning",
		NamespaceID: namespaceID,
		Limit:       10,
	}

	results, err := svc.Search(query)
	require.NoError(t, err)
	assert.NotEmpty(t, results)
}

func TestMemoryService_Tags(t *testing.T) {
	repo := newMockMemoryRepository()
	embedding := service.NewMockEmbeddingService()
	svc := service.NewMemoryService(repo, embedding)

	namespaceID := uuid.New()

	// Create a memory
	memory, err := svc.Write(namespaceID, "Test content", "project", 0.5, []string{"initial"}, nil)
	require.NoError(t, err)

	// Add tags
	err = svc.AddTags(memory.ID, []string{"tag1", "tag2"})
	require.NoError(t, err)

	// Verify tags were added
	retrieved, err := svc.Read(memory.ID)
	require.NoError(t, err)
	_ = retrieved // Use the variable
	assert.Contains(t, repo.tags[memory.ID], "tag1")
	assert.Contains(t, repo.tags[memory.ID], "tag2")

	// Remove a tag
	err = svc.RemoveTags(memory.ID, []string{"tag1"})
	require.NoError(t, err)

	// Verify tag was removed
	assert.NotContains(t, repo.tags[memory.ID], "tag1")
	assert.Contains(t, repo.tags[memory.ID], "tag2")
}

func TestMockEmbeddingService(t *testing.T) {
	svc := service.NewMockEmbeddingService()

	// Test single embedding
	embedding, err := svc.Embed("test text")
	require.NoError(t, err)
	assert.NotNil(t, embedding)
	assert.Equal(t, 384, len(embedding)) // Standard embedding size

	// Test batch embedding
	texts := []string{"text1", "text2", "text3"}
	embeddings, err := svc.EmbedBatch(texts)
	require.NoError(t, err)
	assert.Equal(t, 3, len(embeddings))
	for _, emb := range embeddings {
		assert.Equal(t, 384, len(emb))
	}

	// Test deterministic property
	embedding1, _ := svc.Embed("same text")
	embedding2, _ := svc.Embed("same text")
	assert.Equal(t, embedding1, embedding2)

	// Test different inputs produce different embeddings
	embedding3, _ := svc.Embed("different text")
	assert.NotEqual(t, embedding1, embedding3)
}
