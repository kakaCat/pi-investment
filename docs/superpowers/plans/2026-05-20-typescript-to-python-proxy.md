# TypeScript to Python Backend Proxy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate TypeScript API from direct file/database access to Python Flask backend proxy

**Architecture:** Create PythonBackendClient for HTTP communication, migrate routes in 4 phases (backtest → training → signals → others), remove all direct file system and database access from TypeScript layer

**Tech Stack:** TypeScript, Express, Python Flask, node-fetch or axios

---

## File Structure

**New Files:**
- `src/services/python/python-backend-client.ts` - HTTP client for Python backend
- `src/services/python/python-backend-client.test.ts` - Unit tests for client

**Modified Files:**
- `.env.example` - Add Python backend configuration
- `src/api/web/routes/backtest.ts` - Migrate to proxy pattern
- `src/api/web/routes/training.ts` - Migrate to proxy pattern
- `src/api/web/routes/signals.ts` - Migrate to proxy pattern
- `src/api/web/routes/stocks.ts` - Migrate to proxy pattern
- `src/api/web/routes/features.ts` - Migrate to proxy pattern
- `src/api/web/routes/performance.ts` - Migrate to proxy pattern
- `src/api/web/routes/charts.ts` - Migrate to proxy pattern

---

## Task 1: Create PythonBackendClient

**Files:**
- Create: `src/services/python/python-backend-client.ts`
- Create: `src/services/python/python-backend-client.test.ts`

- [ ] **Step 1: Write failing test for getInstance singleton**

Create `src/services/python/python-backend-client.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { PythonBackendClient } from './python-backend-client.js';

describe('PythonBackendClient', () => {
  it('should return same instance on multiple calls', () => {
    const instance1 = PythonBackendClient.getInstance();
    const instance2 = PythonBackendClient.getInstance();
    expect(instance1).toBe(instance2);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test src/services/python/python-backend-client.test.ts`
Expected: FAIL with "Cannot find module"

- [ ] **Step 3: Create PythonBackendClient class with singleton**

Create `src/services/python/python-backend-client.ts`:

```typescript
export class PythonBackendClient {
  private static instance: PythonBackendClient | null = null;
  private baseURL: string;
  private timeout: number;

  private constructor() {
    this.baseURL = process.env.PYTHON_BACKEND_URL || 'http://localhost:5000';
    this.timeout = parseInt(process.env.PYTHON_BACKEND_TIMEOUT || '30000', 10);
  }

  static getInstance(): PythonBackendClient {
    if (!PythonBackendClient.instance) {
      PythonBackendClient.instance = new PythonBackendClient();
    }
    return PythonBackendClient.instance;
  }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test src/services/python/python-backend-client.test.ts`
Expected: PASS

- [ ] **Step 5: Commit singleton implementation**

```bash
git add src/services/python/
git commit -m "feat(python-client): add PythonBackendClient singleton"
```

- [ ] **Step 6: Write failing test for GET request success**

Add to `src/services/python/python-backend-client.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

describe('PythonBackendClient', () => {
  // ... existing test

  describe('get', () => {
    beforeEach(() => {
      global.fetch = vi.fn();
    });

    afterEach(() => {
      vi.restoreAllMocks();
    });

    it('should make GET request and return JSON data', async () => {
      const mockData = { result: 'success' };
      (global.fetch as any).mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => mockData,
      });

      const client = PythonBackendClient.getInstance();
      const result = await client.get('/api/test', { param: 'value' });

      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:5000/api/test?param=value',
        expect.objectContaining({
          method: 'GET',
          headers: { 'Content-Type': 'application/json' },
        })
      );
      expect(result).toEqual(mockData);
    });
  });
});
```

- [ ] **Step 7: Run test to verify it fails**

Run: `npm test src/services/python/python-backend-client.test.ts`
Expected: FAIL with "client.get is not a function"

- [ ] **Step 8: Implement GET method**

Add to `src/services/python/python-backend-client.ts`:

