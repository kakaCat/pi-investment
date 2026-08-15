# Agent OS Architecture

## Overview

Agent OS is a centralized operating system layer for AI agents, providing core infrastructure services including scheduling, resource management, memory, decision tracking, permissions, and event streaming.

## System Architecture

### Layered Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Client Layer                          │
│  - agent-ts (TypeScript AI Agent)                       │
│  - HTTP API clients                                     │
│  - WebSocket clients                                    │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                  API Gateway Layer                      │
│  ┌─────────────┐  ┌─────────────┐  ┌──────────────┐   │
│  │ HTTP Server │  │  WebSocket  │  │   Metrics    │   │
│  │   :8080     │  │   :8081     │  │   :9090      │   │
│  └─────────────┘  └─────────────┘  └──────────────┘   │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                  Service Layer                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Scheduler        Resource Mgr    Memory System   │  │
│  │ - Cron tasks     - Quotas        - Vector search │  │
│  │ - DAG deps       - Tracking      - BM25 search   │  │
│  │ - Execution      - Limits        - Hybrid        │  │
│  └──────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────┐  │
│  │ Decision System  Permissions     Event Bus       │  │
│  │ - Audit trail    - RBAC          - Pub/Sub       │  │
│  │ - Recording      - Agent roles   - PG NOTIFY     │  │
│  │ - Analytics      - Command auth  - WebSocket     │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│                  Data Layer                             │
│  ┌──────────────────────────────────────────────────┐  │
│  │              PostgreSQL Database                  │  │
│  │  - Agents, tasks, executions                      │  │
│  │  - Events, memory, decisions                      │  │
│  │  - ACID transactions                              │  │
│  │  - NOTIFY/LISTEN for events                       │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

## Core Modules

### 1. Scheduler

**Purpose**: Execute scheduled tasks for agents with cron-like timing and DAG dependencies.

**Features**:
- Cron expression support (minute, hour, day, month, weekday)
- Task dependencies (DAG)
- Task execution history
- Retry on failure
- Concurrent execution with limits

**Implementation**:
- Location: `internal/scheduler/`
- Storage: PostgreSQL (`tasks`, `task_executions` tables)
- Execution: Background goroutine pool

**Example**:
```go
task := Task{
    Name: "daily-report",
    AgentID: agentID,
    Schedule: "0 9 * * *",  // 9 AM daily
    Dependencies: []string{"data-sync"},
}
```

### 2. Resource Manager

**Purpose**: Track and enforce resource quotas per agent namespace.

**Features**:
- Per-agent quota tracking
- Multiple resource types (API calls, compute time, storage)
- Quota enforcement
- Usage reporting
- Overflow detection

**Implementation**:
- Location: `internal/resource/`
- Storage: PostgreSQL (`agents` table with quota fields)
- Enforcement: Middleware on API calls

**Example**:
```go
// Check quota before operation
if !resourceMgr.CheckQuota(agentID, "api_calls", 1) {
    return ErrQuotaExceeded
}

// Record usage
resourceMgr.RecordUsage(agentID, "api_calls", 1)
```

### 3. Memory System

**Purpose**: Store and retrieve agent memories using hybrid search (vector + BM25).

**Features**:
- Vector embeddings for semantic search
- BM25 for keyword matching
- Reciprocal Rank Fusion (RRF) for result merging
- TTL support for ephemeral memories
- Per-agent memory isolation

**Implementation**:
- Location: `internal/memory/`
- Storage: PostgreSQL with pgvector extension
- Search: BM25 (via pg_trgm) + Vector similarity

**Example**:
```go
// Store memory
memory.Store(agentID, "project-context", "Working on Agent OS")

// Search
results := memory.Search(agentID, "what am I working on?", 5)
```

### 4. Decision System

**Purpose**: Record agent decisions for audit trail and analysis.

**Features**:
- Decision recording with input/output
- Confidence scores
- Execution status tracking
- Analytics and reporting
- Outcome tracking

**Implementation**:
- Location: `internal/decision/`
- Storage: PostgreSQL (`decisions` table)
- Querying: SQL with indexes on decision_type, agent_id, status

**Example**:
```go
decision := Decision{
    AgentID: agentID,
    Type: "trade",
    Input: map[string]interface{}{"symbol": "AAPL"},
    Output: map[string]interface{}{"action": "buy", "quantity": 100},
    Confidence: 0.85,
}
```

### 5. Permissions (RBAC)

**Purpose**: Role-based access control for agent commands.

**Features**:
- Role definitions (admin, agent, guest)
- Command-level permissions
- Agent-to-role mapping
- Permission checking middleware
- YAML-based configuration

**Implementation**:
- Location: `internal/middleware/auth.go`
- Config: `config/permissions.yaml`
- Enforcement: Cobra middleware on all commands

**Example**:
```yaml
roles:
  agent:
    permissions:
      - task:create
      - task:list
      - memory:read
      - memory:write
```

### 6. Event Bus

**Purpose**: System-wide event streaming for real-time notifications.

**Features**:
- PostgreSQL NOTIFY/LISTEN for reliable delivery
- WebSocket streaming to clients
- Event filtering by type
- Multi-subscriber support
- Persistent event log

**Implementation**:
- Location: `internal/events/`
- Backend: PostgreSQL NOTIFY/LISTEN
- Frontend: WebSocket server on :8081
- Storage: `events` table for audit

**Example**:
```go
// Publish event
eventBus.Publish("task.completed", map[string]interface{}{
    "task_id": taskID,
    "status": "success",
})

// Subscribe via WebSocket
ws://localhost:8081/ws/events?filters=task.*,decision.*
```

