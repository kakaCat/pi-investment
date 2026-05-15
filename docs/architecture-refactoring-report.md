# Evolution System 架构重构报告

> 日期: 2026-05-15  
> 类型: 领域边界明确化重构

---

## 1. 重构背景

### 1.1 问题识别

Evolution System 和投资 Agent 之间存在**领域边界模糊**的问题：

```
问题 1: 职责混淆
├─ 投资 Agent (DeepSeek) 既做投资决策，又做代码生成
├─ 同一个 Agent Session 承担两个不同角色
└─ 通过 SessionContext 切换 system prompt

问题 2: 循环依赖风险
├─ Agent Loop → Evolution Service
├─ Evolution Service → Code Generator
├─ Code Generator → Agent Loop (getSession)
└─ 形成循环依赖

问题 3: 架构不清晰
├─ Evolution (元系统) 直接操作 Agent (业务系统)
├─ 代码生成逻辑耦合在投资决策系统中
└─ 难以独立测试和扩展
```

---

## 2. 重构方案

### 2.1 选择的方案

**方案 2: 使用 Codex Agent 进行代码生成**

```
┌─────────────────────────────────────────────────┐
│     Investment Agent (DeepSeek)                 │
│     - 专注投资决策                               │
│     - 分析市场数据                               │
│     - 执行交易策略                               │
└─────────────────────────────────────────────────┘
                    ↑ 被优化
                    │
┌─────────────────────────────────────────────────┐
│         Evolution System (元系统)               │
│         - 分析性能差距                           │
│         - 生成优化建议                           │
│         - 协调执行                               │
└──────────────┬──────────────────────────────────┘
               │ 委托代码生成
               ↓
┌─────────────────────────────────────────────────┐
│       Codex Agent (GPT-5.4)                     │
│       - 专门负责代码生成                         │
│       - 独立进程，无依赖                         │
│       - 通过 CLI 调用                            │
└─────────────────────────────────────────────────┘
```

### 2.2 方案优势

1. ✅ **职责清晰**: 投资 Agent 专注投资，Codex 专注代码生成
2. ✅ **完全解耦**: Evolution 不依赖投资 Agent
3. ✅ **利用现有基础设施**: 项目已有 Codex 集成（CLAUDE.md）
4. ✅ **更强的代码生成能力**: GPT-5.4 > DeepSeek（代码生成场景）
5. ✅ **可独立测试**: 可以单独测试代码生成能力
6. ✅ **无循环依赖**: 单向依赖链

---

## 3. 实施细节

### 3.1 修改的文件

#### 文件 1: `src/services/intelligence/code-generator.ts`

**修改前**:
```typescript
// 依赖投资 Agent
import { getSession } from '../../core/agent/agent-loop.js';

export async function generateToolCode(spec: ToolAddition) {
  const session = await getSession();  // ❌ 使用投资 Agent
  await session.prompt(prompt);
  // ...
}
```

**修改后**:
```typescript
// 使用 Codex CLI
import { exec } from 'child_process';

export async function generateToolCode(spec: ToolAddition) {
  // ✅ 调用 Codex (GPT-5.4)
  await execAsync(
    `codex exec --dangerously-bypass-approvals-and-sandbox --ephemeral ` +
    `-C ${process.cwd()} -o ${outputFile} "${prompt}"`
  );
  // ...
}
```

**关键变更**:
- 删除了对 `getSession()` 的依赖
- 删除了对 `session-adapter.js` 的依赖
- 使用 `child_process.exec` 调用 Codex CLI
- 添加了错误处理和超时机制（2 分钟）
- 添加了临时文件清理逻辑

---

#### 文件 2: `src/core/agent/agent-loop.ts`

**修改前**:
```typescript
function buildSystemPromptForContext(ctx: SessionContext | null): string {
  if (ctx?.type === 'cron_evolution') {
    return `你是一个专业的投资工具代码生成助手。`; // ❌ 代码生成角色
  }
  return buildAgentSystemPrompt(...); // 投资决策角色
}

function getToolsForContext(ctx: SessionContext | null): ToolDefinition[] {
  if (ctx?.type === 'cron_evolution') {
    return []; // 代码生成不需要工具
  }
  return getEffectiveTools();
}
```

**修改后**:
```typescript
function buildSystemPromptForContext(ctx: SessionContext | null): string {
  // ✅ 所有上下文都使用投资决策 prompt
  // 代码生成已委托给 Codex
  return buildAgentSystemPrompt({
    memoryContext: "",
    dailyMemory: "",
    tools: getEffectiveTools(),
    workspaceDir: paths.root,
  });
}

function getToolsForContext(ctx: SessionContext | null): ToolDefinition[] {
  // ✅ 所有上下文都使用完整工具集
  return getEffectiveTools();
}
```

