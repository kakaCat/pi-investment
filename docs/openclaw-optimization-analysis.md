# OpenClaw Architecture Analysis & PI-Investment Optimization Recommendations

**Analysis Date**: 2026-08-13  
**Source**: OpenClaw (Claude Code) open-source codebase

---

## Executive Summary

OpenClaw (Claude Code) is Anthropic's production-grade AI agent framework. After analyzing its architecture, I've identified **8 high-impact optimization areas** for the pi-investment agent project that can significantly improve reliability, maintainability, and performance.

---

## 1. Loop Detection & Circuit Breaker (P0 - Critical)

### OpenClaw Implementation

**File**: `src/agents/tool-loop-detection.ts` (624 lines)

**Key Features**:
- **Hash-based tool call tracking**: Uses SHA-256 digest of `toolName + stableStringify(params)` to detect identical calls
- **Three-tier detection**:
  - **Generic Repeat**: Same tool+params called N times
  - **Known Poll No Progress**: Polling tools returning identical results repeatedly
  - **Ping-Pong**: Alternating between two tool patterns with no progress
- **Progressive thresholds**:
  - Warning: 10 calls
  - Critical: 20 calls
  - Global Circuit Breaker: 30 calls (hard stop)
- **Result hashing**: Tracks tool outcomes to detect "no progress" loops

```typescript
// OpenClaw's approach
export function detectToolCallLoop(
  state: SessionState,
  toolName: string,
  params: unknown,
  config?: ToolLoopDetectionConfig,
): LoopDetectionResult {
  const history = state.toolCallHistory ?? [];
  const currentHash = hashToolCall(toolName, params);
  const noProgress = getNoProgressStreak(history, toolName, currentHash);
  
  if (noProgressStreak >= globalCircuitBreakerThreshold) {
    return {
      stuck: true,
      level: "critical",
      detector: "global_circuit_breaker",
      message: "Session execution blocked by global circuit breaker"
    };
  }
  // ... more detectors
}
```

### PI-Investment Current State

**File**: `agent-ts/src/services/loop-guardian.ts` (exists)

**Gaps**:
- ✅ Has basic no_tool detection
- ✅ Has silent failure notification
- ❌ **No tool call hashing/fingerprinting**
- ❌ **No ping-pong detection**
- ❌ **No result-based no-progress detection**
- ❌ **No configurable thresholds per tool type**

### Recommended Actions

**Priority**: P0 (Already causing production issues per memory)

1. **Add Tool Call Fingerprinting**
   ```typescript
   // Add to loop-guardian.ts
   import { createHash } from 'crypto';
   
   function hashToolCall(toolName: string, params: unknown): string {
     const serialized = JSON.stringify(params, Object.keys(params).sort());
     return `${toolName}:${createHash('sha256').update(serialized).digest('hex')}`;
   }
   ```

2. **Implement Result-Based Detection**
   ```typescript
   interface ToolCallRecord {
     toolName: string;
     argsHash: string;
     resultHash?: string; // Hash of tool output
     timestamp: number;
   }
   
   // Detect if same input produces same output repeatedly
   function getNoProgressStreak(history: ToolCallRecord[]): number {
     // Implementation similar to OpenClaw's
   }
   ```

3. **Add Ping-Pong Detector**
   ```typescript
   // Detect alternating pattern: A -> B -> A -> B with no progress
   function detectPingPongLoop(history: ToolCallRecord[]): {
     detected: boolean;
     count: number;
     toolA: string;
     toolB: string;
   }
   ```

4. **Configure Thresholds by Tool Category**
   ```typescript
   const LOOP_CONFIG = {
     market_data: { warning: 5, critical: 10 },  // Fast fail for data fetching
     analysis: { warning: 8, critical: 15 },      // More tolerance for analysis
     trading: { warning: 3, critical: 5 },        // Strict for trading actions
   };
   ```

**Expected Impact**: Reduce infinite loop incidents by 80-90%, catch stuck patterns earlier.

---

## 2. Retry Policy with Exponential Backoff (P0)

### OpenClaw Implementation

**File**: `src/infra/retry.ts` (138 lines)

