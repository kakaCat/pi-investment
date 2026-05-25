# QuantSys V2 Daemon Migration Design

**Date:** 2026-05-25  
**Author:** Claude (Opus 4.7)  
**Status:** Approved

## Executive Summary

Migrate TypeScript agent's six-layer architecture tools (L1-L6, ~30 tools) from the deleted `quant/` backend to the new `quantsys-v2/` backend by implementing a JSON-RPC 2.0 daemon service in quantsys-v2.

**Migration Strategy:** Gradual, phased migration with independent validation at each layer.

**Timeline:** 8-12 days across 5 phases.

## Background

### Current State

- **TypeScript Agent Tools:** Six-layer architecture (L1 Data Pipeline → L6 Monitoring)
- **Backend:** Tools call `callQuantSysDaemon()` which expects `quant/quantsys/cli --daemon`
- **Problem:** `quant/` directory has been deleted; only `quantsys-v2/` exists
- **Impact:** All new six-layer tools are broken

### Why This Approach

**Decision: Preserve daemon architecture (not direct HTTP)**

Reasons:
1. Maintains existing TypeScript adapter pattern
2. Avoids dependency on Flask server always running
3. Cleaner separation: daemon for tools, HTTP for web clients
4. Consistent with original architecture design

**Decision: Independent daemon service (not CLI-based)**

Reasons:
1. Decoupled from Flask API
2. Lightweight, focused on tool support
3. Direct access to services/repositories
4. Easier to maintain and test

**Decision: Gradual migration (not big-bang)**

Reasons:
1. Lower risk, easier to debug
2. Can validate each layer independently
3. Existing HTTP-based tools (opportunity-scan, portfolio-dashboard) remain unaffected
4. Aligns with agile development principles

## Architecture

### Overall Architecture

```
TypeScript Agent (src/)
    ↓ JSON-RPC 2.0 over stdin/stdout
quantsys-v2/daemon/server.py (new)
    ↓ Direct calls
quantsys-v2/services/ + repositories/
    ↓
PostgreSQL Database
```

### Core Components

#### 1. Daemon Server (`quantsys-v2/daemon/server.py`)

Main entry point for the daemon process.

**Responsibilities:**
- Listen on stdin, write to stdout
- Parse JSON-RPC 2.0 requests
- Route to appropriate handlers
- Return JSON-RPC 2.0 responses
- Error recovery and logging

**Lifecycle:**
- Long-running process (does not auto-exit)
- Started by TypeScript adapter on first tool call
- Gracefully handles shutdown signals

#### 2. Protocol Handler (`quantsys-v2/daemon/protocol.py`)

JSON-RPC 2.0 protocol implementation.

**Responsibilities:**
- Parse and validate JSON-RPC requests
- Construct JSON-RPC responses
- Standard error code mapping
- Request/response serialization

**Protocol Specification:**

Request format:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "get_stock_info",
  "params": {
    "symbol": "600519"
  }
}
```

Success response:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": "{\"symbol\": \"600519\", \"name\": \"贵州茅台\", ...}"
}
```

Error response:
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    "code": -32603,
    "message": "Internal error: Stock not found"
  }
}
```

**Error Codes:**
- `-32700` - Parse error (JSON parsing failed)
- `-32600` - Invalid Request (malformed request)
- `-32601` - Method not found (unknown method)
- `-32602` - Invalid params (parameter validation failed)
- `-32603` - Internal error (service/repository error)

**Key Design Decision:** The `result` field contains a JSON string (not an object). This matches the existing TypeScript adapter expectation where it calls `JSON.parse(result)`.

#### 3. Method Registry (`quantsys-v2/daemon/registry.py`)

Method registration and discovery system.

**Responsibilities:**
- Maintain `method_name → handler_function` mapping
- Auto-discover handlers from `daemon/handlers/`
- Provide `@register_method` decorator
- Validate method signatures

**Usage Pattern:**
```python
from daemon.registry import register_method

@register_method("get_stock_info")
async def get_stock_info(params: dict) -> str:
    # Implementation
    pass
```

#### 4. Method Handlers (`quantsys-v2/daemon/handlers/`)

Business logic implementations organized by layer.

**File Structure:**
- `data_handlers.py` - L1 Data Pipeline methods
- `factor_handlers.py` - L2 Factor Factory methods
- `model_handlers.py` - L3 Model Layer methods

**Handler Pattern:**
```python
from daemon.registry import register_method
from services.stock_service import StockService
import json

@register_method("get_stock_info")
async def get_stock_info(params: dict) -> str:
    """获取股票基本信息"""
    symbol = params.get("symbol")
    if not symbol:
        raise ValueError("symbol is required")
    
    service = StockService()
    result = await service.get_stock_info(symbol)
    return json.dumps(result, ensure_ascii=False)