**关键变更**:
- 删除了 `cron_evolution` 的特殊处理
- 简化了上下文切换逻辑
- 投资 Agent 现在只有一个角色：投资决策
- 添加了注释说明 `cron_evolution` 已废弃

---

### 3.2 沙箱验证（无需修改）

`sandbox-validator.ts` **完全不需要修改**，因为它只关心文件路径：

```typescript
export async function validateInSandbox(
  toolFilePath: string,    // 👈 只需要文件路径
  testFilePath?: string
): Promise<ValidationResult[]>
```

验证流程保持不变：
1. ✅ 编译验证: `tsc --noEmit`
2. ✅ 单元测试: `npm test`
3. ✅ 集成测试: 动态导入验证结构

---

## 4. 测试验证

### 4.1 测试脚本

创建了 `src/scripts/test-codex-generation.ts` 用于验证完整流程：

```typescript
测试流程:
1. 定义测试工具规格
2. 调用 Codex 生成代码
3. 写入临时文件
4. 沙箱三级验证
5. 清理临时文件
```

### 4.2 运行测试

```bash
# 编译测试
npx tsc --noEmit src/services/intelligence/code-generator.ts
npx tsc --noEmit src/core/agent/agent-loop.ts

# 功能测试（需要 Codex 可用）
npm run build
node dist/scripts/test-codex-generation.js
```

---

## 5. 影响分析

### 5.1 受影响的模块

| 模块 | 影响 | 状态 |
|-----|------|------|
| `code-generator.ts` | 重写代码生成逻辑 | ✅ 已完成 |
| `agent-loop.ts` | 删除代码生成分支 | ✅ 已完成 |
| `sandbox-validator.ts` | 无影响 | ✅ 无需修改 |
| `evolution-executor.ts` | 无影响（调用接口不变） | ✅ 无需修改 |
| `evolution-service.ts` | 无影响 | ✅ 无需修改 |

### 5.2 API 兼容性

**对外接口完全兼容**：

```typescript
// 接口签名不变
export async function generateToolCode(
  toolSpec: ToolAddition
): Promise<GeneratedCode>
```

调用方（`evolution-executor.ts`）无需修改。

---

## 6. 优势总结

### 6.1 架构改进

| 维度 | 改进前 | 改进后 |
|-----|--------|--------|
| 职责分离 | ❌ Agent 承担双重角色 | ✅ 各司其职 |
| 依赖关系 | ⚠️ 循环依赖风险 | ✅ 单向依赖 |
| 可测试性 | ⚠️ 难以独立测试 | ✅ 可独立测试 |
| 代码生成能力 | DeepSeek | ✅ GPT-5.4（更强） |
| 扩展性 | ⚠️ 耦合紧密 | ✅ 易于扩展 |

### 6.2 代码质量

- **代码行数**: 减少约 50 行（删除了上下文切换逻辑）
- **复杂度**: 降低（消除了条件分支）
- **可读性**: 提升（职责更清晰）
- **维护性**: 提升（模块独立）

---

## 7. 后续工作

### 7.1 立即行动（本周）

1. ✅ 完成代码重构
2. ⏳ 运行端到端测试（需要 Codex 可用）
3. ⏳ 更新相关文档

### 7.2 短期优化（本月）

1. 添加 Codex 调用的重试机制
2. 优化 prompt 模板（提高代码质量）
3. 添加代码生成的性能监控

### 7.3 长期改进（季度）

1. 支持多个代码生成模型（Claude Opus, GPT-5.4, DeepSeek）
2. 实现代码生成的 A/B 测试
3. 建立代码生成质量评估体系

---

## 8. 风险与缓解

### 8.1 潜在风险

| 风险 | 影响 | 缓解措施 |
|-----|------|---------|
| Codex 不可用 | 代码生成失败 | 添加降级方案（使用 DeepSeek） |
| Codex 响应慢 | 进化流程变慢 | 添加超时和重试机制 |
| 生成代码质量下降 | 沙箱验证失败 | 优化 prompt，添加示例 |

### 8.2 回滚方案

如果重构出现问题，可以快速回滚：

```bash
# 回滚到重构前的版本
git revert <commit-hash>
```

所有修改都在 2 个文件中，回滚成本低。

---

## 9. 总结

### 9.1 重构成果

✅ **成功实现了领域边界的明确化**：
- 投资 Agent 专注投资决策
- Codex Agent 专注代码生成
- Evolution System 作为元系统协调两者

✅ **架构更清晰**：
- 消除了循环依赖
- 单向依赖链
- 模块职责清晰

✅ **代码质量提升**：
- 减少了 50 行代码
- 降低了复杂度
- 提高了可测试性

### 9.2 经验教训

1. **领域边界要在设计阶段明确**，而不是实现后再重构
2. **职责单一原则**适用于 Agent 系统
3. **利用现有基础设施**（Codex）比重新实现更高效

---

**文档维护**: 请在后续优化后更新此文档
