package domain

import (
	"errors"
	"time"

	"github.com/google/uuid"
)

// Decision-specific errors
var (
	ErrDecisionNotFound = errors.New("decision not found")
	ErrInvalidAction    = errors.New("invalid action")
	ErrInvalidConfidence = errors.New("confidence must be between 0 and 1")
)

// DecisionAction represents the type of investment decision
type DecisionAction string

const (
	ActionWatch DecisionAction = "watch"
	ActionBuy   DecisionAction = "buy"
	ActionSell  DecisionAction = "sell"
	ActionHold  DecisionAction = "hold"
)

// Decision represents an investment decision made by an agent
type Decision struct {
	ID          uuid.UUID              `json:"id"`
	AgentID     string                 `json:"agent_id"`
	Action      DecisionAction         `json:"action"`
	Targets     []string               `json:"targets"`      // Stock symbols
	Reason      string                 `json:"reason"`       // Decision rationale
	Confidence  float64                `json:"confidence"`   // [0, 1]
	Context     map[string]interface{} `json:"context"`      // Decision context
	CreatedAt   time.Time              `json:"created_at"`
	ExecutedAt  *time.Time             `json:"executed_at"`  // When executed
	Outcome     map[string]interface{} `json:"outcome"`      // Execution result
}

// DecisionFilter represents filtering criteria for decisions
type DecisionFilter struct {
	AgentID    string         `json:"agent_id,omitempty"`
	Action     DecisionAction `json:"action,omitempty"`
	Executed   *bool          `json:"executed,omitempty"` // nil = all, true = executed, false = pending
	StartTime  *time.Time     `json:"start_time,omitempty"`
	EndTime    *time.Time     `json:"end_time,omitempty"`
	Limit      int            `json:"limit"`
	Offset     int            `json:"offset"`
}

// Validate validates the decision data
func (d *Decision) Validate() error {
	if d.AgentID == "" {
		return errors.New("agent_id is required")
	}
	if d.Action == "" {
		return ErrInvalidAction
	}
	if d.Action != ActionWatch && d.Action != ActionBuy && d.Action != ActionSell && d.Action != ActionHold {
		return ErrInvalidAction
	}
	if len(d.Targets) == 0 {
		return errors.New("targets cannot be empty")
	}
	if d.Confidence < 0 || d.Confidence > 1 {
		return ErrInvalidConfidence
	}
	return nil
}

// IsExecuted returns true if the decision has been executed
func (d *Decision) IsExecuted() bool {
	return d.ExecutedAt != nil
}

// DecisionRepository defines the interface for decision data access
type DecisionRepository interface {
	// Write operations
	Create(decision *Decision) error
	Update(decision *Decision) error
	Delete(id uuid.UUID) error

	// Read operations
	GetByID(id uuid.UUID) (*Decision, error)
	List(filter *DecisionFilter) ([]*Decision, error)

	// Statistics
	CountByAgent(agentID string) (int64, error)
	CountByAction(agentID string, action DecisionAction) (int64, error)
}

// DecisionService defines the interface for decision business logic
type DecisionService interface {
	// Core operations
	Record(agentID string, action DecisionAction, targets []string, reason string, confidence float64, context map[string]interface{}) (*Decision, error)
	Get(id uuid.UUID) (*Decision, error)
	Update(id uuid.UUID, outcome map[string]interface{}) error
	Delete(id uuid.UUID) error

	// Query operations
	List(filter *DecisionFilter) ([]*Decision, error)
	ListByAgent(agentID string, limit, offset int) ([]*Decision, error)
	ListByAction(agentID string, action DecisionAction, limit, offset int) ([]*Decision, error)

	// Statistics
	GetStats(agentID string) (map[string]interface{}, error)
}
