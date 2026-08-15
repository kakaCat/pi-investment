package services

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"strconv"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

type Skill struct {
	ID               string                 `json:"id"`
	Name             string                 `json:"name"`
	Description      string                 `json:"description"`
	Category         string                 `json:"category"`
	Owner            string                 `json:"owner"`
	CurrentVersionID *string                `json:"current_version_id"`
	Status           string                 `json:"status"`
	CreatedAt        time.Time              `json:"created_at"`
	UpdatedAt        time.Time              `json:"updated_at"`
	Metadata         map[string]interface{} `json:"metadata,omitempty"`
}

type SkillVersion struct {
	ID              string                 `json:"id"`
	SkillID         string                 `json:"skill_id"`
	Version         string                 `json:"version"`
	Content         string                 `json:"content"`
	ContentHash     string                 `json:"content_hash"`
	Author          string                 `json:"author"`
	CommitMessage   string                 `json:"commit_message"`
	ParentVersionID *string                `json:"parent_version_id"`
	CreatedAt       time.Time              `json:"created_at"`
	Metadata        map[string]interface{} `json:"metadata,omitempty"`
}

type SkillMetadata struct {
	ID          string                 `json:"id"`
	Name        string                 `json:"name"`
	Description string                 `json:"description"`
	Category    string                 `json:"category"`
	Owner       string                 `json:"owner"`
	Status      string                 `json:"status"`
	Metadata    map[string]interface{} `json:"metadata,omitempty"`
}

type SkillDetail struct {
	ID               string                 `json:"id"`
	Name             string                 `json:"name"`
	Description      string                 `json:"description"`
	Category         string                 `json:"category"`
	Owner            string                 `json:"owner"`
	CurrentVersionID *string                `json:"current_version_id"`
	Status           string                 `json:"status"`
	CreatedAt        time.Time              `json:"created_at"`
	UpdatedAt        time.Time              `json:"updated_at"`
	Metadata         map[string]interface{} `json:"metadata,omitempty"`
	Content          string                 `json:"content"`
	Version          string                 `json:"version"`
}

type SkillService struct {
	db *pgxpool.Pool
}

func NewSkillService(db *pgxpool.Pool) *SkillService {
	return &SkillService{db: db}
}

// ListSkills returns skill metadata list (without content)
func (s *SkillService) ListSkills(ctx context.Context, owner string, status string) ([]SkillMetadata, error) {
	query := `
        SELECT id, name, description, category, owner, status, metadata
        FROM skills
        WHERE 1=1
    `
	args := []interface{}{}
	argIdx := 1

	if owner != "" {
		query += fmt.Sprintf(" AND owner = $%d", argIdx)
		args = append(args, owner)
		argIdx++
	}

	if status != "" {
		query += fmt.Sprintf(" AND status = $%d", argIdx)
		args = append(args, status)
		argIdx++
	}

	query += " ORDER BY name"

	rows, err := s.db.Query(ctx, query, args...)
	if err != nil {
		return nil, fmt.Errorf("query skills: %w", err)
	}
	defer rows.Close()

	var skills []SkillMetadata
	for rows.Next() {
		var skill SkillMetadata
		var metadataJSON []byte

		err := rows.Scan(
			&skill.ID,
			&skill.Name,
			&skill.Description,
			&skill.Category,
			&skill.Owner,
			&skill.Status,
			&metadataJSON,
		)
		if err != nil {
			return nil, fmt.Errorf("scan skill: %w", err)
		}

		// Parse JSONB metadata
		if metadataJSON != nil {
			if err := json.Unmarshal(metadataJSON, &skill.Metadata); err != nil {
				return nil, fmt.Errorf("unmarshal metadata: %w", err)
			}
		}

		skills = append(skills, skill)
	}

	if skills == nil {
		skills = []SkillMetadata{}
	}

	return skills, nil
}

// GetSkill returns skill detail (with content)
func (s *SkillService) GetSkill(ctx context.Context, id string) (*SkillDetail, error) {
	query := `
        SELECT
            s.id, s.name, s.description, s.category, s.owner,
            s.current_version_id, s.status, s.created_at, s.updated_at, s.metadata,
            sv.content, sv.version
        FROM skills s
        LEFT JOIN skill_versions sv ON s.current_version_id = sv.id
        WHERE s.id = $1
    `

	var detail SkillDetail
	var metadataJSON []byte
	var content *string
	var version *string

	err := s.db.QueryRow(ctx, query, id).Scan(
		&detail.ID,
		&detail.Name,
		&detail.Description,
		&detail.Category,
		&detail.Owner,
		&detail.CurrentVersionID,
		&detail.Status,
		&detail.CreatedAt,
		&detail.UpdatedAt,
		&metadataJSON,
		&content,
		&version,
	)
	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, fmt.Errorf("skill not found: %s", id)
		}
		return nil, fmt.Errorf("get skill: %w", err)
	}

	// Parse JSONB metadata
	if metadataJSON != nil {
		if err := json.Unmarshal(metadataJSON, &detail.Metadata); err != nil {
			return nil, fmt.Errorf("unmarshal metadata: %w", err)
		}
	}

	if content != nil {
		detail.Content = *content
	}
	if version != nil {
		detail.Version = *version
	}

	return &detail, nil
}

