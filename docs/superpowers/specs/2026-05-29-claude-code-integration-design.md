# Claude Code Integration Design

**Date:** 2026-05-29  
**Status:** Approved  
**Author:** AI Assistant

## Overview

This design document describes the integration of Claude Code into the pi-investment agent system using the Agent Client Protocol (ACP). The integration enables the DeepSeek agent to delegate code-related tasks, complex analysis, and technical decisions to Claude Code through a lightweight CLI wrapper.

## Goals

1. Enable DeepSeek agent to leverage Claude Code's capabilities for code-related tasks
2. Support automatic delegation of complex technical analysis
3. Implement seamless collaboration between DeepSeek (quantitative decisions) and Claude Code (technical implementation)
4. Maintain consistency with existing tool patterns (e.g., `backend_control`)

## Non-Goals

- Replacing DeepSeek as the primary agent
- Implementing full ACP protocol client from scratch
- Building a custom session management system (initial version)
- Supporting remote Claude Code instances

## Use Cases

### Primary Scenarios

1. **Code Review and Analysis**
   - User: "帮我审查一下 src/services/portfolio.ts 的代码"
   - DeepSeek detects code review request → delegates to Claude Code
   - Claude Code performs detailed review → returns findings
   - DeepSeek integrates results and responds to user

2. **Code Refactoring**
   - User: "重构 factor calculation 模块，提高性能"
   - DeepSeek identifies refactoring task → calls Claude Code
   - Claude Code analyzes and refactors code → returns changes
   - DeepSeek validates changes and reports to user

3. **Architecture Analysis**
   - User: "分析当前工具系统的架构设计"
   - DeepSeek recognizes complex analysis → delegates to Claude Code
   - Claude Code performs deep architectural analysis
   - DeepSeek synthesizes findings with domain knowledge

4. **Bug Fixing**
   - User: "修复 data pipeline 中的内存泄漏问题"
   - DeepSeek detects bug fix request → engages Claude Code
   - Claude Code investigates and fixes → returns solution
   - DeepSeek verifies fix and updates user

5. **Code Generation**
   - User: "生成一个新的技术指标计算工具"
   - DeepSeek outlines requirements → Claude Code implements
   - Claude Code generates code with tests
   - DeepSeek integrates into tool registry

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     DeepSeek Agent                          │
│  ┌───────────────────────────────────────────────────────┐  │
│  │              Tool Registry                            │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │         claude_code Tool                        │  │  │
│  │  │  - Parameter validation                         │  │  │
│  │  │  - Automatic trigger detection                  │  │  │
│  │  │  - CLI process management                       │  │  │
│  │  │  - Stream handling                              │  │  │
│  │  │  - Error handling                               │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ spawn
                            ▼
                  ┌──────────────────┐
                  │  claude-code CLI │
                  │  (Local Install) │
                  └──────────────────┘
```

### File Structure

```
src/infrastructure/tools/agent/
├── claude-code-tool.ts          # Main tool implementation
├── claude-code-tool.test.ts     # Unit tests
└── claude-code-types.ts         # TypeScript types (optional)

src/infrastructure/tools/
└── index.ts                     # Tool registration
```

### Tool Definition

**Tool Name:** `claude_code`

**Parameters:**
```typescript
interface ClaudeCodeParams {
  task: string;           // Task description for Claude Code
  context?: string;       // Optional context information
  files?: string[];       // Relevant file paths
  timeout?: number;       // Timeout in milliseconds (default: 120000)
}
```

**Return Type:**
```typescript
interface ClaudeCodeResult {
  success: boolean;
  output: string;              // Claude Code's output
  files_modified?: string[];   // List of modified files
  execution_time: number;      // Execution time in milliseconds
  error?: string;              // Error message if failed
}
```

## Implementation Details

### 1. CLI Process Management

**Spawning Process:**
```typescript
import { spawn } from 'child_process';

const cliPath = process.env.CLAUDE_CODE_CLI_PATH || 'claude-code';
const process = spawn(cliPath, args, {
  stdio: ['pipe', 'pipe', 'pipe'],
  cwd: projectRoot,
  env: { ...process.env }
});
```

**Timeout Control:**
```typescript
const timeoutMs = params.timeout || 120000;
const timeout = setTimeout(() => {
  process.kill('SIGTERM');
  reject(new Error(`Claude Code execution timeout after ${timeoutMs}ms`));
}, timeoutMs);

process.on('exit', () => clearTimeout(timeout));
```

**Cleanup:**
```typescript
process.on('exit', (code) => {
  clearTimeout(timeout);
  if (code !== 0) {
    reject(new Error(`Claude Code exited with code ${code}`));
  }
});
```

### 2. Input/Output Handling

**Input (stdin):**
```typescript
const input = JSON.stringify({
  task: params.task,
  context: params.context,
  files: params.files
});