**Key Features**:
- **Configurable retry strategy**: attempts, minDelayMs, maxDelayMs, jitter
- **Exponential backoff**: `minDelayMs * 2^(attempt-1)`
- **Retry-After header support**: Honors server-side retry hints
- **Conditional retry**: `shouldRetry(err, attempt) => boolean` callback
- **Jitter**: Adds randomness to prevent thundering herd (0-100% jitter)

```typescript
export async function retryAsync<T>(
  fn: () => Promise<T>,
  options: RetryOptions = {},
): Promise<T> {
  const resolved = resolveRetryConfig(DEFAULT_RETRY_CONFIG, options);
  
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    try {
      return await fn();
    } catch (err) {
      if (attempt >= maxAttempts || !shouldRetry(err, attempt)) {
        throw err;
      }
      
      // Exponential backoff with jitter
      let delay = minDelayMs * 2 ** (attempt - 1);
      delay = Math.min(delay, maxDelayMs);
      delay = applyJitter(delay, jitter); // ±jitter% randomness
      
      await sleep(delay);
    }
  }
}
```

### PI-Investment Current State

**Files**: 
- `agent-ts/src/infrastructure/llm/index.ts` (has basic retry)
- `quantsys-v2` (various ad-hoc retry logic)

**Gaps**:
- ✅ SDK has built-in LLM retry (per memory)
- ❌ **No unified retry infrastructure**
- ❌ **No jitter (thundering herd risk)**
- ❌ **No per-error-type retry logic**
- ❌ **Inconsistent retry configs across services**

### Recommended Actions

**Priority**: P0 (Network reliability critical for trading)

1. **Create Unified Retry Module**
   ```typescript
   // agent-ts/src/infrastructure/retry.ts
   export class RetryPolicy {
     static readonly NETWORK_ERROR = {
       attempts: 5,
       minDelayMs: 500,
       maxDelayMs: 30_000,
       jitter: 0.3, // 30% jitter
       shouldRetry: (err: any) => 
         err.code === 'ECONNRESET' || 
         err.code === 'ETIMEDOUT' ||
         err.response?.status === 429,
     };
     
     static readonly API_RATE_LIMIT = {
       attempts: 3,
       minDelayMs: 2000,
       maxDelayMs: 60_000,
       jitter: 0.5,
       retryAfterMs: (err: any) => 
         err.response?.headers['retry-after'] * 1000,
     };
     
     static readonly DATA_SOURCE = {
       attempts: 4,
       minDelayMs: 1000,
       maxDelayMs: 15_000,
       jitter: 0.4,
       shouldRetry: (err: any) => 
         err.response?.status >= 500 || // Server errors
         err.code === 'ECONNREFUSED',   // Service down
     };
   }
   ```

2. **Apply to Critical Paths**
   ```typescript
   // In quantsys-v2 API clients
   import { retryAsync, RetryPolicy } from './retry';
   
   async function fetchMarketData(symbol: string) {
     return retryAsync(
       () => akshareClient.get(`/stock/${symbol}`),
       RetryPolicy.DATA_SOURCE
     );
   }
   ```

3. **Add Retry Metrics**
   ```typescript
   interface RetryMetrics {
     totalAttempts: number;
     successOnRetry: number;
     finalFailures: number;
     avgRetryCount: number;
   }
   
   // Log to PostgreSQL for analysis
   ```

**Expected Impact**: Reduce transient network failure incidents by 70%, improve data source reliability.

---

## 3. Structured Session State Management (P1)

### OpenClaw Implementation

**File**: `src/logging/diagnostic-session-state.ts`

**Key Features**:
- **Typed session state**: All state fields have explicit types
- **History tracking**: Tool calls, warnings, errors tracked in arrays
- **Sliding window**: Old history auto-pruned (e.g., last 30 tool calls)
- **State snapshots**: Can checkpoint/restore session state
- **Diagnostic exports**: Session state can be dumped for debugging

```typescript
export interface SessionState {
  sessionId: string;
  startTime: number;
  
  // Tool call history for loop detection
  toolCallHistory?: Array<{
    toolName: string;
    argsHash: string;
    resultHash?: string;
    toolCallId?: string;
    timestamp: number;
  }>;
  
  // Warning tracking (deduplication)
  issuedWarnings?: Set<string>;
  
  // Error recovery state
  consecutiveErrors?: number;
  lastErrorTime?: number;
  
  // Custom metadata
  metadata?: Record<string, unknown>;
}
```

