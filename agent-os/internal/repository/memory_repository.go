package repository

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"
	"time"
	"unicode/utf8"

	"github.com/google/uuid"
	"github.com/lib/pq"

	"github.com/pi-investment/agent-os/internal/domain"
)

type memoryRepository struct {
	db *sql.DB
}

// NewMemoryRepository creates a new memory repository
func NewMemoryRepository(db *sql.DB) domain.MemoryRepository {
	return &memoryRepository{db: db}
}

// Create inserts a new memory into the database
func (r *memoryRepository) Create(memory *domain.Memory) error {
	query := `
		INSERT INTO memories (id, namespace_id, content, category, importance, embedding, created_at, updated_at, accessed_count, metadata)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
	`

	if memory.ID == uuid.Nil {
		memory.ID = uuid.New()
	}

	now := time.Now()
	memory.CreatedAt = now
	memory.UpdatedAt = now

	// Serialize embedding as JSON for now (will use pgvector later)
	var embeddingJSON []byte
	if memory.Embedding != nil {
		var err error
		embeddingJSON, err = json.Marshal(memory.Embedding)
		if err != nil {
			return fmt.Errorf("failed to marshal embedding: %w", err)
		}
	}

	// Serialize metadata
	metadataJSON, err := json.Marshal(memory.Metadata)
	if err != nil {
		return fmt.Errorf("failed to marshal metadata: %w", err)
	}

	_, err = r.db.Exec(query,
		memory.ID,
		memory.NamespaceID,
		memory.Content,
		memory.Category,
		memory.Importance,
		embeddingJSON,
		memory.CreatedAt,
		memory.UpdatedAt,
		memory.AccessedCount,
		metadataJSON,
	)

	if err != nil {
		return fmt.Errorf("failed to create memory: %w", err)
	}

	// Insert tags if present
	if len(memory.Tags) > 0 {
		if err := r.AddTags(memory.ID, memory.Tags); err != nil {
			return fmt.Errorf("failed to add tags: %w", err)
		}
	}

	return nil
}

// Update updates an existing memory
func (r *memoryRepository) Update(memory *domain.Memory) error {
	query := `
		UPDATE memories
		SET content = $1, category = $2, importance = $3, embedding = $4, updated_at = $5, metadata = $6
		WHERE id = $7
	`

	memory.UpdatedAt = time.Now()

	// Serialize embedding
	var embeddingJSON []byte
	if memory.Embedding != nil {
		var err error
		embeddingJSON, err = json.Marshal(memory.Embedding)
		if err != nil {
			return fmt.Errorf("failed to marshal embedding: %w", err)
		}
	}

	// Serialize metadata
	metadataJSON, err := json.Marshal(memory.Metadata)
	if err != nil {
		return fmt.Errorf("failed to marshal metadata: %w", err)
	}

	result, err := r.db.Exec(query,
		memory.Content,
		memory.Category,
		memory.Importance,
		embeddingJSON,
		memory.UpdatedAt,
		metadataJSON,
		memory.ID,
	)

	if err != nil {
		return fmt.Errorf("failed to update memory: %w", err)
	}

	rows, _ := result.RowsAffected()
	if rows == 0 {
		return fmt.Errorf("memory not found: %s", memory.ID)
	}

	return nil
}

// Delete removes a memory from the database
func (r *memoryRepository) Delete(id uuid.UUID) error {
	query := `DELETE FROM memories WHERE id = $1`

	result, err := r.db.Exec(query, id)
	if err != nil {
		return fmt.Errorf("failed to delete memory: %w", err)
	}

	rows, _ := result.RowsAffected()
	if rows == 0 {
		return fmt.Errorf("memory not found: %s", id)
	}

	return nil
}

