# t-001 实施方案：reqboard_task_execute

## 1. 工具概述

### 1.1 功能目标
实现 `reqboard_task_execute` 工具，让 Agent 能够：
- 读取任务卡信息（标题、描述、验收标准、实施方案）
- 动态生成 6 阶段详细执行计划
- 逐个阶段调用 DSH subagent 执行
- 实时更新 Markdown 任务卡进度

### 1.2 工具签名

```typescript
tools.reqboard_task_execute({
  task_id: 't-62e62f',           // 必填：任务 ID
  account_name?: 'agent_brain',  // 可选：执行账户（默认本实例账户）
  resume_from?: 3                // 可选：从第几阶段恢复（失败重试用）
})
```

### 1.3 输出结构

```typescript
{
  success: boolean,
  task_id: string,
  status: 'completed' | 'failed' | 'partial',
  stages: {
    stage: number,
    name: string,
    status: 'completed' | 'failed' | 'skipped',
    subagent_id?: string,
    output?: string,
    error?: string
  }[],
  next_step?: string  // 失败时的建议
}
```

---

## 2. 核心逻辑

### 2.1 执行流程

```
1. 读取任务卡
   ↓
2. 生成 6 阶段计划（调用 agentGenerateDetailedPlan）
   ↓
3. 更新任务卡（添加详细计划节）
   ↓
4. 循环执行每个阶段：
   4.1 更新任务卡进度（⏳ 阶段 N 进行中）
   4.2 调用 subagent 执行该阶段
   4.3 收集 subagent 输出
   4.4 更新任务卡进度（✅ 阶段 N 完成 / ❌ 失败）
   4.5 如果失败：记录失败信息，停止执行
   ↓
5. 全部完成：更新任务卡状态
   ↓
6. 返回执行结果
```

### 2.2 agentGenerateDetailedPlan 函数

这是内部辅助函数，根据任务信息生成 6 阶段计划：

```typescript
function agentGenerateDetailedPlan(task: {
  title: string,
  description: string,
  acceptance: string,
  implementation: string,
  side: 'backend' | 'frontend' | 'fullstack' | 'doc'
}): Stage[] {
  // 基础 6 阶段模板
  const baseStages = [
    { stage: 1, name: '需求分析', prompt: '分析任务目标和验收标准' },
    { stage: 2, name: '方案设计', prompt: '设计技术方案和实现路径' },
    { stage: 3, name: '代码实现', prompt: '编写核心代码' },
    { stage: 4, name: '测试验证', prompt: '运行测试并验证' },
    { stage: 5, name: '文档更新', prompt: '更新相关文档' },
    { stage: 6, name: '提交汇报', prompt: '生成完工汇报' }
  ];
  
  // 根据 side 调整阶段
  if (task.side === 'doc') {
    // 文档类任务：跳过测试
    return [1, 2, 3, 5, 6];
  }
  
  // 为每个阶段生成具体的 prompt
  return baseStages.map(stage => ({
    ...stage,
    prompt: generateStagePrompt(stage, task)
  }));
}
```

### 2.3 updateTaskCard 函数

更新 Markdown 任务卡的进度：

```typescript
async function updateTaskCard(
  taskId: string,
  updates: {
    detailedPlan?: Stage[],      // 添加详细计划节
    currentStage?: number,        // 当前阶段
    stageStatus?: 'running' | 'completed' | 'failed',
    stageOutput?: string,
    subagentId?: string
  }
): Promise<void> {
  // 1. 读取任务卡文件
  const cardPath = `docs/requirements/REQ-xxx/tasks/${taskId}.md`;
  const content = await readFile(cardPath);
  
  // 2. 解析 Markdown
  const sections = parseMarkdown(content);
  
  // 3. 更新或添加节
  if (updates.detailedPlan) {
    // 添加 "## 详细执行计划" 节
    sections.push({
      title: '详细执行计划',
      content: formatDetailedPlan(updates.detailedPlan)
    });
  }
  
  if (updates.currentStage !== undefined) {
    // 更新 "## 执行进度" 节
    updateProgressSection(sections, updates);
  }
  
  // 4. 重新生成 Markdown
  const newContent = renderMarkdown(sections);
  
  // 5. 写回文件
  await writeFile(cardPath, newContent);
}
```

---

## 3. 数据结构

### 3.1 Stage（阶段）

```typescript
interface Stage {
  stage: number;           // 阶段编号 1-6
  name: string;            // 阶段名称
  prompt: string;          // 传给 subagent 的完整提示词
  status?: 'pending' | 'running' | 'completed' | 'failed';
  subagent_id?: string;    // subagent ID（用于追踪）
  output?: string;         // 输出摘要
  error?: string;          // 错误信息
}
```

### 3.2 任务卡 Markdown 格式

