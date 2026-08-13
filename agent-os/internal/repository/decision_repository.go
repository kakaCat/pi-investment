package repository

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"time"

	"github.com/google/uuid"
	"github.com/lib/pq"

	"github.com/pi-investment/agent-os/internal/domain"
)

type decisionRepository struct {
	db *sql.DB
}

// NewDecisionRepository creates a new decision repository
func NewDecisionRepository(db *sql.DB) domain.DecisionRepository {
	return &decisionRepository{db: db}
}

// Create inserts a new decision into the database
func (r *decisionRepository) Create(decision *domain.Decision) error {
	query := `
		INSERT INTO decisions (id, agent_id, action, targets, reason, confidence, context, created_at, executed_at, outcome)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
	`

	if decision.ID == uuid.Nil {
		decision.ID = uuid.New()
	}

	if decision.CreatedAt.IsZero() {
		decision.CreatedAt = time.Now()
	}

	// Serialize context
	contextJSON, err := json.Marshal(decision.Context)
	if err != nil {
		return fmt.Errorf("failed to marshal context: %w", err)
	}

	// Serialize outcome
	outcomeJSON, err := json.Marshal(decision.Outcome)
	if err != nil {
		return fmt.Errorf("failed to marshal outcome: %w", err)
	}

	_, err = r.db.Exec(query,
		decision.ID,
		decision.AgentID,
		decision.Action,
		pq.Array(decision.Targets),
		decision.Reason,
		decision.Confidence,
		contextJSON,
		decision.CreatedAt,
		decision.ExecutedAt,
		outcomeJSON,
	)

	if err != nil {
		return fmt.Errorf("failed to create decision: %w", err)
	}

	return nil
}

// Update updates an existing decision
func (r *decisionRepository) Update(decision *domain.Decision) error {
	query := `
		UPDATE decisions
		SET action = $1, targets = $2, reason = $3, confidence = $4, context = $5, executed_at = $6, outcome = $7
		WHERE id = $8
	`

	// Serialize context
	contextJSON, err := json.Marshal(decision.Context)
	if err != nil {
		return fmt.Errorf("failed to marshal context: %w", err)
	}

	// Serialize outcome
	outcomeJSON, err := json.Marshal(decision.Outcome)
	if err != nil {
		return fmt.Errorf("failed to marshal outcome: %w", err)
	}

	result, err := r.db.Exec(query,
		decision.Action,
		pq.Array(decision.Targets),
		decision.Reason,
		decision.Confidence,
		contextJSON,
		decision.ExecutedAt,
		outcomeJSON,
		decision.ID,
	)

	if err != nil {
		return fmt.Errorf("failed to update decision: %w", err)
	}

	rows, _ := result.RowsAffected()
	if rows == 0 {
		return domain.ErrDecisionNotFound
	}

	return nil
}

// Delete removes a decision from the database
func (r *decisionRepository) Delete(id uuid.UUID) error {
	query := `DELETE FROM decisions WHERE id = $1`

	result, err := r.db.Exec(query, id)
	if err != nil {
		return fmt.Errorf("failed to delete decision: %w", err)
	}

	rows, _ := result.RowsAffected()
	if rows == 0 {
		return domain.ErrDecisionNotFound
	}

	return nil
}

// GetByID retrieves a decision by ID
func (r *decisionRepository) GetByID(id uuid.UUID) (*domain.Decision, error) {
	query := `
		SELECT id, agent_id, action, targets, reason, confidence, context, created_at, executed_at, outcome
		FROM decisions
		WHERE id = $1
	`

	decision := &domain.Decision{}
	var contextJSON []byte
	var outcomeJSON []byte
	var targets []string

	err := r.db.QueryRow(query, id).Scan(
		&decision.ID,
		&decision.AgentID,
		&decision.Action,
		pq.Array(&targets),
		&decision.Reason,
		&decision.Confidence,
		&contextJSON,
		&decision.CreatedAt,
		&decision.ExecutedAt,
		&outcomeJSON,
	)

	if err == sql.ErrNoRows {
		return nil, domain.ErrDecisionNotFound
	}
	if err != nil {
		return nil, fmt.Errorf("failed to get decision: %w", err)
	}

	decision.Targets = targets

	// Deserialize context
	if contextJSON != nil {
		if err := json.Unmarshal(contextJSON, &decision.Context); err != nil {
			return nil, fmt.Errorf("failed to unmarshal context: %w", err)
		}
	}

	// Deserialize outcome
	if outcomeJSON != nil {
		if err := json.Unmarshal(outcomeJSON, &decision.Outcome); err != nil {
			return nil, fmt.Errorf("failed to unmarshal outcome: %w", err)
		}
	}

	return decision, nil
}