// GetByID retrieves a memory by ID
func (r *memoryRepository) GetByID(id uuid.UUID) (*domain.Memory, error) {
	query := `
		SELECT m.id, m.namespace_id, m.content, m.category, m.importance, m.embedding,
		       m.created_at, m.updated_at, m.accessed_count, m.last_accessed_at, m.metadata,
		       COALESCE(array_agg(mt.tag) FILTER (WHERE mt.tag IS NOT NULL), '{}') as tags
		FROM memories m
		LEFT JOIN memory_tags mt ON m.id = mt.memory_id
		WHERE m.id = $1
		GROUP BY m.id
	`

	memory := &domain.Memory{}
	var embeddingJSON []byte
	var metadataJSON []byte
	var tags []string

	err := r.db.QueryRow(query, id).Scan(
		&memory.ID,
		&memory.NamespaceID,
		&memory.Content,
		&memory.Category,
		&memory.Importance,
		&embeddingJSON,
		&memory.CreatedAt,
		&memory.UpdatedAt,
		&memory.AccessedCount,
		&memory.LastAccessedAt,
		&metadataJSON,
		pq.Array(&tags),
	)

	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("memory not found: %s", id)
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get memory: %w", err)
	}

	// Deserialize embedding
	if embeddingJSON != nil {
		if err := json.Unmarshal(embeddingJSON, &memory.Embedding); err != nil {
			return nil, fmt.Errorf("failed to unmarshal embedding: %w", err)
		}
	}

	// Deserialize metadata
	if err := json.Unmarshal(metadataJSON, &memory.Metadata); err != nil {
		return nil, fmt.Errorf("failed to unmarshal metadata: %w", err)
	}

	memory.Tags = tags

	return memory, nil
}

// List retrieves memories for a namespace with pagination
func (r *memoryRepository) List(namespaceID uuid.UUID, limit, offset int) ([]*domain.Memory, error) {
	query := `
		SELECT m.id, m.namespace_id, m.content, m.category, m.importance, m.embedding,
		       m.created_at, m.updated_at, m.accessed_count, m.last_accessed_at, m.metadata,
		       COALESCE(array_agg(mt.tag) FILTER (WHERE mt.tag IS NOT NULL), '{}') as tags
		FROM memories m
		LEFT JOIN memory_tags mt ON m.id = mt.memory_id
		WHERE m.namespace_id = $1
		GROUP BY m.id
		ORDER BY m.created_at DESC
		LIMIT $2 OFFSET $3
	`

	rows, err := r.db.Query(query, namespaceID, limit, offset)
	if err != nil {
		return nil, fmt.Errorf("failed to list memories: %w", err)
	}
	defer rows.Close()

	return r.scanMemories(rows)
}

// Search performs a basic text search on memory content
func (r *memoryRepository) Search(query *domain.SearchQuery) ([]*domain.SearchResult, error) {
	// For now, use simple ILIKE search. Will enhance with BM25 later.
	sqlQuery := `
		SELECT m.id, m.namespace_id, m.content, m.category, m.importance, m.embedding,
		       m.created_at, m.updated_at, m.accessed_count, m.last_accessed_at, m.metadata,
		       COALESCE(array_agg(mt.tag) FILTER (WHERE mt.tag IS NOT NULL), '{}') as tags,
		       1.0 as score
		FROM memories m
		LEFT JOIN memory_tags mt ON m.id = mt.memory_id
		WHERE m.namespace_id = $1
		  AND m.content ILIKE $2
	`

	args := []interface{}{query.NamespaceID, "%" + query.Query + "%"}
	argIndex := 3

	// Add category filter
	if len(query.Categories) > 0 {
		sqlQuery += fmt.Sprintf(" AND m.category = ANY($%d)", argIndex)
		args = append(args, pq.Array(query.Categories))
		argIndex++
	}

	// Add importance filter
	if query.MinImportance > 0 {
		sqlQuery += fmt.Sprintf(" AND m.importance >= $%d", argIndex)
		args = append(args, query.MinImportance)
		argIndex++
	}

	sqlQuery += ` GROUP BY m.id ORDER BY m.importance DESC, m.created_at DESC`

	// Add pagination
	sqlQuery += fmt.Sprintf(" LIMIT $%d OFFSET $%d", argIndex, argIndex+1)
	args = append(args, query.Limit, query.Offset)

	rows, err := r.db.Query(sqlQuery, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to search memories: %w", err)
	}
	defer rows.Close()

	return r.scanSearchResults(rows)
}

