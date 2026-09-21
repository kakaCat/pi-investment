# 需求文档：Workflow 使用 Subagent 执行以减少上下文压力

> **创建**: 2026-09-21  
> **状态**: brainstorming

## 一、问题陈述

### 1.1 用户需求

> "使用 workflow 是想利用 subagent 减少上下文内容消耗，节省 token"

**核心问题**：当前 workflow 没有使用 subagent，导致主窗口上下文累积。

### 1.2 当前实现（ctx.workflow）

**代码位置**：`src/application/use-cases/ExecuteTask.ts` 第152-167行

```typescript
// 当前实现
outcome = await deps.workflow.start({
  script,
  meta: { name: 'reqboard-subtask-...' },
  args: { subtaskId, parentId, stageKind },
  parent: ...,
  signal: ...,
})
```

**问题分析**：
1. `deps.workflow` 是什么？它在哪个上下文执行？
2. 是否会累积主窗口的上下文？
3. 与 DSH 的 `ctx.subagent` 有什么区别？

**需要调研**：
- `deps.workflow` 的实际实现（`WorkflowEngine` 接口）
- 它的上下文隔离机制
- 与 `subagent` 工具的对比

### 1.3 期望设计（ctx.subagent）

**使用 DSH 的 subagent 工具**：

```typescript
// 期望实现
const result = await ctx.subagent({
  description: task.title,
  prompt: buildSubtaskPrompt(parent, task),
  // run_in_background: false  // 同步等待完成
})
```

**优势**：
1. **独立上下文**：subagent 有自己的对话历史，不影响主窗口
2. **节省 token**：主窗口不累积子任务的执行细节
3. **标准工具**：使用 DSH 原生的 subagent 机制

## 二、功能需求

### FR-1: 调研当前 workflow 实现

**目标**：理解 `deps.workflow` 的实际机制，确认是否需要替换。

**调研内容**：
1. `WorkflowEngine` 接口定义（在 `src/application/ports.ts`）
2. 实际实现（哪个插件提供？）
3. 上下文隔离：是否在主窗口上下文执行？
4. token 消耗：是否累积到主窗口？

**调研产出**：
- 技术调研文档（对比 workflow vs subagent）
- 明确是否需要替换
- 如需替换，列出具体改动点

### FR-2: 设计 Subagent 执行方案

**目标**：设计用 `ctx.subagent` 替代 `deps.workflow.start` 的方案。

**设计要点**：
1. **Prompt 构建**：如何把 `script` 转换为 `prompt`？
   - 当前：`generateSubtaskScript()` 生成脚本
   - 期望：`buildSubtaskPrompt()` 生成自然语言 prompt

2. **产出解析**：如何从 subagent 返回值提取结果？
   - 当前：`parseSubtaskOutput(outcome)`
   - 期望：解析 subagent 的 `output` 字段

3. **错误处理**：subagent 失败如何处理？
   - 重试机制
   - 错误信息提取

4. **状态同步**：如何更新任务卡状态？
   - 开始执行：`in_progress`
   - 完成：`done`
   - 失败：`failed`

**设计产出**：
- 接口设计文档（`executeWithSubagent` 函数）
- 数据流图（prompt → subagent → output → task done）
- 错误处理流程

### FR-3: 实现 Subagent 执行器

**目标**：修改 `ExecuteTask.ts`，使用 `ctx.subagent` 执行子任务。

**核心改动**：

```typescript
// src/application/use-cases/ExecuteTask.ts

// 旧代码（删除）
// outcome = await deps.workflow.start({ script, ... })

// 新代码
const prompt = buildSubtaskPrompt(parent, task, label)
const subagentResult = await deps.subagent({
  description: fmt('执行子卡：{title}', { title: task.title }),
  prompt,
  // run_in_background: false  // 同步等待
})

// 解析 subagent 返回值
const parsed = parseSubagentOutput(subagentResult)
```

**依赖注入**：
```typescript
// src/application/ports.ts

export interface UseCaseDeps {
  // ... 其他依赖
  
  // 新增
  subagent: (args: {
    description: string
    prompt: string
    run_in_background?: boolean
  }) => Promise<{ output: unknown }>
  
  // 可选：保留 workflow 作为降级方案
  workflow?: WorkflowEngine
}
```

**验收标准**：
```gherkin
Given 一个任务卡处于 in_progress 状态
When ExecuteTask 使用 subagent 执行
Then subagent 在独立上下文中执行
And 主窗口不累积执行细节
And subagent 完成后，任务卡状态更新为 done
And 产出（filesChanged / completed / evidence）正确解析
```

