# Enhanced Financial Data Service E2E Test

## Test Environment

- quantsys-v2 server running on http://127.0.0.1:5001
- TypeScript agent with updated client
- Test stock: 600519 (贵州茅台)

## Test Scenario 1: Basic V2 API Flow

### 1.1 Start quantsys-v2 server

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
python start_all.py &
sleep 5
```

### 1.2 Test auto mode (cache miss then hit)

```bash
# First request - cache miss
curl -X GET "http://127.0.0.1:5001/api/v2/stock/600519/financials?source=auto" | jq '.cached'
# Expected: false

# Second request - cache hit
curl -X GET "http://127.0.0.1:5001/api/v2/stock/600519/financials?source=auto" | jq '.cached'
# Expected: true
```

### 1.3 Test fresh mode (bypass cache)

```bash
curl -X GET "http://127.0.0.1:5001/api/v2/stock/600519/financials?source=fresh" | jq '.cached'
# Expected: false (always)
```

### 1.4 Test cache_only mode

```bash
# With warm cache - should succeed
curl -X GET "http://127.0.0.1:5001/api/v2/stock/600519/financials?source=cache_only"
# Expected: 200 OK

# Clear cache
curl -X POST "http://127.0.0.1:5001/api/v2/financials/cache/clear"

# With cold cache - should fail
curl -X GET "http://127.0.0.1:5001/api/v2/stock/600519/financials?source=cache_only"
# Expected: 500 error with "缓存未命中"
```

### 1.5 Check statistics

```bash
curl -X GET "http://127.0.0.1:5001/api/v2/financials/stats" | jq '.stats'
# Expected: total_requests, cache_hits, cache_hit_rate, provider_stats, etc.
```

## Test Scenario 2: TypeScript Agent Integration

### 2.1 Test via Agent tool

Start TypeScript agent:
```bash
cd /Users/mac/Documents/ai/pi-investment
npm run dev
```

Use tool (in agent):
```
data_fetch_financial({
  symbol: "600519",
  dataType: "statements",
  source: "auto"
})
```

**Expected:** Returns financial data, second call hits cache

### 2.2 Test fresh mode

```
data_fetch_financial({
  symbol: "600519",
  dataType: "statements",
  source: "fresh"
})
```

**Expected:** Always fetches fresh data

### 2.3 Test default behavior (backward compatibility)

```
data_fetch_financial({
  symbol: "600519",
  dataType: "statements"
})
```

**Expected:** Works with default source='auto', no breaking changes

## Test Scenario 3: Circuit Breaker Behavior

### 3.1 Simulate provider failures

Stop quantsys-v2 temporarily:
```bash
pkill -f "python api/server.py"
```

Make requests:
```bash
for i in {1..5}; do
  curl -X GET "http://127.0.0.1:5001/api/v2/stock/600519/financials"
  sleep 1
done
```

**Expected:** Circuit breakers open after 3 failures

### 3.2 Restart and verify recovery

```bash
cd /Users/mac/Documents/ai/pi-investment/quantsys-v2
python api/server.py &
sleep 65  # Wait for circuit breaker timeout (60s)

curl -X GET "http://127.0.0.1:5001/api/v2/stock/600519/financials"
```

**Expected:** Circuit breaker half-open, request succeeds, breaker closes

## Success Criteria

✅ V2 API endpoints respond correctly  
✅ Cache hit on second request with auto mode  
✅ Fresh mode bypasses cache  
✅ cache_only mode works as expected  
✅ Statistics tracking is accurate  
✅ TypeScript agent can use source parameter  
✅ Circuit breaker opens after failures and recovers  
✅ No regressions in existing functionality  

## Test Results

**Date:** 2026-06-04  
**Tester:** [To be filled]

- Scenario 1: ⏳ Pending
- Scenario 2: ⏳ Pending  
- Scenario 3: ⏳ Pending

**Notes:** [Add observations here]