// SearchBM25 performs BM25 full-text search.
// 2026-09-11（REQ-342799，w-c8cae280）：先走 PostgreSQL 全文检索；**零命中时回退到按词 OR 子串匹配**。
// 背景：FTS 使用 'english' 配置，中文无法正确分词；且 plainto_tsquery 把多个词以 AND 连接——
// 实测『业绩归因 超额 beta alpha』『这次修复的信号账本假数据问题是什么』等查询恒返回 0 条，
// 使 memory_search 静默给出「无历史」的假结论（R-008 决策前检索因此空转）。
func (r *memoryRepository) SearchBM25(query *domain.SearchQuery) ([]*domain.SearchResult, error) {
	results, err := r.searchFullText(query)
	if err != nil {
		return nil, err
	}
	if len(results) > 0 {
		return results, nil
	}
	return r.searchTermOR(query)
}

// searchFullText 原实现：PostgreSQL ts_rank_cd 全文检索
func (r *memoryRepository) searchFullText(query *domain.SearchQuery) ([]*domain.SearchResult, error) {
	// Use PostgreSQL's ts_rank_cd for BM25-like ranking
	sqlQuery := `
		SELECT m.id, m.namespace_id, m.content, m.category, m.importance, m.embedding,
		       m.created_at, m.updated_at, m.accessed_count, m.last_accessed_at, m.metadata,
		       COALESCE(array_agg(mt.tag) FILTER (WHERE mt.tag IS NOT NULL), '{}') as tags,
		       ts_rank_cd(to_tsvector('english', m.content), plainto_tsquery('english', $2)) as score
		FROM memories m
		LEFT JOIN memory_tags mt ON m.id = mt.memory_id
		WHERE m.namespace_id = $1
		  AND to_tsvector('english', m.content) @@ plainto_tsquery('english', $2)
	`

	args := []interface{}{query.NamespaceID, query.Query}
	argIndex := 3

	// Add category filter
	if len(query.Categories) > 0 {
		sqlQuery += fmt.Sprintf(" AND m.category = ANY($%d)", argIndex)
		args = append(args, pq.Array(query.Categories))
		argIndex++
	}

	// Add importance filter
	if query.MinImportance > 0 {
		sqlQuery += fmt.Sprintf(" AND m.importance >= $%d", argIndex)
		args = append(args, query.MinImportance)
		argIndex++
	}

	sqlQuery += ` GROUP BY m.id ORDER BY score DESC, m.importance DESC`

	// Add pagination
	sqlQuery += fmt.Sprintf(" LIMIT $%d OFFSET $%d", argIndex, argIndex+1)
	args = append(args, query.Limit, query.Offset)

	rows, err := r.db.Query(sqlQuery, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to search memories with BM25: %w", err)
	}
	defer rows.Close()

	return r.scanSearchResults(rows)
}

// memoryQueryStopWords 查询停用词（中英混合，避免噪声词主导 OR 匹配）
var memoryQueryStopWords = map[string]bool{
	"的": true, "了": true, "是": true, "在": true, "和": true, "与": true, "有": true,
	"我": true, "你": true, "他": true, "这": true, "那": true, "什么": true, "怎么": true,
	"如何": true, "为什么": true, "吗": true, "呢": true, "请": true, "一下": true, "已经": true,
	"今天": true, "可以": true, "需要": true, "问题": true, "是否": true, "以及": true,
	"我们": true, "他们": true, "这个": true, "那个": true, "还是": true, "就是": true,
	"the": true, "a": true, "an": true, "is": true, "are": true, "to": true, "of": true,
	"and": true, "or": true, "for": true, "what": true, "how": true, "this": true, "that": true,
}

