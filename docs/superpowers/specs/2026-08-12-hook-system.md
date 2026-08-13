# Hook System Implementation (T6 / W2.4)

## Overview

The Hook system provides a declarative extension mechanism for intercepting and controlling tool execution in the agent. It was implemented as part of the framework evolution roadmap to enable pluggable behavior modifications without modifying core engine code.

## Architecture

### Components

1. **Registry** (`src/services/hooks/registry.ts`)
   - Central registration point for all hooks
   - Manages hook definitions with priority-based ordering
   - Filters hooks by trigger type

2. **Executor** (`src/services/hooks/executor.ts`)
   - Executes registered hooks in priority order
   - Implements per-hook timeout protection
   - Handles errors gracefully (non-blocking)
   - Logs interceptions to audit trail

3. **Integration Points**
   - `src/sdk-facade.ts`: Hook execution before tool calls
   - `src/infrastructure/session/session-factory.ts`: Turn/tool call counter management
   - `src/api/extensions/loop-guardian.ts`: LoopGuardian hook registration

## Hook Definition

```typescript
interface HookDefinition {
  name: string;              // Unique identifier
  priority: number;          // Lower = executes first
  timeoutMs: number;         // Max execution time
  triggers: HookTrigger[];   // Which events trigger this hook
  handler: HookHandler;      // The hook logic
}

type HookAction = "allow" | "block" | "modify";

interface HookResult {
  action: HookAction;
  reason?: string;           // Logged for non-allow actions
  modifiedArgs?: unknown;    // Used when action is "modify"
}
```

## Execution Flow

```
Tool Call Request
    ↓
normalizeToolDefinition() intercepts
    ↓
executeBeforeToolCallHooks({
  toolName: string,
  args: unknown,
  turnCount: number,
  toolCallCount: number
})
    ↓
For each hook (priority order):
  - Execute with timeout
  - If block/modify → return immediately
  - If error → log and continue
  - If allow → continue to next
    ↓
Result:
  - block: Return error message to LLM
  - modify: Use modified args
  - allow: Proceed normally
```

## Audit Trail

Non-allow actions are logged to `.pi-invest/hooks.log`:

```
2026-08-12T10:30:45.123Z [hook-name] action=block reason="..." tool=tool_name turn=15
```

## LoopGuardian Integration

The LoopGuardian's R3 rule (repeat call detection) has been migrated to use the hook system:

**Before**: Direct interception in `tool_execution_start` event handler
**After**: Registered hook with priority 20

```typescript
registerLoopGuardianHooks(state);  // Called on agent_start
unregisterLoopGuardianHooks();     // Called on agent_end
```

### Hooks Registered

1. **loop-guardian-repeat-call-intercept** (priority 20)
   - Detects consecutive identical tool calls (same tool + args)
   - Blocks after threshold (default: 3 consecutive calls)
   - Returns block action with reason

## Usage Example

### Registering a Hook

```typescript
import { hookRegistry } from "./services/hooks/index.js";

hookRegistry.register({
  name: "rate-limit-check",
  priority: 5,
  timeoutMs: 100,
  triggers: ["before_tool_call"],
  handler: async (context) => {
    if (isRateLimited(context.toolName)) {
      return {
        action: "block",
        reason: "Rate limit exceeded"
      };
    }
    return { action: "allow" };
  }
});
```

### Hook Context

Handlers receive:
- `toolName`: Name of the tool being called
- `args`: Tool arguments
- `turnCount`: Current turn number in session
- `toolCallCount`: Total tool calls in session

## Testing

### Hook System Tests (`src/services/hooks/hooks.test.ts`)

All 12 tests passing:
- ✅ Registry operations (register, duplicate detection)
- ✅ Priority ordering (ascending)
- ✅ Trigger filtering
- ✅ Execution: allow default, block early return, modify
- ✅ Timeout protection
- ✅ Error handling (non-blocking)
- ✅ Audit logging

### LoopGuardian Tests

All 20 tests passing:
- ✅ Core rule tests (R1-R7)
- ✅ Integration tests (event wiring)
- ✅ No regression from hook migration

