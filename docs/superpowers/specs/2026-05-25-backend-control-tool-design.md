# Backend Control Tool Design

**Date:** 2026-05-25  
**Author:** AI Agent  
**Status:** Approved

## Overview

Add a `backend_control` tool to the agent's tool registry, enabling lifecycle management of quantsys-v2 backend services (REST API on port 5001, WebSocket on port 5003) through conversational commands.

## Motivation

Currently, backend services must be started manually via terminal commands (`python start_all.py`). This creates friction when:
- Agent needs backend data but services aren't running
- User wants to restart services after configuration changes
- Debugging requires checking service status

A dedicated tool allows the agent to manage backend lifecycle autonomously or on-demand, improving workflow efficiency.

## Design

### Tool Definition

**Name:** `backend_control`

**Description:** Manage quantsys-v2 backend services lifecycle (start/stop/restart/status)

**Parameters:**
- `action` (required): Operation type
  - `start` - Launch backend services
  - `stop` - Terminate backend services
  - `restart` - Stop then start services
  - `status` - Query current service state
- `service` (optional, default: `all`): Target service
  - `all` - Both REST API and WebSocket
  - `rest` - REST API only (port 5001)
  - `websocket` - WebSocket only (port 5003)

**Return Value:**
```typescript
{
  success: boolean;
  message: string;
  services?: {
    rest?: { status: 'running' | 'stopped', pid?: number, port: 5001, uptime?: string };
    websocket?: { status: 'running' | 'stopped', pid?: number, port: 5003, uptime?: string };
  };
  error?: string;
}
```

### Architecture

**File Location:** `src/infrastructure/tools/agent/backend-control-tool.ts`

**Dependencies:**
- `child_process` - Process spawning and management
- `fs` - PID file persistence
- `http` - Health check requests

**State Management:**
- PID tracking file: `.backend/pids.json`
  ```json
  {
    "rest": { "pid": 12345, "startTime": "2026-05-25T10:00:00Z" },
    "websocket": { "pid": 12346, "startTime": "2026-05-25T10:00:01Z" }
  }
  ```

### Implementation Details

#### 1. Start Operation

**Command Execution:**
- `service=all`: `cd quantsys-v2 && python start_all.py`
- `service=rest`: `cd quantsys-v2 && python api/server.py`
- `service=websocket`: `cd quantsys-v2 && python api/server_websocket.py`

**Process Management:**
- Spawn with `detached: true` and `stdio: 'ignore'` for background execution
- Call `subprocess.unref()` to prevent blocking agent
- Save PID and start time to `.backend/pids.json`

**Startup Verification:**
- Wait up to 10 seconds for service to become healthy
- Poll health endpoint every 500ms: `GET http://127.0.0.1:5001/api/health`
- Expected response: `{"status": "ok", "db_connected": true}`

**Why:** The `start_all.py` script uses multiprocessing to launch both services. We need to track the parent process PID for proper lifecycle management.

**How to apply:** When `service=all`, save the parent process PID. For individual services, save their respective PIDs. This allows granular control even when services were started together.

#### 2. Stop Operation

**Process Termination:**
1. Read PIDs from `.backend/pids.json`
2. Send SIGTERM for graceful shutdown
3. Wait up to 5 seconds for process exit
4. If still running, send SIGKILL
5. Clean up PID file entries

**Edge Cases:**
- PID file missing → Attempt to find process by port (`lsof -ti:5001`)
- Process already dead → Clean up stale PID file, return success
- Permission denied → Return error with troubleshooting hint

**Why:** Graceful shutdown (SIGTERM) allows Flask to close database connections and finish in-flight requests. SIGKILL is a fallback for hung processes.

**How to apply:** Always try SIGTERM first. Only escalate to SIGKILL after timeout to avoid data corruption.

#### 3. Status Operation

**Health Check Strategy:**
1. Check if PID exists: `ps -p <pid>`
2. Verify port binding: `lsof -ti:5001`
3. HTTP health check: `GET /api/health` (3s timeout)
4. Calculate uptime from saved start time

**Status States:**
- `running` - Process alive, port bound, health check passes
- `unhealthy` - Process alive but health check fails
- `stopped` - No process found

**Why:** Multi-layer checks prevent false positives. A process might exist but be unresponsive, or the PID file might be stale.

**How to apply:** Return detailed status for debugging. If unhealthy, suggest restart action.

#### 4. Restart Operation

**Sequence:**
1. Execute stop operation
2. Wait 2 seconds for cleanup
3. Execute start operation

**Why:** The delay ensures ports are fully released before rebinding. Immediate restart can fail with "address already in use" errors.

**How to apply:** Use the same stop/start logic with a fixed delay. Don't optimize away the delay—it's necessary for reliability.

### Error Handling

**Startup Failures:**

| Error | Detection | Response |
|-------|-----------|----------|
| Port occupied | Health check fails, `lsof` shows different PID | "Port 5001 already in use. Run `backend_control status` to check or `stop` first." |
| Python not found | Spawn error `ENOENT` | "Python not found. Ensure Python 3.9+ is in PATH." |
| Missing dependencies | Process exits immediately | "Backend startup failed. Run `cd quantsys-v2 && pip install -r requirements.txt`" |
| Database connection | Health check returns `db_connected: false` | "Backend started but database connection failed. Check PostgreSQL." |

**Stop Failures:**

