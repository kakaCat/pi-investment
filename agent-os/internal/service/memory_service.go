package service

import (
	"fmt"
	"math"

	"github.com/google/uuid"

	"github.com/pi-investment/agent-os/internal/domain"
)

type memoryService struct {
	repo      domain.MemoryRepository
	embedding domain.EmbeddingService
}

// NewMemoryService creates a new memory service
func NewMemoryService(repo domain.MemoryRepository, embedding domain.EmbeddingService) domain.MemoryService {
	return &memoryService{
		repo:      repo,
		embedding: embedding,
	}
}

// Write creates a new memory
func (s *memoryService) Write(namespaceID uuid.UUID, content, category string, importance float64, tags []string, metadata map[string]any) (*domain.Memory, error) {
	// Validate inputs
	if content == "" {
		return nil, fmt.Errorf("content cannot be empty")
	}

	if importance < 0 || importance > 1 {
		return nil, fmt.Errorf("importance must be between 0 and 1")
	}

	// Generate embedding
	var embedding []float64
	var err error
	if s.embedding != nil {
		embedding, err = s.embedding.Embed(content)
		if err != nil {
			// Log warning but don't fail - embeddings are optional
			fmt.Printf("Warning: failed to generate embedding: %v\n", err)
		}
	}

	// Create memory object
	memory := &domain.Memory{
		NamespaceID: namespaceID,
		Content:     content,
		Category:    category,
		Importance:  importance,
		Embedding:   embedding,
		Tags:        tags,
		Metadata:    metadata,
	}

	// Save to repository
	if err := s.repo.Create(memory); err != nil {
		return nil, fmt.Errorf("failed to create memory: %w", err)
	}

	return memory, nil
}

// Read retrieves a memory by ID and increments access count
func (s *memoryService) Read(id uuid.UUID) (*domain.Memory, error) {
	memory, err := s.repo.GetByID(id)
	if err != nil {
		return nil, err
	}

	// Increment access count asynchronously
	go s.repo.IncrementAccessCount(id)

	return memory, nil
}

// Update updates a memory's content and importance
func (s *memoryService) Update(id uuid.UUID, content string, importance float64) error {
	// Get existing memory
	memory, err := s.repo.GetByID(id)
	if err != nil {
		return err
	}

	// Update fields
	if content != "" {
		memory.Content = content

		// Regenerate embedding if content changed
		if s.embedding != nil {
			embedding, err := s.embedding.Embed(content)
			if err != nil {
				fmt.Printf("Warning: failed to regenerate embedding: %v\n", err)
			} else {
				memory.Embedding = embedding
			}
		}
	}

	if importance >= 0 && importance <= 1 {
		memory.Importance = importance
	}

	// Save to repository
	return s.repo.Update(memory)
}

// Delete removes a memory
func (s *memoryService) Delete(id uuid.UUID) error {
	return s.repo.Delete(id)
}

// Search performs a search based on the query
func (s *memoryService) Search(query *domain.SearchQuery) ([]*domain.SearchResult, error) {
	// Use BM25 for text search
	return s.repo.SearchBM25(query)
}

// SearchHybrid performs hybrid search (BM25 + Vector)
func (s *memoryService) SearchHybrid(query *domain.SearchQuery) ([]*domain.SearchResult, error) {
	// Get BM25 results
	bm25Results, err := s.repo.SearchBM25(query)
	if err != nil {
		return nil, fmt.Errorf("BM25 search failed: %w", err)
	}

	// If no embedding service, return BM25 results only
	if s.embedding == nil {
		return bm25Results, nil
	}

	// Generate embedding for query
	queryEmbedding, err := s.embedding.Embed(query.Query)
	if err != nil {
		// Fall back to BM25 only
		fmt.Printf("Warning: failed to generate query embedding: %v\n", err)
		return bm25Results, nil
	}

	// Get vector results
	vectorResults, err := s.repo.SearchVector(query, queryEmbedding)
	if err != nil {
		// Fall back to BM25 only
		fmt.Printf("Warning: vector search failed: %v\n", err)
		return bm25Results, nil
	}

	// Merge results using Reciprocal Rank Fusion (RRF)
	merged := mergeSearchResults(bm25Results, vectorResults)

	// Apply limit
	if query.Limit > 0 && len(merged) > query.Limit {
		merged = merged[:query.Limit]
	}

	return merged, nil
}