## Design Decisions

### 1. Priority-based Sequential Execution

Hooks execute in priority order (ascending) to ensure predictable behavior. The first hook to return `block` or `modify` stops execution.

**Rationale**: Avoids conflicting modifications and provides clear control flow.

### 2. Per-hook Timeout

Each hook has its own timeout, implemented with `Promise.race()`.

**Rationale**: Prevents one slow hook from blocking the entire pipeline.

### 3. Non-blocking Error Handling

Hook errors are logged but don't prevent subsequent hooks from executing.

**Rationale**: System resilience - one broken hook shouldn't break the entire agent.

### 4. Global Counter State

Turn and tool call counters are maintained globally in `sdk-facade.ts` rather than passed through context.

**Rationale**: Simplifies integration with existing SDK event system.

### 5. Partial LoopGuardian Migration

Only R3 (repeat call) migrated to hooks. R1/R2 (turn nudge) remain in original location.

**Rationale**: R1/R2 are turn-boundary checks, not tool-call interceptions. Clean separation of concerns.

## Future Extensions

The hook system supports additional trigger points (defined but not yet implemented):

- `after_tool_call`: Post-execution validation
- `turn_end`: Turn boundary policies
- `agent_end`: Final validation before task completion

### Example Use Cases

1. **Security Policy Enforcement**
   ```typescript
   // Block tools that access sensitive data without auth
   hookRegistry.register({
     name: "security-check",
     priority: 1,  // Execute first
     triggers: ["before_tool_call"],
     handler: async (ctx) => {
       if (isSensitiveTool(ctx.toolName) && !hasAuth()) {
         return { action: "block", reason: "Unauthorized" };
       }
       return { action: "allow" };
     }
   });
   ```

2. **Parameter Sanitization**
   ```typescript
   // Modify args to sanitize inputs
   hookRegistry.register({
     name: "sanitize-inputs",
     priority: 10,
     triggers: ["before_tool_call"],
     handler: async (ctx) => {
       const sanitized = sanitize(ctx.args);
       if (sanitized !== ctx.args) {
         return {
           action: "modify",
           modifiedArgs: sanitized,
           reason: "Input sanitized"
         };
       }
       return { action: "allow" };
     }
   });
   ```

3. **Cost Control**
   ```typescript
   // Block expensive operations over budget
   hookRegistry.register({
     name: "budget-check",
     priority: 3,
     triggers: ["before_tool_call"],
     handler: async (ctx) => {
       const cost = estimateCost(ctx.toolName, ctx.args);
       if (budget.remaining() < cost) {
         return { action: "block", reason: "Budget exceeded" };
       }
       return { action: "allow" };
     }
   });
   ```

## Performance Considerations

- **Overhead**: ~1-2ms per hook (including timeout setup)
- **Typical load**: 1-3 hooks per tool call
- **Total impact**: <5ms additional latency per tool call

The performance impact is negligible compared to typical tool execution times (50-500ms).

## Troubleshooting

### Hook Not Firing

1. Check hook is registered: `hookRegistry.getRegisteredHooks()`
2. Verify trigger matches: `hookRegistry.getHooksForTrigger("before_tool_call")`
3. Check priority ordering if multiple hooks

### Hook Timing Out

Increase `timeoutMs` in hook definition. Default 100ms should be sufficient for most checks.

### Audit Log Missing Entries

- Only `block` and `modify` actions are logged
- `allow` actions are silent (performance)
- Check `.pi-invest/hooks.log` exists and is writable

## References

- Design doc: `docs/superpowers/plans/2026-08-12-execution-tickets.md` (T6)
- LoopGuardian design: `docs/superpowers/specs/2026-08-11-loop-guardian-design.md`
- Framework evolution: `docs/superpowers/plans/2026-08-12-framework-evolution-roadmap.md`

## Version History

- **2026-08-12**: Initial implementation (T6/W2.4)
  - Hook registry and executor
  - LoopGuardian R3 migration
  - SDK integration
  - Test coverage: 32 tests passing
