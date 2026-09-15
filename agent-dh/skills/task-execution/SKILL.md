---
name: task-execution
description: 任务执行 SOP - 读取任务卡作为执行指令，自足完成任务
whenToUse: 当前窗口有进行中的任务时（reqboard_task_detail 显示 in_progress 任务）
---

# 任务执行 SOP

## 核心理念

**任务卡 = 自足执行指令**

每个任务包含：
- `title`: 要做什么（如"实现用户登录 API"）
- `description`: 怎么做（详细步骤）
- `context`: 需求背景（为什么做）
- `acceptance`: 验收标准（怎么算完成）
- `phase`: 阶段（implement/test/review）
- `side`: 端侧（frontend/backend/fullstack）

## 执行流程

### 1. 读取任务（自动触发）

当前窗口有 `in_progress` 任务时，SystemPrompt 自动注入：

```
【任务执行中】
当前任务：{task.title}

任务说明：
{task.description}

需求背景：
{task.context}

验收标准：
{task.acceptance}

阶段：{task.phase} | 端侧：{task.side}

---
请按照任务说明执行，完成后推进到下一阶段。
```

### 2. 执行任务

根据 `phase` 和 `side` 决定执行内容：

#### phase=implement, side=backend
- 实现接口代码
- 运行单元测试
- 提交代码

#### phase=implement, side=frontend
- 实现页面/组件
- 本地测试
- 提交代码

#### phase=test
- 运行测试用例
- 记录测试结果
- 生成测试报告

#### phase=review
- 自查代码
- 准备 review 材料

### 3. 推进任务状态

完成当前阶段后，调用 `reqboard_task_move` 推进：

```typescript
// 开发完成 → 联调
reqboard_task_move({
  task_id: 't-xxx',
  to: 'integrating',
  reason: '后端接口已实现并通过单测'
})

// 联调完成 → 测试
reqboard_task_move({
  task_id: 't-xxx',
  to: 'testing',
  reason: '前后端联调通过'
})

// 测试完成 → Review
reqboard_task_move({
  task_id: 't-xxx',
  to: 'in_review',
  reason: '测试用例全部通过'
})
```

### 4. 检查任务完成

所有任务完成后，需求自动推进到 `accepting`（验收阶段）。

## 关键工具

- `reqboard_task_detail`: 查看当前任务
- `reqboard_task_move`: 推进任务状态
- `reqboard_overview`: 查看整体进度

## 示例：完整任务卡

```json
{
  "title": "实现用户登录 API",
  "description": "创建 POST /api/auth/login 接口\n- 接收 username 和 password\n- 验证用户凭证\n- 返回 JWT token\n- 记录登录日志\n\n文件位置：src/routes/auth.ts",
  "context": "需求：用户登录功能（REQ-abc123）\n背景：新用户系统需要基础的登录认证",
  "acceptance": "- [ ] 接口返回正确的 JWT token\n- [ ] 错误密码返回 401\n- [ ] 单测覆盖率 > 80%\n- [ ] 登录日志写入数据库",
  "phase": "implement",
  "side": "backend"
}
```

Agent 读取后就知道：
1. 要做什么：实现登录 API
2. 怎么做：接收参数、验证、返回 token、记录日志
3. 文件在哪：src/routes/auth.ts
4. 怎么验证：4 个验收标准

## 最佳实践

### 任务拆分要点

1. **自足性**：description 要详细到 agent 不需要问人
2. **可验证**：acceptance 要具体（跑什么命令、看到什么结果）
3. **适当粒度**：1-2小时能完成
4. **明确依赖**：dependsOn 列清楚

### description 模板

```
实现 XXX 功能

步骤：
1. 修改文件 A
2. 新增文件 B
3. 运行测试：npm test xxx

注意事项：
- 遵循项目代码规范
- 处理边界情况 X
```

### acceptance 模板

```
- [ ] 功能测试通过
- [ ] 单测覆盖率 > 80%
- [ ] 代码符合规范
- [ ] 无编译错误
```

## 与 SystemPrompt 的集成

需要在 pmboard 的 capture.ts 中增加任务执行段：

```typescript
// 当窗口有 in_progress 任务时注入
if (currentTask && currentTask.status === 'in_progress') {
  return `
【任务执行中】
任务：${currentTask.title}

${currentTask.description}

背景：${currentTask.context}

验收：${currentTask.acceptance}
  `
}
```
