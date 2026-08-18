package domain

import (
	"encoding/json"
	"time"

	"github.com/google/uuid"
)

// EvolutionRun 策略进化运行记录
type EvolutionRun struct {
	ID                 uuid.UUID       `json:"id"`
	StrategyID         string          `json:"strategy_id"`
	Mode               string          `json:"mode"`
	Generations        int             `json:"generations"`
	Status             string          `json:"status"` // running | completed | failed
	Fitness            float64         `json:"fitness,omitempty"`
	FitnessImprovement float64         `json:"fitness_improvement,omitempty"`
	Proposals          json.RawMessage `json:"proposals,omitempty"`
	BestParams         json.RawMessage `json:"best_params,omitempty"`
	CreatedAt          time.Time       `json:"created_at"`
	CompletedAt        *time.Time      `json:"completed_at,omitempty"`
}

// EvolutionRunRequest 进化运行请求（POST /api/v1/evolution/run）
// strategy_id 兼容数字（203）与字符串（"203"）两种形式
type EvolutionRunRequest struct {
	StrategyID  json.Number `json:"strategy_id"`
	Mode        string      `json:"mode"`
	Generations int         `json:"generations"`
}

// EvolutionLeaderboardEntry 排行榜条目
type EvolutionLeaderboardEntry struct {
	StrategyID string    `json:"strategy_id"`
	Fitness    float64   `json:"fitness"`
	RunID      uuid.UUID `json:"run_id"`
	Mode       string    `json:"mode"`
	UpdatedAt  time.Time `json:"updated_at"`
}
