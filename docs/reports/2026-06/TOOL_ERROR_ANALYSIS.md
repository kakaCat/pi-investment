# Tool Error Analysis - Session 20260624T02220_6d7e846c

## 📋 Executive Summary

Analyzed 713KB of event logs from the failed session. Found **11 failed bash tool calls** out of 102+ turns, all with `params: null` indicating missing command inputs.

---

## 🔍 Error Patterns

### 1. **Params Logging Issue**
**Problem**: All failed bash calls show `params: null` in events.jsonl
```json
{"event":"tool.call","tool_name":"bash","params":null,"params_length":0}
```

**Root Cause**: The SDK's `tool_execution_start` event is not passing the actual command through `event.input`. 

**Location**: [observable-logger.ts:247-259](../agent-ts/src/infrastructure/logging/observable-logger.ts#L247)
```typescript
export function logToolCall(toolName: string, toolId: string, input: any) {
  logEvent('tool.call', {
    params: input ?? null,  // ← input is null from SDK event
  });
}
```

### 2. **Data Calculation Errors**
**Problem**: Abnormal percentage calculations in output before failure:
```
银行板块: 397720  -8761%    ← Should be ~1-5%
券商板块: 14056347  -274631% ← Nonsensical
中国平安: 4941.00  -99.00%   ← Should be ~1-2%
```

**Root Cause**: Backend Python scripts calculating percentages incorrectly, likely:
- Division by wrong baseline (dividing by 0.01 instead of previous value)
- Missing data causing fallback to raw values
- Data formatting errors in quantsys-v2 adapters

### 3. **Empty Output Failures**
**Problem**: Multiple calls with no output and exit code 1
```
Command exited with code 1
(no output)
```

**Likely Causes**:
- Python script crashes before any output
- Import errors in quantsys-v2
- Database connection issues (postgres)
- Network timeouts on data fetching

---

## 🎯 Failed Call Summary

| Turn | Tool | Error Type | Impact |
|------|------|------------|--------|
| 26 | bash | JSON decode error | Data parsing failure |
| 65-69 | bash (3x) | No output, exit 1 | Silent failures |
| 82-83 | bash (2x) | No output, exit 1 | Silent failures |
| 96 | bash | Empty with "---" | Format error |
| 100-102 | bash (4x) | Bad percentages / empty | Data corruption |

**Total**: 11 failures across 5 turn clusters

---

## 🔧 Recommended Fixes

### Priority 1: Enable Command Logging
**Problem**: Can't debug without seeing actual commands
**Fix**: Modify session-factory.ts to log full bash commands:

```typescript
// In session-factory.ts line 136
case 'tool_execution_start': {
  const fullInput = event.input || event.toolInput || event.params;
  logger.logToolCall(event.toolName, event.toolCallId, fullInput);
  
  // Add bash-specific debugging
  if (event.toolName === 'bash' && fullInput) {
    console.log(`🐚 Bash command: ${fullInput.command?.substring(0, 200)}`);
  }
  break;
}
```

### Priority 2: Fix Percentage Calculations
**Location**: Check quantsys-v2/src/adapters/formatters.py or similar

Expected fix pattern:
```python
# WRONG:
pct_change = (current - previous) / 0.01  # ← Hardcoded divisor

# RIGHT:
pct_change = ((current - previous) / previous) * 100 if previous != 0 else 0
```

**Action**: Search for percentage calculation logic in:
- `agent-ts/src/infrastructure/adapters/quant/formatters.ts`
- `quantsys-v2/src/data/formatters.py`
- Any tool calling backend APIs with `/api/sector` or `/api/market`

### Priority 3: Add Error Handling to Bash Tools
**Problem**: Silent failures with no diagnostic output
**Fix**: Wrap Python calls with error capture:

```typescript
// In bash tool wrapper
const command = `
  set -euo pipefail
  python3 -u script.py 2>&1 || {
    echo "ERROR: Python script failed with code $?"
    exit 1
  }
`;
```

### Priority 4: Backend Health Check
**Action Items**:
1. Verify quantsys-v2 backend is running: `ps aux | grep python | grep quantsys`
2. Check for import errors: `cd quantsys-v2 && python -c "from src.data import formatters"`
3. Test database connection: `psql -U postgres -d quantsys -c "SELECT 1"`
4. Review recent backend logs: `tail -100 .backend/*.log`

---

## 🧪 Reproduction Test

Create a minimal test to reproduce the issue:

```typescript
// test-tool-logging.ts
import { createAgentSession } from "@mariozechner/pi-coding-agent";

const session = createAgentSession({
  model: "deepseek-chat",
  tools: [/* bash tool */]
});

await session.prompt("计算银行板块涨跌幅");
// Check if params are logged in events.jsonl
```

---

## 📊 Session Context

**User Query Flow**:
1. Turn 1-25: Stock analysis (招商银行, 华润三九) - **Working**
2. Turn 26: First failure - JSON decode error
3. Turn 65-102: Market sentiment analysis - **Multiple failures**
4. Final query: "下午市场如何" - Partial success with data corruption

**Tools Used Successfully**:
- `factor_calculate` ✅
- `analysis_swing_points` ✅
- `data_fetch_quote` ✅
- `opportunity_scan` ✅
- `market_style_detect` ✅

**Tools Failing**:
- Custom `bash` calls (likely calling Python scripts) ❌

---

## 🚀 Next Steps

1. **Immediate**: Add debug logging to capture bash commands
2. **Short-term**: Fix percentage calculation in formatters
3. **Medium-term**: Add integration tests for bash→Python tool chain
4. **Long-term**: Replace bash wrappers with native TypeScript tools

---

## 📎 References

- Session: `.pi-invest/sessions/20260624T02220_6d7e846c/`
- Events: `events.jsonl` (713KB)
- Conversation: `conversation.json` (75KB)
- Logger: `src/infrastructure/logging/observable-logger.ts:247-259`
- Session Factory: `src/infrastructure/session/session-factory.ts:133-141`
