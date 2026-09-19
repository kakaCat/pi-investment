# t-001 实施方案 v2：基于 DSH Workflow

> **重大变更**：从自己实现循环调用改为使用 DSH 原生 `workflow` 工具

---

## 1. 工具概述

### 1.1 核心变化

**之前的设计**：
- 自己实现 6 阶段循环
- 逐个调用 `subagent`
- 手动管理状态

**现在的设计**：
- 使用 DSH `workflow` 工具（一次调用）
- 编写 JavaScript 编排脚本
- 自动管理多个 subagent

### 1.2 工具签名

```typescript
tools.reqboard_task_execute({
  task_id: 't-62e62f',           // 必填：任务 ID
  resume_from?: 3                // 可选：从第几阶段恢复
})
```

### 1.3 输出结构

```typescript
{
  success: boolean,
  task_id: string,
  workflow_run_id: string,        // DSH workflow 运行 ID
  status: 'completed' | 'failed',
  stages: {
    stage: number,
    name: string,
    status: 'completed' | 'failed',
    output?: string
  }[],
  next_step?: string
}
```

---

## 2. 核心逻辑

### 2.1 执行流程

```
1. 读取任务卡
   ↓
2. 生成 6 阶段定义
   ↓
3. 生成 Workflow 脚本（JavaScript）
   ↓
4. 调用 DSH workflow 工具（一次调用）
   ├─ DSH 自动扇出 6 个 subagent
   ├─ DSH 自动管理并发和错误
   └─ DSH 返回聚合结果
   ↓
5. 解析 workflow 结果
   ↓
6. 更新任务卡（添加执行记录）
   ↓
7. 返回执行结果
```

### 2.2 generateWorkflowScript 函数

核心：生成 JavaScript 编排脚本

```typescript
function generateWorkflowScript(task: {
  title: string,
  description: string,
  acceptance: string,
  implementation: string,
  side: 'backend' | 'frontend' | 'fullstack' | 'doc'
}, resumeFrom?: number): string {
  const stages = generateStageDefinitions(task, resumeFrom);
  
  // 生成 JavaScript 脚本
  return `
    // 任务：${task.title}
    const results = [];
    
    // 阶段 1：需求分析
    ${resumeFrom <= 1 ? `
    const stage1 = await ctx.subagent({
      description: '阶段1：需求分析',
      prompt: \`
        任务：${task.title}
        
        请分析：
        1. 任务目标是什么
        2. 验收标准：${task.acceptance}
        3. 关键挑战和风险
        
        输出：分析结论（JSON格式）
      \`
    });
    results.push({ stage: 1, name: '需求分析', ...stage1 });
    ` : '// 阶段1已完成，跳过'}
    
    // 阶段 2：方案设计
    ${resumeFrom <= 2 ? `
    const stage2 = await ctx.subagent({
      description: '阶段2：方案设计',
      prompt: \`
        基于需求分析：${JSON.stringify(stage1.result)}
        
        设计技术方案：
        1. 数据结构
        2. 接口定义
        3. 关键算法
        
        输出：设计方案（JSON格式）
      \`
    });
    results.push({ stage: 2, name: '方案设计', ...stage2 });
    ` : '// 阶段2已完成，跳过'}
    
    // ... 阶段 3-6 类似
    
    return {
      success: true,
      stages: results
    };
  `;
}
```

### 2.3 核心实现

```typescript
async function executeTask(taskId: string, resumeFrom?: number) {
  // 1. 读取任务卡
  const task = await readTaskCard(taskId);
  
  // 2. 生成 workflow 脚本
  const script = generateWorkflowScript(task, resumeFrom);
  
  // 3. 调用 DSH workflow
  const result = await ctx.tools.workflow({
    meta: {
      name: `执行任务 ${taskId}`,
      description: task.title,
      phases: ['分析', '设计', '实现', '测试', '文档', '汇报']
    },
    script,
    args: { task }
  });
  
  // 4. 更新任务卡
  await updateTaskCard(taskId, {
    workflowRunId: result.runId,
    stages: result.result.stages,
    status: result.result.success ? 'completed' : 'failed'
  });
  
  return result;
}
```

