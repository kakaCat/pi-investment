package repository

import (
	"context"
	"database/sql"
	"encoding/json"
	"fmt"
	"strings"
	"time"

	"github.com/lib/pq"
	"github.com/pi-investment/agent-os/internal/domain"
)

// MemoryWebRepository Web API 记忆仓储接口
type MemoryWebRepository interface {
	List(ctx context.Context, req domain.MemoryListRequest) ([]*domain.MemoryWeb, error)
	Search(ctx context.Context, req domain.MemorySearchRequest) ([]*domain.MemoryWeb, error)
	GetByID(ctx context.Context, id string, includeClosed bool) (*domain.MemoryWeb, error)
	Create(ctx context.Context, req domain.MemoryCreateRequest) (*domain.MemoryWeb, error)
	Update(ctx context.Context, id string, req domain.MemoryUpdateRequest) (*domain.MemoryWeb, error)
	Delete(ctx context.Context, id string, req domain.MemoryDeleteRequest) error
	GetTags(ctx context.Context) ([]*domain.Tag, error)
	CreateTag(ctx context.Context, name string) error
	DeleteTag(ctx context.Context, name string) error
}

type memoryWebRepository struct {
	db *sql.DB
}

// NewMemoryWebRepository 创建 Web API 记忆仓储
func NewMemoryWebRepository(db *sql.DB) MemoryWebRepository {
	return &memoryWebRepository{db: db}
}

// List 获取记忆列表
func (r *memoryWebRepository) List(ctx context.Context, req domain.MemoryListRequest) ([]*domain.MemoryWeb, error) {
	// RFC 009 审计修复：添加 metadata 字段返回
	query := `SELECT id, title, content, category, tags, created_at, updated_at, metadata
	          FROM memories WHERE 1=1`
	
	args := []interface{}{}
	argIndex := 1
	
	// RFC 009: 默认排除 done/dropped/archived 状态的公告板帖子
	if !req.IncludeClosed {
		query += ` AND (metadata->>'board_status' IS NULL OR metadata->>'board_status' NOT IN ('done', 'dropped', 'archived'))`
	}
	
	if req.Category != "" {
		query += fmt.Sprintf(" AND category = $%d", argIndex)
		args = append(args, req.Category)
		argIndex++
	}
	
	if req.Tag != "" {
		query += fmt.Sprintf(" AND $%d = ANY(tags)", argIndex)
		args = append(args, req.Tag)
		argIndex++
	}
	
	query += " ORDER BY created_at DESC"
	
	if req.Limit > 0 {
		query += fmt.Sprintf(" LIMIT $%d", argIndex)
		args = append(args, req.Limit)
	} else {
		query += " LIMIT 100"
	}
	
	rows, err := r.db.QueryContext(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to query memories: %w", err)
	}
	defer rows.Close()
	
	var memories []*domain.MemoryWeb
	for rows.Next() {
		var m domain.MemoryWeb
		var metadataJSON []byte
		err := rows.Scan(
			&m.ID, &m.Title, &m.Content, &m.Category,
			pq.Array(&m.Tags), &m.CreatedAt, &m.UpdatedAt, &metadataJSON,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan memory: %w", err)
		}
		
		// 解析 metadata
		if len(metadataJSON) > 0 {
			if err := json.Unmarshal(metadataJSON, &m.Metadata); err != nil {
				// metadata 解析失败不影响整体返回，继续
			}
		}
		
		memories = append(memories, &m)
	}
	
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows iteration error: %w", err)
	}
	
	return memories, nil
}

