package domain
import "time"

// DecisionStatistics 决策统计（为 Web API 使用）
type DecisionStatistics struct {
	Total              int                    `json:"total"`
	Executed           int                    `json:"executed"`
	Pending            int                    `json:"pending"`
	AvgConfidence      float64                `json:"avgConfidence"`
	TypeDistribution   []DistributionItem     `json:"typeDistribution"`
	StatusDistribution []DistributionItem     `json:"statusDistribution"`
}

// DistributionItem 分布项
type DistributionItem struct {
	Name  string `json:"name"`
	Value int    `json:"value"`
}

// DecisionListRequest 决策列表请求（为 Web API 使用）
type DecisionListRequest struct {
	Action string `json:"action"`
	Status string `json:"status"`
	Limit  int    `json:"limit"`
}

// DecisionWeb Web API 决策视图（扩展字段）
type DecisionWeb struct {
	Decision           // 嵌入原有的 Decision
	Target   *string   `json:"target,omitempty" db:"target"`
	Status   *string   `json:"status,omitempty" db:"status"`
	PnL      *float64  `json:"pnl,omitempty" db:"pnl"`
	Timeline []byte    `json:"timeline,omitempty" db:"timeline"`
	Data     []byte    `json:"data,omitempty" db:"data"`
	UpdatedAt *time.Time `json:"updated_at,omitempty" db:"updated_at"`
}