process.stdin.write(input);
process.stdin.end();
```

**Output (stdout/stderr):**
```typescript
let stdout = '';
let stderr = '';

process.stdout.on('data', (chunk) => {
  stdout += chunk.toString();
  // Optional: real-time logging
  logger.debug('Claude Code output', { chunk: chunk.toString() });
});

process.stderr.on('data', (chunk) => {
  stderr += chunk.toString();
  logger.warn('Claude Code stderr', { chunk: chunk.toString() });
});
```

### 3. Automatic Trigger Detection

**Keyword-based Detection:**
```typescript
const CODE_REVIEW_KEYWORDS = ['review', '审查', 'code review'];
const REFACTOR_KEYWORDS = ['refactor', '重构', 'restructure'];
const ANALYSIS_KEYWORDS = ['analyze architecture', '分析架构', 'architectural analysis'];
const BUG_FIX_KEYWORDS = ['fix bug', '修复', 'debug'];
const CODE_GEN_KEYWORDS = ['generate', '生成代码', 'create code'];

function shouldUseClaude(userMessage: string): boolean {
  const lowerMsg = userMessage.toLowerCase();
  
  return CODE_REVIEW_KEYWORDS.some(kw => lowerMsg.includes(kw)) ||
         REFACTOR_KEYWORDS.some(kw => lowerMsg.includes(kw)) ||
         ANALYSIS_KEYWORDS.some(kw => lowerMsg.includes(kw)) ||
         BUG_FIX_KEYWORDS.some(kw => lowerMsg.includes(kw)) ||
         CODE_GEN_KEYWORDS.some(kw => lowerMsg.includes(kw));
}
```

**Integration Point:**
DeepSeek agent's message processing loop checks user input and automatically invokes `claude_code` tool when appropriate keywords are detected.

### 4. Error Handling

**CLI Not Found:**
```typescript
try {
  await checkClaudeCodeInstalled();
} catch (error) {
  return {
    success: false,
    output: '',
    execution_time: 0,
    error: 'Claude Code CLI not found. Please install: npm install -g @anthropic-ai/claude-code'
  };
}
```

**Execution Timeout:**
```typescript
// Handled by timeout mechanism above
// Returns partial output if available
```

**Process Crash:**
```typescript
process.on('error', (error) => {
  logger.error('Claude Code process error', { error });
  reject(new Error(`Claude Code process failed: ${error.message}`));
});
```

**Permission Issues:**
```typescript
if (error.code === 'EACCES') {
  return {
    success: false,
    output: '',
    execution_time: 0,
    error: 'Permission denied. Check Claude Code CLI permissions.'
  };
}
```

### 5. Tool Registration

**In `src/infrastructure/tools/index.ts`:**
```typescript
import { claudeCodeTool } from './agent/claude-code-tool.js';

export const allCustomTools: ToolDefinition[] = [
  // ... existing tools
  claudeCodeTool,
];
```

**Tool Definition:**
```typescript
export const claudeCodeTool: ToolDefinition = {
  name: 'claude_code',
  description: 'Delegate code-related tasks to Claude Code for implementation, review, or analysis',
  parameters: {
    type: 'object',
    properties: {
      task: {
        type: 'string',
        description: 'Task description for Claude Code'
      },
      context: {
        type: 'string',
        description: 'Optional context information'
      },
      files: {
        type: 'array',
        items: { type: 'string' },
        description: 'Relevant file paths'
      },
      timeout: {
        type: 'number',
        description: 'Timeout in milliseconds (default: 120000)'
      }
    },
    required: ['task']
  },
  handler: async (params: ClaudeCodeParams) => {
    // Implementation
  }
};
```

## Data Flow

### Typical Execution Flow

```
1. User Input
   "帮我审查一下 src/services/portfolio.ts 的代码"
   
2. DeepSeek Agent Processing
   - Receives user message
   - Detects "审查" keyword
   - Decides to use claude_code tool
   
3. Tool Invocation
   claude_code({
     task: "Review code quality and suggest improvements for portfolio service",
     files: ["src/services/portfolio.ts"],
     context: "TypeScript service handling portfolio management"
   })
   
4. CLI Execution
   - Spawn claude-code process
   - Pass task via stdin
   - Stream output from stdout
   
5. Result Processing
   - Collect Claude Code output
   - Parse results
   - Return to DeepSeek
   
6. Response Integration
   - DeepSeek integrates Claude Code findings
   - Adds domain-specific insights
   - Responds to user with comprehensive answer
