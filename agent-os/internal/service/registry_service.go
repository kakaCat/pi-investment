package service

import (
	"fmt"
	"time"

	"github.com/pi-investment/agent-os/internal/domain"
	"github.com/pi-investment/agent-os/internal/repository"
)

// RegistryService defines the interface for agent registry operations
type RegistryService interface {
	Register(req *domain.RegisterAgentRequest) (*domain.Agent, error)
	Unregister(agentID string) error
	Heartbeat(req *domain.HeartbeatRequest) error
	UpdateStatus(req *domain.UpdateStatusRequest) error
	GetAgent(agentID string) (*domain.Agent, error)
	ListAgents() ([]*domain.Agent, error)
	ListAgentsByStatus(status domain.AgentStatus) ([]*domain.Agent, error)
	FindAvailableAgents(capabilities []string) ([]*domain.Agent, error)
	MarkStaleAgentsOffline(timeout time.Duration) (int, error)
}

type registryService struct {
	repo repository.AgentRepository
}

// NewRegistryService creates a new registry service
func NewRegistryService(repo repository.AgentRepository) RegistryService {
	return &registryService{
		repo: repo,
	}
}

// Register registers a new agent
func (s *registryService) Register(req *domain.RegisterAgentRequest) (*domain.Agent, error) {
	// Validate request
	if req.AgentID == "" {
		return nil, fmt.Errorf("agent_id is required")
	}
	if req.SessionID == "" {
		return nil, fmt.Errorf("session_id is required")
	}
	if req.AgentType == "" {
		return nil, fmt.Errorf("agent_type is required")
	}

	// Check if agent already exists
	existing, _ := s.repo.GetByAgentID(req.AgentID)
	if existing != nil {
		return nil, fmt.Errorf("agent %s already registered", req.AgentID)
	}

	// Create agent
	agent := &domain.Agent{
		AgentID:      req.AgentID,
		SessionID:    req.SessionID,
		AgentType:    req.AgentType,
		Status:       domain.AgentStatusIdle,
		Capabilities: req.Capabilities,
		Metadata:     req.Metadata,
	}

	if err := s.repo.Create(agent); err != nil {
		return nil, fmt.Errorf("failed to register agent: %w", err)
	}

	return agent, nil
}

// Unregister removes an agent from the registry
func (s *registryService) Unregister(agentID string) error {
	if agentID == "" {
		return fmt.Errorf("agent_id is required")
	}

	// Verify agent exists
	if _, err := s.repo.GetByAgentID(agentID); err != nil {
		return fmt.Errorf("agent not found: %w", err)
	}

	if err := s.repo.Delete(agentID); err != nil {
		return fmt.Errorf("failed to unregister agent: %w", err)
	}

	return nil
}

// Heartbeat processes a heartbeat from an agent
func (s *registryService) Heartbeat(req *domain.HeartbeatRequest) error {
	if req.AgentID == "" {
		return fmt.Errorf("agent_id is required")
	}

	// Verify agent exists
	agent, err := s.repo.GetByAgentID(req.AgentID)
	if err != nil {
		return fmt.Errorf("agent not found: %w", err)
	}

	// Update heartbeat timestamp
	if err := s.repo.UpdateHeartbeat(req.AgentID); err != nil {
		return fmt.Errorf("failed to update heartbeat: %w", err)
	}

	// Update status if provided
	if req.Status != "" && req.Status != agent.Status {
		if err := s.repo.UpdateStatus(req.AgentID, req.Status); err != nil {
			return fmt.Errorf("failed to update status: %w", err)
		}
	}

	// Record heartbeat in history
	heartbeat := &domain.AgentHeartbeat{
		AgentID:  req.AgentID,
		Status:   req.Status,
		Metadata: req.Metadata,
	}

	if err := s.repo.RecordHeartbeat(heartbeat); err != nil {
		return fmt.Errorf("failed to record heartbeat: %w", err)
	}

	return nil
}

// UpdateStatus updates the status of an agent
func (s *registryService) UpdateStatus(req *domain.UpdateStatusRequest) error {
	if req.AgentID == "" {
		return fmt.Errorf("agent_id is required")
	}
	if req.Status == "" {
		return fmt.Errorf("status is required")
	}

	// Verify agent exists
	if _, err := s.repo.GetByAgentID(req.AgentID); err != nil {
		return fmt.Errorf("agent not found: %w", err)
	}

	if err := s.repo.UpdateStatus(req.AgentID, req.Status); err != nil {
		return fmt.Errorf("failed to update status: %w", err)
	}

	return nil
}

// GetAgent retrieves an agent by ID
func (s *registryService) GetAgent(agentID string) (*domain.Agent, error) {
	if agentID == "" {
		return nil, fmt.Errorf("agent_id is required")
	}

	agent, err := s.repo.GetByAgentID(agentID)
	if err != nil {
		return nil, fmt.Errorf("failed to get agent: %w", err)
	}

	return agent, nil
}

// ListAgents retrieves all agents
func (s *registryService) ListAgents() ([]*domain.Agent, error) {
	agents, err := s.repo.List()
	if err != nil {
		return nil, fmt.Errorf("failed to list agents: %w", err)
	}

	return agents, nil
}

// ListAgentsByStatus retrieves agents by status
func (s *registryService) ListAgentsByStatus(status domain.AgentStatus) ([]*domain.Agent, error) {
	agents, err := s.repo.ListByStatus(status)
	if err != nil {
		return nil, fmt.Errorf("failed to list agents by status: %w", err)
	}

	return agents, nil
}

// FindAvailableAgents finds available agents with specified capabilities
func (s *registryService) FindAvailableAgents(capabilities []string) ([]*domain.Agent, error) {
	agents, err := s.repo.FindAvailableAgents(capabilities)
	if err != nil {
		return nil, fmt.Errorf("failed to find available agents: %w", err)
	}

	return agents, nil
}

// MarkStaleAgentsOffline marks agents that haven't sent heartbeat as offline
func (s *registryService) MarkStaleAgentsOffline(timeout time.Duration) (int, error) {
	staleAgents, err := s.repo.GetStaleAgents(timeout)
	if err != nil {
		return 0, fmt.Errorf("failed to get stale agents: %w", err)
	}

	count := 0
	for _, agent := range staleAgents {
		if err := s.repo.UpdateStatus(agent.AgentID, domain.AgentStatusOffline); err != nil {
			// Log error but continue processing other agents
			continue
		}
		count++
	}

	return count, nil
}