```markdown
# t-62e62f 实现 reqboard_task_execute

## 在做什么
...

## 解决什么问题
...

## 得到什么结果
...

## 详细执行计划

### 阶段 1：需求分析
- 目标：分析任务目标和验收标准
- 状态：✅ 已完成
- Sub-agent: sa-abc123

### 阶段 2：方案设计
- 目标：设计技术方案和实现路径
- 状态：⏳ 进行中
- Sub-agent: sa-def456

### 阶段 3：代码实现
- 状态：⏸ 待开始

...

## 执行进度

当前阶段：2/6
完成率：33%
最近更新：2026-09-19 15:30
```

---

## 4. 实现要点

### 4.1 Subagent 调用

使用 DSH 的 `subagent` 工具：

```typescript
const result = await tools.subagent({
  description: `执行阶段 ${stage.stage}：${stage.name}`,
  prompt: stage.prompt,
  run_in_background: false  // 等待完成
});

// result 包含：
// - runId: string
// - output: JsonValue[]  // subagent 的输出
```

### 4.2 失败处理

- 记录失败阶段编号
- 保存错误信息到任务卡
- 更新任务状态为 `in_progress`（不推进到 done）
- 返回建议：`"可以用 resume_from=N 从失败阶段重新执行"`

### 4.3 幂等性

- 如果任务卡已有"详细执行计划"节 → 读取已有计划
- 如果指定 `resume_from` → 跳过前面已完成的阶段
- 避免重复执行

### 4.4 并发控制

- 单个任务一次只能有一个 `reqboard_task_execute` 在执行
- 使用 DSH todo_write 的 status 作为执行锁
- 执行前检查：`todo` 状态必须是 `in_progress`

---

## 5. 测试策略

### 5.1 单元测试

```typescript
// tests/reqboard-task-execute.test.ts

describe('reqboard_task_execute', () => {
  it('应该能读取任务卡', async () => {
    // ...
  });
  
  it('应该能生成 6 阶段计划', async () => {
    // ...
  });
  
  it('应该能更新任务卡', async () => {
    // ...
  });
  
  it('应该能调用 subagent', async () => {
    // Mock subagent 工具
    // ...
  });
  
  it('失败时应该记录错误', async () => {
    // ...
  });
  
  it('应该支持从断点恢复', async () => {
    // ...
  });
});
```

### 5.2 E2E 测试

创建一个真实任务，执行完整流程：

1. 创建测试需求（REQ-test-001）
2. 拆分任务（t-test-001）
3. 调用 `reqboard_task_execute(t-test-001)`
4. 验证：
   - 任务卡被更新
   - subagent 被调用
   - 最终状态正确

---

## 6. 实施步骤

### 第1步：创建工具骨架（0.5天）
- 在 `packages/pages/dsh-pmboard/src/tools/` 创建 `TaskExecuteTool/`
- 定义工具 schema
- 实现空的 execute 函数

### 第2步：实现 agentGenerateDetailedPlan（0.5天）
- 创建 `application/internal/generate-detailed-plan.ts`
- 实现 6 阶段模板
- 根据 side 调整阶段
- 生成阶段 prompt

### 第3步：实现 updateTaskCard（1天）
- 创建 `application/internal/update-task-card.ts`
- Markdown 解析和生成
- 添加/更新节

### 第4步：实现主执行流程（1天）
- 读取任务卡
- 调用 agentGenerateDetailedPlan
- 循环执行阶段
- 调用 subagent
- 更新进度

### 第5步：失败处理与恢复（0.5天）
- 记录失败信息
- 实现 resume_from 逻辑

### 第6步：测试（1天）
- 单元测试
- E2E 测试
- 修复 bug

**总计：约 4.5 天**

---

## 7. 风险与应对

### 风险1：subagent 超时
- **应对**：设置合理的 timeout，失败后可重试

### 风险2：任务卡解析失败
- **应对**：容错处理，保留原内容

### 风险3：并发执行冲突
- **应对**：使用 todo 状态作为执行锁

---

## 8. 依赖项

### 已有工具
- `tools.subagent` - DSH 提供
- `tools.todo_write` - DSH 提供（用于状态管理）

### 需要实现的内部函数
- `agentGenerateDetailedPlan` - 生成 6 阶段计划
- `updateTaskCard` - 更新 Markdown 任务卡
- `parseMarkdown` / `renderMarkdown` - Markdown 处理

### 外部依赖
- 文件系统（读写任务卡）
- DSH subagent 工具

---

## 9. 验收标准

✅ `npx vitest run tests/reqboard-task-execute.test.ts` 通过  
✅ E2E 测试：能完整执行一个测试任务  
✅ 失败重试：能从断点恢复  
✅ 任务卡更新：Markdown 格式正确，进度可见

---

## 10. 后续优化

- 支持并行执行多个阶段（P1）
- 支持自定义阶段数（P2）
- 支持阶段依赖关系（P2）
- 可视化执行进度（P1，前端）
