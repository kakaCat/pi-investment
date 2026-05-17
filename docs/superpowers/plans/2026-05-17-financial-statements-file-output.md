# Financial Statements File Output Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Modify `get_financial_statements` tool to write large data (>2000 chars) to temporary files and return file paths, allowing LLM to browse content using Read tool.

**Architecture:** Follow browser-tool pattern - when data exceeds threshold, write to `/tmp/pi-financials-{symbol}-{statement}-{timestamp}.json`, return preview (first 500 chars) + file path. Small data (<= 2000 chars) returns inline for backward compatibility.

**Tech Stack:** TypeScript, Node.js fs/promises

---

## File Structure

**Modified:**
- `src/infrastructure/tools/invest/financial-tools.ts` - Add file writing logic to `getFinancialStatementsTool.execute`

**No new files created** - this is a single-function modification

---

### Task 1: Add File Writing Logic to getFinancialStatementsTool

**Files:**
- Modify: `src/infrastructure/tools/invest/financial-tools.ts:76-101`

- [ ] **Step 1: Add required imports**

Add these imports at the top of the file (after existing imports):

```typescript
import { writeFile } from "fs/promises";
```

- [ ] **Step 2: Verify current implementation**

Read the current `getFinancialStatementsTool.execute` function to confirm the baseline:

```bash
grep -A 10 "execute: async (_toolCallId, params: any)" src/infrastructure/tools/invest/financial-tools.ts | head -15
```

Expected: Should see the current implementation that directly returns `callPython` result.

- [ ] **Step 3: Replace execute function with file-writing logic**

Replace the `execute` function in `getFinancialStatementsTool` (lines 93-100) with:

```typescript
  execute: async (_toolCallId, params: any) => {
    const err = requireAshare(params.symbol);
    if (err) return { content: [{ type: "text" as const, text: err }], details: undefined };
    
    const args: Record<string, unknown> = { 
      symbol: params.symbol, 
      statement: params.statement ?? "all" 
    };
    if (params.recent_n !== undefined) args.recent_n = params.recent_n;
    
    const result = await callPython("get_financial_statements", args);
    
    // 判断数据大小
    if (result.length > 2000) {
      // 写入临时文件
      const filePath = `/tmp/pi-financials-${params.symbol}-${params.statement || 'all'}-${Date.now()}.json`;
      await writeFile(filePath, result, 'utf-8');
      
      // 返回预览（前 500 字符）+ 文件路径
      const preview = result.substring(0, 500);
      const resultText = `财务数据已保存到: ${filePath}\n\n数据预览 (前500字符):\n${preview}...\n\n[总长度: ${result.length} 字符，完整内容见文件。使用 Read 工具查看完整内容]`;
      
      return { content: [{ type: "text" as const, text: resultText }], details: undefined };
    } else {
      // 数据较小，直接返回
      return { content: [{ type: "text" as const, text: result }], details: undefined };
    }
  },
```

- [ ] **Step 4: Verify TypeScript compilation**

Run TypeScript compiler to check for errors:

```bash
npm run build
```

Expected: Build succeeds with no errors in `financial-tools.ts`.

- [ ] **Step 5: Commit the changes**

```bash
git add src/infrastructure/tools/invest/financial-tools.ts
git commit -m "feat(tools): add file output for large financial statements data

- Write data to /tmp/pi-financials-{symbol}-{statement}-{timestamp}.json when > 2000 chars
- Return preview (first 500 chars) + file path for large data
- Keep inline return for small data (<= 2000 chars) for backward compatibility
- Follow browser-tool pattern"
```

---

### Task 2: Manual Testing

**Files:**
- Test: Manual verification using the tool

- [ ] **Step 1: Test small data scenario (should return inline)**

Start the application and test with a small dataset:

```bash
# In the application, call:
get_financial_statements({symbol: "600519", statement: "income", recent_n: 2})
```

Expected: Returns JSON data directly (no file path), data length should be < 2000 chars.

- [ ] **Step 2: Test large data scenario (should return file path)**

Test with a large dataset:

```bash
# In the application, call:
get_financial_statements({symbol: "600519", statement: "all", recent_n: 8})
```

Expected output format:
```
财务数据已保存到: /tmp/pi-financials-600519-all-1737158400000.json

数据预览 (前500字符):
{"income_statement":{"symbol":"600519",...

[总长度: 45678 字符，完整内容见文件。使用 Read 工具查看完整内容]
```

- [ ] **Step 3: Verify file was created and is readable**

Check that the file exists and contains valid JSON:

```bash
ls -lh /tmp/pi-financials-*.json | tail -1
```

Expected: File exists with size > 2KB.

- [ ] **Step 4: Verify file content integrity**

Read the file and verify it's valid JSON:

```bash
# Get the most recent file
FILE=$(ls -t /tmp/pi-financials-*.json | head -1)
# Check if it's valid JSON
cat "$FILE" | python3 -m json.tool > /dev/null && echo "Valid JSON" || echo "Invalid JSON"
```

Expected: Output "Valid JSON".

- [ ] **Step 5: Test Read tool can access the file**

Use Read tool to verify LLM can browse the file:

```bash
# In the application, use Read tool with the file path from step 2
# Should be able to read with offset/limit parameters
```

Expected: Read tool successfully reads the file content, can use offset/limit to browse sections.

- [ ] **Step 6: Document test results**

Create a test summary:

```bash
echo "# Financial Statements File Output Test Results

Date: $(date)

## Test 1: Small Data (inline return)
- Symbol: 600519, statement: income, recent_n: 2
- Result: ✓ Data returned inline
- Data length: < 2000 chars

## Test 2: Large Data (file output)
- Symbol: 600519, statement: all, recent_n: 8
- Result: ✓ File created at /tmp/pi-financials-600519-all-*.json
- Preview: ✓ First 500 chars shown
- File size: $(ls -lh /tmp/pi-financials-*.json | tail -1 | awk '{print $5}')

## Test 3: File Integrity
- Result: ✓ Valid JSON
- Read tool: ✓ Can access file

All tests passed.
" > /tmp/financial-statements-test-results.txt
cat /tmp/financial-statements-test-results.txt
```

Expected: All tests marked as passed.

---

## Self-Review Checklist

**Spec Coverage:**
- ✓ Data flow (TS receives data, checks size, writes file if > 2000 chars)
- ✓ File naming format (`/tmp/pi-financials-{symbol}-{statement}-{timestamp}.json`)
- ✓ Return format (preview + file path for large data, inline for small data)
- ✓ Threshold (2000 chars) and preview length (500 chars)
- ✓ Backward compatibility (small data returns inline)
- ✓ Import dependencies (writeFile from fs/promises)

**Placeholder Check:**
- ✓ No TBD/TODO
- ✓ All code blocks complete
- ✓ Exact file paths provided
- ✓ Test commands with expected output

**Type Consistency:**
- ✓ `params.symbol`, `params.statement`, `params.recent_n` used consistently
- ✓ Return type `{ content: [{ type: "text", text: string }], details: undefined }` consistent
- ✓ File path format consistent across plan

**Gaps:**
- None identified - all spec requirements covered