---

## 3. 关键优势

### 3.1 相比自己实现

| 维度 | 自己实现 | DSH Workflow |
|------|---------|--------------|
| 代码量 | ~500行 | ~200行 |
| 并发控制 | 手动实现 | 自动管理 |
| 错误处理 | 手动捕获 | 自动处理 |
| 取消支持 | 需要实现 | 内置支持 |
| 可视化 | 需要自己做 | DSH 自动记录 |
| 状态管理 | 手动维护 | Session 管理 |

### 3.2 DSH Workflow 自动提供

- ✅ 多 subagent 并发扇出
- ✅ Session 事件记录
- ✅ 取消和超时处理
- ✅ 错误聚合
- ✅ 结果标准化

---

## 4. 数据结构

### 4.1 Stage 定义

```typescript
interface StageDefinition {
  stage: number;
  name: string;
  description: string;
  prompt: string;
  dependsOn?: number[];  // 依赖的前置阶段
}
```

### 4.2 任务卡 Markdown 格式

```markdown
# t-62e62f 实现 reqboard_task_execute

## 在做什么
...

## Workflow 执行记录

**Workflow Run ID**: `wf-abc123`
**状态**: ✅ 已完成
**开始时间**: 2026-09-19 15:30
**完成时间**: 2026-09-19 16:45

### 阶段执行详情

#### ✅ 阶段 1：需求分析
- Sub-agent: `sa-001`
- 时长: 5分钟
- 输出: [查看详情](#stage1-output)

#### ✅ 阶段 2：方案设计
- Sub-agent: `sa-002`
- 时长: 8分钟
- 输出: [查看详情](#stage2-output)

...
```

---

## 5. 实现要点

### 5.1 Workflow 脚本生成

**关键点**：
1. 根据 `resumeFrom` 跳过已完成阶段
2. 阶段间传递上下文（通过变量）
3. 错误时提前返回

**示例**：
```javascript
// 阶段3依赖阶段1和2的结果
const stage3 = await ctx.subagent({
  description: '阶段3：代码实现',
  prompt: `
    需求分析：${JSON.stringify(stage1.result)}
    设计方案：${JSON.stringify(stage2.result)}
    
    请实现核心代码...
  `
});
```

### 5.2 失败处理

**DSH Workflow 自动处理**：
- 任一阶段失败 → 整个 workflow 返回错误
- 不需要手动 try-catch

**我们只需**：
```typescript
if (!result.result.success) {
  // 记录失败阶段
  const failedStage = result.result.stages.find(s => s.error);
  
  // 建议从失败阶段恢复
  return {
    success: false,
    message: `阶段${failedStage.stage}失败`,
    next_step: `使用 resume_from=${failedStage.stage} 重试`
  };
}
```

### 5.3 阶段定义模板

```typescript
const STAGE_TEMPLATES = {
  backend: [
    { stage: 1, name: '需求分析', prompt: '...' },
    { stage: 2, name: '方案设计', prompt: '...' },
    { stage: 3, name: '代码实现', prompt: '...' },
    { stage: 4, name: '单元测试', prompt: '...' },
    { stage: 5, name: '集成测试', prompt: '...' },
    { stage: 6, name: '文档更新', prompt: '...' }
  ],
  doc: [
    { stage: 1, name: '需求分析', prompt: '...' },
    { stage: 2, name: '内容规划', prompt: '...' },
    { stage: 3, name: '编写文档', prompt: '...' },
    { stage: 4, name: '审校', prompt: '...' }
  ],
  // ... 其他类型
};
```

---

## 6. 实施步骤（重新规划）

### 第1步：创建工具骨架（0.3天）
- ✅ 更简单：只需定义工具 schema
- ✅ 不需要复杂的循环逻辑

