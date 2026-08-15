package metrics

import (
	"github.com/prometheus/client_golang/prometheus"
	"github.com/prometheus/client_golang/prometheus/promauto"
)

var (
	// Command execution metrics
	CommandExecutionTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "agent_os_command_execution_total",
			Help: "Total number of CLI commands executed",
		},
		[]string{"command", "agent_id", "status"},
	)

	CommandExecutionDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "agent_os_command_execution_duration_seconds",
			Help:    "Duration of CLI command execution in seconds",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"command"},
	)

	// Permission check metrics
	PermissionCheckTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "agent_os_permission_check_total",
			Help: "Total number of permission checks",
		},
		[]string{"agent_id", "command", "result"},
	)

	PermissionCheckDuration = promauto.NewHistogram(
		prometheus.HistogramOpts{
			Name:    "agent_os_permission_check_duration_seconds",
			Help:    "Duration of permission checks in seconds",
			Buckets: []float64{.000001, .000005, .00001, .00005, .0001, .0005, .001},
		},
	)

	// Event Bus metrics
	EventPublishedTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "agent_os_event_published_total",
			Help: "Total number of events published",
		},
		[]string{"event_type", "agent_id"},
	)

	EventPublishDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "agent_os_event_publish_duration_seconds",
			Help:    "Duration of event publishing in seconds",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"event_type"},
	)

	EventSubscribersActive = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "agent_os_event_subscribers_active",
			Help: "Number of active event subscribers",
		},
	)

	// WebSocket metrics
	WebSocketConnectionsActive = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "agent_os_websocket_connections_active",
			Help: "Number of active WebSocket connections",
		},
	)

	WebSocketMessagesTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "agent_os_websocket_messages_total",
			Help: "Total number of WebSocket messages sent",
		},
		[]string{"event_type"},
	)

	WebSocketMessagesDuration = promauto.NewHistogram(
		prometheus.HistogramOpts{
			Name:    "agent_os_websocket_message_duration_seconds",
			Help:    "Duration of WebSocket message delivery in seconds",
			Buckets: []float64{.001, .005, .01, .025, .05, .1, .25, .5, 1},
		},
	)

	// API metrics
	APIRequestsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "agent_os_api_requests_total",
			Help: "Total number of API requests",
		},
		[]string{"method", "endpoint", "status"},
	)

	APIRequestDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "agent_os_api_request_duration_seconds",
			Help:    "Duration of API requests in seconds",
			Buckets: prometheus.DefBuckets,
		},
		[]string{"method", "endpoint"},
	)

	// Database metrics
	DatabaseQueryTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "agent_os_database_query_total",
			Help: "Total number of database queries",
		},
		[]string{"operation", "table", "status"},
	)

	DatabaseQueryDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "agent_os_database_query_duration_seconds",
			Help:    "Duration of database queries in seconds",
			Buckets: []float64{.001, .005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5},
		},
		[]string{"operation", "table"},
	)

	DatabaseConnectionsActive = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "agent_os_database_connections_active",
			Help: "Number of active database connections",
		},
	)

	// Memory service metrics
	MemoryEntriesTotal = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "agent_os_memory_entries_total",
			Help: "Total number of memory entries",
		},
	)

	MemoryOperationsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "agent_os_memory_operations_total",
			Help: "Total number of memory operations",
		},
		[]string{"operation", "status"},
	)

	// Scheduler metrics
	SchedulerTasksActive = promauto.NewGauge(
		prometheus.GaugeOpts{
			Name: "agent_os_scheduler_tasks_active",
			Help: "Number of active scheduled tasks",
		},
	)

	SchedulerTaskExecutionsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "agent_os_scheduler_task_executions_total",
			Help: "Total number of task executions",
		},
		[]string{"task_name", "status"},
	)

	SchedulerTaskDuration = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "agent_os_scheduler_task_duration_seconds",
			Help:    "Duration of scheduled task execution in seconds",
			Buckets: []float64{.1, .5, 1, 5, 10, 30, 60, 120, 300, 600},
		},
		[]string{"task_name"},
	)

	// Decision service metrics
	DecisionsTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "agent_os_decisions_total",
			Help: "Total number of decisions recorded",
		},
		[]string{"agent_id", "action"},
	)

	DecisionConfidence = promauto.NewHistogramVec(
		prometheus.HistogramOpts{
			Name:    "agent_os_decision_confidence",
			Help:    "Confidence score of decisions",
			Buckets: []float64{0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0},
		},
		[]string{"agent_id", "action"},
	)

	// Resource quota metrics
	QuotaUsage = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "agent_os_quota_usage",
			Help: "Current quota usage",
		},
		[]string{"namespace", "resource_type"},
	)

	QuotaLimit = promauto.NewGaugeVec(
		prometheus.GaugeOpts{
			Name: "agent_os_quota_limit",
			Help: "Quota limit",
		},
		[]string{"namespace", "resource_type"},
	)

	QuotaExceededTotal = promauto.NewCounterVec(
		prometheus.CounterOpts{
			Name: "agent_os_quota_exceeded_total",
			Help: "Total number of quota exceeded events",
		},
		[]string{"namespace", "resource_type"},
	)
)