### PI-Investment Current State

**Files**:
- `agent-ts/src/core/session/session-manager.ts`
- `agent-ts/src/core/state/conversation-state.ts`

**Gaps**:
- ✅ Has basic session management
- ❌ **State scattered across multiple objects**
- ❌ **No structured diagnostic state**
- ❌ **No state snapshots for debugging**
- ❌ **No pruning of old history (memory leak risk)**

### Recommended Actions

**Priority**: P1 (Improves debuggability and reliability)

1. **Create Unified SessionState Interface**
   ```typescript
   // agent-ts/src/core/session/session-state.ts
   export interface InvestmentSessionState {
     // Identity
     sessionId: string;
     channel: 'cli' | 'tui' | 'feishu' | 'scheduled';
     startTime: number;
     
     // Tool execution history (for loop detection)
     toolCallHistory: ToolCallRecord[];
     
     // Trading context
     tradingContext?: {
       activeStrategy?: string;
       holdingPositions: string[]; // symbol list
       todayTrades: number;
       riskLevel: 'conservative' | 'moderate' | 'aggressive';
     };
     
     // Error recovery
     consecutiveErrors: number;
     lastErrorTime?: number;
     issuedWarnings: Set<string>;
     
     // Performance tracking
     metrics: {
       toolCallCount: number;
       llmCallCount: number;
       totalTokens: number;
       executionTimeMs: number;
     };
     
     // Debugging
     metadata: Record<string, any>;
   }
   ```

2. **Add State Snapshot/Restore**
   ```typescript
   export class SessionStateManager {
     saveSnapshot(state: InvestmentSessionState): string {
       const snapshot = {
         ...state,
         issuedWarnings: Array.from(state.issuedWarnings),
         timestamp: Date.now(),
       };
       const snapshotId = `snapshot_${state.sessionId}_${Date.now()}`;
       fs.writeFileSync(
         `${SESSION_DIR}/${snapshotId}.json`,
         JSON.stringify(snapshot, null, 2)
       );
       return snapshotId;
     }
     
     restoreSnapshot(snapshotId: string): InvestmentSessionState {
       // Load and restore
     }
   }
   ```

3. **Add Auto-Pruning**
   ```typescript
   function pruneSessionHistory(state: InvestmentSessionState) {
     const MAX_TOOL_HISTORY = 50;
     if (state.toolCallHistory.length > MAX_TOOL_HISTORY) {
       state.toolCallHistory = state.toolCallHistory.slice(-MAX_TOOL_HISTORY);
     }
   }
   ```

**Expected Impact**: Easier debugging, prevent memory leaks, better observability.

---

## 4. Plugin/Extension Architecture (P1-P2)

### OpenClaw Implementation

**Directory**: `src/plugin-sdk/`, `src/plugins/`, `extensions/`

**Key Features**:
- **Plugin manifest**: Each plugin has `openclaw.plugin.json` with metadata
- **Lazy loading**: Plugins loaded on-demand, not at startup
- **Sandboxed execution**: Plugins run in isolated contexts
- **Versioned contracts**: Plugin SDK versioned independently from core
- **Dependency injection**: Plugins receive interfaces, not concrete implementations
- **Hot reload**: Plugins can be updated without restarting

```typescript
// Plugin manifest example
{
  "id": "stock-data-provider",
  "version": "1.0.0",
  "openclaw": {
    "minVersion": "5.0.0",
    "plugin": {
      "entrypoint": "./dist/index.js",
      "capabilities": ["data-source", "market-data"],
      "dependencies": {
        "akshare": "^1.0.0"
      }
    }
  }
}

// Plugin contract
export interface DataProviderPlugin {
  id: string;
  version: string;
  getStockData(symbol: string): Promise<StockData>;
  subscribe?(symbol: string, callback: (data: StockData) => void): void;
}
```

### PI-Investment Current State

**Files**:
- `agent-ts/src/infrastructure/tools/` (60+ tools as monolith)
- `quantsys-v2/adapters/outbound/` (data sources tightly coupled)

**Gaps**:
- ❌ **All tools compiled into main binary**
- ❌ **No plugin architecture**
- ❌ **Data sources tightly coupled to services**
- ❌ **Hard to add new data providers**
- ❌ **No A/B testing of tool implementations**

### Recommended Actions