```typescript
export class PythonBackendClient {
  // ... existing code

  async get(path: string, params?: Record<string, any>): Promise<any> {
    const url = new URL(path, this.baseURL);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null) {
          url.searchParams.append(key, String(value));
        }
      });
    }

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url.toString(), {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const error: any = new Error(`HTTP ${response.status}: ${response.statusText}`);
        error.status = response.status;
        throw error;
      }

      return await response.json();
    } catch (error: any) {
      clearTimeout(timeoutId);
      if (error.name === 'AbortError') {
        const timeoutError: any = new Error('Gateway timeout');
        timeoutError.status = 504;
        throw timeoutError;
      }
      if (error.code === 'ECONNREFUSED' || error.cause?.code === 'ECONNREFUSED') {
        const serviceError: any = new Error('Python backend service unavailable');
        serviceError.status = 503;
        throw serviceError;
      }
      throw error;
    }
  }
}
```

- [ ] **Step 9: Run test to verify it passes**

Run: `npm test src/services/python/python-backend-client.test.ts`
Expected: PASS

- [ ] **Step 10: Commit GET implementation**

```bash
git add src/services/python/
git commit -m "feat(python-client): implement GET method with error handling"
```

- [ ] **Step 11: Write failing test for POST request**

Add to `src/services/python/python-backend-client.test.ts`:

```typescript
describe('post', () => {
  beforeEach(() => {
    global.fetch = vi.fn();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should make POST request with body', async () => {
    const mockData = { id: 123 };
    (global.fetch as any).mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => mockData,
    });

    const client = PythonBackendClient.getInstance();
    const result = await client.post('/api/create', { name: 'test' });

    expect(global.fetch).toHaveBeenCalledWith(
      'http://localhost:5000/api/create',
      expect.objectContaining({
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: 'test' }),
      })
    );
    expect(result).toEqual(mockData);
  });
});
```

- [ ] **Step 12: Run test to verify it fails**

Run: `npm test src/services/python/python-backend-client.test.ts`
Expected: FAIL with "client.post is not a function"

- [ ] **Step 13: Implement POST, PUT, DELETE methods**

Add to `src/services/python/python-backend-client.ts`:

```typescript
export class PythonBackendClient {
  // ... existing code

  async post(path: string, body?: any): Promise<any> {
    return this.request('POST', path, body);
  }

  async put(path: string, body?: any): Promise<any> {
    return this.request('PUT', path, body);
  }

  async delete(path: string): Promise<any> {
    return this.request('DELETE', path);
  }

  private async request(method: string, path: string, body?: any): Promise<any> {
    const url = new URL(path, this.baseURL);
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), this.timeout);

    try {
      const response = await fetch(url.toString(), {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: body ? JSON.stringify(body) : undefined,
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        const error: any = new Error(`HTTP ${response.status}: ${response.statusText}`);
        error.status = response.status;
        throw error;
      }

      return await response.json();
    } catch (error: any) {
      clearTimeout(timeoutId);
      if (error.name === 'AbortError') {
        const timeoutError: any = new Error('Gateway timeout');
        timeoutError.status = 504;
        throw timeoutError;
      }
      if (error.code === 'ECONNREFUSED' || error.cause?.code === 'ECONNREFUSED') {
        const serviceError: any = new Error('Python backend service unavailable');
        serviceError.status = 503;
        throw serviceError;
      }
      throw error;
    }
  }
}
```

- [ ] **Step 14: Run test to verify it passes**

Run: `npm test src/services/python/python-backend-client.test.ts`
Expected: PASS

- [ ] **Step 15: Write failing test for 503 error on connection refused**

Add to `src/services/python/python-backend-client.test.ts`:

```typescript
it('should throw 503 error when connection refused', async () => {
  const connError: any = new Error('fetch failed');
  connError.cause = { code: 'ECONNREFUSED' };
  (global.fetch as any).mockRejectedValue(connError);

  const client = PythonBackendClient.getInstance();
  
  await expect(client.get('/api/test')).rejects.toMatchObject({
    message: 'Python backend service unavailable',
    status: 503,
  });
});
```