// List retrieves decisions based on filter criteria
func (r *decisionRepository) List(filter *domain.DecisionFilter) ([]*domain.Decision, error) {
	query := `
		SELECT id, agent_id, action, targets, reason, confidence, context, created_at, executed_at, outcome
		FROM decisions
		WHERE 1=1
	`

	args := []interface{}{}
	argIndex := 1

	// Add agent_id filter
	if filter.AgentID != "" {
		query += fmt.Sprintf(" AND agent_id = $%d", argIndex)
		args = append(args, filter.AgentID)
		argIndex++
	}

	// Add action filter
	if filter.Action != "" {
		query += fmt.Sprintf(" AND action = $%d", argIndex)
		args = append(args, filter.Action)
		argIndex++
	}

	// Add executed filter
	if filter.Executed != nil {
		if *filter.Executed {
			query += " AND executed_at IS NOT NULL"
		} else {
			query += " AND executed_at IS NULL"
		}
	}

	// Add time range filters
	if filter.StartTime != nil {
		query += fmt.Sprintf(" AND created_at >= $%d", argIndex)
		args = append(args, *filter.StartTime)
		argIndex++
	}

	if filter.EndTime != nil {
		query += fmt.Sprintf(" AND created_at <= $%d", argIndex)
		args = append(args, *filter.EndTime)
		argIndex++
	}

	// Order by created_at descending
	query += " ORDER BY created_at DESC"

	// Add pagination
	query += fmt.Sprintf(" LIMIT $%d OFFSET $%d", argIndex, argIndex+1)
	args = append(args, filter.Limit, filter.Offset)

	rows, err := r.db.Query(query, args...)
	if err != nil {
		return nil, fmt.Errorf("failed to list decisions: %w", err)
	}
	defer rows.Close()

	return r.scanDecisions(rows)
}

// CountByAgent returns the total number of decisions for an agent
func (r *decisionRepository) CountByAgent(agentID string) (int64, error) {
	query := `SELECT COUNT(*) FROM decisions WHERE agent_id = $1`

	var count int64
	err := r.db.QueryRow(query, agentID).Scan(&count)
	if err != nil {
		return 0, fmt.Errorf("failed to count decisions: %w", err)
	}

	return count, nil
}

// CountByAction returns the number of decisions for an agent and action
func (r *decisionRepository) CountByAction(agentID string, action domain.DecisionAction) (int64, error) {
	query := `SELECT COUNT(*) FROM decisions WHERE agent_id = $1 AND action = $2`

	var count int64
	err := r.db.QueryRow(query, agentID, action).Scan(&count)
	if err != nil {
		return 0, fmt.Errorf("failed to count decisions by action: %w", err)
	}

	return count, nil
}

// Helper function to scan multiple decisions
func (r *decisionRepository) scanDecisions(rows *sql.Rows) ([]*domain.Decision, error) {
	var decisions []*domain.Decision

	for rows.Next() {
		decision := &domain.Decision{}
		var contextJSON []byte
		var outcomeJSON []byte
		var targets []string

		err := rows.Scan(
			&decision.ID,
			&decision.AgentID,
			&decision.Action,
			pq.Array(&targets),
			&decision.Reason,
			&decision.Confidence,
			&contextJSON,
			&decision.CreatedAt,
			&decision.ExecutedAt,
			&outcomeJSON,
		)

		if err != nil {
			return nil, fmt.Errorf("failed to scan decision: %w", err)
		}

		decision.Targets = targets

		// Deserialize context
		if contextJSON != nil {
			if err := json.Unmarshal(contextJSON, &decision.Context); err != nil {
				return nil, fmt.Errorf("failed to unmarshal context: %w", err)
			}
		}

		// Deserialize outcome
		if outcomeJSON != nil {
			if err := json.Unmarshal(outcomeJSON, &decision.Outcome); err != nil {
				return nil, fmt.Errorf("failed to unmarshal outcome: %w", err)
			}
		}

		decisions = append(decisions, decision)
	}

	return decisions, rows.Err()
}
