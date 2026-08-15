# Agent OS API Reference

## Overview

Agent OS provides three API interfaces:

1. **HTTP REST API** (`:8080`) - Synchronous operations
2. **WebSocket API** (`:8081`) - Real-time event streaming
3. **Metrics API** (`:9090`) - Prometheus metrics and health checks

## HTTP REST API

Base URL: `http://localhost:8080/api/v1`

### Authentication

All API requests require authentication via API key in the header:

```
Authorization: Bearer <api-key>
```

### Agents

#### Register Agent

```http
POST /api/v1/agents
Content-Type: application/json

{
  "name": "trading-agent",
  "description": "Automated trading agent",
  "quota_limit": 10000
}
```

**Response** (201 Created):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "trading-agent",
  "description": "Automated trading agent",
  "status": "active",
  "quota_limit": 10000,
  "quota_used": 0,
  "created_at": "2026-08-14T10:00:00Z",
  "updated_at": "2026-08-14T10:00:00Z"
}
```

#### Get Agent

```http
GET /api/v1/agents/:id
```

**Response** (200 OK):
```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "trading-agent",
  "status": "active",
  "quota_limit": 10000,
  "quota_used": 42,
  "created_at": "2026-08-14T10:00:00Z",
  "updated_at": "2026-08-14T10:15:00Z"
}
```

#### List Agents

```http
GET /api/v1/agents?status=active&limit=10&offset=0
```

**Query Parameters**:
- `status` (optional) - Filter by status (active, inactive, suspended)
- `limit` (optional, default: 50) - Maximum results
- `offset` (optional, default: 0) - Pagination offset

**Response** (200 OK):
```json
{
  "agents": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "trading-agent",
      "status": "active",
      "quota_used": 42,
      "quota_limit": 10000
    }
  ],
  "total": 1,
  "limit": 10,
  "offset": 0
}
```

#### Update Agent

```http
PATCH /api/v1/agents/:id
Content-Type: application/json

{
  "status": "inactive",
  "quota_limit": 15000
}
```

**Response** (200 OK): Updated agent object

#### Delete Agent

```http
DELETE /api/v1/agents/:id
```

**Response** (204 No Content)

### Tasks

#### Create Task

```http
POST /api/v1/tasks
Content-Type: application/json

{
  "agent_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "daily-report",
  "description": "Generate daily trading report",
  "schedule": "0 9 * * *",
  "priority": 5,
  "dependencies": ["data-sync"]
}
```

**Schedule Format**: Cron expression (minute hour day month weekday)

**Response** (201 Created):
```json
{
  "id": "660e8400-e29b-41d4-a716-446655440000",
  "agent_id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "daily-report",
  "description": "Generate daily trading report",
  "schedule": "0 9 * * *",
  "status": "active",
  "priority": 5,
  "dependencies": ["data-sync"],
  "next_run_at": "2026-08-15T09:00:00Z",
  "created_at": "2026-08-14T10:00:00Z"
}
```

#### Get Task

```http
GET /api/v1/tasks/:id
```

**Response** (200 OK): Task object

#### List Tasks

```http
GET /api/v1/tasks?agent_id=...&status=active&limit=10
```

**Query Parameters**:
- `agent_id` (optional) - Filter by agent
- `status` (optional) - Filter by status
- `limit`, `offset` - Pagination

**Response** (200 OK):
```json
{
  "tasks": [...],
  "total": 10,
  "limit": 10,
  "offset": 0
}
```

#### Update Task

```http
PATCH /api/v1/tasks/:id
Content-Type: application/json

{
  "status": "inactive",
  "schedule": "0 10 * * *"
}
```

**Response** (200 OK): Updated task

#### Delete Task

```http
DELETE /api/v1/tasks/:id
```

**Response** (204 No Content)

#### Get Task Executions

```http
GET /api/v1/tasks/:id/executions?limit=10&offset=0
```

**Response** (200 OK):
```json
{
  "executions": [
    {
      "id": "770e8400-e29b-41d4-a716-446655440000",
      "task_id": "660e8400-e29b-41d4-a716-446655440000",
      "status": "success",
      "started_at": "2026-08-14T09:00:00Z",
      "completed_at": "2026-08-14T09:00:15Z",
      "duration_ms": 15000,
      "result": {"records_processed": 1000}
    }
  ],
  "total": 50
}
```

### Memory

#### Store Memory

```http
POST /api/v1/memory
Content-Type: application/json

