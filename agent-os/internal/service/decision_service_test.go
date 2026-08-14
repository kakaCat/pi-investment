package service

import (
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/mock"

	"github.com/pi-investment/agent-os/internal/domain"
)

// MockDecisionRepository is a mock implementation of DecisionRepository
type MockDecisionRepository struct {
	mock.Mock
}

func (m *MockDecisionRepository) Create(decision *domain.Decision) error {
	args := m.Called(decision)
	return args.Error(0)
}

func (m *MockDecisionRepository) Update(decision *domain.Decision) error {
	args := m.Called(decision)
	return args.Error(0)
}

func (m *MockDecisionRepository) Delete(id uuid.UUID) error {
	args := m.Called(id)
	return args.Error(0)
}

func (m *MockDecisionRepository) GetByID(id uuid.UUID) (*domain.Decision, error) {
	args := m.Called(id)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).(*domain.Decision), args.Error(1)
}

func (m *MockDecisionRepository) List(filter *domain.DecisionFilter) ([]*domain.Decision, error) {
	args := m.Called(filter)
	if args.Get(0) == nil {
		return nil, args.Error(1)
	}
	return args.Get(0).([]*domain.Decision), args.Error(1)
}

func (m *MockDecisionRepository) CountByAgent(agentID string) (int64, error) {
	args := m.Called(agentID)
	return args.Get(0).(int64), args.Error(1)
}

func (m *MockDecisionRepository) CountByAction(agentID string, action domain.DecisionAction) (int64, error) {
	args := m.Called(agentID, action)
	return args.Get(0).(int64), args.Error(1)
}

func TestDecisionService_Record(t *testing.T) {
	tests := []struct {
		name        string
		agentID     string
		action      domain.DecisionAction
		targets     []string
		reason      string
		confidence  float64
		context     map[string]interface{}
		expectError bool
	}{
		{
			name:        "Valid watch decision",
			agentID:     "fin-agent",
			action:      domain.ActionWatch,
			targets:     []string{"600519.SH", "000858.SZ"},
			reason:      "Technical breakout",
			confidence:  0.85,
			context:     map[string]interface{}{"signal": "buy"},
			expectError: false,
		},
		{
			name:        "Valid buy decision",
			agentID:     "fin-agent",
			action:      domain.ActionBuy,
			targets:     []string{"600519.SH"},
			reason:      "Value opportunity",
			confidence:  0.75,
			context:     map[string]interface{}{},
			expectError: false,
		},
		{
			name:        "Invalid - empty agent ID",
			agentID:     "",
			action:      domain.ActionWatch,
			targets:     []string{"600519.SH"},
			reason:      "Test",
			confidence:  0.5,
			context:     nil,
			expectError: true,
		},
		{
			name:        "Invalid - empty targets",
			agentID:     "fin-agent",
			action:      domain.ActionWatch,
			targets:     []string{},
			reason:      "Test",
			confidence:  0.5,
			context:     nil,
			expectError: true,
		},
		{
			name:        "Invalid - confidence out of range",
			agentID:     "fin-agent",
			action:      domain.ActionWatch,
			targets:     []string{"600519.SH"},
			reason:      "Test",
			confidence:  1.5,
			context:     nil,
			expectError: true,
		},
		{
			name:        "Invalid - invalid action",
			agentID:     "fin-agent",
			action:      "invalid",
			targets:     []string{"600519.SH"},
			reason:      "Test",
			confidence:  0.5,
			context:     nil,
			expectError: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Create a new mock for each test
			localMock := new(MockDecisionRepository)
			localSvc := NewDecisionService(localMock)

			if !tt.expectError {
				localMock.On("Create", mock.AnythingOfType("*domain.Decision")).Run(func(args mock.Arguments) {
					// Simulate the repository setting an ID
					decision := args.Get(0).(*domain.Decision)
					if decision.ID == uuid.Nil {
						decision.ID = uuid.New()
					}
				}).Return(nil).Once()
			}

			decision, err := localSvc.Record(tt.agentID, tt.action, tt.targets, tt.reason, tt.confidence, tt.context)

			if tt.expectError {
				assert.Error(t, err)
				assert.Nil(t, decision)
			} else {
				assert.NoError(t, err)
				assert.NotNil(t, decision)
				assert.Equal(t, tt.agentID, decision.AgentID)
				assert.Equal(t, tt.action, decision.Action)
				assert.Equal(t, tt.targets, decision.Targets)
				assert.Equal(t, tt.reason, decision.Reason)
				assert.Equal(t, tt.confidence, decision.Confidence)
				assert.NotEqual(t, uuid.Nil, decision.ID)
			}

			localMock.AssertExpectations(t)
		})
	}
}