**Priority**: P2 (Nice to have, not urgent)

1. **Create Plugin System (Phase 1: Tools)**
   ```typescript
   // agent-ts/src/infrastructure/plugins/plugin-manifest.ts
   export interface ToolPluginManifest {
     id: string;
     name: string;
     version: string;
     category: 'market-data' | 'analysis' | 'trading' | 'utility';
     entrypoint: string;
     minAgentVersion: string;
     capabilities: string[];
   }
   
   // Example: convert pool_manage to plugin
   // plugins/pool-management/plugin.json
   {
     "id": "pool-management",
     "name": "Stock Pool Management",
     "version": "2.0.0",
     "category": "analysis",
     "entrypoint": "./dist/index.js",
     "minAgentVersion": "1.5.0",
     "capabilities": ["pool-crud", "pool-validation"]
   }
   ```

2. **Plugin Loader**
   ```typescript
   export class PluginLoader {
     private plugins = new Map<string, ToolPlugin>();
     
     async loadPlugin(manifestPath: string): Promise<void> {
       const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
       const module = await import(manifest.entrypoint);
       this.plugins.set(manifest.id, module.default);
     }
     
     getTool(pluginId: string, toolName: string): Tool | undefined {
       return this.plugins.get(pluginId)?.tools[toolName];
     }
   }
   ```

3. **Benefits for PI-Investment**
   - **Easy A/B testing**: Load v1 vs v2 of a tool dynamically
   - **Hot swap data sources**: Switch from akshare to alternative without restart
   - **Third-party tools**: Community can contribute plugins
   - **Reduced binary size**: Only load needed plugins

**Expected Impact**: Easier experimentation, better modularity, faster iteration on tools.

---

## 5. Memory/Embedding Search Architecture (P1)

### OpenClaw Implementation

**File**: `src/agents/memory-search.ts`

**Key Features**:
- **Provider abstraction**: Supports OpenAI, Gemini, Voyage, Mistral, Ollama, local models
- **Batch embedding**: Can batch multiple texts for efficiency
- **Multimodal support**: Can embed images (Gemini)
- **Configurable per agent**: Each agent can use different embedding provider
- **Retry-After support**: Handles rate limits gracefully

```typescript
export interface MemoryEmbeddingProvider {
  id: string;
  defaultModel: string;
  transport: 'local' | 'remote';
  
  // Batch processing support
  batch?: {
    enabled: boolean;
    concurrency: number;
    pollIntervalMs: number;
  };
  
  // Multimodal support
  supportsMultimodalEmbeddings?: (params: { model: string }) => boolean;
  
  create: (config: ProviderConfig) => Promise<EmbeddingClient>;
}

// Config resolution with defaults
function resolveMemorySearchConfig(
  config: OpenClawConfig,
  agentId: string
): ResolvedMemorySearchConfig | null {
  // Merges agent-specific + global defaults
  // Returns null if disabled
}
```

### PI-Investment Current State

**Files**:
- `agent-ts/src/services/memory/` (W1.1-W1.6 recall framework)
- Uses `bge-m3` via Ollama

**Gaps**:
- ✅ Has hybrid search (BM25 + vector + RRF) (W1.3)
- ✅ Has recall injection (W1.4)
- ❌ **No fallback providers** (single point of failure)
- ❌ **No batch embedding optimization**
- ❌ **Provider config hardcoded**

### Recommended Actions

**Priority**: P1 (Improve recall system reliability)

1. **Add Provider Fallback Chain**
   ```typescript
   // agent-ts/src/services/memory/embedding-providers.ts
   export const EMBEDDING_PROVIDERS = {
     primary: {
       id: 'ollama-bge-m3',
       baseUrl: 'http://127.0.0.1:11434',
       model: 'bge-m3',
     },
     fallback: [
       {
         id: 'openai-text-embedding-3-small',
         baseUrl: process.env.OPENAI_BASE_URL,
         model: 'text-embedding-3-small',
       },
       {
         id: 'deepseek-embedding',
         baseUrl: process.env.DEEPSEEK_API_BASE,
         model: 'text-embedding-v1',
       },
     ],
   };
   
   async function embedWithFallback(text: string): Promise<number[]> {
     let lastError: Error;
     
     for (const provider of [EMBEDDING_PROVIDERS.primary, ...EMBEDDING_PROVIDERS.fallback]) {
       try {
         return await embedText(provider, text);
       } catch (err) {
         lastError = err;
         console.warn(`Embedding provider ${provider.id} failed, trying next`);
       }
     }
     
     throw lastError;
   }
   ```