// Search 搜索记忆
func (r *memoryWebRepository) Search(ctx context.Context, req domain.MemorySearchRequest) ([]*domain.MemoryWeb, error) {
	// RFC 009 审计修复：添加 metadata 字段返回
	// 使用 ILIKE 进行模糊搜索，支持中文
	query := `SELECT id, title, content, category, tags, created_at, updated_at, metadata
	          FROM memories
	          WHERE (title ILIKE $1 OR content ILIKE $1)`
	
	// RFC 009: 默认排除 done/dropped/archived 状态的公告板帖子
	if !req.IncludeClosed {
		query += ` AND (metadata->>'board_status' IS NULL OR metadata->>'board_status' NOT IN ('done', 'dropped', 'archived'))`
	}
	
	query += " ORDER BY created_at DESC"
	
	if req.Limit > 0 {
		query += fmt.Sprintf(" LIMIT %d", req.Limit)
	} else {
		query += " LIMIT 50"
	}
	
	searchPattern := "%" + req.Query + "%"
	rows, err := r.db.QueryContext(ctx, query, searchPattern)
	if err != nil {
		return nil, fmt.Errorf("failed to search memories: %w", err)
	}
	defer rows.Close()
	
	var memories []*domain.MemoryWeb
	for rows.Next() {
		var m domain.MemoryWeb
		var metadataJSON []byte
		err := rows.Scan(
			&m.ID, &m.Title, &m.Content, &m.Category,
			pq.Array(&m.Tags), &m.CreatedAt, &m.UpdatedAt, &metadataJSON,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan memory: %w", err)
		}
		
		// 解析 metadata
		if len(metadataJSON) > 0 {
			if err := json.Unmarshal(metadataJSON, &m.Metadata); err != nil {
				// metadata 解析失败不影响整体返回，继续
			}
		}
		
		memories = append(memories, &m)
	}
	
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows iteration error: %w", err)
	}
	
	return memories, nil
}

// GetByID 按 ID 精确查询单条记忆（2026-08-28 补充 RESTful 标准端点）
func (r *memoryWebRepository) GetByID(ctx context.Context, id string, includeClosed bool) (*domain.MemoryWeb, error) {
	query := `SELECT id, title, content, category, tags, created_at, updated_at, metadata
	          FROM memories WHERE id = $1`
	
	// 默认排除已关闭状态（done/dropped/archived）
	if !includeClosed {
		query += ` AND (metadata->>'board_status' IS NULL OR metadata->>'board_status' NOT IN ('done', 'dropped', 'archived'))`
	}
	
	var m domain.MemoryWeb
	var metadataJSON []byte
	
	err := r.db.QueryRowContext(ctx, query, id).Scan(
		&m.ID, &m.Title, &m.Content, &m.Category,
		pq.Array(&m.Tags), &m.CreatedAt, &m.UpdatedAt, &metadataJSON,
	)
	
	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("memory not found: %s", id)
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get memory by id: %w", err)
	}
	
	// 解析 metadata
	if len(metadataJSON) > 0 {
		if err := json.Unmarshal(metadataJSON, &m.Metadata); err != nil {
			// metadata 解析失败不影响返回
		}
	}
	
	return &m, nil
}

// Create 写入一条记忆
func (r *memoryWebRepository) Create(ctx context.Context, req domain.MemoryCreateRequest) (*domain.MemoryWeb, error) {
	query := `INSERT INTO memories (title, content, category, tags, agent_id)
	          VALUES ($1, $2, $3, $4, $5)
	          RETURNING id, title, content, category, tags, agent_id, created_at, updated_at`

	var m domain.MemoryWeb
	err := r.db.QueryRowContext(ctx, query,
		req.Title, req.Content, req.Category,
		pq.Array(req.Tags), req.AgentID,
	).Scan(
		&m.ID, &m.Title, &m.Content, &m.Category,
		pq.Array(&m.Tags), &m.AgentID,
		&m.CreatedAt, &m.UpdatedAt,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create memory: %w", err)
	}

	return &m, nil
}

// GetTags 获取所有标签
func (r *memoryWebRepository) GetTags(ctx context.Context) ([]*domain.Tag, error) {
	query := `SELECT name, count, created_at FROM tags ORDER BY count DESC`
	
	rows, err := r.db.QueryContext(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("failed to query tags: %w", err)
	}
	defer rows.Close()
	
	var tags []*domain.Tag
	for rows.Next() {
		var t domain.Tag
		err := rows.Scan(&t.Name, &t.Count, &t.CreatedAt)
		if err != nil {
			return nil, fmt.Errorf("failed to scan tag: %w", err)
		}
		tags = append(tags, &t)
	}
	
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows iteration error: %w", err)
	}
	
	return tags, nil
}