func TestDecisionService_Get(t *testing.T) {
	mockRepo := new(MockDecisionRepository)
	svc := NewDecisionService(mockRepo)

	id := uuid.New()
	expectedDecision := &domain.Decision{
		ID:         id,
		AgentID:    "fin-agent",
		Action:     domain.ActionWatch,
		Targets:    []string{"600519.SH"},
		Reason:     "Test",
		Confidence: 0.8,
		CreatedAt:  time.Now(),
	}

	mockRepo.On("GetByID", id).Return(expectedDecision, nil).Once()

	decision, err := svc.Get(id)

	assert.NoError(t, err)
	assert.Equal(t, expectedDecision, decision)
	mockRepo.AssertExpectations(t)
}

func TestDecisionService_Get_NotFound(t *testing.T) {
	mockRepo := new(MockDecisionRepository)
	svc := NewDecisionService(mockRepo)

	id := uuid.New()
	mockRepo.On("GetByID", id).Return(nil, domain.ErrDecisionNotFound).Once()

	decision, err := svc.Get(id)

	assert.Error(t, err)
	assert.Nil(t, decision)
	assert.Equal(t, domain.ErrDecisionNotFound, err)
	mockRepo.AssertExpectations(t)
}

func TestDecisionService_Update(t *testing.T) {
	mockRepo := new(MockDecisionRepository)
	svc := NewDecisionService(mockRepo)

	id := uuid.New()
	existingDecision := &domain.Decision{
		ID:         id,
		AgentID:    "fin-agent",
		Action:     domain.ActionBuy,
		Targets:    []string{"600519.SH"},
		Reason:     "Test",
		Confidence: 0.8,
		CreatedAt:  time.Now(),
	}

	outcome := map[string]interface{}{
		"status": "executed",
		"profit": 0.05,
	}

	mockRepo.On("GetByID", id).Return(existingDecision, nil).Once()
	mockRepo.On("Update", mock.AnythingOfType("*domain.Decision")).Return(nil).Once()

	err := svc.Update(id, outcome)

	assert.NoError(t, err)
	mockRepo.AssertExpectations(t)
}

func TestDecisionService_Delete(t *testing.T) {
	mockRepo := new(MockDecisionRepository)
	svc := NewDecisionService(mockRepo)

	id := uuid.New()
	mockRepo.On("Delete", id).Return(nil).Once()

	err := svc.Delete(id)

	assert.NoError(t, err)
	mockRepo.AssertExpectations(t)
}

func TestDecisionService_List(t *testing.T) {
	mockRepo := new(MockDecisionRepository)
	svc := NewDecisionService(mockRepo)

	filter := &domain.DecisionFilter{
		AgentID: "fin-agent",
		Action:  domain.ActionWatch,
		Limit:   10,
		Offset:  0,
	}

	expectedDecisions := []*domain.Decision{
		{
			ID:         uuid.New(),
			AgentID:    "fin-agent",
			Action:     domain.ActionWatch,
			Targets:    []string{"600519.SH"},
			Confidence: 0.8,
			CreatedAt:  time.Now(),
		},
		{
			ID:         uuid.New(),
			AgentID:    "fin-agent",
			Action:     domain.ActionWatch,
			Targets:    []string{"000858.SZ"},
			Confidence: 0.75,
			CreatedAt:  time.Now(),
		},
	}

	mockRepo.On("List", filter).Return(expectedDecisions, nil).Once()

	decisions, err := svc.List(filter)

	assert.NoError(t, err)
	assert.Equal(t, len(expectedDecisions), len(decisions))
	assert.Equal(t, expectedDecisions, decisions)
	mockRepo.AssertExpectations(t)
}