## API Servers

### HTTP API Server (:8080)

RESTful API for synchronous operations.

**Endpoints**:
- `POST /api/v1/agents` - Register agent
- `GET /api/v1/agents/:id` - Get agent info
- `POST /api/v1/tasks` - Create task
- `GET /api/v1/tasks` - List tasks
- `POST /api/v1/memory` - Store memory
- `GET /api/v1/memory/search` - Search memories
- `POST /api/v1/decisions` - Record decision
- `GET /api/v1/events` - Get events

### WebSocket Server (:8081)

Real-time event streaming.

**Endpoint**:
- `ws://localhost:8081/ws/events` - Event stream

**Query Parameters**:
- `filters` - Comma-separated event type patterns (e.g., `task.*,decision.*`)

**Message Format**:
```json
{
  "event_type": "task.completed",
  "agent_id": "agent-123",
  "payload": {
    "task_id": "task-456",
    "status": "success"
  },
  "timestamp": "2026-08-14T10:00:00Z"
}
```

### Metrics Server (:9090)

Prometheus metrics and health checks.

**Endpoints**:
- `GET /metrics` - Prometheus metrics
- `GET /health` - Health check

## Data Model

### Core Tables

**agents**
- `id` (UUID, PK)
- `name` (VARCHAR, unique)
- `status` (VARCHAR)
- `quota_limit`, `quota_used` (INTEGER)
- `created_at`, `updated_at` (TIMESTAMP)

**tasks**
- `id` (UUID, PK)
- `agent_id` (UUID, FK)
- `name`, `description` (VARCHAR, TEXT)
- `schedule` (VARCHAR) - cron expression
- `status` (VARCHAR)
- `last_run_at`, `next_run_at` (TIMESTAMP)

**task_executions**
- `id` (UUID, PK)
- `task_id`, `agent_id` (UUID, FK)
- `status` (VARCHAR)
- `started_at`, `completed_at` (TIMESTAMP)
- `duration_ms` (INTEGER)

**events**
- `id` (UUID, PK)
- `agent_id` (UUID, FK, nullable)
- `event_type` (VARCHAR)
- `payload` (JSONB)
- `created_at` (TIMESTAMP)

**memory_entries**
- `id` (UUID, PK)
- `agent_id` (UUID, FK)
- `key`, `value` (VARCHAR, TEXT)
- `ttl` (INTEGER)
- `expires_at` (TIMESTAMP, nullable)

**decisions**
- `id` (UUID, PK)
- `agent_id` (UUID, FK)
- `decision_type` (VARCHAR)
- `input`, `output` (JSONB)
- `confidence` (FLOAT)
- `status` (VARCHAR)

## Monitoring

### Prometheus Metrics

**Command Execution**:
- `agent_os_command_execution_total{command, agent_id, status}`
- `agent_os_command_execution_duration_seconds{command}`

**Permissions**:
- `agent_os_permission_check_total{agent_id, command, result}`
- `agent_os_permission_check_duration_seconds`

**Events**:
- `agent_os_event_published_total{event_type, agent_id}`
- `agent_os_websocket_connections_active`

**API**:
- `agent_os_api_requests_total{method, endpoint, status}`
- `agent_os_api_request_duration_seconds{method, endpoint}`

**Database**:
- `agent_os_database_query_total{operation, table, status}`
- `agent_os_database_query_duration_seconds{operation, table}`

**Scheduler**:
- `agent_os_scheduler_tasks_active`
- `agent_os_scheduler_task_executions_total{task_name, status}`

## Deployment Architecture

### Docker Compose Setup

```
┌─────────────┐
│   Grafana   │ :3000
│  Dashboard  │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Prometheus  │ :9091
│   Scraper   │
└──────┬──────┘
       │ scrape
       ▼
┌─────────────┐
│  Agent OS   │ :8080, :8081, :9090
│ Application │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ PostgreSQL  │ :5432
│  Database   │
└─────────────┘
```

### Scaling Considerations

**Horizontal Scaling**:
- Multiple agent-os instances behind load balancer
- Shared PostgreSQL database
- WebSocket sticky sessions required

**Database Scaling**:
- PostgreSQL replication (primary + replicas)
- Read replicas for analytics queries
- Connection pooling (pgbouncer)

**High Availability**:
- Multiple agent-os replicas
- Database failover (Patroni, Stolon)
- Load balancer health checks

## Security

### Authentication & Authorization

- Agent authentication via API keys
- Role-based access control (RBAC)
- Command-level permission checking
- Audit logging of all operations

### Data Protection

- Database encryption at rest
- TLS for all external connections
- Secrets management (environment variables)
- SQL injection prevention (parameterized queries)

### Network Security

- Internal services on private network
- Firewall rules for external access
- Rate limiting on API endpoints
- DDoS protection at load balancer

## Performance

### Benchmarks

- CLI startup: 6ms
- Auth middleware: 24ns/op
- Permission check: ~1µs
- API request (p50): <10ms
- Database query (p50): <5ms

### Optimization Techniques

- Connection pooling
- Prepared statements
- Index optimization
- Query result caching
- Batch operations
- Goroutine pooling

## Future Enhancements

- [ ] Distributed tracing (OpenTelemetry)
- [ ] Advanced scheduling (distributed cron)
- [ ] Multi-region deployment
- [ ] Advanced memory search (graph embeddings)
- [ ] Real-time dashboard
- [ ] Machine learning for decision analysis
- [ ] Cost optimization recommendations
- [ ] Self-healing mechanisms