```

### Collaboration Pattern

**Division of Responsibilities:**

| Task Type | Handler | Reason |
|-----------|---------|--------|
| Quantitative analysis | DeepSeek | Domain expertise in finance |
| Strategy evaluation | DeepSeek | Investment decision making |
| Code implementation | Claude Code | Superior code generation |
| Code review | Claude Code | Deep code understanding |
| Architecture design | Claude Code | Technical design expertise |
| Bug fixing | Claude Code | Debugging capabilities |
| User interaction | DeepSeek | Primary agent, context aware |
| Task orchestration | DeepSeek | Workflow management |

**Collaboration Flow:**
```
Complex Task
    ↓
DeepSeek analyzes and decomposes
    ↓
    ├─→ Technical subtasks → Claude Code
    └─→ Quantitative subtasks → DeepSeek handles
    ↓
DeepSeek integrates results
    ↓
Unified response to user
```

## Configuration

### Environment Variables

Add to `.env`:
```bash
# Claude Code CLI Configuration
CLAUDE_CODE_CLI_PATH=claude-code    # CLI command path
CLAUDE_CODE_TIMEOUT=120000          # Default timeout (ms)
CLAUDE_CODE_ENABLED=true            # Enable/disable integration
```

### Prerequisites Check

**On Tool Initialization:**
```typescript
async function checkPrerequisites(): Promise<boolean> {
  // Check if CLI is installed
  const cliInstalled = await checkCommand('claude-code --version');
  if (!cliInstalled) {
    logger.warn('Claude Code CLI not found');
    return false;
  }
  
  // Check CLI version
  const version = await getClaudeCodeVersion();
  if (!isVersionCompatible(version)) {
    logger.warn(`Claude Code version ${version} may not be compatible`);
  }
  
  // Check if user is logged in
  const loggedIn = await checkClaudeCodeAuth();
  if (!loggedIn) {
    logger.warn('Claude Code not authenticated');
    return false;
  }
  
  return true;
}
```

**Behavior on Failure:**
- Log warning (not error)
- Tool remains registered but returns helpful error on invocation
- Does not block agent startup

### Dependencies

**No new npm dependencies required.**

Uses Node.js built-in modules:
- `child_process` - Process management
- `path` - Path handling
- `fs/promises` - File system checks

## Testing Strategy

### Unit Tests (`claude-code-tool.test.ts`)

**Test Cases:**
1. Parameter validation
   - Valid parameters
   - Missing required fields
   - Invalid types

2. CLI not found scenario
   - Mock spawn to throw ENOENT
   - Verify error message

3. Timeout handling
   - Mock long-running process
   - Verify timeout triggers
   - Verify process is killed

4. Error handling
   - Process crash
   - Non-zero exit code
   - Permission errors

5. Output parsing
   - Valid JSON output
   - Plain text output
   - Mixed stdout/stderr

**Example Test:**
```typescript
describe('claude-code-tool', () => {
  it('should handle CLI not found', async () => {
    jest.spyOn(child_process, 'spawn').mockImplementation(() => {
      throw new Error('ENOENT');
    });
    
    const result = await claudeCodeTool.handler({
      task: 'test task'
    });
    
    expect(result.success).toBe(false);
    expect(result.error).toContain('not found');
  });
});
```

### Integration Tests

**Prerequisites:**
- Claude Code CLI must be installed
- User must be authenticated

**Test Scenarios:**
1. Simple code review task
2. Code generation task
3. Architecture analysis
4. Concurrent invocations
5. Large file handling

### Manual Testing Checklist

- [ ] Code review request
- [ ] Code refactoring request
- [ ] Architecture analysis
- [ ] Bug fix request
- [ ] Code generation request
- [ ] Timeout scenario (long-running task)
- [ ] CLI not installed scenario
- [ ] Permission error scenario
- [ ] Concurrent calls

## Monitoring and Logging

### Log Events

**Using `observable-logger`:**

```typescript
// Tool invocation
logger.info('Claude Code tool invoked', {
  task: params.task,
  filesCount: params.files?.length || 0,
  hasContext: !!params.context
});

// Execution progress
logger.debug('Claude Code executing', {
  pid: process.pid,
  elapsed: Date.now() - startTime
});

// Completion
logger.info('Claude Code completed', {
  success: result.success,
  executionTime: result.execution_time,
  filesModified: result.files_modified?.length || 0
});