2. **Batch Embedding for Recall**
   ```typescript
   // When recalling multiple memories
   async function batchEmbed(texts: string[]): Promise<number[][]> {
     const BATCH_SIZE = 10;
     const results: number[][] = [];
     
     for (let i = 0; i < texts.length; i += BATCH_SIZE) {
       const batch = texts.slice(i, i + BATCH_SIZE);
       const batchResults = await Promise.all(
         batch.map(text => embedWithFallback(text))
       );
       results.push(...batchResults);
     }
     
     return results;
   }
   ```

3. **Monitor Embedding Performance**
   ```typescript
   interface EmbeddingMetrics {
     provider: string;
     successes: number;
     failures: number;
     avgLatencyMs: number;
     failoverCount: number;
   }
   // Log to database for provider health monitoring
   ```

**Expected Impact**: No recall failures when Ollama is down, faster batch operations.

---

## 6. Structured Error Types & Recovery (P1)

### OpenClaw Implementation

**Files**: `src/infra/errors.ts`, `src/acp/runtime/errors.ts`

**Key Features**:
- **Error code enums**: Every error has a typed code, not just string messages
- **Discriminated unions**: `Result<T, E>` type for recoverable errors
- **Error context**: Errors carry structured metadata
- **Recovery strategies**: Different errors trigger different recovery logic

```typescript
// Structured error codes
export enum ErrorCode {
  NETWORK_TIMEOUT = 'NETWORK_TIMEOUT',
  RATE_LIMIT_EXCEEDED = 'RATE_LIMIT_EXCEEDED',
  INVALID_TOOL_PARAMS = 'INVALID_TOOL_PARAMS',
  TOOL_EXECUTION_FAILED = 'TOOL_EXECUTION_FAILED',
  MODEL_API_ERROR = 'MODEL_API_ERROR',
}

// Error with context
export class StructuredError extends Error {
  constructor(
    public code: ErrorCode,
    message: string,
    public context?: Record<string, unknown>,
    public recoverable: boolean = false,
  ) {
    super(message);
  }
}

// Result type for recoverable failures
export type Result<T, E extends ErrorCode> =
  | { ok: true; value: T }
  | { ok: false; error: E; message: string; context?: Record<string, unknown> };

// Usage
function fetchStockData(symbol: string): Result<StockData, ErrorCode> {
  try {
    const data = api.get(`/stock/${symbol}`);
    return { ok: true, value: data };
  } catch (err) {
    if (err.response?.status === 429) {
      return {
        ok: false,
        error: ErrorCode.RATE_LIMIT_EXCEEDED,
        message: 'API rate limit hit',
        context: { symbol, retryAfter: err.response.headers['retry-after'] },
      };
    }
    return {
      ok: false,
      error: ErrorCode.NETWORK_TIMEOUT,
      message: err.message,
    };
  }
}
```

### PI-Investment Current State

**Gaps**:
- ❌ **Errors are mostly throw/catch strings**
- ❌ **No structured error codes**
- ❌ **Hard to implement error-specific recovery**
- ❌ **No error metrics/categorization**

### Recommended Actions

**Priority**: P1 (Improves error handling and debugging)

1. **Create Error Code Enum**
   ```typescript
   // agent-ts/src/infrastructure/errors.ts
   export enum InvestmentErrorCode {
     // Network
     QUANTSYS_API_UNREACHABLE = 'QUANTSYS_API_UNREACHABLE',
     DATA_SOURCE_TIMEOUT = 'DATA_SOURCE_TIMEOUT',
     
     // Data
     STOCK_DATA_NOT_FOUND = 'STOCK_DATA_NOT_FOUND',
     FINANCIAL_DATA_INCOMPLETE = 'FINANCIAL_DATA_INCOMPLETE',
     
     // Trading
     INSUFFICIENT_FUNDS = 'INSUFFICIENT_FUNDS',
     TRADING_RULE_VIOLATION = 'TRADING_RULE_VIOLATION',
     T1_RESTRICTION = 'T1_RESTRICTION',
     
     // Tool
     TOOL_PARAMS_INVALID = 'TOOL_PARAMS_INVALID',
     POOL_NOT_FOUND = 'POOL_NOT_FOUND',
     
     // LLM
     LLM_RATE_LIMIT = 'LLM_RATE_LIMIT',
     LLM_CONTEXT_TOO_LONG = 'LLM_CONTEXT_TOO_LONG',
   }
   
   export class InvestmentError extends Error {
     constructor(
       public code: InvestmentErrorCode,
       message: string,
       public recoverable: boolean = false,
       public context?: Record<string, any>,
     ) {
       super(message);
       this.name = 'InvestmentError';
     }
   }
   ```

