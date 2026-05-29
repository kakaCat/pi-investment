# quant_cli Strategy ID Error Hint Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Automatically append available strategy list to error messages when `strategy_id` parameter is missing in quant_cli tool calls.

**Architecture:** Add async helper function to fetch strategy list from quantsys-v2 API, modify parameter validation to call it when `strategy_id` is missing, with graceful degradation on failure.

**Tech Stack:** TypeScript, quantsys-v2 HTTP API

---

## File Structure

**Modified Files:**
- `src/infrastructure/tools/core/quant-cli-tool.ts` — Add `fetchStrategyListHint()` helper, make `validateParams()` async, update call site

**Test Files:**
- `src/infrastructure/tools/core/quant-cli-tool.test.ts` — Add tests for new error hint behavior

---

## Task 1: Add fetchStrategyListHint() Helper Function

**Files:**
- Modify: `src/infrastructure/tools/core/quant-cli-tool.ts:1444` (before `validateParams()`)
- Test: `src/infrastructure/tools/core/quant-cli-tool.test.ts`

- [ ] **Step 1: Write the failing test**

Add to `src/infrastructure/tools/core/quant-cli-tool.test.ts`:

```typescript
import { quantCliTool } from './quant-cli-tool.js';
import * as quantV2Client from '../../quant/quant-v2-client.js';

describe('quant_cli strategy_id error hints', () => {
  it('should include strategy list when strategy_id is missing', async () => {
    // Mock strategy.list response
    jest.spyOn(quantV2Client, 'runQuantV2').mockResolvedValue({
      strategies: [
        { id: 53, name: '多因子波段策略v9' },
        { id: 54, name: 'RSI超买超卖策略' },
      ],
    });

    const result = await quantCliTool.execute('test-call-id', {
      command: 'performance.by_strategy',
      params: {},
    });

    const text = result.content[0].text;
    expect(text).toContain('缺少必填参数: strategy_id');
    expect(text).toContain('可用策略列表：');
    expect(text).toContain('ID: 53, 名称: 多因子波段策略v9');
    expect(text).toContain('ID: 54, 名称: RSI超买超卖策略');
  });

  it('should show empty strategy hint when no strategies exist', async () => {
    jest.spyOn(quantV2Client, 'runQuantV2').mockResolvedValue({
      strategies: [],
    });

    const result = await quantCliTool.execute('test-call-id', {
      command: 'performance.by_strategy',
      params: {},
    });

    const text = result.content[0].text;
    expect(text).toContain('当前系统中没有可用策略');
    expect(text).toContain('请先使用 strategy.create 创建策略');
  });

  it('should degrade gracefully when strategy.list fails', async () => {
    jest.spyOn(quantV2Client, 'runQuantV2').mockRejectedValue(
      new Error('Service unavailable')
    );

    const result = await quantCliTool.execute('test-call-id', {
      command: 'performance.by_strategy',
      params: {},
    });

    const text = result.content[0].text;
    expect(text).toContain('缺少必填参数: strategy_id');
    expect(text).toContain('使用 strategy.list 命令查看可用策略列表');
  });

  it('should limit display to 10 strategies when more exist', async () => {
    const strategies = Array.from({ length: 15 }, (_, i) => ({
      id: i + 1,
      name: `策略${i + 1}`,
    }));

    jest.spyOn(quantV2Client, 'runQuantV2').mockResolvedValue({
      strategies,
    });

    const result = await quantCliTool.execute('test-call-id', {
      command: 'performance.by_strategy',
      params: {},
    });

    const text = result.content[0].text;
    expect(text).toContain('ID: 1, 名称: 策略1');
    expect(text).toContain('ID: 10, 名称: 策略10');
    expect(text).not.toContain('ID: 11, 名称: 策略11');
    expect(text).toContain('共 15 个策略，仅显示前 10 个');
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test -- quant-cli-tool.test.ts`

Expected: FAIL with "fetchStrategyListHint is not defined" or similar

- [ ] **Step 3: Add fetchStrategyListHint() function**

Add to `src/infrastructure/tools/core/quant-cli-tool.ts` before `validateParams()` (around line 1444):

