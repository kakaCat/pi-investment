package repository

import (
	"context"
	"database/sql"
	"fmt"

	"github.com/lib/pq"
	"github.com/pi-investment/agent-os/internal/domain"
)

// ProfileWebRepository Web API 用户配置仓储接口
type ProfileWebRepository interface {
	GetProfile(ctx context.Context, username string) (*domain.UserProfile, error)
	UpdateProfile(ctx context.Context, username string, req domain.UpdateProfileRequest) error
	GetAPIKeys(ctx context.Context, username string) ([]*domain.APIKey, error)
	GetActivityLogs(ctx context.Context, username string, req domain.ActivityLogsRequest) ([]*domain.UserActivityLog, error)
}

type profileWebRepository struct {
	db *sql.DB
}

// NewProfileWebRepository 创建 Web API 用户配置仓储
func NewProfileWebRepository(db *sql.DB) ProfileWebRepository {
	return &profileWebRepository{db: db}
}

// GetProfile 获取用户配置
func (r *profileWebRepository) GetProfile(ctx context.Context, username string) (*domain.UserProfile, error) {
	query := `SELECT id, username, email, avatar_url, display_name, bio, preferences, created_at, updated_at
	          FROM user_profiles WHERE username = $1`
	
	var p domain.UserProfile
	err := r.db.QueryRowContext(ctx, query, username).Scan(
		&p.ID, &p.Username, &p.Email, &p.AvatarURL, &p.DisplayName,
		&p.Bio, &p.Preferences, &p.CreatedAt, &p.UpdatedAt,
	)
	
	if err == sql.ErrNoRows {
		return nil, fmt.Errorf("user not found: %s", username)
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get profile: %w", err)
	}
	
	return &p, nil
}

// UpdateProfile 更新用户配置
func (r *profileWebRepository) UpdateProfile(ctx context.Context, username string, req domain.UpdateProfileRequest) error {
	query := `UPDATE user_profiles 
	          SET email = COALESCE($1, email),
	              display_name = COALESCE($2, display_name),
	              bio = COALESCE($3, bio),
	              preferences = COALESCE($4, preferences),
	              updated_at = NOW()
	          WHERE username = $5`
	
	_, err := r.db.ExecContext(ctx, query,
		req.Email, req.DisplayName, req.Bio, req.Preferences, username)
	if err != nil {
		return fmt.Errorf("failed to update profile: %w", err)
	}
	
	return nil
}

// GetAPIKeys 获取用户的 API 密钥列表
func (r *profileWebRepository) GetAPIKeys(ctx context.Context, username string) ([]*domain.APIKey, error) {
	query := `SELECT k.id, k.name, k.key_prefix, k.user_id, k.permissions, k.expires_at, k.last_used_at, k.created_at
	          FROM api_keys k
	          JOIN user_profiles u ON k.user_id = u.id
	          WHERE u.username = $1
	          ORDER BY k.created_at DESC`
	
	rows, err := r.db.QueryContext(ctx, query, username)
	if err != nil {
		return nil, fmt.Errorf("failed to query api keys: %w", err)
	}
	defer rows.Close()
	
	var keys []*domain.APIKey
	for rows.Next() {
		var k domain.APIKey
		err := rows.Scan(
			&k.ID, &k.Name, &k.KeyPrefix, &k.UserID,
			pq.Array(&k.Permissions), &k.ExpiresAt, &k.LastUsedAt, &k.CreatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan api key: %w", err)
		}
		keys = append(keys, &k)
	}
	
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows iteration error: %w", err)
	}
	
	return keys, nil
}

// GetActivityLogs 获取用户活动日志
func (r *profileWebRepository) GetActivityLogs(ctx context.Context, username string, req domain.ActivityLogsRequest) ([]*domain.UserActivityLog, error) {
	query := `SELECT l.id, l.user_id, l.action, l.resource, l.details, l.ip_address, l.user_agent, l.timestamp
	          FROM user_activity_logs l
	          JOIN user_profiles u ON l.user_id = u.id
	          WHERE u.username = $1
	          ORDER BY l.timestamp DESC`
	
	if req.Limit > 0 {
		query += fmt.Sprintf(" LIMIT %d", req.Limit)
	} else {
		query += " LIMIT 50"
	}
	
	rows, err := r.db.QueryContext(ctx, query, username)
	if err != nil {
		return nil, fmt.Errorf("failed to query activity logs: %w", err)
	}
	defer rows.Close()
	
	var logs []*domain.UserActivityLog
	for rows.Next() {
		var l domain.UserActivityLog
		err := rows.Scan(
			&l.ID, &l.UserID, &l.Action, &l.Resource, &l.Details,
			&l.IPAddress, &l.UserAgent, &l.Timestamp,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan activity log: %w", err)
		}
		logs = append(logs, &l)
	}
	
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("rows iteration error: %w", err)
	}
	
	return logs, nil
}