// List retrieves memories for a namespace
func (s *memoryService) List(namespaceID uuid.UUID, limit, offset int) ([]*domain.Memory, error) {
	return s.repo.List(namespaceID, limit, offset)
}

// ListByCategory retrieves memories by category
func (s *memoryService) ListByCategory(namespaceID uuid.UUID, category string, limit int) ([]*domain.Memory, error) {
	query := &domain.SearchQuery{
		NamespaceID: namespaceID,
		Categories:  []string{category},
		Limit:       limit,
		Offset:      0,
	}

	results, err := s.repo.Search(query)
	if err != nil {
		return nil, err
	}

	memories := make([]*domain.Memory, len(results))
	for i, result := range results {
		memories[i] = result.Memory
	}

	return memories, nil
}

// ListByTags retrieves memories by tags
func (s *memoryService) ListByTags(namespaceID uuid.UUID, tags []string, limit int) ([]*domain.Memory, error) {
	return s.repo.GetByTags(namespaceID, tags, limit)
}

// AddTags adds tags to a memory
func (s *memoryService) AddTags(memoryID uuid.UUID, tags []string) error {
	return s.repo.AddTags(memoryID, tags)
}

// RemoveTags removes tags from a memory
func (s *memoryService) RemoveTags(memoryID uuid.UUID, tags []string) error {
	return s.repo.RemoveTags(memoryID, tags)
}

// mergeSearchResults merges BM25 and vector search results using RRF
func mergeSearchResults(bm25Results, vectorResults []*domain.SearchResult) []*domain.SearchResult {
	k := 60.0 // RRF constant

	// Build rank maps
	bm25Ranks := make(map[uuid.UUID]int)
	vectorRanks := make(map[uuid.UUID]int)

	for i, result := range bm25Results {
		bm25Ranks[result.Memory.ID] = i + 1
	}

	for i, result := range vectorResults {
		vectorRanks[result.Memory.ID] = i + 1
	}

	// Build combined result set
	resultMap := make(map[uuid.UUID]*domain.SearchResult)

	// Add all BM25 results
	for _, result := range bm25Results {
		resultMap[result.Memory.ID] = &domain.SearchResult{
			Memory: result.Memory,
			Score:  0,
			Source: "hybrid",
		}
	}

	// Add all vector results
	for _, result := range vectorResults {
		if _, exists := resultMap[result.Memory.ID]; !exists {
			resultMap[result.Memory.ID] = &domain.SearchResult{
				Memory: result.Memory,
				Score:  0,
				Source: "hybrid",
			}
		}
	}

	// Compute RRF scores
	for id, result := range resultMap {
		score := 0.0

		if rank, ok := bm25Ranks[id]; ok {
			score += 1.0 / (k + float64(rank))
		}

		if rank, ok := vectorRanks[id]; ok {
			score += 1.0 / (k + float64(rank))
		}

		result.Score = score
	}

	// Convert to slice and sort by score
	var merged []*domain.SearchResult
	for _, result := range resultMap {
		merged = append(merged, result)
	}

	// Sort by score descending
	for i := 0; i < len(merged)-1; i++ {
		for j := i + 1; j < len(merged); j++ {
			if merged[i].Score < merged[j].Score {
				merged[i], merged[j] = merged[j], merged[i]
			}
		}
	}

	return merged
}

// mockEmbeddingService is a simple mock for testing without real embeddings
type mockEmbeddingService struct{}

func NewMockEmbeddingService() domain.EmbeddingService {
	return &mockEmbeddingService{}
}

func (m *mockEmbeddingService) Embed(text string) ([]float64, error) {
	// Generate a simple deterministic embedding based on text hash
	hash := 0
	for _, c := range text {
		hash = hash*31 + int(c)
	}

	// Generate 384-dimensional vector (common embedding size)
	embedding := make([]float64, 384)
	for i := range embedding {
		// Use sine/cosine to create pseudo-random but deterministic values
		embedding[i] = math.Sin(float64(hash+i)) * 0.5
	}

	return embedding, nil
}

func (m *mockEmbeddingService) EmbedBatch(texts []string) ([][]float64, error) {
	embeddings := make([][]float64, len(texts))
	for i, text := range texts {
		emb, err := m.Embed(text)
		if err != nil {
			return nil, err
		}
		embeddings[i] = emb
	}
	return embeddings, nil
}
