# Backend Control Tool Health Check Enhancement

**Date:** 2026-05-27  
**Status:** Design  
**Author:** Claude (Opus 4.7)

## Problem Statement

The `backend_control` tool currently implements health check polling when starting services, but has reliability and user experience issues:

1. **Silent waiting period**: Users see no feedback during the 10-second health check wait, leading to confusion about whether the tool is stuck
2. **Generic error messages**: When health checks fail, the tool returns "Health check failed after 10 seconds" without diagnostic information
3. **Fixed timeout**: 10 seconds may be insufficient for slow-starting services or too long for fast failures
4. **No log visibility**: When services fail to start, users cannot see the actual error from service logs

This led to a real incident where the agent used bash to start services directly (blocking the terminal) instead of using the backend_control tool, because the tool's behavior was unclear.

## Goals

1. **Provide clear progress feedback** during service startup
2. **Return actionable error messages** when startup fails
3. **Implement adaptive timeout** with staged polling
4. **Surface service logs** on failure for debugging

## Design

### 1. Staged Health Check Polling

Replace the current fixed-interval polling with a two-stage approach:

**Stage 1: Fast polling (0-5 seconds)**
- Poll every 500ms
- Optimized for services that start quickly
- Most successful startups complete in this stage

**Stage 2: Slow polling (5-15 seconds)**
- Poll every 1000ms
- Handles slower service initialization
- Total timeout extended from 10s to 15s

**Rationale:** Services typically either start quickly (<5s) or need more time (10-15s). The staged approach optimizes for the common case while accommodating slower startups.

### 2. Progress Feedback

**Initial response** (immediately after spawn):
```typescript
{
  type: "text",
  text: `🚀 正在启动 ${service} 服务...

进程已启动 (PID: ${subprocess.pid})
等待服务就绪... (最多等待 15 秒)

[健康检查中...]`
}
```

**Success response** (after health check passes):
```typescript
{
  type: "text",
  text: `✅ ${service} 服务启动成功

PID: ${subprocess.pid}
端口: ${targetPort}
启动耗时: ${elapsed}ms
数据库连接: ${dbConnected ? '✅' : '❌'}`
}
```

**Implementation note:** Since tool execution is synchronous, we cannot send intermediate updates. The initial message sets expectations, and the final message confirms success with timing details.

### 3. Enhanced Error Diagnostics

When health check fails, execute diagnostic steps in order:

#### Step 1: Check process status
```typescript
if (!isProcessAlive(subprocess.pid)) {
  return {
    success: false,
    error: "进程启动后崩溃",
    diagnostics: {
      reason: "process_crashed",
      logs: readServiceLogs(50) // last 50 lines
    }
  };
}
```

#### Step 2: Check port availability
```typescript
const portInUse = await isPortInUse(targetPort);
if (portInUse && !isOurProcess(targetPort, subprocess.pid)) {
  return {
    success: false,
    error: `端口 ${targetPort} 已被其他进程占用`,
    diagnostics: {
      reason: "port_conflict",
      conflictingPid: getProcessOnPort(targetPort)
    }
  };
}
```

#### Step 3: Analyze service logs
```typescript
const logs = readServiceLogs(30);
const errorPatterns = [
  /ModuleNotFoundError/,
  /ImportError/,
  /Address already in use/,
  /Connection refused/,
  /Database.*error/i,
];

const detectedErrors = logs.filter(line => 
  errorPatterns.some(pattern => pattern.test(line))
);

return {
  success: false,
  error: "服务未响应健康检查",
  diagnostics: {
    reason: "health_check_timeout",
    recentLogs: logs,
    detectedErrors,
    hint: detectedErrors.length > 0 
      ? "检测到以下错误，请查看日志" 
      : "未检测到明显错误，可能是启动时间过长"
  }
};
```

### 4. Log File Management

