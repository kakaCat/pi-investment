package resource

import (
	"context"
	"fmt"

	"github.com/google/uuid"
)

// Service provides resource management business logic
type Service struct {
	repo *Repository
}

// NewService creates a new resource service
func NewService(repo *Repository) *Service {
	return &Service{repo: repo}
}

// ============================================================================
// NAMESPACE OPERATIONS
// ============================================================================

// GetNamespace retrieves a namespace by name
func (s *Service) GetNamespace(ctx context.Context, name string) (*Namespace, error) {
	return s.repo.GetNamespaceByName(ctx, name)
}

// ListNamespaces retrieves all namespaces
func (s *Service) ListNamespaces(ctx context.Context) ([]*Namespace, error) {
	return s.repo.ListNamespaces(ctx)
}

// ============================================================================
// QUOTA OPERATIONS
// ============================================================================

// GetQuotas retrieves all quotas for a namespace
func (s *Service) GetQuotas(ctx context.Context, namespaceName string) ([]*ResourceQuota, error) {
	ns, err := s.repo.GetNamespaceByName(ctx, namespaceName)
	if err != nil {
		return nil, err
	}

	return s.repo.GetQuotasByNamespace(ctx, ns.ID)
}

// GetQuota retrieves a specific quota
func (s *Service) GetQuota(ctx context.Context, namespaceName, resourceType string) (*ResourceQuota, error) {
	ns, err := s.repo.GetNamespaceByName(ctx, namespaceName)
	if err != nil {
		return nil, err
	}

	return s.repo.GetQuota(ctx, ns.ID, resourceType)
}

// AllocateResource allocates a resource and checks quota
func (s *Service) AllocateResource(ctx context.Context, namespaceName, resourceType string, amount int64, taskRunID *uuid.UUID) error {
	ns, err := s.repo.GetNamespaceByName(ctx, namespaceName)
	if err != nil {
		return err
	}

	// Get current quota
	quota, err := s.repo.GetQuota(ctx, ns.ID, resourceType)
	if err != nil {
		return err
	}

	// Check if allocation is allowed
	if !quota.CanAllocate(amount) {
		return fmt.Errorf("quota exceeded: cannot allocate %d %s (used: %d, limit: %d)",
			amount, quota.Unit, quota.UsedValue, quota.LimitValue)
	}

	// Update quota usage
	if err := s.repo.UpdateQuotaUsage(ctx, ns.ID, resourceType, amount); err != nil {
		return err
	}

	// Log the allocation
	log := &ResourceUsageLog{
		NamespaceID:  ns.ID,
		ResourceType: resourceType,
		Amount:       amount,
		Operation:    "allocate",
		TaskRunID:    taskRunID,
		Metadata:     map[string]interface{}{},
	}

	return s.repo.LogUsage(ctx, log)
}

// ReleaseResource releases a resource
func (s *Service) ReleaseResource(ctx context.Context, namespaceName, resourceType string, amount int64, taskRunID *uuid.UUID) error {
	ns, err := s.repo.GetNamespaceByName(ctx, namespaceName)
	if err != nil {
		return err
	}

	// Update quota usage (negative delta)
	if err := s.repo.UpdateQuotaUsage(ctx, ns.ID, resourceType, -amount); err != nil {
		return err
	}

	// Log the release
	log := &ResourceUsageLog{
		NamespaceID:  ns.ID,
		ResourceType: resourceType,
		Amount:       amount,
		Operation:    "release",
		TaskRunID:    taskRunID,
		Metadata:     map[string]interface{}{},
	}

	return s.repo.LogUsage(ctx, log)
}

// SetQuotaLimit updates the limit for a quota
func (s *Service) SetQuotaLimit(ctx context.Context, namespaceName, resourceType string, limitValue int64) error {
	ns, err := s.repo.GetNamespaceByName(ctx, namespaceName)
	if err != nil {
		return err
	}

	return s.repo.SetQuotaLimit(ctx, ns.ID, resourceType, limitValue)
}

// ResetQuotaUsage resets the usage counter for a quota
func (s *Service) ResetQuotaUsage(ctx context.Context, namespaceName, resourceType string) error {
	ns, err := s.repo.GetNamespaceByName(ctx, namespaceName)
	if err != nil {
		return err
	}

	return s.repo.ResetQuotaUsage(ctx, ns.ID, resourceType)
}

// ============================================================================
// USAGE MONITORING
// ============================================================================

// GetUsageHistory retrieves usage history for a namespace
func (s *Service) GetUsageHistory(ctx context.Context, namespaceName string, limit int) ([]*ResourceUsageLog, error) {
	ns, err := s.repo.GetNamespaceByName(ctx, namespaceName)
	if err != nil {
		return nil, err
	}

	return s.repo.GetUsageHistory(ctx, ns.ID, limit)
}

// GetQuotaUsageOverview retrieves quota usage overview for all namespaces
func (s *Service) GetQuotaUsageOverview(ctx context.Context) ([]*QuotaUsageView, error) {
	return s.repo.GetQuotaUsageView(ctx)
}

// CheckQuotaHealth checks if any quotas are close to or exceeding limits
func (s *Service) CheckQuotaHealth(ctx context.Context, warningThreshold float64) ([]QuotaAlert, error) {
	views, err := s.repo.GetQuotaUsageView(ctx)
	if err != nil {
		return nil, err
	}

	var alerts []QuotaAlert
	for _, v := range views {
		if v.UsagePercent >= 100 {
			alerts = append(alerts, QuotaAlert{
				Namespace:    v.Namespace,
				ResourceType: v.ResourceType,
				UsagePercent: v.UsagePercent,
				Severity:     "critical",
				Message:      fmt.Sprintf("Quota exceeded: %s %s (%.2f%%)", v.Namespace, v.ResourceType, v.UsagePercent),
			})
		} else if v.UsagePercent >= warningThreshold {
			alerts = append(alerts, QuotaAlert{
				Namespace:    v.Namespace,
				ResourceType: v.ResourceType,
				UsagePercent: v.UsagePercent,
				Severity:     "warning",
				Message:      fmt.Sprintf("Quota warning: %s %s (%.2f%%)", v.Namespace, v.ResourceType, v.UsagePercent),
			})
		}
	}

	return alerts, nil
}

// QuotaAlert represents a quota health alert
type QuotaAlert struct {
	Namespace    string  `json:"namespace"`
	ResourceType string  `json:"resource_type"`
	UsagePercent float64 `json:"usage_percent"`
	Severity     string  `json:"severity"` // warning, critical
	Message      string  `json:"message"`
}