- [ ] **Step 16: Run test to verify it passes (already implemented)**

Run: `npm test src/services/python/python-backend-client.test.ts`
Expected: PASS

- [ ] **Step 17: Write failing test for 504 timeout error**

Add to `src/services/python/python-backend-client.test.ts`:

```typescript
it('should throw 504 error on timeout', async () => {
  (global.fetch as any).mockImplementation(() => 
    new Promise((resolve) => setTimeout(resolve, 35000))
  );

  const client = PythonBackendClient.getInstance();
  
  await expect(client.get('/api/test')).rejects.toMatchObject({
    message: 'Gateway timeout',
    status: 504,
  });
});
```

- [ ] **Step 18: Run test to verify it passes (already implemented)**

Run: `npm test src/services/python/python-backend-client.test.ts`
Expected: PASS

- [ ] **Step 19: Implement healthCheck method**

Add to `src/services/python/python-backend-client.ts`:

```typescript
export class PythonBackendClient {
  // ... existing code

  async healthCheck(): Promise<boolean> {
    try {
      await this.get('/api/health');
      return true;
    } catch (error) {
      return false;
    }
  }
}
```

- [ ] **Step 20: Commit complete PythonBackendClient**

```bash
git add src/services/python/
git commit -m "feat(python-client): add POST/PUT/DELETE and healthCheck methods"
```

---

## Task 2: Add Environment Configuration

**Files:**
- Modify: `.env.example`

- [ ] **Step 1: Add Python backend configuration to .env.example**

Add to `.env.example`:

```bash
# Python Backend Configuration
PYTHON_BACKEND_URL=http://localhost:5000
PYTHON_BACKEND_TIMEOUT=30000
```

- [ ] **Step 2: Commit configuration**

```bash
git add .env.example
git commit -m "config: add Python backend environment variables"
```

---

## Task 3: Phase 1 - Migrate Backtest Routes

**Files:**
- Modify: `src/api/web/routes/backtest.ts`

- [ ] **Step 1: Verify Python endpoints exist**

Run: `curl http://localhost:5000/api/backtest/results`
Expected: JSON response or connection error (if Python not running)

Run: `curl -X POST http://localhost:5000/api/backtest -H "Content-Type: application/json" -d '{"strategy_id":"test"}'`
Expected: JSON response or validation error

- [ ] **Step 2: Backup current backtest.ts implementation**

```bash
cp src/api/web/routes/backtest.ts src/api/web/routes/backtest.ts.backup
```

- [ ] **Step 3: Migrate GET /api/backtest/results endpoint**

In `src/api/web/routes/backtest.ts`, replace the `/results` route handler:

```typescript
import { PythonBackendClient } from '../../../services/python/python-backend-client.js';

// LEGACY: direct file access - kept for rollback
/*
router.get('/results', async (req, res, next) => {
  try {
    const symbol = typeof req.query.symbol === 'string' ? req.query.symbol : undefined;
    const date = typeof req.query.date === 'string' ? req.query.date : undefined;
    // ... old implementation
  } catch (error) {
    next(error);
  }
});
*/

// NEW: proxy to Python backend
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

- [ ] **Step 4: Remove unused imports from backtest.ts**

Remove these imports:

```typescript
// Remove:
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

// Remove these lines:
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
```

- [ ] **Step 5: Test GET /results endpoint**

Start Python backend:
```bash
cd quant/api && python3 server.py
```

Start TypeScript API:
```bash
npm run dev
```

Test:
```bash
curl http://localhost:3000/api/backtest/results
```
Expected: JSON response with backtest results

- [ ] **Step 6: Migrate POST /api/backtest/run endpoint**

In `src/api/web/routes/backtest.ts`, replace the `/run` route handler:

```typescript
// LEGACY: direct BacktestEngine usage
/*
router.post('/run', requireOpsAuth(), async (req, res, next) => {
  try {
    const { strategy_id, symbol, start_date, end_date, initial_capital = 100000 } = req.body;
    // ... old implementation with BacktestEngine
  } catch (error) {
    next(error);
  }
});
*/

