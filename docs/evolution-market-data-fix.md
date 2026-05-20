# Evolution Market Data Collection Fix

## Problem
The evolution function was failing to collect market data, showing:
- All indices (sh000001, sz399001, sz399006) returning 0.00%
- Data quality marked as "low"
- Error: "获取指数 [code] 历史数据失败"

## Root Cause Analysis

### Issue 1: Broken Sina Finance API
**File**: `python/akshare_bridge.py`

The `stock_zh_index_daily()` function in AkShare relies on Sina Finance API, which returned 404:
```
URL: https://finance.sina.com.cn/realstock/company/000001/hisdata/klc_kl.js
Response: 404 Not Found
```

**Fix**: Switched to Tencent data source using `stock_zh_index_daily_tx()`
- Removed code prefix stripping (Tencent API expects full symbol like 'sh000001')
- Updated column mapping: `'amount'` → `'volume'`

### Issue 2: Insufficient Timeout Configuration
**Files**: 
- `src/infrastructure/tools/shared/python-caller-resilient-adapter.ts`
- `src/infrastructure/tools/python-bridge.ts`

The Tencent API takes ~85 seconds to fetch data, but timeouts were too short:
- Original: 35s (resilient adapter) and 90s (bridge)
- Problem: Requests timed out before data could be retrieved

**Fix**: Increased timeouts for slow data sources
1. Added `TIMEOUT_VERY_SLOW = 120000ms` (2 minutes)
2. Configured `get_index_history` to use `TIMEOUT_VERY_SLOW`
3. Configured `get_sector_fund_flow` to use `TIMEOUT_VERY_SLOW`
4. Increased python-bridge max timeout to 150s
5. Set both functions to retry only once (to avoid long wait times)

## Changes Made

### 1. Python Bridge (`python/akshare_bridge.py`)
```python
# Before
if symbol.startswith('sh'):
    code = symbol[2:]
elif symbol.startswith('sz'):
    code = symbol[2:]
df = ak.stock_zh_index_daily(symbol=code)

# After
df = ak.stock_zh_index_daily_tx(symbol=symbol)

# Column mapping adjusted
'volume': _safe_float(row.get('amount', 0), decimals=0)  # Tencent uses 'amount'
```

### 2. Timeout Configuration (`python-caller-resilient-adapter.ts`)
```typescript
// Added new timeout tier
const TIMEOUT_VERY_SLOW = 120000; // 2 minutes

// Updated config
const TIMEOUT_CONFIG: Record<string, number> = {
  // ... other configs
  get_index_history: TIMEOUT_VERY_SLOW,
  get_sector_fund_flow: TIMEOUT_VERY_SLOW,
};

const RETRY_CONFIG: Record<string, number> = {
  // ... other configs
  get_index_history: 1,
  get_sector_fund_flow: 1,
};
```

### 3. Bridge Layer Timeout (`python-bridge.ts`)
```typescript
// Before
const REQUEST_TIMEOUT_MS = 90000; // 90 seconds

// After
const REQUEST_TIMEOUT_MS = 150000; // 150 seconds
```

## Verification
After fixes, all three indices successfully retrieve data:
- ✓ sh000001 (上证指数): 0.34% (sideways)
- ✓ sz399001 (深证成指): 8.67% (up)
- ✓ sz399006 (创业板指): 18.34% (up)

## Impact
- Evolution function can now collect complete market context
- Data quality should improve from "low" to "medium" or "high"
- Market environment analysis will be more accurate

## Future Considerations
1. Monitor Tencent API performance - if it becomes unreliable, consider:
   - Adding fallback to East Money data source (`stock_zh_index_daily_em`)
   - Implementing API health checks
   - Caching historical data more aggressively

2. Consider optimizing data collection:
   - Parallel requests for multiple indices
   - Incremental updates instead of full history fetches
   - Pre-warming cache during off-peak hours
