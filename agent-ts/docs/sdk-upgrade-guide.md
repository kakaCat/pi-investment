# SDK 升级指南

当 `@mariozechner/pi-coding-agent` 升级导致编译错误时，按此指南操作。

## 架构原理

```
业务代码 (119 files) → 统一导入 sdk-facade.ts
                            ↕
      sdk-facade.ts ← 唯一导入 @mariozechner/ 的地方
      session-facade.ts
      compaction-facade.ts
```

**关键规则：只有 `src/sdk-facade.ts`、`src/session-facade.ts`、`src/compaction-facade.ts` 这 3 个文件直接导入 SDK。** 其他所有文件通过 facade 间接使用 SDK。

## 常见升级场景

### 场景 1: ToolDefinition 新增必填字段

```typescript
// sdk-facade.ts 修改 normalizeToolDefinition:
export function normalizeToolDefinition(tool: PiToolDefinition): SdkToolDefinition {
  return {
    name: tool.name,
    label: tool.label ?? tool.name,
    description: tool.description,
    parameters: tool.parameters as SdkToolDefinition["parameters"],
    newRequiredField: tool.newRequiredField ?? defaultValue, // ← 新增
    execute: async (...) => { ... },
  } as SdkToolDefinition;
}
```

**影响范围**: 仅 `sdk-facade.ts` 的 `normalizeToolDefinition` 函数。

### 场景 2: execute 签名变更（参数顺序/数量调整）

```typescript
// sdk-facade.ts 修改 normalizeToolDefinition 中的 execute:
export function normalizeToolDefinition(tool: PiToolDefinition): SdkToolDefinition {
  return {
    // ... 其他字段不变 ...
    execute: async (
      toolCallId: string,
      params: unknown,
      signal?: AbortSignal,
      onUpdate?: (update: unknown) => void,
      ctx?: unknown,
      newExtraParam?: Something  // ← 新增或调整参数
    ): Promise<AgentToolResult<unknown>> => {
      return tool.execute(toolCallId, params, signal, onUpdate, ctx);
    },
  } as SdkToolDefinition;
}
```

**影响范围**: 仅 `sdk-facade.ts` 的 `normalizeToolDefinition` 函数。所有工具文件无需修改（它们使用固定的 `PiToolExecute` 签名）。

### 场景 3: createAgentSession 参数变更

```typescript
// session-facade.ts 修改:
export async function createSession(options: CreateSessionOptions) {
  // 调整参数映射
  return sdkCreateAgentSession({
    ...options,
    newOption: options.legacyOption ?? defaultNewOption,
  } as any);
}
```

**影响范围**: 仅 `session-facade.ts`。

### 场景 4: estimateTokens / generateSummary 签名变更

```typescript
// compaction-facade.ts 修改:
export function estimateTokens(message: unknown): number {
  return sdkEstimateTokens(message as any, { newOption: true }); // ← 适配新参数
}
```

**影响范围**: 仅 `compaction-facade.ts`。

### 场景 5: SDK 模块重组（类型移到新包）

1. 更新 `sdk-facade.ts` 中的 import 路径
2. 业务代码无需修改（它们只导入 facade）

### 场景 6: 新增 SDK 功能

1. 评估：业务代码需要直接使用吗？
   - 是 → 在 facade 中添加包装
   - 否 → 不做任何事

## 升级检查清单

```bash
# 1. 检查是否只有 facade 文件直接导入 SDK
grep -rn "from '@mariozechner/pi-coding-agent'" src/ --include="*.ts" \
  | grep -v sdk-facade | grep -v session-facade | grep -v compaction-facade
# 应返回空

grep -rn "from '@mariozechner/pi-agent-core'" src/ --include="*.ts" \
  | grep -v sdk-facade
# 应返回空

# 2. 编译检查
npm run build
# 应零错误

# 3. 运行测试
npm test
# 应全部通过
```

## 快速修复流程

1. `npm run build` → 查看错误
2. 根据错误类型，修改 1-3 个 facade 文件
3. 再次 `npm run build` → 确认零错误
4. `npm test` → 确认功能正常

**预计时间：5-30 分钟**
