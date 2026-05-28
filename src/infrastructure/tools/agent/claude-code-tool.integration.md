# Claude Code Tool Integration Test Guide

## Overview

This document provides manual integration test scenarios for the `claude_code` tool, which delegates code-related tasks to the Claude Code CLI.

## Prerequisites

### 1. Claude Code CLI Installation

Verify Claude Code CLI is installed and accessible:

```bash
which claude
# Expected: /usr/local/bin/claude (or similar path)

claude --version
# Expected: Claude Code CLI version output
```

If not installed, follow the installation guide at: https://docs.anthropic.com/claude/docs/claude-code

### 2. Authentication

Ensure Claude Code CLI is authenticated:

```bash
claude auth status
# Expected: "Authenticated as: <your-email>"
```

If not authenticated:

```bash
claude auth login
```

### 3. Environment Configuration

Check environment variables (optional, uses defaults if not set):

```bash
echo $CLAUDE_CODE_CLI_PATH      # Default: "claude"
echo $CLAUDE_CODE_TIMEOUT       # Default: 120000 (2 minutes)
echo $CLAUDE_CODE_MAX_RETRIES   # Default: 3
```

## Test Scenarios

### Scenario 1: Code Review

**Objective**: Verify the tool can perform code review on existing files.

**Steps**:
1. Start the TypeScript agent
2. Execute the tool with a code review task:

```typescript
const result = await claudeCodeTool.execute({
  task: "Review the code in src/infrastructure/tools/agent/claude-code-tool.ts for potential bugs and improvements",
  files: ["src/infrastructure/tools/agent/claude-code-tool.ts"]
});
```

**Expected Result**:
- `success: true`
- `output` contains code review feedback
- `executionTime` < 120000ms
- No errors in logs

### Scenario 2: Code Generation

**Objective**: Verify the tool can generate new code.

**Steps**:
1. Execute the tool with a code generation task:

```typescript
const result = await claudeCodeTool.execute({
  task: "Generate a TypeScript utility function to format stock symbols (e.g., '600519' -> '600519.SH')",
  context: "The function should handle both Shanghai (SH) and Shenzhen (SZ) exchanges"
});
```

**Expected Result**:
- `success: true`
- `output` contains generated TypeScript code
- Code is syntactically valid
- Function signature matches requirements

### Scenario 3: Architecture Analysis

**Objective**: Verify the tool can analyze project architecture.

**Steps**:
1. Execute the tool with an architecture analysis task:

```typescript
const result = await claudeCodeTool.execute({
  task: "Analyze the architecture of the tool system in src/infrastructure/tools/",
  files: [
    "src/infrastructure/tools/data/",
    "src/infrastructure/tools/factor/",
    "src/infrastructure/tools/invest/"
  ]
});
```

**Expected Result**:
- `success: true`
- `output` contains architectural insights
- Identifies patterns, dependencies, and potential improvements

### Scenario 4: Bug Fix Assistance

**Objective**: Verify the tool can help diagnose and fix bugs.

**Steps**:
1. Execute the tool with a bug fix task:

```typescript
const result = await claudeCodeTool.execute({
  task: "Analyze why the factor calculation might fail with empty data",
  context: "Users report factor_calculate tool returns empty results for some stocks",
  files: ["src/infrastructure/tools/factor/calculate-tool.ts"]
});
```

**Expected Result**:
- `success: true`
- `output` contains root cause analysis
- Suggests specific fixes with code examples

### Scenario 5: Timeout Handling

**Objective**: Verify the tool handles timeouts gracefully.

**Steps**:
1. Execute the tool with a short timeout:

```typescript
const result = await claudeCodeTool.execute({
  task: "Perform a comprehensive security audit of the entire codebase",
  timeout: 5000  // 5 seconds (intentionally short)
});
```

**Expected Result**:
- `success: false`
- `error` contains timeout message
- Process is terminated cleanly
- No zombie processes remain

### Scenario 6: CLI Not Installed

**Objective**: Verify the tool handles missing CLI gracefully.

**Steps**:
1. Temporarily rename the Claude CLI:

```bash
sudo mv /usr/local/bin/claude /usr/local/bin/claude.bak
```

2. Execute the tool:

```typescript
const result = await claudeCodeTool.execute({
  task: "Review this code"
});
```

3. Restore the CLI:

```bash
sudo mv /usr/local/bin/claude.bak /usr/local/bin/claude
```

**Expected Result**:
- `success: false`
- `error` contains "Claude Code CLI not found" or similar
- Clear error message guides user to install CLI

### Scenario 7: Concurrent Calls

**Objective**: Verify the tool handles concurrent executions.

**Steps**:
1. Execute multiple tool calls in parallel:

```typescript
const results = await Promise.all([
  claudeCodeTool.execute({ task: "Review file A" }),
  claudeCodeTool.execute({ task: "Review file B" }),
  claudeCodeTool.execute({ task: "Review file C" })
]);
```

**Expected Result**:
- All calls complete successfully
- No race conditions or resource conflicts
- Each result is independent and correct

### Scenario 8: Large Output Handling

**Objective**: Verify the tool handles large CLI outputs.

**Steps**:
1. Execute a task that generates large output:

```typescript
const result = await claudeCodeTool.execute({
  task: "Generate comprehensive documentation for all tools in src/infrastructure/tools/",
  files: ["src/infrastructure/tools/"]
});
```

**Expected Result**:
- `success: true`
- `output` contains complete documentation (no truncation)
- Memory usage remains reasonable

## Running the Tests

### Manual Testing via Agent

1. Start the TypeScript agent:

```bash
npm run dev
```

2. In the agent prompt, trigger the tool:

```
请审查 src/infrastructure/tools/agent/claude-code-tool.ts 的代码质量
```

3. Observe the tool execution and verify results.

### Automated Testing (Future)

Integration tests should be added to the test suite:

```bash
npm run test:integration
```

## Troubleshooting

### Issue: "Claude Code CLI not found"

**Cause**: CLI not installed or not in PATH.

**Solution**:
1. Install Claude Code CLI
2. Verify installation: `which claude`
3. Set `CLAUDE_CODE_CLI_PATH` if installed in non-standard location

### Issue: "Authentication required"

**Cause**: CLI not authenticated.

**Solution**:
```bash
claude auth login
```

### Issue: Timeout errors

**Cause**: Task takes longer than configured timeout.

**Solution**:
1. Increase timeout: `CLAUDE_CODE_TIMEOUT=300000` (5 minutes)
2. Or pass `timeout` parameter in tool call
3. Break down complex tasks into smaller subtasks

### Issue: Empty or incomplete output

**Cause**: CLI process terminated unexpectedly.

**Solution**:
1. Check CLI logs: `claude logs`
2. Verify network connectivity
3. Check system resources (memory, CPU)
4. Retry with simpler task to isolate issue

### Issue: "spawn ENOENT" error

**Cause**: CLI path incorrect or permissions issue.

**Solution**:
1. Verify CLI path: `which claude`
2. Check execute permissions: `ls -l $(which claude)`
3. Set correct path: `export CLAUDE_CODE_CLI_PATH=/path/to/claude`

## Performance Benchmarks

Expected performance for typical tasks:

| Task Type | Expected Time | Max Timeout |
|-----------|---------------|-------------|
| Code review (single file) | 10-30s | 120s |
| Code generation (function) | 5-15s | 60s |
| Architecture analysis | 30-60s | 180s |
| Bug diagnosis | 15-45s | 120s |
| Refactoring suggestions | 20-40s | 120s |

## Security Considerations

1. **Input Validation**: Tool validates all inputs before passing to CLI
2. **Command Injection**: Uses `spawn` with array arguments (no shell injection)
3. **Output Sanitization**: CLI output is treated as untrusted data
4. **Timeout Protection**: All CLI calls have timeout limits
5. **Resource Limits**: CLI process is terminated if exceeds limits

## Next Steps

After completing manual integration tests:

1. Document any issues found
2. Add automated integration tests to CI/CD pipeline
3. Monitor tool usage in production
4. Collect user feedback for improvements
5. Update this guide based on real-world usage patterns
