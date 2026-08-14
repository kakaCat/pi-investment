package service

import (
	"fmt"
	"time"

	"github.com/google/uuid"

	"github.com/pi-investment/agent-os/internal/domain"
)

type decisionService struct {
	repo domain.DecisionRepository
}

// NewDecisionService creates a new decision service
func NewDecisionService(repo domain.DecisionRepository) domain.DecisionService {
	return &decisionService{
		repo: repo,
	}
}

// Record creates a new decision
func (s *decisionService) Record(agentID string, action domain.DecisionAction, targets []string, reason string, confidence float64, context map[string]interface{}) (*domain.Decision, error) {
	// Create decision object
	decision := &domain.Decision{
		AgentID:    agentID,
		Action:     action,
		Targets:    targets,
		Reason:     reason,
		Confidence: confidence,
		Context:    context,
	}

	// Validate
	if err := decision.Validate(); err != nil {
		return nil, err
	}

	// Save to repository
	if err := s.repo.Create(decision); err != nil {
		return nil, fmt.Errorf("failed to record decision: %w", err)
	}

	return decision, nil
}

// Get retrieves a decision by ID
func (s *decisionService) Get(id uuid.UUID) (*domain.Decision, error) {
	return s.repo.GetByID(id)
}

// Update updates a decision's outcome
func (s *decisionService) Update(id uuid.UUID, outcome map[string]interface{}) error {
	// Get existing decision
	decision, err := s.repo.GetByID(id)
	if err != nil {
		return err
	}

	// Update outcome and execution time
	decision.Outcome = outcome
	if !decision.IsExecuted() {
		now := time.Now()
		decision.ExecutedAt = &now
	}

	// Save to repository
	return s.repo.Update(decision)
}

// Delete removes a decision
func (s *decisionService) Delete(id uuid.UUID) error {
	return s.repo.Delete(id)
}

// List retrieves decisions based on filter
func (s *decisionService) List(filter *domain.DecisionFilter) ([]*domain.Decision, error) {
	// Set default limit if not specified
	if filter.Limit == 0 {
		filter.Limit = 20
	}

	return s.repo.List(filter)
}

// ListByAgent retrieves decisions for a specific agent
func (s *decisionService) ListByAgent(agentID string, limit, offset int) ([]*domain.Decision, error) {
	if limit == 0 {
		limit = 20
	}

	filter := &domain.DecisionFilter{
		AgentID: agentID,
		Limit:   limit,
		Offset:  offset,
	}

	return s.repo.List(filter)
}

// ListByAction retrieves decisions for a specific agent and action
func (s *decisionService) ListByAction(agentID string, action domain.DecisionAction, limit, offset int) ([]*domain.Decision, error) {
	if limit == 0 {
		limit = 20
	}

	filter := &domain.DecisionFilter{
		AgentID: agentID,
		Action:  action,
		Limit:   limit,
		Offset:  offset,
	}

	return s.repo.List(filter)
}

// GetStats returns statistics about decisions for an agent
func (s *decisionService) GetStats(agentID string) (map[string]interface{}, error) {
	// Get total count
	totalCount, err := s.repo.CountByAgent(agentID)
	if err != nil {
		return nil, fmt.Errorf("failed to get total count: %w", err)
	}

	// Get counts by action
	watchCount, err := s.repo.CountByAction(agentID, domain.ActionWatch)
	if err != nil {
		return nil, fmt.Errorf("failed to get watch count: %w", err)
	}

	buyCount, err := s.repo.CountByAction(agentID, domain.ActionBuy)
	if err != nil {
		return nil, fmt.Errorf("failed to get buy count: %w", err)
	}

	sellCount, err := s.repo.CountByAction(agentID, domain.ActionSell)
	if err != nil {
		return nil, fmt.Errorf("failed to get sell count: %w", err)
	}

	holdCount, err := s.repo.CountByAction(agentID, domain.ActionHold)
	if err != nil {
		return nil, fmt.Errorf("failed to get hold count: %w", err)
	}

	// Get recent decisions
	recentDecisions, err := s.ListByAgent(agentID, 10, 0)
	if err != nil {
		return nil, fmt.Errorf("failed to get recent decisions: %w", err)
	}

	// Count executed vs pending
	executedCount := 0
	for _, d := range recentDecisions {
		if d.IsExecuted() {
			executedCount++
		}
	}

	stats := map[string]interface{}{
		"total_decisions": totalCount,
		"by_action": map[string]int64{
			"watch": watchCount,
			"buy":   buyCount,
			"sell":  sellCount,
			"hold":  holdCount,
		},
		"recent_executed": executedCount,
		"recent_pending":  len(recentDecisions) - executedCount,
	}

	return stats, nil
}