### 第2步：实现阶段定义生成（0.5天）
- 定义阶段模板
- 根据 task.side 选择模板
- 生成阶段 prompt

### 第3步：实现 Workflow 脚本生成（1天）
- **核心工作**：生成 JavaScript 字符串
- 支持阶段跳过（resumeFrom）
- 阶段间上下文传递

### 第4步：实现 updateTaskCard（0.5天）
- 解析 workflow 结果
- 更新 Markdown（添加执行记录节）

### 第5步：集成和测试（1天）
- 集成各组件
- 单元测试
- E2E 测试

**新总计：约 3.3 天**（比原方案节省 1.2 天！）

---

## 7. 风险与应对

### 风险1：Workflow 脚本生成复杂
- **应对**：先支持最简单的线性流程，后续再优化

### 风险2：Workflow 工具不稳定
- **应对**：实现降级方案（fallback 到自己循环调用）

### 风险3：调试困难（生成的脚本）
- **应对**：添加详细日志，保存生成的脚本到文件

---

## 8. 代码结构

```
packages/pages/dsh-pmboard/src/tools/TaskExecuteTool/
├── TaskExecuteTool.ts           # 工具定义
├── generate-stages.ts           # 阶段定义生成
├── generate-workflow-script.ts  # Workflow 脚本生成（核心）
├── update-task-card.ts          # 任务卡更新
├── stage-templates.ts           # 阶段模板库
└── types.ts                     # 类型定义
```

---

## 9. 验收标准

✅ `npx vitest run tests/reqboard-task-execute.test.ts` 通过  
✅ 能生成正确的 Workflow 脚本  
✅ Workflow 执行成功并返回结果  
✅ 任务卡正确更新执行记录  
✅ 失败时能从断点恢复

---

## 10. 示例：生成的 Workflow 脚本

```javascript
// === Workflow Script for t-62e62f ===
// 任务：实现 reqboard_task_execute

const results = [];

// 阶段 1：需求分析
const stage1 = await ctx.subagent({
  description: '阶段1：需求分析',
  prompt: `
    任务：实现 reqboard_task_execute
    
    请分析：
    1. 该工具的核心功能是什么
    2. 验收标准：npx vitest run tests/reqboard-task-execute.test.ts 通过
    3. 技术难点和风险
    
    输出JSON：{ objective, risks, acceptance }
  `
});
results.push({ stage: 1, name: '需求分析', output: stage1 });

// 阶段 2：方案设计
const stage2 = await ctx.subagent({
  description: '阶段2：方案设计',
  prompt: `
    基于需求分析：${JSON.stringify(stage1.output)}
    
    设计：
    1. 工具 schema（输入输出）
    2. 核心函数（generateWorkflowScript / updateTaskCard）
    3. 数据流
    
    输出JSON：{ schema, functions, dataFlow }
  `
});
results.push({ stage: 2, name: '方案设计', output: stage2 });

// 阶段 3-6 类似...

return {
  success: true,
  stages: results,
  summary: `完成 ${results.length} 个阶段`
};
```

---

## 11. 后续优化

- 支持阶段并行执行（P1）
- 支持动态阶段数（P2）
- Workflow 可视化（前端，P1）
- 阶段模板可配置（P2）

---

## 12. 与原方案对比

| 维度 | 原方案（循环调用） | 新方案（DSH Workflow） |
|------|------------------|----------------------|
| 实现复杂度 | 高（手动管理状态） | 中（脚本生成） |
| 代码量 | ~500行 | ~200行 |
| 工期 | 4.5天 | 3.3天 |
| 可维护性 | 中 | 高（标准化） |
| 可扩展性 | 中 | 高（脚本灵活） |
| 错误处理 | 需手动实现 | DSH 自动处理 |
| 可视化 | 需自己做 | DSH 自带 |

**结论**：新方案在所有维度都优于原方案！
