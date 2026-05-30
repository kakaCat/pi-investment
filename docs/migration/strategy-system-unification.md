# Strategy System Unification Migration Guide

## Overview

The strategy execution system has been unified into a single `strategy.execute` command in `quant_cli`. This migration consolidates three execution modes (single, batch, pipeline) into one consistent interface.

**Migration Date**: 2026-05-30  
**Target Completion**: v3.0 (deprecated commands will be removed)

## What Changed

### Before (Deprecated)

**Multiple fragmented commands:**

1. **`signal.generate`** (quant_cli command)
   - Used for batch signal generation
   - Wrote signals to database with `status='pending'`
   - Required separate arbitration step

2. **`strategy_execute`** (standalone tool)
   - Used for single stock execution
   - Returned formatted signal with risk parameters
   - Separate tool registration

### After (New Unified System)

**Single unified command: `strategy.execute`**

Three execution modes via `action` parameter:

1. **`action: "single"`** — Execute strategy on one stock
2. **`action: "batch"`** — Execute strategy on multiple stocks
3. **`action: "pipeline"`** — Full pipeline (signal → risk check → order creation)

## Migration Mappings

### 1. signal.generate → strategy.execute (batch mode)

**Old:**
```typescript
quant_cli({
  command: "signal.generate",
  params: {
    strategy_id: "53",
    symbols: ["600000", "000001"]
  }
})
```

**New:**
```typescript
quant_cli({
  command: "strategy.execute",
  params: {
    action: "batch",
    strategy: "53",
    symbols: ["600000", "000001"]
  }
})
```

**Key Changes:**
- `strategy_id` → `strategy`
- Add `action: "batch"`
- Command name changed

### 2. strategy_execute tool → strategy.execute (single mode)

**Old:**
```typescript
strategy_execute({
  symbol: "600000",
  strategy: "VolatilityBreakout",
  date: "2026-05-30"
})
```

**New:**
```typescript
quant_cli({
  command: "strategy.execute",
  params: {
    action: "single",
    symbol: "600000",
    strategy: "VolatilityBreakout"
  }
})
```

**Key Changes:**
- Use `quant_cli` instead of standalone tool
- Add `action: "single"`
- Same parameter names (symbol, strategy)

## New Features

### Pipeline Mode (New in v2.1)

Full end-to-end execution with risk checks and order creation:

```typescript
quant_cli({
  command: "strategy.execute",
  params: {
    action: "pipeline",
    symbols: ["600000", "000001"],
    strategy: "53",
    risk_check: true,      // Enable risk filtering
    auto_order: true       // Auto-create orders for passed signals
  }
})
```

**Pipeline Flow:**
1. Generate signals for all symbols
2. Apply risk checks (optional)
3. Create orders for approved signals (optional)
4. Return summary statistics

## Backward Compatibility

### Automatic Mapping (Until v3.0)

The system provides automatic backward compatibility:

1. **`signal.generate`** — Automatically mapped to `strategy.execute` with `action='batch'`
   - Deprecation warning shown in console
   - Full functionality preserved
   - Will be removed in v3.0

2. **`strategy_execute` tool** — Marked as deprecated
   - Still available in tool registry
   - Deprecation notice in documentation
   - Will be removed in v3.0

### Migration Timeline

| Version | Status |
|---------|--------|
| v2.1 (current) | New unified system available; old commands deprecated but functional |
| v2.2-v2.9 | Deprecation warnings; encourage migration |
| v3.0 | **Old commands removed** — migration required |

## Benefits of New System

1. **Consistency** — Single command for all execution modes
2. **Discoverability** — All modes documented in one place
3. **Extensibility** — Easy to add new execution modes
4. **Type Safety** — Unified parameter validation
5. **Pipeline Support** — End-to-end execution in one call

## Testing Your Migration

### Test Single Mode
```bash
# Old way (still works with warning)
strategy_execute({ symbol: "600000", strategy: "Turtle" })

# New way
quant_cli({
  command: "strategy.execute",
  params: { action: "single", symbol: "600000", strategy: "Turtle" }
})
```

### Test Batch Mode
```bash
# Old way (still works with warning)
quant_cli({
  command: "signal.generate",
  params: { strategy_id: "53", symbols: ["600000"] }
})

# New way
quant_cli({
  command: "strategy.execute",
  params: { action: "batch", strategy: "53", symbols: ["600000"] }
})
```

### Test Pipeline Mode (New)
```bash
quant_cli({
  command: "strategy.execute",
  params: {
    action: "pipeline",
    strategy: "53",
    symbols: ["600000", "000001"],
    risk_check: true,
    auto_order: false
  }
})
```

## Common Issues

### Issue 1: "action parameter required"

**Error:**
```
缺少必填参数: action
```

**Solution:**
Add `action` parameter with value `"single"`, `"batch"`, or `"pipeline"`.

### Issue 2: "strategy_id not found"

**Error:**
```
不支持的参数: strategy_id
```

**Solution:**
Use `strategy` instead of `strategy_id` in new system.

### Issue 3: Missing symbols in batch mode

**Error:**
```
缺少必填参数: symbols
```

**Solution:**
Batch mode requires `symbols` array parameter.

## Getting Help

- **Command help**: `quant_cli({ command: "help", params: { name: "strategy.execute" } })`
- **Strategy list**: `quant_cli({ command: "strategy.list" })`
- **Documentation**: See `docs/plans/strategy-system-unification-plan.md`

## Related Documents

- Implementation Plan: `docs/plans/strategy-system-unification-plan.md`
- API Specification: `quantsys-v2/api/routes/strategies.py`
- Tool Definition: `src/infrastructure/tools/core/quant-cli-tool.ts`
