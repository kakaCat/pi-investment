# Legacy Orders API Cleanup Report

**Date**: 2026-08-25  
**Task**: Remove old `/api/orders/*` and `/api/trades/*` endpoints and migrate all clients to new simulation API

## Background

Phase 3 deleted 12 legacy order API endpoints from `quantsys-v2`, but client code (agent-ts, web-frontend) still had references to these old endpoints.

## Changes Made

### 1. Agent-TS Migration

**File**: `agent-ts/src/infrastructure/tools/trade/trade-monitor-tool.ts`

**Changes**:
- `orders.list` → `simulation.pending-orders` (with `account_name: agent_virtual`)
- `trades.list` → `simulation.trades`

**File**: `agent-ts/src/infrastructure/adapters/quant/quant-v2-client.ts`

**Changes**:
- Removed: `"orders.list": { path: "/api/orders/list", method: "GET" }`
- Removed: `"trades.list": { path: "/api/trades/list", method: "GET" }`
- Added: `"simulation.pending-orders": { path: "/api/simulation/accounts/{account_name}/pending-orders", method: "GET" }`
- Added: `"simulation.trades": { path: "/api/simulation/trades", method: "GET" }`

**File**: `agent-ts/src/infrastructure/tools/trade/trade-monitor-tool.test.ts`

**Changes**:
- Updated mock command from `orders.list` → `simulation.pending-orders`

### 2. Web-Frontend Cleanup

**File**: `web-frontend/src/services/api/trading.ts`

**Deleted unused methods** (frontend views already migrated in Phase 3):
- `getOrders()` - was calling `/api/orders/list`
- `getOrderById()` - was calling `/api/orders/detail/{id}`
- `createOrder()` - was calling `/api/orders/create`
- `cancelOrder()` - was calling `/api/orders/cancel/{id}`
- `updateOrder()` - was calling `/api/orders/update/{id}`
- `getTradeHistory()` - was calling `/api/trades/list`
- `getTrades()` - was calling `/api/trades/list`

**Kept methods**:
- `getPositions()` - still used by portfolio view
- `getPortfolioSummary()` - still used by portfolio view
- `getHoldings()`, `getEquityCurve()`, `getAllocation()` - portfolio-related
- `getExecutions()`, `getExecutionStats()` - execution monitoring
- `executeSignal()`, `cancelExecution()`, `closeExecution()` - execution management

**File**: `web-frontend/tests/unit/api-contract.test.ts`

**Changes**:
- Removed all old orders/trades API test cases
- Updated to test only remaining methods (`getPositions`, `getPortfolioSummary`)

## Verification

### Agent-TS Tests
```bash
cd agent-ts && npm test -- trade-monitor-tool.test.ts
```
**Result**: ✅ 4 passed, 0 failed

### Web-Frontend Tests
```bash
cd web-frontend && npm test -- api-contract.test.ts
```
**Result**: ✅ 10 passed, 0 failed

### API Endpoint Check
```bash
# Old endpoints return 404 (deleted)
curl http://localhost:5001/api/orders/create  # 404
curl http://localhost:5001/api/orders/list    # 404
curl http://localhost:5001/api/trades/list    # 404

# New endpoints work
curl http://localhost:5001/api/simulation/accounts/agent_virtual/pending-orders  # 200
curl http://localhost:5001/api/simulation/trades  # 200
```

## Impact

### Before
- 3 projects (quantsys-v2, agent-ts, web-frontend) had references to old orders API
- Old endpoints deleted but clients not updated → potential runtime errors

### After
- ✅ **agent-ts**: `trade_monitor` tool now uses simulation API
- ✅ **web-frontend**: Dead code removed, only actively used methods remain
- ✅ **quantsys-v2**: Old endpoints deleted (Phase 3)
- ✅ All tests pass

## Summary

| Project | Files Changed | Lines Removed | Status |
|---------|---------------|---------------|--------|
| agent-ts | 3 | ~10 | ✅ Tests pass |
| web-frontend | 2 | ~50 | ✅ Tests pass |
| **Total** | **5** | **~60** | **✅ Complete** |

## Next Steps

1. ✅ Commit changes
2. ⏸️ Push to GitHub (after frontend manual testing)
3. ⏸️ Code review
4. ⏸️ Mark Phase 3.3 complete in deprecation plan

## Related Documents

- [Phase 3 Completion Report](./order-deprecation-phase3.md)
- [Frontend Migration Report](./frontend-migration-complete.md)
- [Legacy System Deprecation Plan](../../architecture/legacy-system-deprecation-plan.md)