```typescript
/**
 * 获取策略列表提示文本（用于 strategy_id 参数缺失时的错误消息）
 * @returns 格式化的策略列表提示，或降级提示（查询失败时）
 */
async function fetchStrategyListHint(): Promise<string> {
  try {
    const response = await runQuantV2("strategy.list", {});
    const strategies = (response as any)?.strategies || [];
    
    if (strategies.length === 0) {
      return "提示：当前系统中没有可用策略。请先使用 strategy.create 创建策略。";
    }
    
    // 格式化策略列表（最多显示前 10 个）
    const displayStrategies = strategies.slice(0, 10);
    const strategyLines = displayStrategies.map((s: any) => 
      `  - ID: ${s.id}, 名称: ${s.name}`
    ).join('\n');
    
    const moreHint = strategies.length > 10 
      ? `\n\n（共 ${strategies.length} 个策略，仅显示前 10 个）` 
      : '';
    
    return `可用策略列表：\n${strategyLines}${moreHint}\n\n提示：使用 strategy.list 命令可查看完整策略详情。`;
    
  } catch (error) {
    // 降级：查询失败时返回通用提示
    return "提示：使用 strategy.list 命令查看可用策略列表。";
  }
}
```

- [ ] **Step 4: Run test to verify it still fails**

Run: `npm test -- quant-cli-tool.test.ts`

Expected: FAIL because `validateParams()` is not async yet and doesn't call the helper

- [ ] **Step 5: Commit helper function**

```bash
git add src/infrastructure/tools/core/quant-cli-tool.ts src/infrastructure/tools/core/quant-cli-tool.test.ts
git commit -m "feat(quant-cli): add fetchStrategyListHint helper function"
```

---

## Task 2: Make validateParams() Async and Add Strategy Hint Logic

**Files:**
- Modify: `src/infrastructure/tools/core/quant-cli-tool.ts:1444`
- Test: `src/infrastructure/tools/core/quant-cli-tool.test.ts`

- [ ] **Step 1: Update validateParams() signature to async**

Change function signature at line 1444:

```typescript
// Before:
function validateParams(_command: string, rule: CommandRule, params: Record<string, unknown>): string | null {

// After:
async function validateParams(_command: string, rule: CommandRule, params: Record<string, unknown>): Promise<string | null> {
```

- [ ] **Step 2: Add strategy_id special handling**

Modify the required parameter check (around line 1473):

```typescript
// Before:
if (paramRule.required && isEmpty(value)) {
  return `缺少必填参数: ${key}。原因：该参数是命令执行的必要条件，不能为空。`;
}

// After:
if (paramRule.required && isEmpty(value)) {
  // 特殊处理：strategy_id 参数缺失时附加策略列表
  if (key === 'strategy_id') {
    const strategyListHint = await fetchStrategyListHint();
    return `缺少必填参数: ${key}。原因：该参数是命令执行的必要条件，不能为空。\n\n${strategyListHint}`;
  }
  return `缺少必填参数: ${key}。原因：该参数是命令执行的必要条件，不能为空。`;
}
```

- [ ] **Step 3: Update call site to await validateParams()**

Find the call site in the `execute` function (around line 1334):

```typescript
// Before:
const validation = validateParams(command, rule, params);
if (validation) {
  return validationError(validation, formatCommandHelp(command, rule));
}

// After:
const validation = await validateParams(command, rule, params);
if (validation) {
  return validationError(validation, formatCommandHelp(command, rule));
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test -- quant-cli-tool.test.ts`

Expected: All tests PASS

- [ ] **Step 5: Commit validation changes**

```bash
git add src/infrastructure/tools/core/quant-cli-tool.ts
git commit -m "feat(quant-cli): add strategy list hint to strategy_id validation errors"
```

---

## Task 3: Manual Integration Testing

**Files:**
- Test: Manual testing with quantsys-v2 service

- [ ] **Step 1: Ensure quantsys-v2 is running**

Run: `cd quantsys-v2 && python start_all.py`

Expected: REST API on port 5001, WebSocket on port 5003

- [ ] **Step 2: Test with missing strategy_id (service available)**

In the TypeScript agent, call:

```typescript
quant_cli({
  command: "performance.by_strategy",
  params: {}
})
```

Expected output should include:
- "缺少必填参数: strategy_id"
- "可用策略列表："
- List of strategies with IDs and names

- [ ] **Step 3: Test with quantsys-v2 stopped (degradation)**

Stop quantsys-v2: `cd quantsys-v2 && pkill -f "python.*server.py"`