// NEW: proxy to Python backend
router.post('/run', requireOpsAuth(), async (req, res, next) => {
  try {
    const client = PythonBackendClient.getInstance();
    const data = await client.post('/api/backtest', req.body);
    res.json(data);
  } catch (error) {
    next(error);
  }
});
```

- [ ] **Step 7: Remove BacktestEngine and StockDBService imports**

Remove from `src/api/web/routes/backtest.ts`:

```typescript
// Remove:
type QuantServiceInstance = import('../../../services/quant/quant-service.js').QuantService;
type StockDBServiceInstance = import('../../../services/data/stock-db-service.js').StockDBService;

let quantService: QuantServiceInstance | undefined;
let stockDBService: StockDBServiceInstance | undefined;

async function getQuantService(): Promise<QuantServiceInstance> { ... }
async function getStockDBService(): Promise<StockDBServiceInstance> { ... }
```

- [ ] **Step 8: Test POST /run endpoint**

```bash
curl -X POST http://localhost:3000/api/backtest/run \
  -H "Content-Type: application/json" \
  -d '{"strategy_id":"ma_cross","symbol":"600036","start_date":"2026-01-01","end_date":"2026-05-01"}'
```
Expected: JSON response with backtest result

- [ ] **Step 9: Commit Phase 1 migration**

```bash
git add src/api/web/routes/backtest.ts
git commit -m "refactor(backtest): migrate to Python backend proxy"
```


---

## Task 4: Phase 2 - Migrate Training Routes

**Files:**
- Modify: `src/api/web/routes/training.ts`

- [ ] **Step 1: Verify Python training endpoints exist**

```bash
curl http://localhost:5000/api/training/history
curl http://localhost:5000/api/training/reports
```
Expected: JSON responses

- [ ] **Step 2: Backup current training.ts**

```bash
cp src/api/web/routes/training.ts src/api/web/routes/training.ts.backup
```

- [ ] **Step 3: Migrate GET /api/training/history endpoint**

In `src/api/web/routes/training.ts`:

```typescript
import { PythonBackendClient } from '../../../services/python/python-backend-client.js';

// LEGACY: direct file access
/*
router.get('/history', async (req, res, next) => {
  try {
    const files = fs.readdirSync(modelsDir);
    // ... old implementation
  } catch (error) {
    next(error);
  }
});
*/

// NEW: proxy to Python backend
router.get('/history', async (req, res, next) => {
  try {
    const client = PythonBackendClient.getInstance();
    const data = await client.get('/api/training/history', req.query);
    res.json(data);
  } catch (error) {
    next(error);
  }
});
```

- [ ] **Step 4: Migrate GET /api/training/reports endpoint**

```typescript
// LEGACY: direct file access
/*
router.get('/reports', async (req, res, next) => {
  try {
    const files = fs.readdirSync(modelsDir);
    // ... old implementation
  } catch (error) {
    next(error);
  }
});
*/

// NEW: proxy to Python backend
router.get('/reports', async (req, res, next) => {
  try {
    const client = PythonBackendClient.getInstance();
    const data = await client.get('/api/training/reports', req.query);
    res.json(data);
  } catch (error) {
    next(error);
  }
});
```

- [ ] **Step 5: Migrate GET /api/training/report/:filename endpoint**

```typescript
// LEGACY: direct file access
/*
router.get('/report/:filename', async (req, res, next) => {
  try {
    const content = fs.readFileSync(reportPath, 'utf-8');
    // ... old implementation
  } catch (error) {
    next(error);
  }
});
*/