{
  "agent_id": "550e8400-e29b-41d4-a716-446655440000",
  "key": "project-context",
  "value": "Working on Agent OS production deployment",
  "ttl": 3600
}
```

**TTL**: Time-to-live in seconds (optional, null = permanent)

**Response** (201 Created):
```json
{
  "id": "880e8400-e29b-41d4-a716-446655440000",
  "agent_id": "550e8400-e29b-41d4-a716-446655440000",
  "key": "project-context",
  "value": "Working on Agent OS production deployment",
  "ttl": 3600,
  "expires_at": "2026-08-14T11:00:00Z",
  "created_at": "2026-08-14T10:00:00Z"
}
```

#### Get Memory

```http
GET /api/v1/memory/:agent_id/:key
```

**Response** (200 OK): Memory entry object

#### Search Memory

```http
POST /api/v1/memory/search
Content-Type: application/json

{
  "agent_id": "550e8400-e29b-41d4-a716-446655440000",
  "query": "what am I working on?",
  "limit": 5
}
```

**Response** (200 OK):
```json
{
  "results": [
    {
      "key": "project-context",
      "value": "Working on Agent OS production deployment",
      "score": 0.92,
      "created_at": "2026-08-14T10:00:00Z"
    }
  ],
  "total": 1
}
```

#### Delete Memory

```http
DELETE /api/v1/memory/:agent_id/:key
```

**Response** (204 No Content)

### Decisions

#### Record Decision

```http
POST /api/v1/decisions
Content-Type: application/json

{
  "agent_id": "550e8400-e29b-41d4-a716-446655440000",
  "decision_type": "trade",
  "input": {
    "symbol": "AAPL",
    "price": 150.00,
    "signal": "buy"
  },
  "output": {
    "action": "buy",
    "quantity": 100,
    "price_limit": 151.00
  },
  "confidence": 0.85
}
```

**Response** (201 Created):
```json
{
  "id": "990e8400-e29b-41d4-a716-446655440000",
  "agent_id": "550e8400-e29b-41d4-a716-446655440000",
  "decision_type": "trade",
  "input": {...},
  "output": {...},
  "confidence": 0.85,
  "status": "pending",
  "created_at": "2026-08-14T10:00:00Z"
}
```

#### Get Decision

```http
GET /api/v1/decisions/:id
```

**Response** (200 OK): Decision object

#### List Decisions

```http
GET /api/v1/decisions?agent_id=...&type=trade&status=executed&limit=10
```

**Query Parameters**:
- `agent_id` (optional)
- `type` (optional) - Decision type
- `status` (optional) - Status filter
- `from_date`, `to_date` (optional) - Date range
- `limit`, `offset` - Pagination

**Response** (200 OK):
```json
{
  "decisions": [...],
  "total": 50,
  "limit": 10,
  "offset": 0
}
```

#### Update Decision Status

```http
PATCH /api/v1/decisions/:id
Content-Type: application/json

{
  "status": "executed",
  "executed_at": "2026-08-14T10:05:00Z"
}
```

**Response** (200 OK): Updated decision

### Events

#### Get Events

```http
GET /api/v1/events?agent_id=...&type=task.*&from=2026-08-14T00:00:00Z&limit=50
```

**Query Parameters**:
- `agent_id` (optional)
- `type` (optional) - Event type pattern (supports wildcards)
- `from`, `to` (optional) - Date range (ISO 8601)
- `limit`, `offset` - Pagination

**Response** (200 OK):
```json
{
  "events": [
    {
      "id": "aa0e8400-e29b-41d4-a716-446655440000",
      "agent_id": "550e8400-e29b-41d4-a716-446655440000",
      "event_type": "task.completed",
      "payload": {
        "task_id": "660e8400-e29b-41d4-a716-446655440000",
        "status": "success"
      },
      "created_at": "2026-08-14T10:00:00Z"
    }
  ],
  "total": 1
}
```

## WebSocket API

URL: `ws://localhost:8081/ws/events`

### Connection

```javascript
const ws = new WebSocket('ws://localhost:8081/ws/events?filters=task.*,decision.*');

ws.onopen = () => {
  console.log('Connected to event stream');
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Event received:', data);
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};

ws.onclose = () => {
  console.log('Disconnected from event stream');
};
```

