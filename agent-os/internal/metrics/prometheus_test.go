package metrics

import (
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/prometheus/client_golang/prometheus/promhttp"
)

func TestPrometheusMetricsEndpoint(t *testing.T) {
	// Record some metrics first to ensure they appear
	CommandExecutionTotal.WithLabelValues("init", "test-agent", "success").Inc()
	PermissionCheckTotal.WithLabelValues("test-agent", "init", "allowed").Inc()
	EventPublishedTotal.WithLabelValues("init.event", "test-agent").Inc()
	WebSocketConnectionsActive.Set(1)
	APIRequestsTotal.WithLabelValues("GET", "/test", "200").Inc()
	DatabaseQueryTotal.WithLabelValues("SELECT", "agents", "success").Inc()
	MemoryEntriesTotal.Set(100)
	SchedulerTasksActive.Set(5)
	DecisionsTotal.WithLabelValues("test-agent", "buy").Inc()
	QuotaUsage.WithLabelValues("test-agent", "api_calls").Set(50)

	// Create test server with metrics handler
	req := httptest.NewRequest("GET", "/metrics", nil)
	w := httptest.NewRecorder()

	handler := promhttp.Handler()
	handler.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Expected status 200, got %d", w.Code)
	}

	body := w.Body.String()

	// Check for our custom metrics
	expectedMetrics := []string{
		"agent_os_command_execution_total",
		"agent_os_permission_check_total",
		"agent_os_event_published_total",
		"agent_os_websocket_connections_active",
		"agent_os_api_requests_total",
		"agent_os_database_query_total",
		"agent_os_memory_entries_total",
		"agent_os_scheduler_tasks_active",
		"agent_os_decisions_total",
		"agent_os_quota_usage",
	}

	for _, metric := range expectedMetrics {
		if !strings.Contains(body, metric) {
			t.Errorf("Expected metric %s not found in response", metric)
		}
	}

	// Check for HELP and TYPE comments
	if !strings.Contains(body, "# HELP") {
		t.Error("Expected HELP comments in metrics output")
	}
	if !strings.Contains(body, "# TYPE") {
		t.Error("Expected TYPE comments in metrics output")
	}
}

func TestMetricsRecording(t *testing.T) {
	// Record some metrics with correct label cardinality
	CommandExecutionTotal.WithLabelValues("test", "agent1", "success").Inc()
	PermissionCheckTotal.WithLabelValues("agent1", "test", "allowed").Inc()
	EventPublishedTotal.WithLabelValues("test.event", "agent1").Inc()

	// Create test server
	req := httptest.NewRequest("GET", "/metrics", nil)
	w := httptest.NewRecorder()

	handler := promhttp.Handler()
	handler.ServeHTTP(w, req)

	body := w.Body.String()

	// Verify metrics were recorded
	if !strings.Contains(body, "agent_os_command_execution_total") {
		t.Error("Commands metric not found")
	}
	if !strings.Contains(body, "agent_os_permission_check_total") {
		t.Error("Permission checks metric not found")
	}
	if !strings.Contains(body, "agent_os_event_published_total") {
		t.Error("Events metric not found")
	}
}

func TestHealthEndpoint(t *testing.T) {
	handler := http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusOK)
		w.Write([]byte("OK"))
	})

	req := httptest.NewRequest("GET", "/health", nil)
	w := httptest.NewRecorder()

	handler.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Errorf("Expected status 200, got %d", w.Code)
	}

	if w.Body.String() != "OK" {
		t.Errorf("Expected body 'OK', got %s", w.Body.String())
	}
}