// NEW: proxy to Python backend
router.get('/report/:filename', async (req, res, next) => {
  try {
    const client = PythonBackendClient.getInstance();
    const data = await client.get(`/api/training/report/${req.params.filename}`);
    res.json(data);
  } catch (error) {
    next(error);
  }
});
```

- [ ] **Step 6: Migrate POST /api/training/start endpoint**

```typescript
// LEGACY: direct script execution
/*
router.post('/start', requireOpsAuth(), async (req, res, next) => {
  try {
    // ... old implementation with subprocess
  } catch (error) {
    next(error);
  }
});
*/

// NEW: proxy to Python backend
router.post('/start', requireOpsAuth(), async (req, res, next) => {
  try {
    const client = PythonBackendClient.getInstance();
    const data = await client.post('/api/training/start', req.body);
    res.json(data);
  } catch (error) {
    next(error);
  }
});
```

- [ ] **Step 7: Remove fs imports from training.ts**

Remove:
```typescript
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
```

- [ ] **Step 8: Test training endpoints**

```bash
curl http://localhost:3000/api/training/history
curl http://localhost:3000/api/training/reports
```
Expected: JSON responses

- [ ] **Step 9: Commit Phase 2 migration**

```bash
git add src/api/web/routes/training.ts
git commit -m "refactor(training): migrate to Python backend proxy"
```

---

## Task 5: Phase 3 - Migrate Signals Routes

**Files:**
- Modify: `src/api/web/routes/signals.ts`

- [ ] **Step 1: Verify Python signals endpoints exist**

```bash
curl http://localhost:5000/api/signals
curl http://localhost:5000/api/signals/history
```
Expected: JSON responses

- [ ] **Step 2: Backup current signals.ts**

```bash
cp src/api/web/routes/signals.ts src/api/web/routes/signals.ts.backup
```

- [ ] **Step 3: Migrate GET /api/signals endpoint**

In `src/api/web/routes/signals.ts`:

```typescript
import { PythonBackendClient } from '../../../services/python/python-backend-client.js';

// LEGACY: direct file access with FactorLibrary
/*
router.get('/', async (req, res, next) => {
  try {
    const rawData = fs.readFileSync(signalsPath, 'utf-8');
    // ... old implementation
  } catch (error) {
    next(error);
  }
});
*/

// NEW: proxy to Python backend
router.get('/', async (req, res, next) => {
  try {
    const client = PythonBackendClient.getInstance();
    const data = await client.get('/api/signals', req.query);
    res.json(data);
  } catch (error) {
    next(error);
  }
});
```

- [ ] **Step 4: Migrate GET /api/signals/history endpoint**

```typescript
// LEGACY: direct file access
/*
router.get('/history', async (req, res, next) => {
  try {
    // ... old implementation
  } catch (error) {
    next(error);
  }
});
*/

// NEW: proxy to Python backend
router.get('/history', async (req, res, next) => {
  try {
    const client = PythonBackendClient.getInstance();
    const data = await client.get('/api/signals/history', req.query);
    res.json(data);
  } catch (error) {
    next(error);
  }
});
```

- [ ] **Step 5: Migrate POST /api/signals/scan endpoint**

```typescript
// LEGACY: direct FactorLibrary usage
/*
router.post('/scan', async (req, res, next) => {
  try {
    // ... old implementation with FactorLibrary
  } catch (error) {
    next(error);
  }
});
*/

// NEW: proxy to Python backend
router.post('/scan', async (req, res, next) => {
  try {
    const client = PythonBackendClient.getInstance();
    const data = await client.post('/api/signals/scan', req.body);
    res.json(data);
  } catch (error) {
    next(error);
  }
});
```

- [ ] **Step 6: Remove FactorLibrary and StockDBService imports**

Remove from `src/api/web/routes/signals.ts`:

```typescript
// Remove:
import fs from 'fs';
import path from 'path';
type FactorLibraryInstance = import('../../../services/quant/factor-library.js').FactorLibrary;
type StockDBServiceInstance = import('../../../services/data/stock-db-service.js').StockDBService;