**Log file location:** `/tmp/quantsys-v2-${service}.log`
- `rest` service → `/tmp/quantsys-v2-rest.log`
- `websocket` service → `/tmp/quantsys-v2-websocket.log`
- `all` (start_all.py) → `/tmp/quantsys-v2.log`

**Log reading utility:**
```typescript
function readServiceLogs(lines: number, service: string): string[] {
  const logFile = service === "all" 
    ? "/tmp/quantsys-v2.log"
    : `/tmp/quantsys-v2-${service}.log`;
  
  if (!existsSync(logFile)) {
    return ["日志文件不存在"];
  }
  
  // Read last N lines efficiently
  const content = execSync(`tail -n ${lines} "${logFile}"`, {
    encoding: "utf-8",
    timeout: 2000
  });
  
  return content.trim().split("\n");
}
```

### 5. Port Conflict Detection

**Utility function:**
```typescript
async function isPortInUse(port: number): Promise<boolean> {
  try {
    const result = execSync(`lsof -ti:${port}`, {
      encoding: "utf-8",
      timeout: 2000
    });
    return result.trim().length > 0;
  } catch {
    return false;
  }
}

function getProcessOnPort(port: number): number | null {
  try {
    const result = execSync(`lsof -ti:${port}`, {
      encoding: "utf-8",
      timeout: 2000
    });
    const pid = parseInt(result.trim().split("\n")[0]);
    return isNaN(pid) ? null : pid;
  } catch {
    return null;
  }
}
```

### 6. Updated startService Function Signature

```typescript
interface StartResult {
  success: boolean;
  pid?: number;
  message?: string;
  error?: string;
  diagnostics?: {
    reason: "process_crashed" | "port_conflict" | "health_check_timeout";
    logs?: string[];
    detectedErrors?: string[];
    hint?: string;
    conflictingPid?: number;
    elapsedMs?: number;
  };
}
```

## Implementation Changes

### Files to modify:
1. `src/infrastructure/tools/agent/backend-control-tool.ts`
   - Update `startService()` function (lines 201-287)
   - Add `readServiceLogs()` utility
   - Add `isPortInUse()` and `getProcessOnPort()` utilities
   - Update `StartResult` interface
   - Modify spawn to redirect logs to service-specific files

### New behavior:
- Stage 1: Poll every 500ms for 5 seconds (10 attempts)
- Stage 2: Poll every 1000ms for 10 seconds (10 attempts)
- Total timeout: 15 seconds (was 10 seconds)
- On failure: Run diagnostics and return detailed error

### Backward compatibility:
- Tool interface unchanged (same parameters)
- Return type extended with optional `diagnostics` field
- Existing callers continue to work

## Testing Strategy

### Unit tests (backend-control-tool.test.ts):
1. **Fast startup**: Service becomes healthy in <2 seconds
2. **Slow startup**: Service becomes healthy after 8 seconds
3. **Process crash**: Process exits immediately after spawn
4. **Port conflict**: Port already in use by another process
5. **Timeout**: Service never becomes healthy within 15 seconds
6. **Log parsing**: Detect common error patterns in logs

### Integration tests:
1. Start actual quantsys-v2 service and verify health check
2. Simulate port conflict and verify error message
3. Simulate service crash and verify log capture

### Manual testing:
1. Start service with `backend_control` tool
2. Verify progress messages appear
3. Kill service mid-startup and verify crash detection
4. Start service with port already in use and verify conflict detection

## Rollout Plan

1. **Phase 1**: Implement staged polling and progress feedback
2. **Phase 2**: Add diagnostic utilities (log reading, port checking)
3. **Phase 3**: Integrate diagnostics into error handling
4. **Phase 4**: Update tests and documentation

## Success Metrics

- Health check success rate: >95% for valid startups
- False positive rate (timeout on valid startup): <5%
- Error message actionability: Users can diagnose issues from error message alone
- No more incidents of agent using bash to start services

## Open Questions

None - design approved by user.