// searchTermOR 按词做 OR 子串匹配，按命中词数排序（中文友好；FTS 零命中时的回退路径）
func (r *memoryRepository) searchTermOR(query *domain.SearchQuery) ([]*domain.SearchResult, error) {
	terms := splitQueryTerms(query.Query)
	if len(terms) == 0 {
		return nil, nil
	}
	patterns := make([]string, 0, len(terms))
	for _, t := range terms {
		patterns = append(patterns, "%"+escapeLike(t)+"%")
	}

	sqlQuery := `
		SELECT m.id, m.namespace_id, m.content, m.category, m.importance, m.embedding,
		       m.created_at, m.updated_at, m.accessed_count, m.last_accessed_at, m.metadata,
		       COALESCE(array_agg(mt.tag) FILTER (WHERE mt.tag IS NOT NULL), '{}') as tags,
		       (SELECT count(*)::float FROM unnest($2::text[]) AS p WHERE m.content ILIKE p) as score
		FROM memories m
		LEFT JOIN memory_tags mt ON m.id = mt.memory_id
		WHERE m.namespace_id = $1
		  AND m.content ILIKE ANY($2::text[])
	`
	args := []interface{}{query.NamespaceID, pq.Array(patterns)}
	argIndex := 3

	if len(query.Categories) > 0 {
		sqlQuery += fmt.Sprintf(" AND m.category = ANY($%d)", argIndex)
		args = append(args, pq.Array(query.Categories))
		argIndex++
	}
	if query.MinImportance > 0 {
		sqlQuery += fmt.Sprintf(" AND m.importance >= $%d", argIndex)
		args = append(args, query.MinImportance)
		argIndex++
	}

	sqlQuery += ` GROUP BY m.id ORDER BY score DESC, m.importance DESC, m.created_at DESC`
	sqlQuery += fmt.Sprintf(" LIMIT $%d OFFSET $%d", argIndex, argIndex+1)
	args = append(args, query.Limit, query.Offset)

	rows, err := r.db.Query(sqlQuery, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to search memories with term-OR fallback: %w", err)
	}
	defer rows.Close()
	return r.scanSearchResults(rows)
}

// splitQueryTerms 把查询切成有信息量的检索词；长中文句切 n-gram（无空格时整句永远匹配不上）
func splitQueryTerms(q string) []string {
	fields := strings.FieldsFunc(q, func(r rune) bool {
		switch r {
		case ' ', '\t', '\n', '\r', ',', '，', '。', '、', ';', '；', ':', '：',
			'!', '！', '?', '？', '(', ')', '（', '）', '[', ']', '【', '】', '"', '\'', '`':
			return true
		}
		return false
	})
	seen := map[string]bool{}
	out := make([]string, 0, len(fields))
	for _, f := range fields {
		t := strings.TrimSpace(f)
		if t == "" || memoryQueryStopWords[strings.ToLower(t)] || utf8.RuneCountInString(t) < 2 {
			continue
		}
		for _, sub := range cjkQueryTerms(t) {
			if !seen[sub] {
				seen[sub] = true
				out = append(out, sub)
			}
		}
	}
	return out
}

// cjkQueryTerms 较长中文片段生成 4/3 字 n-gram（长者优先，最多 12 个）
func cjkQueryTerms(t string) []string {
	runes := []rune(t)
	if len(runes) <= 6 {
		return []string{t}
	}
	out := []string{}
	for _, n := range []int{4, 3} {
		for i := 0; i+n <= len(runes); i++ {
			out = append(out, string(runes[i:i+n]))
			if len(out) >= 12 {
				return out
			}
		}
	}
	if len(out) == 0 {
		return []string{t}
	}
	return out
}

// escapeLike 转义 LIKE 元字符，避免查询里的 % _ 变成通配符
func escapeLike(s string) string {
	s = strings.ReplaceAll(s, "\\", "\\\\")
	s = strings.ReplaceAll(s, "%", "\\%")
	s = strings.ReplaceAll(s, "_", "\\_")
	return s
}

