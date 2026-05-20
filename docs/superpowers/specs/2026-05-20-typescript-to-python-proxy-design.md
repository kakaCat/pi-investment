# TypeScript API to Python Backend Proxy Architecture

**Date:** 2026-05-20  
**Status:** Approved  
**Scope:** Full migration of TypeScript API from direct file/database access to Python Flask backend proxy

## Problem Statement

Currently, the TypeScript API layer (`src/api/web/routes/`) directly accesses the filesystem and database through:
- `fs.readFileSync/readdirSync` for reading JSON files (backtest results, training reports, signals)
- `StockDBService` for database queries
- `BacktestEngine` for running backtests

This creates architectural issues:
- Duplicated data access logic between TypeScript and Python
- TypeScript needs to understand Python's file structure and database schema
- Difficult to maintain consistency when data formats change
- Python backend exists but is underutilized

**Goal:** Refactor TypeScript API to be a pure proxy layer that forwards all data operations to the Python Flask backend.

## Requirements

1. **Full proxy migration** - All TypeScript routes must call Python backend, no direct file/database access
2. **Independent services** - Python Flask runs on separate port (5000), TypeScript API on port 3000
3. **Reuse existing endpoints** - Use Python Flask endpoints that already exist, add missing ones
4. **Fast failure** - When Python service unavailable, return 503 immediately (no retries, no fallback)
5. **Gradual migration** - Migrate in phases to reduce risk

## Architecture

### Current Architecture
```
Frontend → TypeScript API → Filesystem/Database
```

### Target Architecture
```
Frontend → TypeScript API (Proxy) → Python Flask (Data Layer) → Filesystem/Database
```

### Service Topology
- **TypeScript API**: `http://localhost:3000` - Express server, authentication, request routing
- **Python Flask**: `http://localhost:5000` - Data access, business logic, file operations
- **Communication**: HTTP/JSON over localhost

## Design

### 1. PythonBackendClient

**Location:** `src/services/python/python-backend-client.ts`

**Purpose:** Unified HTTP client for all Python backend communication.

**Interface:**
```typescript
class PythonBackendClient {
  private baseURL: string;        // from env: PYTHON_BACKEND_URL
  private timeout: number;        // from env: PYTHON_BACKEND_TIMEOUT
  
  static getInstance(): PythonBackendClient;
  
  async get(path: string, params?: Record<string, any>): Promise<any>;
  async post(path: string, body?: any): Promise<any>;
  async put(path: string, body?: any): Promise<any>;
  async delete(path: string): Promise<any>;
  
  async healthCheck(): Promise<boolean>;
}
```

**Error Handling:**
- Connection refused / ECONNREFUSED → throw 503 "Python backend service unavailable"
- Timeout → throw 504 "Gateway timeout"
- Python returns 4xx/5xx → pass through status code and error message
- No retry logic, fail fast

**Configuration:**
- `PYTHON_BACKEND_URL` - default `http://localhost:5000`
- `PYTHON_BACKEND_TIMEOUT` - default `30000` (30 seconds)

**Why:** Centralizes all HTTP logic, error handling, and configuration. Routes become simple one-liners.

**How to apply:** Every route that currently accesses files or database will use this client instead.

### 2. Route Migration Pattern

**Before (direct file access):**
```typescript
router.get('/results', async (req, res, next) => {
  const files = fs.readdirSync(backtestDir);
  const content = fs.readFileSync(filePath, 'utf-8');
  const data = JSON.parse(content);
  res.json(data);
});
```

**After (proxy to Python):**
```typescript
router.get('/results', async (req, res, next) => {
  try {
    const client = PythonBackendClient.getInstance();
    const data = await client.get('/api/backtest/results', req.query);
    res.json(data);
  } catch (error) {
    next(error);
  }
});
```

**Code to remove:**
- All `fs.readFileSync`, `fs.readdirSync`, `fs.existsSync` calls
- `StockDBService` imports and usage
- `BacktestEngine`, `FactorLibrary` imports and instantiation
- Local file path construction (`path.join`, `__dirname`)
- JSON parsing logic (Python returns parsed JSON)

**Code to keep:**
- Route definitions and Express middleware
- Authentication middleware (`requireOpsAuth`)
- Request parameter extraction (`req.query`, `req.body`)
- Response sending (`res.json`)

**Why:** Simplifies TypeScript routes to pure forwarding logic. All business logic moves to Python where it belongs.

**How to apply:** Apply this pattern to every route file during migration phases.

### 3. Migration Phases

**Phase 1: Backtest Routes** (`src/api/web/routes/backtest.ts`)
- `GET /api/backtest/results` → `GET /api/backtest/results` (Python exists)
- `POST /api/backtest/run` → `POST /api/backtest` (Python exists)
- Remove: `BacktestEngine`, `StockDBService`, file reading logic

**Phase 2: Training Routes** (`src/api/web/routes/training.ts`)
- `GET /api/training/history` → Python endpoint (verify exists)
- `GET /api/training/reports` → Python endpoint (verify exists)
- `GET /api/training/report/<filename>` → Python endpoint (verify exists)
- `POST /api/training/start` → Python endpoint (verify exists)
- Remove: All `fs.readFileSync` calls for training reports

**Phase 3: Signals Routes** (`src/api/web/routes/signals.ts`)
- `GET /api/signals` → Python endpoint (verify exists)
- `GET /api/signals/history` → Python endpoint (verify exists)
- `POST /api/signals/scan` → Python endpoint (verify exists)
- Remove: `FactorLibrary`, `StockDBService`, signal file reading

