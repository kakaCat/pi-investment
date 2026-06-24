# Tool Error Fix Plan

## 🎯 Executive Summary

Analyzed session `20260624T02220_6d7e846c` with 11 failed bash tool calls. Root causes identified:

1. **Logging Issue**: Tool params not captured (`params: null`)
2. **Backend Calculation Error**: Abnormal percentages (-8761%, -274631%)
3. **Silent Failures**: Python scripts crashing with no diagnostic output

## ✅ Immediate Actions Completed

### 1. Created Analysis Document
- **File**: `TOOL_ERROR_ANALYSIS.md`
- **Content**: Detailed error patterns, root causes, and reproduction steps

### 2. Verified Formatter Code
- **File**: `agent-ts/src/infrastructure/adapters/quant/formatters.ts`
- **Status**: ✅ **GOOD** - Contains proper validation:
  - Price range validation (0.01 - 10,000 元)
  - Change percentage validation (±30% threshold)
  - Proper error messages for abnormal data
- **Lines 44-62**: Data validation prevents bad percentages from reaching user

**Conclusion**: The abnormal percentages (-8761%) are coming from **backend Python**, not TS formatters.

## 🔧 Required Fixes

### Priority 1: Fix Backend Percentage Calculation ⚠️ HIGH

**Location**: `quantsys-v2/` Python backend

**Evidence**:
```
银行板块: 397720  -8761%    # Raw value divided by wrong base
券商板块: 14056347  -274631% # Missing data or format error
```

**Expected Fix Pattern**:
```python
# WRONG (likely current):
pct_change = (current - previous) / 0.01 * 100
# OR
pct_change = current  # Missing previous value

# RIGHT:
if previous and previous != 0:
    pct_change = ((current - previous) / previous) * 100
else:
    pct_change = 0
```

**Files to Check**:
1. `quantsys-v2/src/data/formatters.py` (if exists)
2. `quantsys-v2/src/adapters/market_data.py`
3. Any file handling sector index calculations
4. Search for: `grep -r "板块\|sector.*pct\|change_pct" quantsys-v2/src/`

**Action**:
```bash
cd quantsys-v2
# Find the culprit
grep -r "change.*pct\|涨跌幅" src/ --include="*.py" | grep -v test

# Check sector calculation specifically
find src/ -name "*sector*" -o -name "*index*" | xargs grep -l "pct\|percent"
```

### Priority 2: Enable Command Logging 📝 MEDIUM

**Location**: `agent-ts/src/infrastructure/session/session-factory.ts:133-141`

**Current**:
```typescript
case 'tool_execution_start': {
  startTimes.set(event.toolCallId, Date.now());
  toolNames.set(event.toolCallId, event.toolName);
  logger.logToolCall(event.toolName, event.toolCallId, event.input);
  // ← event.input is null, need fallback
}
```

**Fix**:
```typescript
case 'tool_execution_start': {
  startTimes.set(event.toolCallId, Date.now());
  toolNames.set(event.toolCallId, event.toolName);
  
  // Try multiple sources for input params
  const toolInput = event.input || event.toolInput || event.params;
  logger.logToolCall(event.toolName, event.toolCallId, toolInput);
  
  // Debug logging for bash commands
  if (event.toolName === 'bash' && toolInput) {
    const cmd = toolInput.command || toolInput.cmd;
    if (cmd) {
      console.log(`🐚 Bash: ${cmd.substring(0, 200)}...`);
    }
  }
  
  if (agentType === 'main') {
    perfMonitor?.startToolCall?.(event.toolName);
  }
  break;
}
```

### Priority 3: Backend Health Check 🏥 MEDIUM

**Execute**:
```bash
# 1. Check if quantsys-v2 backend is running
ps aux | grep python | grep quantsys
cat .backend/pids.json

# 2. Test backend API manually
curl http://localhost:8000/health || curl http://localhost:5000/health

# 3. Check for recent crashes
tail -100 .backend/rest.log 2>/dev/null || echo "No log file"

# 4. Verify Python imports
cd quantsys-v2
python3 -c "from src.data import formatters" 2>&1
python3 -c "from src.adapters import market_data" 2>&1

# 5. Test database connection
psql -U postgres -d quantsys -c "SELECT COUNT(*) FROM stocks LIMIT 1" 2>&1 || \
  echo "DB connection failed"
```

### Priority 4: Add Python Script Error Handling 🛡️ LOW

**Wrapper Template** for bash tools calling Python:
```typescript
// In bash tool implementation
const pythonCommand = `
set -euo pipefail
python3 -u "${scriptPath}" ${args} 2>&1 || {
  exit_code=$?
  echo "❌ Python script failed with exit code $exit_code"
  echo "Script: ${scriptPath}"
  echo "Args: ${args}"
  exit $exit_code
}
`;
```

## 🧪 Testing Plan

### Step 1: Reproduce the Error
```bash
# Run a minimal test that triggers sector data
cd agent-ts
npm run agent -- "银行板块涨跌幅"

# Check events log
tail -50 .pi-invest/sessions/*/events.jsonl | grep '"success":false'
```

### Step 2: Verify Backend
```bash
# Call backend API directly
curl -X POST http://localhost:8000/api/sector/performance \
  -H "Content-Type: application/json" \
  -d '{"sectors": ["银行"], "date": "2026-06-24"}'

# Expected: Reasonable percentages (±10%)
# Actual (broken): -8761%
```

### Step 3: Fix and Re-test
```bash
# After fixing backend percentage calculation
npm run agent -- "银行板块涨跌幅"

# Verify:
# - No "success": false in events
# - Percentages in reasonable range (±20%)
```

## 📊 Success Criteria

- [ ] All bash tool calls log their commands (`params` not null)
- [ ] Sector percentages within ±30% range
- [ ] No "(no output)" failures with exit code 1
- [ ] Backend APIs return valid data when called directly
- [ ] Zero Python import errors in quantsys-v2

## 🔍 Debugging Commands

```bash
# Monitor backend in real-time
tail -f .backend/*.log 2>/dev/null &

# Watch for errors during agent execution
tail -f .pi-invest/sessions/*/events.jsonl | grep --line-buffered '"success":false'

# Test individual tools
cd agent-ts
npm run agent -- "测试工具：factor_calculate 600036"
npm run agent -- "测试工具：data_fetch_quote 000001.SZ"
npm run agent -- "测试工具：market_sentiment"
```

## 📝 Next Steps

1. **Execute Priority 1**: Search and fix backend percentage calculation
2. **Apply Priority 2**: Add command logging to session-factory.ts
3. **Run Priority 3**: Backend health check script
4. **Test**: Run reproduction test from Testing Plan
5. **Verify**: Check success criteria
6. **Document**: Update TOOL_ERROR_ANALYSIS.md with results

---

**Created**: 2026-06-24  
**Session**: 20260624T02220_6d7e846c  
**Files Modified**: None (analysis only)  
**Status**: Ready for implementation