### Query Parameters

- `filters` (optional) - Comma-separated event type patterns
  - Example: `task.*,decision.*`
  - Wildcards: `*` matches any characters

### Message Format

```json
{
  "event_type": "task.completed",
  "agent_id": "550e8400-e29b-41d4-a716-446655440000",
  "payload": {
    "task_id": "660e8400-e29b-41d4-a716-446655440000",
    "status": "success",
    "duration_ms": 15000
  },
  "timestamp": "2026-08-14T10:00:00Z"
}
```

### Event Types

- `task.created` - New task created
- `task.updated` - Task updated
- `task.deleted` - Task deleted
- `task.started` - Task execution started
- `task.completed` - Task execution completed
- `task.failed` - Task execution failed
- `decision.recorded` - Decision recorded
- `decision.executed` - Decision executed
- `agent.registered` - Agent registered
- `agent.updated` - Agent updated
- `quota.exceeded` - Quota exceeded

## Metrics API

URL: `http://localhost:9090`

### Health Check

```http
GET /health
```

**Response** (200 OK):
```
OK
```

### Prometheus Metrics

```http
GET /metrics
```

**Response** (200 OK): Prometheus text format

**Sample Metrics**:
```
# HELP agent_os_command_execution_total Total number of CLI commands executed
# TYPE agent_os_command_execution_total counter
agent_os_command_execution_total{command="task:create",agent_id="agent-1",status="success"} 42

# HELP agent_os_api_requests_total Total number of API requests
# TYPE agent_os_api_requests_total counter
agent_os_api_requests_total{method="GET",endpoint="/api/v1/tasks",status="200"} 150

# HELP agent_os_database_query_duration_seconds Duration of database queries
# TYPE agent_os_database_query_duration_seconds histogram
agent_os_database_query_duration_seconds_bucket{operation="SELECT",table="tasks",le="0.005"} 145
```

## Error Responses

All error responses follow this format:

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Agent not found",
    "details": {
      "agent_id": "550e8400-e29b-41d4-a716-446655440000"
    }
  }
}
```

### Error Codes

- `400 BAD_REQUEST` - Invalid request parameters
- `401 UNAUTHORIZED` - Missing or invalid authentication
- `403 FORBIDDEN` - Insufficient permissions
- `404 RESOURCE_NOT_FOUND` - Resource not found
- `409 CONFLICT` - Resource conflict (e.g., duplicate name)
- `422 VALIDATION_ERROR` - Request validation failed
- `429 RATE_LIMIT_EXCEEDED` - Quota exceeded
- `500 INTERNAL_ERROR` - Internal server error
- `503 SERVICE_UNAVAILABLE` - Service temporarily unavailable

## Rate Limiting

Rate limits are enforced per agent:

- Default: 1000 requests per hour
- Configurable via agent quota_limit
- Headers:
  - `X-RateLimit-Limit` - Request limit
  - `X-RateLimit-Remaining` - Remaining requests
  - `X-RateLimit-Reset` - Reset timestamp

## Pagination

List endpoints support pagination:

- `limit` (default: 50, max: 100)
- `offset` (default: 0)

Response includes:
- `total` - Total records
- `limit` - Applied limit
- `offset` - Applied offset

## Examples

### Complete Agent Workflow

```bash
# 1. Register agent
curl -X POST http://localhost:8080/api/v1/agents \
  -H "Content-Type: application/json" \
  -d '{"name": "my-agent", "quota_limit": 10000}'

# 2. Create task
curl -X POST http://localhost:8080/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "daily-sync",
    "schedule": "0 2 * * *"
  }'

# 3. Store memory
curl -X POST http://localhost:8080/api/v1/memory \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "550e8400-e29b-41d4-a716-446655440000",
    "key": "api-key",
    "value": "secret-123"
  }'

# 4. Record decision
curl -X POST http://localhost:8080/api/v1/decisions \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "550e8400-e29b-41d4-a716-446655440000",
    "decision_type": "action",
    "input": {"query": "What should I do?"},
    "output": {"action": "continue"},
    "confidence": 0.9
  }'

# 5. Get events
curl http://localhost:8080/api/v1/events?agent_id=550e8400-e29b-41d4-a716-446655440000
```