// CreateTag 创建标签
func (r *memoryWebRepository) CreateTag(ctx context.Context, name string) error {
	query := `INSERT INTO tags (name, count) VALUES ($1, 0) ON CONFLICT (name) DO NOTHING`
	
	_, err := r.db.ExecContext(ctx, query, name)
	if err != nil {
		return fmt.Errorf("failed to create tag: %w", err)
	}
	
	return nil
}

// DeleteTag 删除标签
func (r *memoryWebRepository) DeleteTag(ctx context.Context, name string) error {
	query := `DELETE FROM tags WHERE name = $1`
	
	_, err := r.db.ExecContext(ctx, query, name)
	if err != nil {
		return fmt.Errorf("failed to delete tag: %w", err)
	}
	
	return nil
}

// Update 更新记忆（PATCH /api/v1/memory/{id}）
func (r *memoryWebRepository) Update(ctx context.Context, id string, req domain.MemoryUpdateRequest) (*domain.MemoryWeb, error) {
	// RFC 009: 支持 content 更新和 metadata patch，带 expected_revision 乐观锁
	// RFC 009 审计修复：添加事务保护，防止并发操作导致数据不一致
	
	// 开始事务
	tx, err := r.db.BeginTx(ctx, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback() // 失败时自动回滚
	
	var setClauses []string
	var args []interface{}
	argIndex := 1
	
	// 如果有 expected_revision，先读取当前 metadata 并自动递增 revision
	var needUpdateMetadata bool
	var currentMetadata map[string]interface{}
	
	if req.ExpectedRevision != nil || req.MetadataPatch != nil {
		queryRead := `SELECT metadata FROM memories WHERE id = $1 FOR UPDATE` // 添加 FOR UPDATE 锁行
		var metadataJSON []byte
		err := tx.QueryRowContext(ctx, queryRead, id).Scan(&metadataJSON) // 使用 tx 而不是 r.db
		if err != nil {
			if err == sql.ErrNoRows {
				return nil, fmt.Errorf("memory not found: %s", id)
			}
			return nil, fmt.Errorf("failed to read current metadata: %w", err)
		}
		
		if len(metadataJSON) > 0 {
			if err := json.Unmarshal(metadataJSON, &currentMetadata); err != nil {
				return nil, fmt.Errorf("failed to unmarshal metadata: %w", err)
			}
		} else {
			currentMetadata = make(map[string]interface{})
		}
		
		// 如果有 expected_revision，说明需要乐观锁，自动递增 revision
		if req.ExpectedRevision != nil {
			currentRevision := 1
			if rev, ok := currentMetadata["revision"].(float64); ok {
				currentRevision = int(rev)
			}
			currentMetadata["revision"] = currentRevision + 1
			needUpdateMetadata = true
		}
		
		// 应用 metadata patch
		if req.MetadataPatch != nil {
			for k, v := range req.MetadataPatch {
				currentMetadata[k] = v
			}
			needUpdateMetadata = true
		}
	}
	
	if req.Content != nil {
		setClauses = append(setClauses, fmt.Sprintf("content = $%d", argIndex))
		args = append(args, *req.Content)
		argIndex++
	}
	
	if needUpdateMetadata {
		setClauses = append(setClauses, fmt.Sprintf("metadata = $%d", argIndex))
		mergedJSON, err := json.Marshal(currentMetadata)
		if err != nil {
			return nil, fmt.Errorf("failed to marshal merged metadata: %w", err)
		}
		args = append(args, mergedJSON)
		argIndex++
	}
	
	if len(setClauses) == 0 {
		return nil, fmt.Errorf("no fields to update")
	}
	
	setClauses = append(setClauses, fmt.Sprintf("updated_at = $%d", argIndex))
	args = append(args, time.Now())
	argIndex++
	
	whereClause := fmt.Sprintf("id = $%d", argIndex)
	args = append(args, id)
	argIndex++
	
	if req.ExpectedRevision != nil {
		whereClause += fmt.Sprintf(" AND (metadata->>'revision')::int = $%d", argIndex)
		args = append(args, *req.ExpectedRevision)
		argIndex++
	}
	
	query := fmt.Sprintf("UPDATE memories SET %s WHERE %s RETURNING id, content, category, created_at, updated_at, metadata",
		strings.Join(setClauses, ", "), whereClause)
	
	var memory domain.MemoryWeb
	var metadataJSON []byte
	err = tx.QueryRowContext(ctx, query, args...).Scan( // 使用 tx
		&memory.ID, &memory.Content, &memory.Category,
		&memory.CreatedAt, &memory.UpdatedAt, &metadataJSON,
	)
	
	if err != nil {
		if err == sql.ErrNoRows {
			if req.ExpectedRevision != nil {
				var exists bool
				checkQuery := `SELECT EXISTS(SELECT 1 FROM memories WHERE id = $1)`
				_ = tx.QueryRowContext(ctx, checkQuery, id).Scan(&exists) // 使用 tx
				if exists {
					return nil, fmt.Errorf("revision conflict: expected %d", *req.ExpectedRevision)
				}
			}
			return nil, fmt.Errorf("memory not found: %s", id)
		}
		return nil, fmt.Errorf("failed to update memory: %w", err)
	}
	
	// 填充 Title（从 metadata 或使用默认值）
	var metadata map[string]interface{}
	if len(metadataJSON) > 0 {
		_ = json.Unmarshal(metadataJSON, &metadata)
		if title, ok := metadata["title"].(string); ok {
			memory.Title = title
		}
	}
	
	// 提交事务
	if err := tx.Commit(); err != nil {
		return nil, fmt.Errorf("failed to commit transaction: %w", err)
	}
	
	return &memory, nil
}

// Delete 删除记忆（软删：设置 metadata.board_status=dropped）
func (r *memoryWebRepository) Delete(ctx context.Context, id string, req domain.MemoryDeleteRequest) error {
	// RFC 009 审计修复：添加事务保护
	
	// 开始事务
	tx, err := r.db.BeginTx(ctx, nil)
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback() // 失败时自动回滚
	
	var currentMetadata map[string]interface{}
	queryRead := `SELECT metadata FROM memories WHERE id = $1 FOR UPDATE` // 添加 FOR UPDATE 锁行
	var metadataJSON []byte
	err = tx.QueryRowContext(ctx, queryRead, id).Scan(&metadataJSON) // 使用 tx
	if err != nil {
		if err == sql.ErrNoRows {
			return fmt.Errorf("memory not found: %s", id)
		}
		return fmt.Errorf("failed to read metadata: %w", err)
	}
	
	if len(metadataJSON) > 0 {
		if err := json.Unmarshal(metadataJSON, &currentMetadata); err != nil {
			return fmt.Errorf("failed to unmarshal metadata: %w", err)
		}
	} else {
		currentMetadata = make(map[string]interface{})
	}
	
	currentMetadata["board_status"] = "dropped"
	if req.Reason != "" {
		currentMetadata["drop_reason"] = req.Reason
	}
	currentMetadata["closed_at"] = time.Now().Format(time.RFC3339)
	
	updatedJSON, err := json.Marshal(currentMetadata)
	if err != nil {
		return fmt.Errorf("failed to marshal metadata: %w", err)
	}
	
	query := `UPDATE memories SET metadata = $1, updated_at = $2 WHERE id = $3`
	result, err := tx.ExecContext(ctx, query, updatedJSON, time.Now(), id) // 使用 tx
	if err != nil {
		return fmt.Errorf("failed to soft delete memory: %w", err)
	}
	
	rows, _ := result.RowsAffected()
	if rows == 0 {
		return fmt.Errorf("memory not found: %s", id)
	}
	
	// 提交事务
	if err := tx.Commit(); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}
	
	return nil
}