// Errors
logger.error('Claude Code failed', {
  error: result.error,
  task: params.task,
  executionTime: result.execution_time
});
```

### Performance Metrics

**Track:**
- Total invocations
- Average execution time
- Success rate
- Timeout rate
- Most common task types
- Files modified count

**Implementation:**
```typescript
interface ClaudeCodeMetrics {
  totalInvocations: number;
  successCount: number;
  failureCount: number;
  timeoutCount: number;
  totalExecutionTime: number;
  taskTypes: Record<string, number>;
}
```

### Error Monitoring

**Common Errors to Monitor:**
- CLI not installed (ENOENT)
- Authentication failures
- Timeout occurrences
- Process crashes
- Permission errors (EACCES)

## Future Enhancements

**Not in initial implementation, but possible extensions:**

1. **Session Management**
   - Maintain persistent Claude Code session
   - Reuse context across multiple calls
   - Reduce startup overhead

2. **Result Caching**
   - Cache results for identical tasks
   - TTL-based invalidation
   - Reduce redundant calls

3. **Concurrency Control**
   - Limit simultaneous Claude Code processes
   - Queue management
   - Priority-based scheduling

4. **Interactive Mode**
   - Multi-turn conversations with Claude Code
   - Clarification questions
   - Iterative refinement

5. **Configuration UI**
   - TUI-based configuration
   - Runtime enable/disable
   - Timeout adjustment

6. **Advanced Trigger Logic**
   - ML-based task classification
   - Confidence scoring
   - User preference learning

7. **Fallback Mechanism**
   - Fallback to Claude API if CLI unavailable
   - Graceful degradation

## Security Considerations

1. **Input Sanitization**
   - Validate file paths (no path traversal)
   - Sanitize task descriptions
   - Limit file list size

2. **Process Isolation**
   - Run in separate process
   - Resource limits (timeout)
   - Clean up on failure

3. **Credential Management**
   - Rely on Claude Code's own auth
   - No credential storage in this tool
   - Respect user's Claude Code session

4. **Output Validation**
   - Validate file modification claims
   - Check for suspicious operations
   - Log all file changes

## Success Criteria

**The integration is successful if:**

1. ✅ DeepSeek agent can automatically delegate code tasks to Claude Code
2. ✅ Code review, refactoring, and analysis tasks work end-to-end
3. ✅ Error handling is robust (CLI missing, timeout, crashes)
4. ✅ Performance is acceptable (< 2 minutes for typical tasks)
5. ✅ Logging provides visibility into Claude Code operations
6. ✅ Unit tests achieve > 80% coverage
7. ✅ Integration tests pass with real Claude Code CLI
8. ✅ Tool integrates seamlessly with existing tool registry

## Timeline Estimate

**Implementation Phases:**

1. **Phase 1: Core Implementation** (2-3 hours)
   - Tool definition and registration
   - CLI process management
   - Basic input/output handling

2. **Phase 2: Error Handling** (1-2 hours)
   - Timeout mechanism
   - Error scenarios
   - Prerequisites check

3. **Phase 3: Testing** (2-3 hours)
   - Unit tests
   - Integration tests
   - Manual testing

4. **Phase 4: Integration** (1 hour)
   - Tool registration
   - Documentation updates
   - Environment setup

**Total Estimate:** 6-9 hours

## Appendix

### Example Tool Usage

```typescript
// Example 1: Code review
const result = await claudeCodeTool.handler({
  task: 'Review this service for code quality, performance, and best practices',
  files: ['src/services/portfolio-service.ts'],
  context: 'Portfolio management service handling user positions'
});

// Example 2: Refactoring
const result = await claudeCodeTool.handler({
  task: 'Refactor factor calculation to improve performance and readability',
  files: ['src/infrastructure/tools/factor/'],
  timeout: 180000  // 3 minutes
});

// Example 3: Architecture analysis
const result = await claudeCodeTool.handler({
  task: 'Analyze the tool system architecture and suggest improvements',
  context: 'Six-layer quantitative investment architecture with 30+ tools',
  files: ['src/infrastructure/tools/']
});
```

### CLI Command Reference

**Assumed Claude Code CLI interface:**
```bash
# Basic usage
claude-code --task "Review code" --files "src/file.ts"

# With context
claude-code --task "Refactor" --context "Performance optimization" --files "src/"

# JSON input mode (preferred)
echo '{"task":"...","files":[...]}' | claude-code --json
```

**Note:** Actual CLI interface may differ. Implementation should adapt to the real Claude Code CLI API.

### References

- [Agent Client Protocol (ACP) Specification](https://docs.anthropic.com/acp)
- [Claude Code Documentation](https://docs.anthropic.com/claude-code)
- [pi-investment Tool System](../../../CLAUDE.md#agent-工具系统)
- [backend_control Tool Implementation](../../../src/infrastructure/tools/agent/backend-control-tool.ts)
