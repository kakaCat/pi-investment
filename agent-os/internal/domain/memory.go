package domain

import (
	"errors"
	"time"

	"github.com/google/uuid"
)

// Common errors
var (
	ErrMemoryNotFound = errors.New("memory not found")
	ErrInvalidInput   = errors.New("invalid input")
)

// Memory represents a single memory entry
type Memory struct {
	ID             uuid.UUID      `json:"id"`
	NamespaceID    uuid.UUID      `json:"namespace_id"`
	Content        string         `json:"content"`
	Category       string         `json:"category"` // user, feedback, project, reference
	Importance     float64        `json:"importance"`
	Embedding      []float64      `json:"embedding,omitempty"` // Vector embedding
	CreatedAt      time.Time      `json:"created_at"`
	UpdatedAt      time.Time      `json:"updated_at"`
	AccessedCount  int            `json:"accessed_count"`
	LastAccessedAt *time.Time     `json:"last_accessed_at,omitempty"`
	Tags           []string       `json:"tags,omitempty"`
	Metadata       map[string]any `json:"metadata,omitempty"`
}

// SearchQuery represents a memory search query
type SearchQuery struct {
	Query         string    `json:"query"`
	NamespaceID   uuid.UUID `json:"namespace_id"`
	Categories    []string  `json:"categories,omitempty"`
	Tags          []string  `json:"tags,omitempty"`
	MinImportance float64   `json:"min_importance,omitempty"`
	Limit         int       `json:"limit"`
	Offset        int       `json:"offset"`
}

// SearchResult represents a memory search result with score
type SearchResult struct {
	Memory *Memory `json:"memory"`
	Score  float64 `json:"score"`  // Relevance score
	Source string  `json:"source"` // bm25, vector, or hybrid
}

// MemoryRepository defines the interface for memory data access
type MemoryRepository interface {
	// Write operations
	Create(memory *Memory) error
	Update(memory *Memory) error
	Delete(id uuid.UUID) error

	// Read operations
	GetByID(id uuid.UUID) (*Memory, error)
	List(namespaceID uuid.UUID, limit, offset int) ([]*Memory, error)

	// Search operations
	Search(query *SearchQuery) ([]*SearchResult, error)
	SearchBM25(query *SearchQuery) ([]*SearchResult, error)
	SearchVector(query *SearchQuery, embedding []float64) ([]*SearchResult, error)

	// Tag operations
	AddTags(memoryID uuid.UUID, tags []string) error
	RemoveTags(memoryID uuid.UUID, tags []string) error
	GetByTags(namespaceID uuid.UUID, tags []string, limit int) ([]*Memory, error)

	// Access tracking
	IncrementAccessCount(id uuid.UUID) error
}

// MemoryService defines the interface for memory business logic
type MemoryService interface {
	// Core operations
	Write(namespaceID uuid.UUID, content, category string, importance float64, tags []string, metadata map[string]any) (*Memory, error)
	Read(id uuid.UUID) (*Memory, error)
	Update(id uuid.UUID, content string, importance float64) error
	Delete(id uuid.UUID) error

	// Search operations
	Search(query *SearchQuery) ([]*SearchResult, error)
	SearchHybrid(query *SearchQuery) ([]*SearchResult, error) // BM25 + Vector hybrid search

	// List operations
	List(namespaceID uuid.UUID, limit, offset int) ([]*Memory, error)
	ListByCategory(namespaceID uuid.UUID, category string, limit int) ([]*Memory, error)
	ListByTags(namespaceID uuid.UUID, tags []string, limit int) ([]*Memory, error)

	// Tag operations
	AddTags(memoryID uuid.UUID, tags []string) error
	RemoveTags(memoryID uuid.UUID, tags []string) error
}

// EmbeddingService defines the interface for generating embeddings
type EmbeddingService interface {
	// Generate embedding vector from text
	Embed(text string) ([]float64, error)

	// Batch embedding
	EmbedBatch(texts []string) ([][]float64, error)
}