let factorLibrary: FactorLibraryInstance | undefined;
async function getFactorLibrary(): Promise<FactorLibraryInstance> { ... }
```

- [ ] **Step 7: Test signals endpoints**

```bash
curl http://localhost:3000/api/signals
curl http://localhost:3000/api/signals/history
```
Expected: JSON responses

- [ ] **Step 8: Commit Phase 3 migration**

```bash
git add src/api/web/routes/signals.ts
git commit -m "refactor(signals): migrate to Python backend proxy"
```

---

## Task 6: Phase 4 - Migrate Remaining Routes

**Files:**
- Modify: `src/api/web/routes/stocks.ts`
- Modify: `src/api/web/routes/features.ts`
- Modify: `src/api/web/routes/performance.ts`
- Modify: `src/api/web/routes/charts.ts`

- [ ] **Step 1: Migrate stocks.ts routes**

For each route in `src/api/web/routes/stocks.ts`, apply proxy pattern:

```typescript
import { PythonBackendClient } from '../../../services/python/python-backend-client.js';

// Example for GET /api/stocks/list
router.get('/list', async (req, res, next) => {
  try {
    const client = PythonBackendClient.getInstance();
    const data = await client.get('/api/stocks/list', req.query);
    res.json(data);
  } catch (error) {
    next(error);
  }
});

// Example for GET /api/stocks/:symbol/factors
router.get('/:symbol/factors', async (req, res, next) => {
  try {
    const client = PythonBackendClient.getInstance();
    const data = await client.get(`/api/stocks/${req.params.symbol}/factors`, req.query);
    res.json(data);
  } catch (error) {
    next(error);
  }
});

// Example for POST /api/stocks/compare
router.post('/compare', async (req, res, next) => {
  try {
    const client = PythonBackendClient.getInstance();
    const data = await client.post('/api/stocks/compare', req.body);
    res.json(data);
  } catch (error) {
    next(error);
  }
});
```

- [ ] **Step 2: Test stocks endpoints**

```bash
curl http://localhost:3000/api/stocks/list
curl http://localhost:3000/api/stocks/600036/factors
```
Expected: JSON responses

- [ ] **Step 3: Commit stocks migration**

```bash
git add src/api/web/routes/stocks.ts
git commit -m "refactor(stocks): migrate to Python backend proxy"
```

- [ ] **Step 4: Migrate features.ts routes**

```typescript
import { PythonBackendClient } from '../../../services/python/python-backend-client.js';

router.get('/', async (req, res, next) => {
  try {
    const client = PythonBackendClient.getInstance();
    const data = await client.get('/api/feature-importance', req.query);
    res.json(data);
  } catch (error) {
    next(error);
  }
});
```

- [ ] **Step 5: Commit features migration**

```bash
git add src/api/web/routes/features.ts
git commit -m "refactor(features): migrate to Python backend proxy"
```

- [ ] **Step 6: Migrate performance.ts routes**

```typescript
import { PythonBackendClient } from '../../../services/python/python-backend-client.js';

router.get('/strategy/:strategy_id', async (req, res, next) => {
  try {
    const client = PythonBackendClient.getInstance();
    const data = await client.get(`/api/performance/strategy/${req.params.strategy_id}`, req.query);
    res.json(data);
  } catch (error) {
    next(error);
  }
});
```

- [ ] **Step 7: Commit performance migration**

```bash
git add src/api/web/routes/performance.ts
git commit -m "refactor(performance): migrate to Python backend proxy"
```

- [ ] **Step 8: Migrate charts.ts routes**

```typescript
import { PythonBackendClient } from '../../../services/python/python-backend-client.js';

router.get('/accuracy', async (req, res, next) => {
  try {
    const client = PythonBackendClient.getInstance();
    const data = await client.get('/api/charts/accuracy', req.query);
    res.json(data);
  } catch (error) {
    next(error);
  }
});
```

- [ ] **Step 9: Commit charts migration**

```bash
git add src/api/web/routes/charts.ts
git commit -m "refactor(charts): migrate to Python backend proxy"
```

---

## Task 7: Integration Testing

**Files:**
- None (manual testing)

- [ ] **Step 1: Start both services**

Terminal 1:
```bash
cd quant/api
python3 server.py
```

Terminal 2:
```bash
npm run dev
```

- [ ] **Step 2: Test backtest workflow**

```bash
# Get backtest results
curl http://localhost:3000/api/backtest/results

