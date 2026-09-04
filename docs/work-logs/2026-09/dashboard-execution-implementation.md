# Dashboard Execution Plugin Implementation

**Date**: 2026-09-03  
**Status**: Implemented, plugin loading issue under investigation  
**Location**: `agent-dh/packages/pages/execution/`

## Overview

Implemented the dashboard execution status page plugin for agent-dh based on the detailed spec in `agent-dh/docs/design/dashboard-implementation-detail.md`.

## Implementation

### Package Structure

```
agent-dh/packages/pages/execution/
├── package.json
├── README.md
├── src/
│   ├── index.ts                        # Plugin entry point
│   ├── types/
│   │   └── index.ts                    # TypeScript type definitions
│   ├── services/
│   │   ├── checkpoint-registry.ts      # Checkpoint definitions (M0-M6, L1-L4)
│   │   ├── http.ts                     # HTTP client utility
│   │   └── data-aggregation.ts         # Data fetching and aggregation
│   └── routes/
│       └── dashboard-routes.ts         # HTTP route handlers
└── dist/                               # Build output (compiled .mjs)
    ├── index.mjs
    └── index.d.mts
```

### Key Components

#### 1. Checkpoint Registry (`checkpoint-registry.ts`)

Defines all 24 checkpoints across engine (M0-M6) and autonomy (L1-L4) modules:

- **M0**: Data Foundation (日K同步, 数据质量检查, 周度财务更新)
- **M1**: Market Perception (regime落库, 主线主题落库)
- **M2**: Stock Pool (股票池刷新)
- **M3**: Signal & Execution (信号生成, 信号执行, 胜率回填)
- **M4**: Risk Control (风控/熔断)
- **M5**: Trade Verification (交易对账)
- **M6**: Experience (盘后经验沉淀)
- **L1**: Strategy Validation (策略验证)
- **L2**: Knowledge Distillation (经验蒸馏)
- **L3**: Validation Gate (验证门裁决)
- **L4**: Weekly Report (周报)

Each checkpoint includes:
- Verification method (scheduler_task, v2_regime, v2_themes, v2_memory_kind, genome_file)
- Expected execution days and time
- Grace period
- Downstream flow blocking information

#### 2. Data Aggregation Service (`data-aggregation.ts`)

Fetches and aggregates data from multiple sources:

- **quantsys-v2** (:5001): Health, scheduler tasks/runs, market perception APIs
- **agent-os** (:8080): Health status
- **PostgreSQL**: Connection status (via v2)
- **Local logs**: Error event extraction
- **Genome files**: Evolution status verification

Implements graceful degradation - single source failure only affects related data blocks.

#### 3. Route Handlers (`dashboard-routes.ts`)

- `GET /dashboard/execution` - HTML dashboard page
- `GET /dashboard/api/board` - JSON API returning `BoardData`

The HTML page includes:
- Real-time health status cards
- Checkpoint status grid (color-coded by status)
- Recent error events
- Scheduled task details
- Auto-refresh (30s health, 60s checkpoints)
- Stale data notice when API unavailable

#### 4. HTTP Client (`http.ts`)

Utility for making requests to upstream services with:
- Configurable timeout (default 4s)
- Automatic JSON unwrapping
- Error handling for connection failures
- Response envelope support

### Routes

- **Page**: `http://127.0.0.1:13080/dashboard/execution`
- **API**: `http://127.0.0.1:13080/dashboard/api/board`

### Integration

Added to agent-dh profile:

1. **package.json**: Added dependency
   ```json
   "@pi-investment/dashboard-execution": "file:../../../pi-investment/agent-dh/packages/pages/execution"
   ```

2. **cordis.patch.yml**: Registered plugin
   ```yaml
   - id: dashboard-execution
     name: '@pi-investment/dashboard-execution'
   ```

3. **Build**: Compiled with tsdown
   ```bash
   pnpm build  # Outputs to dist/index.mjs
   ```

## Current Status

### ✅ Completed

- [x] Package structure created
- [x] Type definitions implemented
- [x] Checkpoint registry with real task mappings
- [x] HTTP client utility
- [x] Data aggregation service with multi-source fetching
- [x] Route handlers (HTML + API)
- [x] HTML dashboard UI with auto-refresh
- [x] Plugin integration in profile
- [x] Build configuration and compilation

### ⚠️ Issue: Plugin Not Loading

**Symptom**: Routes return 404, no console.log output in logs, plugin appears not to be loaded by DSH

**Verification**:
- ✅ Module imports successfully in isolation
- ✅ Build output generated correctly (dist/index.mjs)
- ✅ Symlink exists in profile node_modules
- ✅ cordis.patch.yml contains plugin registration
- ✅ Other plugins (lifecycle, wake-webhook) work correctly
- ❌ Dashboard routes not registered
- ❌ No plugin apply() debug output

**Potential Causes**:
1. DSH plugin loading mechanism not picking up the new plugin
2. Cordis injection timing issue
3. Plugin configuration format mismatch
4. Missing dependency or cordis version incompatibility