// SearchVector performs vector similarity search
func (r *memoryRepository) SearchVector(query *domain.SearchQuery, embedding []float64) ([]*domain.SearchResult, error) {
	// For now, we'll use cosine similarity with JSON embeddings
	// TODO: Replace with pgvector when available

	// First get all memories with embeddings
	sqlQuery := `
		SELECT m.id, m.namespace_id, m.content, m.category, m.importance, m.embedding,
		       m.created_at, m.updated_at, m.accessed_count, m.last_accessed_at, m.metadata,
		       COALESCE(array_agg(mt.tag) FILTER (WHERE mt.tag IS NOT NULL), '{}') as tags
		FROM memories m
		LEFT JOIN memory_tags mt ON m.id = mt.memory_id
		WHERE m.namespace_id = $1
		  AND m.embedding IS NOT NULL
	`

	args := []interface{}{query.NamespaceID}

	if len(query.Categories) > 0 {
		sqlQuery += " AND m.category = ANY($2)"
		args = append(args, pq.Array(query.Categories))
	}

	sqlQuery += " GROUP BY m.id"

	rows, err := r.db.Query(sqlQuery, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to search memories with vector: %w", err)
	}
	defer rows.Close()

	// Scan and compute similarity in Go (temporary solution)
	var results []*domain.SearchResult
	for rows.Next() {
		memory := &domain.Memory{}
		var embeddingJSON []byte
		var metadataJSON []byte
		var tags []string

		err := rows.Scan(
			&memory.ID,
			&memory.NamespaceID,
			&memory.Content,
			&memory.Category,
			&memory.Importance,
			&embeddingJSON,
			&memory.CreatedAt,
			&memory.UpdatedAt,
			&memory.AccessedCount,
			&memory.LastAccessedAt,
			&metadataJSON,
			pq.Array(&tags),
		)

		if err != nil {
			return nil, fmt.Errorf("failed to scan memory: %w", err)
		}

		// Deserialize embedding
		if embeddingJSON != nil {
			if err := json.Unmarshal(embeddingJSON, &memory.Embedding); err != nil {
				continue // Skip memories with invalid embeddings
			}
		}

		// Deserialize metadata
		if err := json.Unmarshal(metadataJSON, &memory.Metadata); err != nil {
			return nil, fmt.Errorf("failed to unmarshal metadata: %w", err)
		}

		memory.Tags = tags

		// Compute cosine similarity
		score := cosineSimilarity(embedding, memory.Embedding)

		results = append(results, &domain.SearchResult{
			Memory: memory,
			Score:  score,
			Source: "vector",
		})
	}

	// Sort by score descending
	for i := 0; i < len(results)-1; i++ {
		for j := i + 1; j < len(results); j++ {
			if results[i].Score < results[j].Score {
				results[i], results[j] = results[j], results[i]
			}
		}
	}

	// Apply limit
	if query.Limit > 0 && len(results) > query.Limit {
		results = results[:query.Limit]
	}

	return results, nil
}

// AddTags adds tags to a memory
func (r *memoryRepository) AddTags(memoryID uuid.UUID, tags []string) error {
	if len(tags) == 0 {
		return nil
	}

	// Build bulk insert query
	var values []string
	var args []interface{}
	argIndex := 1

	for _, tag := range tags {
		values = append(values, fmt.Sprintf("($%d, $%d)", argIndex, argIndex+1))
		args = append(args, memoryID, tag)
		argIndex += 2
	}

	query := fmt.Sprintf(`
		INSERT INTO memory_tags (memory_id, tag)
		VALUES %s
		ON CONFLICT (memory_id, tag) DO NOTHING
	`, strings.Join(values, ", "))

	_, err := r.db.Exec(query, args...)
	if err != nil {
		return fmt.Errorf("failed to add tags: %w", err)
	}

	return nil
}

// RemoveTags removes tags from a memory
func (r *memoryRepository) RemoveTags(memoryID uuid.UUID, tags []string) error {
	if len(tags) == 0 {
		return nil
	}

	query := `DELETE FROM memory_tags WHERE memory_id = $1 AND tag = ANY($2)`

	_, err := r.db.Exec(query, memoryID, pq.Array(tags))
	if err != nil {
		return fmt.Errorf("failed to remove tags: %w", err)
	}

	return nil
}

// GetByTags retrieves memories by tags
func (r *memoryRepository) GetByTags(namespaceID uuid.UUID, tags []string, limit int) ([]*domain.Memory, error) {
	query := `
		SELECT DISTINCT m.id, m.namespace_id, m.content, m.category, m.importance, m.embedding,
		       m.created_at, m.updated_at, m.accessed_count, m.last_accessed_at, m.metadata,
		       COALESCE(array_agg(mt2.tag) FILTER (WHERE mt2.tag IS NOT NULL), '{}') as tags
		FROM memories m
		JOIN memory_tags mt ON m.id = mt.memory_id
		LEFT JOIN memory_tags mt2 ON m.id = mt2.memory_id
		WHERE m.namespace_id = $1
		  AND mt.tag = ANY($2)
		GROUP BY m.id
		ORDER BY m.importance DESC, m.created_at DESC
		LIMIT $3
	`

	rows, err := r.db.Query(query, namespaceID, pq.Array(tags), limit)
	if err != nil {
		return nil, fmt.Errorf("failed to get memories by tags: %w", err)
	}
	defer rows.Close()

	return r.scanMemories(rows)
}