### FR-4: 性能与 Token 消耗验证

**目标**：验证使用 subagent 后，主窗口 token 消耗确实减少。

**验证方法**：
1. **对比测试**：
   - 场景：执行 5 张子卡的 workflow
   - 对比：旧实现（workflow）vs 新实现（subagent）
   - 指标：主窗口对话历史长度、token 消耗

2. **预期结果**：
   - 旧实现：主窗口包含 5 张子卡的完整执行日志
   - 新实现：主窗口只包含"启动 subagent"和"接收结果"
   - Token 节省：约 50-80%（取决于子任务复杂度）

**验收标准**：
- 主窗口对话历史不包含子任务执行细节
- Token 消耗显著低于旧实现
- 功能行为保持一致（产出、错误处理等）

## 三、技术调研（待完成）

### 3.1 当前 workflow 机制

**问题清单**：
1. `deps.workflow` 的实际实现是什么？
2. `WorkflowEngine` 接口定义？
3. 脚本在哪里执行？主窗口还是独立进程？
4. 上下文如何管理？

**调研方法**：
- 查看 `src/application/ports.ts` 的 `WorkflowEngine` 接口
- 查找哪个插件实现了这个接口
- 阅读实现代码，理解上下文隔离机制

### 3.2 Subagent 工具能力

**已知信息**（从系统提示词）：
- `subagent` 工具：委托独立任务到子 agent
- 子 agent 有自己的上下文，不共享父 agent 的对话历史
- 支持 `run_in_background: true`（后台执行）

**需要确认**：
- 同步模式（`run_in_background: false`）的行为
- 返回值格式
- 错误处理机制

## 四、范围边界

### 4.1 本次做什么

1. **调研当前 workflow 实现**（FR-1）
2. **设计 subagent 执行方案**（FR-2）
3. **实现替换**（FR-3）
4. **验证 token 节省**（FR-4）

### 4.2 本次不做什么

1. **不改动任务卡生成逻辑**：子卡的生成保持不变
2. **不改动 AdvanceChain 骨牌机制**：事件链执行器保持不变
3. **不实现并行执行**：仍然是串行，只是改用 subagent

### 4.3 依赖与约束

- **依赖**：DSH 的 `subagent` 工具
- **约束**：产出格式必须与当前一致（`filesChanged` / `completed` / `evidence`）
- **兼容**：可选保留 `workflow` 作为降级方案

## 五、预期收益

### 5.1 Token 节省

**示例**（5 张子卡）：

| 维度 | 旧实现（workflow） | 新实现（subagent） |
|------|--------------------|--------------------|
| 主窗口对话长度 | 5 张卡的完整日志（约 10K tokens） | 5 条"启动/完成"消息（约 2K tokens） |
| Token 消耗 | 100% | 20% |
| 节省 | - | **80%** |

### 5.2 其他收益

- **上下文清晰**：主窗口只看到高层流程，不被细节淹没
- **调试方便**：子任务失败时，可以独立查看 subagent 日志
- **可扩展性**：未来可以轻松支持并行（`run_in_background: true`）

## 六、风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| workflow 有特殊能力 subagent 没有 | 高 | 先调研清楚再决定是否替换 |
| 产出格式不兼容 | 中 | 详细设计解析逻辑，确保一致 |
| 错误处理不完善 | 中 | 重试机制，清晰的错误信息 |
| 破坏现有功能 | 低 | 保留 workflow 作为降级方案 |

## 七、实施计划

### Phase 1: 调研阶段（当前）
- 调研 `deps.workflow` 实际实现
- 对比 workflow vs subagent 能力
- 输出调研报告

### Phase 2: 设计阶段
- 设计 subagent 执行方案
- 定义接口和数据流
- 设计错误处理

### Phase 3: 实现阶段
- 修改 `ExecuteTask.ts`
- 实现 `buildSubtaskPrompt`
- 实现 `parseSubagentOutput`

### Phase 4: 验证阶段
- 功能测试（端到端 workflow）
- 性能测试（token 消耗对比）
- 回归测试（确保不破坏现有功能）

## 八、下一步

**批准进入调研阶段**，产出：
1. **技术调研报告**：`deps.workflow` 实现分析
2. **对比文档**：workflow vs subagent 能力对比
3. **可行性结论**：是否替换，如何替换

然后进入**设计阶段**，输出详细技术设计文档。

---

**需求类型**：feature  
**难度级别**：expert（涉及执行引擎替换）  
**功能点数**：4 个（FR-1 调研 / FR-2 设计 / FR-3 实现 / FR-4 验证）  
**优先级**：高（实现 workflow 设计初衷）