| Error | Detection | Response |
|-------|-----------|----------|
| Process not found | `ps -p` returns non-zero | Clean PID file, return "Service already stopped" |
| Permission denied | `kill` returns EPERM | "Cannot stop process (PID: X). Check process owner." |
| Timeout | Process still alive after SIGKILL | "Force stop failed. Manual intervention required: `kill -9 <pid>`" |

**Status Failures:**

| Error | Detection | Response |
|-------|-----------|----------|
| Health check timeout | HTTP request exceeds 3s | Mark as "unhealthy", suggest restart |
| Stale PID file | PID exists but port not bound | Clean PID file, mark as "stopped" |

**Timeouts:**
- Startup wait: 10 seconds
- Graceful stop: 5 seconds
- Health check: 3 seconds

**Why:** Clear error messages with actionable next steps reduce debugging time. Timeouts prevent the tool from hanging indefinitely.

**How to apply:** Always include the specific error and a suggested fix. Log full error details for debugging but return user-friendly messages.

### Integration

**Tool Registry:**
Add to `src/infrastructure/tools/index.ts`:
```typescript
import { backendControlTool } from "./agent/backend-control-tool.js";

export const allCustomTools = [
  // ... existing tools
  restartAgentTool,
  backendControlTool,  // Add after restart-agent-tool
  // ...
];
```

**Tool Ordering:**
Place in "Agent 元工具" section after `restartAgentTool`, before memory tools. Both are system-level operations but used less frequently than workflow tools.

**Why:** Grouping with `restartAgentTool` makes operational tools discoverable. Placement after high-frequency tools reduces prompt token usage for common tasks.

**How to apply:** Follow the existing tool ordering convention in `index.ts`. Don't add to the top—reserve that for workflow-critical tools.

### Testing Strategy

**Unit Tests:** `src/infrastructure/tools/agent/backend-control-tool.test.ts`

Test cases:
1. Start operation spawns correct command
2. Stop operation sends SIGTERM then SIGKILL
3. Status operation parses health check response
4. Restart operation calls stop then start
5. Error handling for missing PID file
6. Error handling for port conflicts
7. Timeout handling for hung processes

**Integration Tests:**
1. Start backend, verify health endpoint responds
2. Stop backend, verify process terminates
3. Restart backend, verify new PID assigned
4. Status check returns accurate uptime

**Manual Testing:**
1. Start backend via tool, check `ps aux | grep server.py`
2. Query data via agent tools (verify backend connectivity)
3. Stop backend, verify agent reports error on next data request
4. Restart backend, verify agent recovers

**Why:** Unit tests ensure logic correctness. Integration tests verify real process management. Manual tests confirm end-to-end workflow.

**How to apply:** Mock `child_process` and `fs` in unit tests. Use a test database for integration tests to avoid affecting production data.

## Alternatives Considered

**Alternative 1: Multiple Fine-Grained Tools**
Create separate `start_backend`, `stop_backend`, `restart_backend`, `backend_status` tools.

**Pros:**
- Simpler parameters (no `action` enum)
- Aligns with DeepSeek's single-tool-call pattern

**Cons:**
- Adds 4 tools to registry (increases prompt size)
- Code duplication across tools
- Harder to maintain consistency

**Decision:** Rejected. The sub-command pattern is standard in CLI tools and keeps the tool count manageable.

**Alternative 2: Extend restart-agent-tool**
Rename to `system_control` and add backend management.

**Pros:**
- Unified system operations
- No new tool added

**Cons:**
- Violates single responsibility principle
- Increases complexity of existing stable tool
- Backend and agent lifecycles are independent

**Decision:** Rejected. Backend control is a distinct operational domain that deserves its own tool.

**Alternative 3: Auto-Start on Demand**
Automatically start backend when agent detects it's down.

**Pros:**
- Zero user intervention
- Seamless experience

**Cons:**
- Unexpected behavior (user might not want backend running)
- Hides failures (backend crashes go unnoticed)
- Complicates error attribution

**Decision:** Rejected. Explicit control is better than implicit magic. User should decide when to start services.

## Future Extensions

**Potential Enhancements:**
1. **Log Streaming:** `action=logs` to tail backend logs
2. **Performance Metrics:** `action=metrics` to show CPU/memory usage
3. **Auto-Restart:** `action=watch` to monitor and restart on crash
4. **Multi-Backend Support:** Extend to manage v1 backend (port 5002)
5. **Health Alerts:** Proactive notifications when backend becomes unhealthy

**Why:** These are valuable but not critical for MVP. Start with core lifecycle operations, add observability features based on usage patterns.

**How to apply:** Design the tool interface to be extensible. Adding new actions should only require new case branches, not architectural changes.

## Success Criteria

1. Agent can start backend via `backend_control` tool
2. Agent can check backend status and report uptime
3. Agent can restart backend after configuration changes
4. Tool handles port conflicts gracefully
5. Tool cleans up stale PID files automatically
6. Unit test coverage > 80%
7. Integration tests pass on CI

## Implementation Checklist

- [ ] Create `backend-control-tool.ts` with tool definition
- [ ] Implement start operation with process spawning
- [ ] Implement stop operation with graceful shutdown
- [ ] Implement status operation with health checks
- [ ] Implement restart operation
- [ ] Add PID file management (`.backend/pids.json`)
- [ ] Add error handling for all failure modes
- [ ] Write unit tests
- [ ] Write integration tests
- [ ] Register tool in `index.ts`
- [ ] Update CLAUDE.md with tool documentation
- [ ] Manual testing: start/stop/restart/status
- [ ] Commit and verify in agent session