// IncrementAccessCount increments the access count for a memory
func (r *memoryRepository) IncrementAccessCount(id uuid.UUID) error {
	query := `
		UPDATE memories
		SET accessed_count = accessed_count + 1, last_accessed_at = $1
		WHERE id = $2
	`

	_, err := r.db.Exec(query, time.Now(), id)
	if err != nil {
		return fmt.Errorf("failed to increment access count: %w", err)
	}

	return nil
}

// Helper functions

func (r *memoryRepository) scanMemories(rows *sql.Rows) ([]*domain.Memory, error) {
	var memories []*domain.Memory

	for rows.Next() {
		memory := &domain.Memory{}
		var embeddingJSON []byte
		var metadataJSON []byte
		var tags []string

		err := rows.Scan(
			&memory.ID,
			&memory.NamespaceID,
			&memory.Content,
			&memory.Category,
			&memory.Importance,
			&embeddingJSON,
			&memory.CreatedAt,
			&memory.UpdatedAt,
			&memory.AccessedCount,
			&memory.LastAccessedAt,
			&metadataJSON,
			pq.Array(&tags),
		)

		if err != nil {
			return nil, fmt.Errorf("failed to scan memory: %w", err)
		}

		// Deserialize embedding
		if embeddingJSON != nil {
			if err := json.Unmarshal(embeddingJSON, &memory.Embedding); err != nil {
				return nil, fmt.Errorf("failed to unmarshal embedding: %w", err)
			}
		}

		// Deserialize metadata
		if err := json.Unmarshal(metadataJSON, &memory.Metadata); err != nil {
			return nil, fmt.Errorf("failed to unmarshal metadata: %w", err)
		}

		memory.Tags = tags
		memories = append(memories, memory)
	}

	return memories, rows.Err()
}

func (r *memoryRepository) scanSearchResults(rows *sql.Rows) ([]*domain.SearchResult, error) {
	var results []*domain.SearchResult

	for rows.Next() {
		memory := &domain.Memory{}
		var embeddingJSON []byte
		var metadataJSON []byte
		var tags []string
		var score float64

		err := rows.Scan(
			&memory.ID,
			&memory.NamespaceID,
			&memory.Content,
			&memory.Category,
			&memory.Importance,
			&embeddingJSON,
			&memory.CreatedAt,
			&memory.UpdatedAt,
			&memory.AccessedCount,
			&memory.LastAccessedAt,
			&metadataJSON,
			pq.Array(&tags),
			&score,
		)

		if err != nil {
			return nil, fmt.Errorf("failed to scan search result: %w", err)
		}

		// Deserialize embedding
		if embeddingJSON != nil {
			if err := json.Unmarshal(embeddingJSON, &memory.Embedding); err != nil {
				return nil, fmt.Errorf("failed to unmarshal embedding: %w", err)
			}
		}

		// Deserialize metadata
		if err := json.Unmarshal(metadataJSON, &memory.Metadata); err != nil {
			return nil, fmt.Errorf("failed to unmarshal metadata: %w", err)
		}

		memory.Tags = tags

		results = append(results, &domain.SearchResult{
			Memory: memory,
			Score:  score,
			Source: "bm25",
		})
	}

	return results, rows.Err()
}

// cosineSimilarity computes cosine similarity between two vectors
func cosineSimilarity(a, b []float64) float64 {
	if len(a) != len(b) || len(a) == 0 {
		return 0.0
	}

	var dotProduct, normA, normB float64
	for i := range a {
		dotProduct += a[i] * b[i]
		normA += a[i] * a[i]
		normB += b[i] * b[i]
	}

	if normA == 0 || normB == 0 {
		return 0.0
	}

	return dotProduct / (sqrt(normA) * sqrt(normB))
}

func sqrt(x float64) float64 {
	if x <= 0 {
		return 0
	}
	// Simple Newton's method for square root
	z := x
	for i := 0; i < 10; i++ {
		z = z - (z*z-x)/(2*z)
	}
	return z
}