Call the same command again.

Expected output should include:
- "缺少必填参数: strategy_id"
- "提示：使用 strategy.list 命令查看可用策略列表"

- [ ] **Step 4: Test other commands requiring strategy_id**

Test all 6 affected commands:
- `strategy.get`
- `strategy.optimize`
- `strategy.run`
- `backtest.strategy`
- `signal.generate`

Each should show strategy list hint when `strategy_id` is missing.

- [ ] **Step 5: Verify other required parameters unchanged**

Test a command with different required parameter (e.g., `stock.technical` without `symbol`):

```typescript
quant_cli({
  command: "stock.technical",
  params: {}
})
```

Expected: Standard error message without strategy list (no regression)

- [ ] **Step 6: Document test results**

Create: `docs/testing/2026-05-29-quant-cli-strategy-hint-test.md`

```markdown
# quant_cli Strategy Hint Integration Test Results

**Date:** 2026-05-29

## Test Cases

### 1. Missing strategy_id with service available
- Command: `performance.by_strategy` with empty params
- Result: ✅ Shows strategy list with IDs and names

### 2. Missing strategy_id with service unavailable
- Command: `performance.by_strategy` with empty params (service stopped)
- Result: ✅ Degrades to generic hint

### 3. All affected commands
- `strategy.get`: ✅
- `strategy.optimize`: ✅
- `strategy.run`: ✅
- `backtest.strategy`: ✅
- `signal.generate`: ✅
- `performance.by_strategy`: ✅

### 4. Other required parameters
- `stock.technical` without `symbol`: ✅ No regression

### 5. Strategy list > 10 items
- Result: ✅ Shows first 10 + total count

### 6. Empty strategy list
- Result: ✅ Shows creation hint

## Conclusion

All test cases passed. Feature working as designed.
```

- [ ] **Step 7: Commit test documentation**

```bash
git add docs/testing/2026-05-29-quant-cli-strategy-hint-test.md
git commit -m "docs: add quant_cli strategy hint integration test results"
```

---

## Task 4: Update CLAUDE.md Documentation

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Add note to quant_cli tool section**

Find the "Agent 工具系统" section in CLAUDE.md and add a note about the enhanced error messages:

```markdown
### quant_cli 工具增强（2026-05-29）

**智能错误提示**：当缺少 `strategy_id` 必填参数时，错误消息会自动附加可用策略列表，减少工具调用次数。

适用命令：
- `performance.by_strategy`
- `strategy.get`
- `strategy.optimize`
- `strategy.run`
- `backtest.strategy`
- `signal.generate`

示例错误输出：
```
缺少必填参数: strategy_id。原因：该参数是命令执行的必要条件，不能为空。

可用策略列表：
  - ID: 53, 名称: 多因子波段策略v9
  - ID: 54, 名称: RSI超买超卖策略
```

容错处理：如果 quantsys-v2 服务不可用，降级为通用提示。
```

- [ ] **Step 2: Commit documentation update**

```bash
git add CLAUDE.md
git commit -m "docs: document quant_cli strategy_id error hint enhancement"
```

---

## Self-Review Checklist

**Spec Coverage:**
- ✅ fetchStrategyListHint() helper function (Task 1)
- ✅ validateParams() made async (Task 2)
- ✅ strategy_id special handling (Task 2)
- ✅ Call site updated with await (Task 2)
- ✅ All 6 affected commands tested (Task 3)
- ✅ Graceful degradation tested (Task 3)
- ✅ Documentation updated (Task 4)

**Placeholder Check:**
- ✅ No TBD/TODO markers
- ✅ All code blocks complete
- ✅ All test cases have expected output
- ✅ All file paths exact

**Type Consistency:**
- ✅ `fetchStrategyListHint()` returns `Promise<string>`
- ✅ `validateParams()` returns `Promise<string | null>`
- ✅ All async/await usage consistent

**Test Coverage:**
- ✅ Strategy list display (normal case)
- ✅ Empty strategy list
- ✅ Service unavailable (degradation)
- ✅ >10 strategies (truncation)
- ✅ Other required parameters (no regression)
- ✅ All 6 affected commands

---

## Execution Notes

- Total tasks: 4
- Estimated time: 20-30 minutes
- Dependencies: quantsys-v2 service must be available for integration testing
- Risk: Low (changes isolated to error handling path)