```

**Dependency Strategy:** Create service instances per request (stateless). Rationale: quantsys-v2 repositories already use connection pooling, so no need for shared instances. Simplifies lifecycle management.

**Error Handling:**
- `ValueError` → `-32602` (Invalid params)
- `Exception` → `-32603` (Internal error)
- All errors logged to stderr

#### 5. TypeScript Adapter (modify `src/infrastructure/quant/quantsys-daemon-adapter.ts`)

**Changes Required:**
1. Update `QUANT_ROOT` path:
   ```typescript
   const QUANT_ROOT = join(PROJECT_ROOT, "quantsys-v2");  // was "quant"
   ```

2. Update spawn command:
   ```typescript
   this.process = spawn(pythonCmd, ["-m", "daemon.server"], {  // was ["-m", "quantsys.cli", "--daemon"]
   ```

3. Keep JSON-RPC protocol unchanged

## Method Inventory

### L1 Data Pipeline Layer (6 methods)

| Method | Description | Service/Repository |
|--------|-------------|-------------------|
| `get_stock_info` | Stock basic info | StockService |
| `get_stock_realtime_price` | Real-time price | QuoteService |
| `get_stock_news` | Stock news | NewsService |
| `get_announcements` | Announcements | AnnouncementService |
| `get_stock_history` | K-line data | KlineRepository |
| `get_financial_statements` | Financial reports | FinancialRepository |

### L2 Factor Factory Layer (5 methods)

| Method | Description | Service/Repository |
|--------|-------------|-------------------|
| `calculate_technical_indicators` | Technical indicators (MA, MACD, RSI, Bollinger) | IndicatorService |
| `get_stock_valuation` | Valuation analysis (PE, PB, Graham) | ValuationService |
| `get_quality_score` | Quality score (0-100) | QualityService |
| `get_pe_percentile` | PE percentile (historical) | ValuationService |
| `analyze_price_action` | Price action analysis | AnalysisService |

### L3 Model Layer (5 methods)

| Method | Description | Service/Repository |
|--------|-------------|-------------------|
| `train_model` | Train ML model | MLService |
| `predict_signal_confidence` | Predict signal confidence | MLService |
| `evaluate_model` | Evaluate model performance | MLService |
| `monitor_model` | Monitor model metrics | MLService |
| `list_models` | List available models | MLService |

### L4-L6 Layers

Portfolio (L4), Trade (L5), and Monitor (L6) layers primarily use local file operations (`.pi-invest/` directory) and do not require daemon methods.

**Total: 16 methods**

## Directory Structure

### New Files

```
quantsys-v2/
├── daemon/
│   ├── __init__.py
│   ├── server.py              # Main entry, JSON-RPC server
│   ├── protocol.py            # JSON-RPC protocol handling
│   ├── registry.py            # Method registration
│   └── handlers/
│       ├── __init__.py
│       ├── data_handlers.py   # L1 data layer methods
│       ├── factor_handlers.py # L2 factor layer methods
│       └── model_handlers.py  # L3 model layer methods
```

### Modified Files

```
src/infrastructure/quant/
└── quantsys-daemon-adapter.ts  # Path configuration changes
```

## Implementation Plan

### Phase 1: Infrastructure (1-2 days)

**Deliverables:**
- `daemon/server.py` - Main daemon process
- `daemon/protocol.py` - JSON-RPC 2.0 handler
- `daemon/registry.py` - Method registration system
- Basic integration test

**Acceptance Criteria:**
- Daemon starts and responds to ping request
- JSON-RPC protocol correctly parses requests/responses
- Error handling works for malformed requests

### Phase 2: L1 Data Layer (2-3 days)

**Deliverables:**
- Implement 6 data layer methods in `daemon/handlers/data_handlers.py`
- Unit tests for each method
- Integration tests with real database
- Update TypeScript adapter configuration

**Acceptance Criteria:**
- All 6 methods return correct data format
- TypeScript tools (`data_fetch_stock`, `data_fetch_kline`, `data_fetch_financial`) work end-to-end
- Error cases handled gracefully

### Phase 3: L2 Factor Layer (2-3 days)

**Deliverables:**
- Implement 5 factor layer methods in `daemon/handlers/factor_handlers.py`
- Unit tests for each method
- Integration tests

**Acceptance Criteria:**
- All 5 methods return correct calculations
- TypeScript tool (`factor_calculate`) works end-to-end
- Performance acceptable (< 2s per factor)

### Phase 4: L3 Model Layer (2-3 days)

**Deliverables:**
- Implement 5 model layer methods in `daemon/handlers/model_handlers.py`
- Unit tests for each method
- Integration tests

**Acceptance Criteria:**
- All 5 methods work correctly
- TypeScript tools (`model_train`, `model_predict`, etc.) work end-to-end
- Model persistence works correctly

### Phase 5: Documentation and Cleanup (1 day)

**Deliverables:**
- Update `CLAUDE.md` with daemon architecture
- Update `.env.example` with correct paths
- Add `quantsys-v2/daemon/README.md` usage guide
- Remove obsolete references to `quant/`

**Acceptance Criteria:**
- Documentation accurate and complete
- New developers can understand the architecture
- No broken references to old `quant/` directory

## Testing Strategy

### Unit Tests

**Location:** `quantsys-v2/tests/daemon/test_handlers.py`

**Approach:**
- Test each handler method in isolation
- Mock services/repositories
- Verify input validation
- Verify output format (JSON string)
- Verify error handling

**Example:**
```python
@pytest.mark.asyncio
async def test_get_stock_info_success(mocker):
    mock_service = mocker.patch('daemon.handlers.data_handlers.StockService')
    mock_service.return_value.get_stock_info.return_value = {"symbol": "600519"}
    
    result = await get_stock_info({"symbol": "600519"})
    assert json.loads(result)["symbol"] == "600519"
```

### Integration Tests

**Location:** `quantsys-v2/tests/daemon/test_integration.py`

**Approach:**
- Start real daemon process
- Send JSON-RPC requests via stdin
- Read responses from stdout
- Verify end-to-end flow
- Test with real database (test database)

**Example:**
```python
def test_daemon_get_stock_info():
    proc = subprocess.Popen(
        ["python", "-m", "daemon.server"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    request = {"jsonrpc": "2.0", "id": 1, "method": "get_stock_info", "params": {"symbol": "600519"}}
    proc.stdin.write(json.dumps(request).encode() + b"\n")
    proc.stdin.flush()
    
    response = json.loads(proc.stdout.readline())
    assert response["jsonrpc"] == "2.0"
    assert "result" in response
```

### End-to-End Tests

**Location:** `src/infrastructure/tools/*/test.ts`

**Approach:**
- Call TypeScript tools directly
- Verify complete call chain (TypeScript → daemon → services → database)
- Test error scenarios
- Verify tool output format

**Example:**
```typescript
test('data_fetch_stock returns stock info', async () => {
  const result = await dataFetchStockTool.execute('test-id', {
    symbol: '600519',
    fields: ['info', 'price']
  });
  
  expect(result.content[0].type).toBe('text');
  const data = JSON.parse(result.content[0].text);
  expect(data.info).toBeDefined();
  expect(data.price).toBeDefined();
});
```

## Rollback Plan

### Rollback Triggers

- Daemon crashes frequently (> 3 times per hour)
- Response time unacceptable (> 5s per request)
- Data corruption or incorrect results
- Critical bugs blocking development

### Rollback Steps

1. **Immediate:** Revert TypeScript adapter changes
   ```typescript
   const QUANT_ROOT = join(PROJECT_ROOT, "quant");  // revert
   ```

2. **Short-term:** Switch affected tools to HTTP calls
   - Modify tools to call Flask API directly
   - Similar to existing `opportunity-scan-tool.ts` pattern

3. **Long-term:** Re-evaluate architecture
   - Consider direct HTTP approach (original Option A)
   - Consider hybrid approach (daemon for some, HTTP for others)

### Risk Mitigation

- Each phase is independent; can rollback individual phases
- Keep old HTTP-based tools unchanged during migration
- Feature flags for new daemon-based tools
- Comprehensive logging for debugging

## Success Metrics

### Functional Metrics

- ✅ All 16 daemon methods implemented and tested
- ✅ All TypeScript tools work end-to-end
- ✅ Zero data corruption or incorrect results
- ✅ Error handling covers all edge cases

### Performance Metrics

- ✅ Daemon startup time < 2 seconds
- ✅ Average request latency < 1 second
- ✅ P99 request latency < 3 seconds
- ✅ Memory usage < 200 MB

### Quality Metrics

- ✅ Unit test coverage > 80%
- ✅ Integration test coverage for all methods
- ✅ Zero critical bugs in production
- ✅ Documentation complete and accurate

## Open Questions

None. All design decisions have been made and approved.

## Appendix: Alternative Approaches Considered

### Alternative 1: Direct HTTP Calls

**Approach:** TypeScript tools call Flask API directly via HTTP.

**Pros:**
- Simpler implementation
- No daemon process to manage
- Consistent with web client architecture

**Cons:**
- Requires Flask server always running
- Higher latency (HTTP overhead)
- Tight coupling to Flask API

**Decision:** Rejected. Daemon approach provides better separation and doesn't require Flask for CLI tools.

### Alternative 2: CLI-Based Daemon

**Approach:** Add `--daemon` mode to `quantsys-v2/cli/main.py`, which wraps HTTP API calls.

**Pros:**
- Reuses existing CLI infrastructure
- No duplicate business logic

**Cons:**
- Depends on Flask server running
- CLI becomes more complex
- Daemon is just an HTTP wrapper (unnecessary layer)

**Decision:** Rejected. Independent daemon is cleaner and more performant.

### Alternative 3: Big-Bang Migration

**Approach:** Implement all methods at once and switch everything simultaneously.

**Pros:**
- Faster completion
- Unified architecture immediately

**Cons:**
- High risk
- Difficult to debug issues
- Large testing burden

**Decision:** Rejected. Gradual migration is safer and more manageable.
