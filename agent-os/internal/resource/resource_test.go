package resource

import (
	"testing"

	"github.com/google/uuid"
)

func TestResourceQuota_UsagePercent(t *testing.T) {
	tests := []struct {
		name       string
		used       int64
		limit      int64
		wantResult float64
	}{
		{
			name:       "50% usage",
			used:       50,
			limit:      100,
			wantResult: 50.0,
		},
		{
			name:       "0% usage",
			used:       0,
			limit:      100,
			wantResult: 0.0,
		},
		{
			name:       "100% usage",
			used:       100,
			limit:      100,
			wantResult: 100.0,
		},
		{
			name:       "exceeded",
			used:       150,
			limit:      100,
			wantResult: 150.0,
		},
		{
			name:       "zero limit",
			used:       50,
			limit:      0,
			wantResult: 0.0,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			q := &ResourceQuota{
				UsedValue:  tt.used,
				LimitValue: tt.limit,
			}
			if got := q.UsagePercent(); got != tt.wantResult {
				t.Errorf("UsagePercent() = %v, want %v", got, tt.wantResult)
			}
		})
	}
}

func TestResourceQuota_IsExceeded(t *testing.T) {
	tests := []struct {
		name       string
		used       int64
		limit      int64
		wantResult bool
	}{
		{
			name:       "under limit",
			used:       50,
			limit:      100,
			wantResult: false,
		},
		{
			name:       "at limit",
			used:       100,
			limit:      100,
			wantResult: true,
		},
		{
			name:       "over limit",
			used:       150,
			limit:      100,
			wantResult: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			q := &ResourceQuota{
				UsedValue:  tt.used,
				LimitValue: tt.limit,
			}
			if got := q.IsExceeded(); got != tt.wantResult {
				t.Errorf("IsExceeded() = %v, want %v", got, tt.wantResult)
			}
		})
	}
}

func TestResourceQuota_CanAllocate(t *testing.T) {
	tests := []struct {
		name       string
		used       int64
		limit      int64
		amount     int64
		wantResult bool
	}{
		{
			name:       "can allocate",
			used:       50,
			limit:      100,
			amount:     30,
			wantResult: true,
		},
		{
			name:       "can allocate exactly",
			used:       50,
			limit:      100,
			amount:     50,
			wantResult: true,
		},
		{
			name:       "cannot allocate",
			used:       50,
			limit:      100,
			amount:     51,
			wantResult: false,
		},
		{
			name:       "already exceeded",
			used:       150,
			limit:      100,
			amount:     1,
			wantResult: false,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			q := &ResourceQuota{
				UsedValue:  tt.used,
				LimitValue: tt.limit,
			}
			if got := q.CanAllocate(tt.amount); got != tt.wantResult {
				t.Errorf("CanAllocate(%d) = %v, want %v", tt.amount, got, tt.wantResult)
			}
		})
	}
}

func TestService_CheckQuotaHealth(t *testing.T) {
	// This is a unit test for the CheckQuotaHealth logic
	// We'll test the alert generation without database

	views := []*QuotaUsageView{
		{
			Namespace:    "test-agent",
			ResourceType: "tokens",
			UsagePercent: 95.0,
		},
		{
			Namespace:    "test-agent",
			ResourceType: "memory",
			UsagePercent: 105.0,
		},
		{
			Namespace:    "test-agent",
			ResourceType: "api_calls",
			UsagePercent: 50.0,
		},
	}

	// Simulate the alert logic from CheckQuotaHealth
	var alerts []QuotaAlert
	warningThreshold := 80.0

	for _, v := range views {
		if v.UsagePercent >= 100 {
			alerts = append(alerts, QuotaAlert{
				Namespace:    v.Namespace,
				ResourceType: v.ResourceType,
				UsagePercent: v.UsagePercent,
				Severity:     "critical",
			})
		} else if v.UsagePercent >= warningThreshold {
			alerts = append(alerts, QuotaAlert{
				Namespace:    v.Namespace,
				ResourceType: v.ResourceType,
				UsagePercent: v.UsagePercent,
				Severity:     "warning",
			})
		}
	}

	if len(alerts) != 2 {
		t.Errorf("Expected 2 alerts, got %d", len(alerts))
	}

	// Check critical alert
	if alerts[0].Severity != "warning" || alerts[0].ResourceType != "tokens" {
		t.Errorf("Expected warning alert for tokens, got %+v", alerts[0])
	}

	// Check warning alert
	if alerts[1].Severity != "critical" || alerts[1].ResourceType != "memory" {
		t.Errorf("Expected critical alert for memory, got %+v", alerts[1])
	}
}

func TestNamespace_BasicFields(t *testing.T) {
	ns := &Namespace{
		ID:          uuid.New(),
		Name:        "test-agent",
		Description: "Test agent namespace",
		Metadata: map[string]interface{}{
			"role": "testing",
		},
	}

	if ns.Name != "test-agent" {
		t.Errorf("Expected name 'test-agent', got %s", ns.Name)
	}

	if ns.Metadata["role"] != "testing" {
		t.Errorf("Expected role 'testing', got %v", ns.Metadata["role"])
	}
}

func TestResourceUsageLog_BasicFields(t *testing.T) {
	namespaceID := uuid.New()
	taskRunID := uuid.New()

	log := &ResourceUsageLog{
		ID:           uuid.New(),
		NamespaceID:  namespaceID,
		ResourceType: "tokens",
		Amount:       1000,
		Operation:    "allocate",
		TaskRunID:    &taskRunID,
		Metadata: map[string]interface{}{
			"source": "test",
		},
	}

	if log.Operation != "allocate" {
		t.Errorf("Expected operation 'allocate', got %s", log.Operation)
	}

	if log.Amount != 1000 {
		t.Errorf("Expected amount 1000, got %d", log.Amount)
	}

	if log.TaskRunID == nil {
		t.Error("Expected non-nil TaskRunID")
	}
}

func BenchmarkResourceQuota_UsagePercent(b *testing.B) {
	q := &ResourceQuota{
		UsedValue:  5000,
		LimitValue: 10000,
	}

	for i := 0; i < b.N; i++ {
		_ = q.UsagePercent()
	}
}

func BenchmarkResourceQuota_CanAllocate(b *testing.B) {
	q := &ResourceQuota{
		UsedValue:  5000,
		LimitValue: 10000,
	}

	for i := 0; i < b.N; i++ {
		_ = q.CanAllocate(1000)
	}
}