2. **Error Recovery Strategy**
   ```typescript
   export class ErrorRecoveryStrategy {
     static handle(error: InvestmentError): RecoveryAction {
       switch (error.code) {
         case InvestmentErrorCode.QUANTSYS_API_UNREACHABLE:
           return { action: 'retry', delayMs: 5000, maxAttempts: 3 };
           
         case InvestmentErrorCode.LLM_RATE_LIMIT:
           return { action: 'backoff', delayMs: 60000 };
           
         case InvestmentErrorCode.T1_RESTRICTION:
           return { action: 'abort', reason: 'Cannot sell T1 stocks' };
           
         case InvestmentErrorCode.INSUFFICIENT_FUNDS:
           return { action: 'reduce_size', newSize: 0.5 }; // Try with 50% size
           
         default:
           return { action: 'abort', reason: error.message };
       }
     }
   }
   ```

3. **Add Error Metrics**
   ```typescript
   // Track error patterns for alerting
   interface ErrorMetrics {
     errorCode: InvestmentErrorCode;
     count: number;
     lastOccurrence: Date;
     recovered: number;
     failed: number;
   }
   
   // Store in PostgreSQL, alert if same error > 10 times in 1 hour
   ```

**Expected Impact**: Better error handling, faster debugging, automatic recovery for common failures.

---

## 7. Configuration Schema Validation (P2)

### OpenClaw Implementation

**Files**: `src/config/config.ts`, uses Zod for validation

**Key Features**:
- **Schema-first config**: Config structure defined as Zod schemas
- **Automatic validation**: Invalid config rejected at startup
- **Type safety**: TypeScript types auto-derived from schemas
- **Default values**: Schema defines fallbacks for optional fields
- **Config migration**: Old config formats auto-migrated to new

```typescript
import { z } from 'zod';

// Schema definition
const AgentConfigSchema = z.object({
  model: z.string().default('claude-sonnet-4'),
  maxTokens: z.number().min(1000).max(200000).default(8000),
  temperature: z.number().min(0).max(2).default(1.0),
  memorySearch: z.object({
    enabled: z.boolean().default(true),
    provider: z.enum(['openai', 'gemini', 'local']).default('openai'),
    model: z.string().optional(),
  }).optional(),
  tools: z.object({
    loopDetection: z.object({
      enabled: z.boolean().default(true),
      warningThreshold: z.number().default(10),
      criticalThreshold: z.number().default(20),
    }).default({}),
  }).default({}),
});

// Type auto-derived
type AgentConfig = z.infer<typeof AgentConfigSchema>;

// Usage
function loadConfig(rawConfig: unknown): AgentConfig {
  const result = AgentConfigSchema.safeParse(rawConfig);
  if (!result.success) {
    throw new Error(`Invalid config: ${result.error.message}`);
  }
  return result.data; // Validated + defaults applied
}
```

### PI-Investment Current State

**Files**:
- `agent-ts/.env` (environment variables)
- `agent-ts/src/config.ts` (minimal validation)

**Gaps**:
- ❌ **No schema validation**
- ❌ **Runtime errors from typos in config**
- ❌ **No type safety for config**
- ❌ **Hard to know what config options exist**

### Recommended Actions

**Priority**: P2 (Nice to have, improves developer experience)