**Phase 4: Other Routes**
- `stocks.ts` - stock list, factors, comparison, data status
- `features.ts` - feature importance
- `performance.ts` - strategy performance
- `charts.ts` - chart data
- `jobs.ts`, `scheduler.ts`, `platform.ts` - already mostly proxied

**Why this order:** Backtest and training are high-value, well-defined endpoints. Signals has more complexity. Other routes are lower priority.

**How to apply:** Complete one phase, test thoroughly, stabilize for 1 week, then proceed to next phase.

### 4. Python Endpoint Verification

**Process:**
1. For each TypeScript route, identify the target Python endpoint
2. Check `quant/api/server.py` for `@app.route` decorator
3. If missing, add the endpoint to Python Flask
4. If exists but response format differs, adjust Python to match frontend expectations

**Known Python endpoints** (from `server.py`):
- `/api/backtest/results` - line 1969 ✓
- `/api/backtest` - line 2049 ✓
- `/api/training/history` - line 2089 ✓
- `/api/training/reports` - line 2130 ✓
- `/api/training/report/<filename>` - line 2150 ✓
- `/api/training/start` - line 2166 ✓
- `/api/signals` - line 1557 ✓
- `/api/signals/history` - line 1598 ✓
- `/api/stocks/list` - line 1761 ✓
- `/api/stock/<symbol>/factors` - line 1395 ✓
- Many others already exist

**Action items:**
- Create checklist of all TypeScript routes
- Map each to Python endpoint
- Test each Python endpoint independently
- Add missing endpoints before migrating corresponding TypeScript route

**Why:** Ensures Python backend is complete before removing TypeScript logic. Prevents runtime failures.

**How to apply:** Before starting each migration phase, verify all target Python endpoints exist and return correct data.

### 5. Configuration and Deployment

**Environment Variables** (`.env`):
```bash
# Python Backend Configuration
PYTHON_BACKEND_URL=http://localhost:5000
PYTHON_BACKEND_TIMEOUT=30000
```

**Development Startup:**
```bash
# Terminal 1: Start Python Flask
cd quant/api
python3 server.py

# Terminal 2: Start TypeScript API
npm run dev
```

**Production Deployment:**
- Python Flask: Deploy with gunicorn/uwsgi on port 5000
- TypeScript API: Deploy with pm2/docker on port 3000
- Both services must be running for system to function
- Use process manager to ensure both services restart on failure

**Health Check:**
- TypeScript API calls `PythonBackendClient.healthCheck()` on startup
- If Python unavailable, log warning but continue startup
- First request will fail with 503 if Python still down
- No automatic service restart or dependency management

**Why:** Independent services allow separate scaling and deployment. Fast failure makes issues obvious.

**How to apply:** Update deployment scripts and documentation to start both services.

### 6. Testing and Validation

**Unit Tests:**
- `PythonBackendClient` error handling (mock fetch responses)
- Test 503 on connection refused
- Test 504 on timeout
- Test pass-through of Python errors

**Integration Tests:**
- Start real Python Flask service
- Test each migrated endpoint
- Compare response format before/after migration
- Verify error responses (Python down, invalid params)

**Regression Tests:**
- Manual frontend testing of key workflows
- Backtest results display
- Training report viewing
- Signal list and filtering

**Validation Checklist (per phase):**
- [ ] Python endpoint exists and accessible
- [ ] TypeScript route forwards correctly
- [ ] Response format matches frontend expectations
- [ ] Error handling works (503 when Python down)
- [ ] Performance acceptable (latency increase < 100ms)
- [ ] Old file/database access code removed

**Rollback Plan:**
- Keep old code as comments with `// LEGACY: direct file access` marker
- If issues found, uncomment old code and redeploy
- After 1 week of stable operation, delete legacy code permanently

**Why:** Gradual validation reduces risk. Rollback plan provides safety net.

**How to apply:** Execute validation checklist after each phase before proceeding to next.

## Implementation Checklist

1. [ ] Create `PythonBackendClient` class
2. [ ] Add environment variables to `.env.example`
3. [ ] Verify Python endpoints for Phase 1 (backtest)
4. [ ] Migrate `backtest.ts` routes
5. [ ] Test Phase 1 thoroughly
6. [ ] Verify Python endpoints for Phase 2 (training)
7. [ ] Migrate `training.ts` routes
8. [ ] Test Phase 2 thoroughly
9. [ ] Verify Python endpoints for Phase 3 (signals)
10. [ ] Migrate `signals.ts` routes
11. [ ] Test Phase 3 thoroughly
12. [ ] Migrate remaining routes (Phase 4)
13. [ ] Update documentation (README, deployment guide)
14. [ ] Remove all legacy code after stabilization

## Success Criteria

- Zero direct file system access in TypeScript routes
- Zero `StockDBService` usage in TypeScript routes
- All data operations go through Python Flask
- System functions correctly with both services running
- Clear 503 errors when Python service down
- No performance degradation (< 100ms latency increase)
- All frontend features work as before

## Non-Goals

- Retry logic or circuit breakers (fast failure only)
- Fallback to direct file access (pure proxy)
- Response caching (keep it simple)
- Load balancing or multiple Python instances (single service)
- Automatic service discovery or health monitoring