func TestDecisionService_List_DefaultLimit(t *testing.T) {
	mockRepo := new(MockDecisionRepository)
	svc := NewDecisionService(mockRepo)

	filter := &domain.DecisionFilter{
		AgentID: "fin-agent",
	}

	mockRepo.On("List", mock.MatchedBy(func(f *domain.DecisionFilter) bool {
		return f.Limit == 20 // Default limit
	})).Return([]*domain.Decision{}, nil).Once()

	_, err := svc.List(filter)

	assert.NoError(t, err)
	mockRepo.AssertExpectations(t)
}

func TestDecisionService_ListByAgent(t *testing.T) {
	mockRepo := new(MockDecisionRepository)
	svc := NewDecisionService(mockRepo)

	agentID := "fin-agent"
	expectedDecisions := []*domain.Decision{
		{
			ID:         uuid.New(),
			AgentID:    agentID,
			Action:     domain.ActionWatch,
			Targets:    []string{"600519.SH"},
			Confidence: 0.8,
			CreatedAt:  time.Now(),
		},
	}

	mockRepo.On("List", mock.MatchedBy(func(f *domain.DecisionFilter) bool {
		return f.AgentID == agentID && f.Limit == 20
	})).Return(expectedDecisions, nil).Once()

	decisions, err := svc.ListByAgent(agentID, 0, 0)

	assert.NoError(t, err)
	assert.Equal(t, expectedDecisions, decisions)
	mockRepo.AssertExpectations(t)
}

func TestDecisionService_ListByAction(t *testing.T) {
	mockRepo := new(MockDecisionRepository)
	svc := NewDecisionService(mockRepo)

	agentID := "fin-agent"
	action := domain.ActionBuy
	expectedDecisions := []*domain.Decision{
		{
			ID:         uuid.New(),
			AgentID:    agentID,
			Action:     action,
			Targets:    []string{"600519.SH"},
			Confidence: 0.8,
			CreatedAt:  time.Now(),
		},
	}

	mockRepo.On("List", mock.MatchedBy(func(f *domain.DecisionFilter) bool {
		return f.AgentID == agentID && f.Action == action && f.Limit == 20
	})).Return(expectedDecisions, nil).Once()

	decisions, err := svc.ListByAction(agentID, action, 0, 0)

	assert.NoError(t, err)
	assert.Equal(t, expectedDecisions, decisions)
	mockRepo.AssertExpectations(t)
}

func TestDecisionService_GetStats(t *testing.T) {
	mockRepo := new(MockDecisionRepository)
	svc := NewDecisionService(mockRepo)

	agentID := "fin-agent"

	// Mock count calls
	mockRepo.On("CountByAgent", agentID).Return(int64(100), nil).Once()
	mockRepo.On("CountByAction", agentID, domain.ActionWatch).Return(int64(40), nil).Once()
	mockRepo.On("CountByAction", agentID, domain.ActionBuy).Return(int64(30), nil).Once()
	mockRepo.On("CountByAction", agentID, domain.ActionSell).Return(int64(20), nil).Once()
	mockRepo.On("CountByAction", agentID, domain.ActionHold).Return(int64(10), nil).Once()

	// Mock recent decisions
	now := time.Now()
	executedAt := now.Add(-time.Hour)
	recentDecisions := []*domain.Decision{
		{
			ID:         uuid.New(),
			AgentID:    agentID,
			Action:     domain.ActionBuy,
			ExecutedAt: &executedAt,
		},
		{
			ID:      uuid.New(),
			AgentID: agentID,
			Action:  domain.ActionWatch,
		},
	}

	mockRepo.On("List", mock.MatchedBy(func(f *domain.DecisionFilter) bool {
		return f.AgentID == agentID && f.Limit == 10
	})).Return(recentDecisions, nil).Once()

	stats, err := svc.GetStats(agentID)

	assert.NoError(t, err)
	assert.NotNil(t, stats)
	assert.Equal(t, int64(100), stats["total_decisions"])

	byAction := stats["by_action"].(map[string]int64)
	assert.Equal(t, int64(40), byAction["watch"])
	assert.Equal(t, int64(30), byAction["buy"])
	assert.Equal(t, int64(20), byAction["sell"])
	assert.Equal(t, int64(10), byAction["hold"])

	assert.Equal(t, 1, stats["recent_executed"])
	assert.Equal(t, 1, stats["recent_pending"])

	mockRepo.AssertExpectations(t)
}