1. **Add Zod Schemas for Config**
   ```typescript
   // agent-ts/src/config-schema.ts
   import { z } from 'zod';
   
   const ModelConfigSchema = z.object({
     provider: z.enum(['deepseek', 'openai', 'kimi']).default('deepseek'),
     modelId: z.string().default('deepseek-v4-flash'),
     apiKey: z.string().min(1),
     baseUrl: z.string().url().optional(),
     maxTokens: z.number().int().min(1000).max(200000).default(8000),
     temperature: z.number().min(0).max(2).default(1.0),
   });
   
   const QuantsysConfigSchema = z.object({
     apiUrl: z.string().url(),
     timeout: z.number().int().min(1000).default(30000),
     retryAttempts: z.number().int().min(0).max(10).default(3),
   });
   
   const AgentConfigSchema = z.object({
     model: ModelConfigSchema,
     quantsys: QuantsysConfigSchema,
     memory: z.object({
       enabled: z.boolean().default(true),
       recallLimit: z.number().int().min(1).max(50).default(10),
     }).default({}),
     loopGuard: z.object({
       enabled: z.boolean().default(true),
       maxNoToolTurns: z.number().int().default(3),
     }).default({}),
   });
   
   export type AgentConfig = z.infer<typeof AgentConfigSchema>;
   ```

2. **Load with Validation**
   ```typescript
   // agent-ts/src/config.ts
   export function loadConfig(): AgentConfig {
     const raw = {
       model: {
         provider: process.env.MODEL_PROVIDER || 'deepseek',
         modelId: process.env.MODEL_ID || 'deepseek-v4-flash',
         apiKey: process.env.DEEPSEEK_API_KEY,
         maxTokens: parseInt(process.env.MAX_TOKENS || '8000'),
       },
       quantsys: {
         apiUrl: process.env.QUANTSYS_V2_API_URL,
       },
       // ... more
     };
     
     const result = AgentConfigSchema.safeParse(raw);
     if (!result.success) {
       console.error('Invalid configuration:');
       console.error(result.error.format());
       process.exit(1);
     }
     
     return result.data;
   }
   ```

**Expected Impact**: Catch config errors at startup, not at runtime. Better documentation of config options.

---

## 8. Testing Infrastructure (P2)

### OpenClaw Implementation

**Key Features**:
- **Vitest with V8 coverage**: 70% coverage threshold enforced
- **Isolated tests**: Each test cleans up state (no shared state leaks)
- **Test profiles**: `serial`, `forks`, `live` modes
- **Mock helpers**: Reusable mocks for common patterns
- **Contract tests**: Verify plugin interfaces don't break

```typescript
// Test utilities
export function createMockSession(overrides?: Partial<SessionState>): SessionState {
  return {
    sessionId: 'test-session',
    startTime: Date.now(),
    toolCallHistory: [],
    issuedWarnings: new Set(),
    consecutiveErrors: 0,
    metadata: {},
    ...overrides,
  };
}

// Test with isolated state
describe('loop detection', () => {
  let state: SessionState;
  
  beforeEach(() => {
    state = createMockSession(); // Fresh state each test
  });
  
  it('detects repeated tool calls', () => {
    for (let i = 0; i < 15; i++) {
      recordToolCall(state, 'fetch_data', { symbol: '600519' });
    }
    
    const result = detectToolCallLoop(state, 'fetch_data', { symbol: '600519' });
    expect(result.stuck).toBe(true);
    expect(result.level).toBe('warning');
  });
});
```

### PI-Investment Current State

**Files**:
- `agent-ts/tests/` (Jest tests, 37 suites baseline per memory)
- `quantsys-v2/tests/` (pytest, with some failing baselines)

**Gaps**:
- ❌ **Low test coverage** (no enforced threshold)
- ❌ **Tests not isolated** (state leaks between tests)
- ❌ **No contract tests** (tools can break silently)
- ❌ **Manual test execution** (no CI gate)

### Recommended Actions

**Priority**: P2 (Long-term quality improvement)

1. **Add Contract Tests for Tools**
   ```typescript
   // agent-ts/tests/tools/tool-contracts.test.ts
   import { getAllTools } from '@/infrastructure/tools';
   
   describe('Tool Contracts', () => {
     it('all tools implement required interface', () => {
       const tools = getAllTools();
       
       for (const tool of tools) {
         expect(tool).toHaveProperty('name');
         expect(tool).toHaveProperty('description');
         expect(tool).toHaveProperty('parameters');
         expect(tool).toHaveProperty('run');
         expect(typeof tool.run).toBe('function');
       }
     });
     
     it('tool parameters are valid JSON schema', () => {
       const tools = getAllTools();
       
       for (const tool of tools) {
         expect(() => {
           validateJsonSchema(tool.parameters);
         }).not.toThrow();
       }
     });
   });
   ```