**Next Steps**:
1. Check DSH plugin loader source code to understand loading mechanism
2. Compare with working plugins (lifecycle, wake-webhook) for any differences
3. Try explicit plugin registration in cordis.yml instead of cordis.patch.yml
4. Add plugin to profile bundles if required
5. Check for any plugin loader cache that needs clearing

## Data Flow

```
Browser → /dashboard/execution (HTML page)
          ↓
Browser → /dashboard/api/board (polling 30-60s)
          ↓
DataAggregationService
          ├→ quantsys-v2 :5001 (health, scheduler, market perception)
          ├→ agent-os :8080 (health)
          ├→ Local logs (error events)
          └→ Genome files (evolution status)
          ↓
BoardData response
          ↓
Browser updates UI
```

## API Response Schema

```typescript
interface BoardData {
  health: HealthStatus[];           // System health (v2, os, pg, dh)
  checkpoints: CheckpointResult[];  // Checkpoint verification results
  tasks: SchedulerTask[];           // Scheduler task details
  errors: ErrorEvent[];             // Recent error events
  timeline: TimelineEntry[];        // Daily execution timeline
  blockedFlows?: string[];          // Checkpoints blocked by failures
}
```

## Checkpoint Status Legend

- **confirmed** (green): Checkpoint passed, data up-to-date
- **failed** (red): Checkpoint execution failed
- **late** (yellow): Checkpoint past expected time + grace period
- **pending** (gray): Waiting for execution within grace period
- **off_day** (dim gray): Today is not an expected execution day
- **unknown** (purple): Unable to verify (upstream service unavailable)

## Testing

### Manual Test Commands

```bash
# Test API endpoint
curl -s http://127.0.0.1:13080/dashboard/api/board | jq .

# Test HTML page
curl -s http://127.0.0.1:13080/dashboard/execution | head -30

# Test plugin import
cd ~/.dsh/profiles/investment
node --import tsx/esm -e "import('@pi-investment/dashboard-execution').then(m => console.log('Loaded:', m.name))"

# Build plugin
cd /Users/yunpeng/pi-investment/agent-dh/packages/pages/execution
pnpm build
```

### Expected Behavior

- Dashboard page should render with system health, checkpoints, errors, and tasks
- API should return JSON with `{success: true, data: BoardData}`
- Page should auto-refresh every 30-60 seconds
- Stale data notice should appear when services are unreachable
- Checkpoint status colors should reflect actual execution state

## Architecture Notes

### Design Decisions

1. **Server-side proxy**: Browser never directly calls v2:5001 or os:8080 (security + CORS)
2. **Graceful degradation**: Single service failure doesn't break entire dashboard
3. **Polling interval**: 30s for health (fast feedback), 60s for checkpoints (less critical)
4. **Checkpoint verification**: Multiple verification types (scheduler task, API response, file mtime, log marker)
5. **Flow blocking**: Failed checkpoints cascade to block downstream modules

### Performance Considerations

- Parallel service requests (Promise.allSettled)
- Bounded body reading (256KB limit)
- Request timeouts (4s default)
- Minimal frontend JS (vanilla, no framework)
- Log tailing limited to last 300 lines per file

### Security

- No authentication (internal dashboard, localhost only)
- Request body size limits
- Timeout protection against hanging requests
- Error messages sanitized for external display

## References

- Design spec: `agent-dh/docs/design/dashboard-implementation-detail.md`
- Plugin template: `agent-dh/packages/lifecycle/` (wake-webhook pattern)
- DSH web server: `@deepseek-ai/dsh-web-app`
- Route registration: Lazy injection pattern with `ctx.inject(['webServer'])`

## Files Modified

1. `/Users/yunpeng/.dsh/profiles/investment/package.json` - Added dashboard-execution dependency
2. `/Users/yunpeng/.dsh/profiles/investment/cordis.patch.yml` - Registered plugin
3. `/Users/yunpeng/pi-investment/agent-dh/packages/pages/execution/*` - Full plugin implementation

## Build & Install

```bash
# Build plugin
cd /Users/yunpeng/pi-investment/agent-dh/packages/pages/execution
pnpm build

# Install in profile
cd ~/.dsh/profiles/investment
npm install

# Restart agent-dh
./stop.sh
./start.sh
```

## Troubleshooting

### Routes return 404
- Check if plugin is loaded: grep for "dashboard" in logs
- Verify build output exists: ls dist/index.mjs
- Check symlink: ls -la node_modules/@pi-investment/dashboard-execution

### Empty or stale data
- Check upstream services: curl localhost:5001/api/health, curl localhost:8080/health
- Check log files exist and are readable
- Verify PI_INVEST_DIR environment variable

### Checkpoint verification issues
- Check scheduler task names match exactly
- Verify v2 API endpoints are accessible
- Check genome file paths are correct

## Future Enhancements

- [ ] WebSocket push for real-time updates (no polling)
- [ ] Checkpoint history and trend visualization
- [ ] Alert/notification integration
- [ ] Filtering and search for tasks/errors
- [ ] Export dashboard data as JSON/CSV
- [ ] Mobile-responsive layout
- [ ] Dark/light theme toggle
- [ ] Checkpoint dependency graph visualization