# Run backtest
curl -X POST http://localhost:3000/api/backtest/run \
  -H "Content-Type: application/json" \
  -d '{"strategy_id":"ma_cross","symbol":"600036","start_date":"2026-01-01","end_date":"2026-05-01"}'
```
Expected: Both return valid JSON

- [ ] **Step 3: Test training workflow**

```bash
curl http://localhost:3000/api/training/history
curl http://localhost:3000/api/training/reports
```
Expected: Valid JSON responses

- [ ] **Step 4: Test signals workflow**

```bash
curl http://localhost:3000/api/signals
curl http://localhost:3000/api/signals/history
```
Expected: Valid JSON responses

- [ ] **Step 5: Test error handling - stop Python service**

Stop Python Flask (Ctrl+C in Terminal 1)

```bash
curl http://localhost:3000/api/backtest/results
```
Expected: HTTP 503 with "Python backend service unavailable"

- [ ] **Step 6: Restart Python service and verify recovery**

Restart Python Flask:
```bash
cd quant/api && python3 server.py
```

```bash
curl http://localhost:3000/api/backtest/results
```
Expected: Valid JSON response

- [ ] **Step 7: Document test results**

Create test log noting:
- All endpoints tested
- Response times
- Any issues found
- Confirmation that 503 errors work correctly

---

## Task 8: Cleanup and Documentation

**Files:**
- Remove: `src/api/web/routes/*.backup` files
- Modify: `README.md` or deployment docs

- [ ] **Step 1: Remove backup files**

```bash
rm src/api/web/routes/*.backup
```

- [ ] **Step 2: Remove legacy commented code**

Review each migrated route file and remove `// LEGACY:` commented blocks after confirming stability (wait 1 week in production).

- [ ] **Step 3: Update README with startup instructions**

Add to README.md:

```markdown
## Development Setup

### Starting the Services

This project requires two services to run:

1. **Python Flask Backend** (port 5000):
   ```bash
   cd quant/api
   python3 server.py
   ```

2. **TypeScript API** (port 3000):
   ```bash
   npm run dev
   ```

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
PYTHON_BACKEND_URL=http://localhost:5000
PYTHON_BACKEND_TIMEOUT=30000
```

### Troubleshooting

If you see "Python backend service unavailable" errors:
- Ensure Python Flask is running on port 5000
- Check `PYTHON_BACKEND_URL` in your `.env` file
```

- [ ] **Step 4: Commit documentation**

```bash
git add README.md
git commit -m "docs: add Python backend startup instructions"
```

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "refactor: complete migration to Python backend proxy architecture"
```

---

## Validation Checklist

After completing all tasks, verify:

- [ ] Zero `fs.readFileSync/readdirSync` calls in route files
- [ ] Zero `StockDBService` imports in route files
- [ ] Zero `BacktestEngine` imports in route files
- [ ] Zero `FactorLibrary` imports in route files
- [ ] All routes use `PythonBackendClient.getInstance()`
- [ ] Environment variables documented in `.env.example`
- [ ] Both services start successfully
- [ ] All endpoints return valid responses
- [ ] 503 error when Python service down
- [ ] README updated with startup instructions
- [ ] All tests pass: `npm test`

---

## Rollback Procedure

If issues are found after deployment:

1. Restore backup files:
   ```bash
   cp src/api/web/routes/backtest.ts.backup src/api/web/routes/backtest.ts
   ```

2. Uncomment `// LEGACY:` code blocks

3. Remove `PythonBackendClient` imports

4. Restart TypeScript API

5. Investigate issue before re-attempting migration