2. **Add Coverage Gate**
   ```json
   // agent-ts/package.json
   {
     "scripts": {
       "test": "jest --coverage",
       "test:ci": "jest --coverage --coverageThreshold='{\"global\":{\"branches\":60,\"functions\":60,\"lines\":60,\"statements\":60}}'"
     }
   }
   ```

3. **Isolated Test Helpers**
   ```typescript
   // agent-ts/tests/helpers/setup.ts
   export function isolateTest() {
     beforeEach(() => {
       // Reset singletons
       resetLLMForTests();
       clearToolRegistry();
       
       // Reset environment
       process.env.NODE_ENV = 'test';
       
       // Mock external services
       mockQuantsysApi();
     });
     
     afterEach(() => {
       // Cleanup
       jest.clearAllMocks();
       jest.restoreAllMocks();
     });
   }
   ```

**Expected Impact**: Prevent regressions, faster debugging, safer refactoring.

---

## Summary: Priority Matrix

| Feature | Priority | Effort | Impact | Status |
|---------|----------|--------|--------|--------|
| **Loop Detection & Circuit Breaker** | **P0** | Medium | High | Partially implemented |
| **Retry Policy with Backoff** | **P0** | Low | High | Scattered implementation |
| **Structured Error Types** | **P1** | Medium | High | Not implemented |
| **Session State Management** | **P1** | Medium | Medium | Partially implemented |
| **Memory Provider Fallback** | **P1** | Low | Medium | Not implemented |
| **Configuration Validation** | **P2** | Low | Low | Not implemented |
| **Plugin Architecture** | **P2** | High | Medium | Not planned |
| **Testing Infrastructure** | **P2** | Medium | Medium | Basic coverage |

---

## Immediate Action Plan

### Week 1: Critical Reliability (P0)

1. **Day 1-2**: Enhance Loop Guardian
   - Add tool call fingerprinting
   - Implement result-based no-progress detection
   - Add ping-pong detector
   - Configure per-tool thresholds

2. **Day 3-4**: Unified Retry Infrastructure
   - Create `retry.ts` module
   - Add jitter to prevent thundering herd
   - Apply to critical paths (quantsys API, data sources, LLM)
   - Add retry metrics

3. **Day 5**: Testing & Validation
   - Test loop detection with known patterns
   - Test retry with simulated failures
   - Monitor production for 48 hours

### Week 2: Error Handling & Observability (P1)

1. **Day 1-2**: Structured Error System
   - Define error code enum
   - Create InvestmentError class
   - Implement error recovery strategies

2. **Day 3-4**: Session State Refactor
   - Create unified SessionState interface
   - Add state snapshot/restore
   - Implement auto-pruning

3. **Day 5**: Memory Provider Fallback
   - Add fallback embedding providers
   - Implement batch embedding
   - Add embedding metrics

### Week 3+: Polish & Documentation (P2)

- Config schema validation (Zod)
- Contract tests for tools
- Coverage gates
- Plugin architecture exploration (if needed)

---

## Key Takeaways from OpenClaw

1. **Reliability First**: OpenClaw has multiple layers of protection (loop detection, retry, circuit breakers) because production AI agents WILL fail in unexpected ways.

2. **Observability is Critical**: Every component emits structured logs and metrics. You can't fix what you can't see.

3. **Fail Fast, Fail Explicit**: Structured errors + typed error codes make recovery logic clear and testable.

4. **State Management Matters**: Session state must be explicit, typed, and pruned. Memory leaks kill long-running agents.

5. **Testing is Non-Negotiable**: Contract tests prevent silent breakage. Isolated tests prevent flaky tests.

6. **Configuration is Code**: Schema-validated config catches errors at startup, not in production.

---

## References

- **OpenClaw Repository**: https://github.com/openclaw/openclaw
- **PI-Investment Agent**: `agent-ts/`
- **LoopGuardian (Current)**: `agent-ts/src/services/loop-guardian.ts`
- **Memory (W1.1-W1.6)**: `agent-ts/src/services/memory/`

---

**Next Steps**: Review this document with the team, prioritize based on current pain points, and start Week 1 implementation.