// CreateSkill creates a new skill
func (s *SkillService) CreateSkill(ctx context.Context, name, description, category, owner, content, author string, metadata map[string]interface{}) (*Skill, error) {
	tx, err := s.db.Begin(ctx)
	if err != nil {
		return nil, fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback(ctx)

	// 1. Create skill record
	skillID := uuid.New().String()

	var metadataJSON []byte
	if metadata != nil {
		metadataJSON, err = json.Marshal(metadata)
		if err != nil {
			return nil, fmt.Errorf("marshal metadata: %w", err)
		}
	}

	_, err = tx.Exec(ctx, `
        INSERT INTO skills (id, name, description, category, owner, status, metadata)
        VALUES ($1, $2, $3, $4, $5, 'active', $6)
    `, skillID, name, description, category, owner, metadataJSON)
	if err != nil {
		return nil, fmt.Errorf("insert skill: %w", err)
	}

	// 2. Create first version
	versionID := uuid.New().String()
	contentHash := hashContent(content)
	_, err = tx.Exec(ctx, `
        INSERT INTO skill_versions (id, skill_id, version, content, content_hash, author, commit_message)
        VALUES ($1, $2, 'v1.0.0', $3, $4, $5, 'Initial version')
    `, versionID, skillID, content, contentHash, author)
	if err != nil {
		return nil, fmt.Errorf("insert skill version: %w", err)
	}

	// 3. Update skill's current_version_id
	_, err = tx.Exec(ctx, `
        UPDATE skills SET current_version_id = $1 WHERE id = $2
    `, versionID, skillID)
	if err != nil {
		return nil, fmt.Errorf("update skill current_version_id: %w", err)
	}

	if err := tx.Commit(ctx); err != nil {
		return nil, fmt.Errorf("commit tx: %w", err)
	}

	// 4. Return created skill
	return s.getSkillByID(ctx, skillID)
}

// UpdateSkill updates a skill (creates new version)
func (s *SkillService) UpdateSkill(ctx context.Context, id, content, author, commitMessage string) (*SkillVersion, error) {
	tx, err := s.db.Begin(ctx)
	if err != nil {
		return nil, fmt.Errorf("begin tx: %w", err)
	}
	defer tx.Rollback(ctx)

	// 1. Get current version
	var currentVersion string
	var currentVersionID string
	err = tx.QueryRow(ctx, `
        SELECT sv.version, s.current_version_id
        FROM skills s
        JOIN skill_versions sv ON s.current_version_id = sv.id
        WHERE s.id = $1
    `, id).Scan(&currentVersion, &currentVersionID)
	if err != nil {
		if err == pgx.ErrNoRows {
			return nil, fmt.Errorf("skill not found: %s", id)
		}
		return nil, fmt.Errorf("get current version: %w", err)
	}

	// 2. Calculate new version number
	newVersion := incrementVersion(currentVersion)

	// 3. Create new version
	versionID := uuid.New().String()
	contentHash := hashContent(content)

	_, err = tx.Exec(ctx, `
        INSERT INTO skill_versions (id, skill_id, version, content, content_hash, author, commit_message, parent_version_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
    `, versionID, id, newVersion, content, contentHash, author, commitMessage, currentVersionID)
	if err != nil {
		return nil, fmt.Errorf("insert skill version: %w", err)
	}

	// 4. Update skill's current_version_id
	_, err = tx.Exec(ctx, `
        UPDATE skills SET current_version_id = $1, updated_at = NOW() WHERE id = $2
    `, versionID, id)
	if err != nil {
		return nil, fmt.Errorf("update skill current_version_id: %w", err)
	}

	if err := tx.Commit(ctx); err != nil {
		return nil, fmt.Errorf("commit tx: %w", err)
	}

	// 5. Return new version
	return &SkillVersion{
		ID:              versionID,
		SkillID:         id,
		Version:         newVersion,
		Content:         content,
		ContentHash:     contentHash,
		Author:          author,
		CommitMessage:   commitMessage,
		ParentVersionID: &currentVersionID,
		CreatedAt:       time.Now(),
	}, nil
}

// DeleteSkill marks a skill as inactive
func (s *SkillService) DeleteSkill(ctx context.Context, id string) error {
	result, err := s.db.Exec(ctx, `
        UPDATE skills SET status = 'inactive', updated_at = NOW() WHERE id = $1
    `, id)
	if err != nil {
		return fmt.Errorf("delete skill: %w", err)
	}

	if result.RowsAffected() == 0 {
		return fmt.Errorf("skill not found: %s", id)
	}

	return nil
}

func (s *SkillService) getSkillByID(ctx context.Context, id string) (*Skill, error) {
	query := `SELECT id, name, description, category, owner, current_version_id, status, created_at, updated_at, metadata FROM skills WHERE id = $1`
	var skill Skill
	var metadataJSON []byte

	err := s.db.QueryRow(ctx, query, id).Scan(
		&skill.ID,
		&skill.Name,
		&skill.Description,
		&skill.Category,
		&skill.Owner,
		&skill.CurrentVersionID,
		&skill.Status,
		&skill.CreatedAt,
		&skill.UpdatedAt,
		&metadataJSON,
	)
	if err != nil {
		return nil, fmt.Errorf("get skill by id: %w", err)
	}

	// Parse JSONB metadata
	if metadataJSON != nil {
		if err := json.Unmarshal(metadataJSON, &skill.Metadata); err != nil {
			return nil, fmt.Errorf("unmarshal metadata: %w", err)
		}
	}

	return &skill, nil
}

func hashContent(content string) string {
	hash := sha256.Sum256([]byte(content))
	return hex.EncodeToString(hash[:])
}

func incrementVersion(version string) string {
	// Parse semver: v1.2.3 → v1.2.4
	version = strings.TrimPrefix(version, "v")
	parts := strings.Split(version, ".")

	if len(parts) != 3 {
		// Fallback for non-standard versions
		return "v" + version + "-next"
	}

	// Increment patch version
	patch, err := strconv.Atoi(parts[2])
	if err != nil {
		return "v" + version + "-next"
	}

	parts[2] = strconv.Itoa(patch + 1)
	return "v" + strings.Join(parts, ".")
}
