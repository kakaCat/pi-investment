# Agent 重启后任务恢复功能设计

**日期**: 2026-05-27  
**状态**: 设计完成，待实现  
**作者**: Claude (Opus 4.7)

## 概述

实现 agent 重启后自动恢复任务状态并继续执行的功能，无需用户手动输入。

### 目标

- 重启后自动恢复 TaskManager 中的未完成任务（pending + in_progress）
- 重启后标记 BackgroundTaskManager 中被中断的后台任务为失败
- 自动触发 agent 循环，让 agent 继续执行任务或响应用户消息
- 用户无需手动输入任何内容

### 非目标

- 实时任务持久化（不是崩溃恢复，只是重启恢复）
- 恢复后台任务的执行状态（Worker 线程无法序列化）
- 跨 session 的任务迁移

## 架构设计

### 核心思路

扩展现有的 `.restart/context.json` 机制，在重启时保存任务状态，重启后恢复并自动触发 agent 循环。

### 数据流

```
restart_agent 工具执行
    ↓
收集任务状态（TaskManager + BackgroundTaskManager）
    ↓
序列化到 .restart/context.json
    ↓
进程重启
    ↓
checkRestartContext() 读取 context.json
    ↓
创建 session 和工具管理器
    ↓
restoreTasksIntoManagers() 恢复任务状态
    ↓
restoreConversationIntoSession() 恢复对话 + 注入提示
    ↓
自动触发 agent 循环（无论是否有未完成任务）
```

## 数据结构设计

### 扩展 RestartContext 接口

```typescript
interface RestartContext {
  // 现有字段
  timestamp: string;
  cwd: string;
  reason: string;
  prevSessionKey?: string;
  sdkSessionFile?: string;
  sdkSessionId?: string;
  conversationMessageCount?: number;
  messages?: ConversationMessage[];
  env: {
    NODE_ENV: string;
    BACKGROUND_MODE: string;
  };
  
  // 新增字段
  tasks?: {
    pending: Task[];      // 待执行的任务
    inProgress: Task[];   // 正在执行的任务
    completed: Task[];    // 已完成的任务（最近10个，用于上下文）
  };
  
  backgroundTasks?: {
    interrupted: Array<{
      id: string;
      taskId: number;
      toolName: string;
      params: any;
      startTime: number;
      reason: "restart";  // 中断原因
    }>;
  };
}
```

### 任务恢复策略

| 任务类型 | 恢复策略 | 说明 |
|---------|---------|------|
| pending 任务 | 完整恢复，保持 pending 状态 | 让 agent 按计划执行 |
| in_progress 任务 | 完整恢复，保持 in_progress 状态 | 让 agent 决定是继续还是重新开始 |
| completed 任务 | 可选保存最近 10 个 | 提供上下文参考，不影响执行 |
| background 任务 | 标记为 interrupted，状态为 error | 保存失败信息，让 agent 决定是否重试 |

## 核心组件改动

### 1. restart-agent-tool.ts

#### 新增函数：收集任务状态

```typescript
function collectTaskStates(
  taskManager: TaskManager,
  backgroundTaskManager: BackgroundTaskManager
): {
  tasks: { pending: Task[]; inProgress: Task[]; completed: Task[] };
  backgroundTasks: { interrupted: Array<{...}> };
} {
  // 从 TaskManager 收集任务
  const allTasks = taskManager.getAllTasks(); // 需要新增此方法
  const tasks = {
    pending: allTasks.filter(t => t.status === "pending"),
    inProgress: allTasks.filter(t => t.status === "in_progress"),
    completed: allTasks.filter(t => t.status === "completed").slice(-10) // 最近10个
  };
  
  // 从 BackgroundTaskManager 收集运行中的任务
  const runningTasks = backgroundTaskManager.getRunningTasks(); // 需要新增此方法
  const backgroundTasks = {
    interrupted: runningTasks.map(t => ({
      id: t.id,
      taskId: t.taskId,
      toolName: t.toolName,
      params: t.params,
      startTime: t.startTime,
      reason: "restart" as const
    }))
  };
  
  return { tasks, backgroundTasks };
}
```

#### 修改 execute 函数

在保存上下文时调用 `collectTaskStates()`：

```typescript
// 在 buildRestartContext 之前
const taskStates = collectTaskStates(taskManager, backgroundTaskManager);

const context = buildRestartContext({
  // ... 现有参数
  tasks: taskStates.tasks,
  backgroundTasks: taskStates.backgroundTasks,
});
```

**注意**：需要在 `initRestartAgentTool()` 中传入 taskManager 和 backgroundTaskManager 实例。

### 2. task-tools.ts

#### 新增导出函数

```typescript
/**
 * 获取 TaskManager 实例（用于重启时访问）
 */
export function getTaskManager(): TaskManager {
  if (!taskManager) {
    throw new Error("TaskManager not initialized. Call initTaskTools() first.");
  }
  return taskManager;
}
```

### 3. TaskManager (task-manager.ts)

#### 新增方法

```typescript
/**
 * 获取所有任务（用于重启时收集）
 */
getAllTasks(): Task[] {
  if (!existsSync(this.dir)) return [];
  const files = readdirSync(this.dir)
    .filter(f => f.startsWith("task_") && f.endsWith(".json"));
  return files.map(f => {
    try {
      return JSON.parse(readFileSync(join(this.dir, f), "utf-8"));
    } catch (error) {
      console.warn(`Warning: Failed to read task file ${f}:`, error);
      return null;
    }
  }).filter(t => t !== null) as Task[];
}

/**
 * 批量恢复任务（用于重启后恢复）
 */
restoreTasks(tasks: Task[]): void {
  for (const task of tasks) {
    try {
      this.save(task);
      if (task.id >= this.nextId) {
        this.nextId = task.id + 1;
      }
    } catch (error) {
      console.warn(`Warning: Failed to restore task #${task.id}:`, error);
    }
  }
}
```

### 4. BackgroundTaskManager (background-task-manager.ts)

#### 新增方法

```typescript
/**
 * 获取运行中的任务（用于重启时收集）
 */
getRunningTasks(): BackgroundTask[] {
  return Array.from(this.tasks.values()).filter(t => t.status === "running");
}

/**
 * 恢复中断的任务为失败状态（用于重启后恢复）
 */
restoreInterruptedTasks(interrupted: Array<{
  id: string;
  taskId: number;
  toolName: string;
  params: any;
  startTime: number;
  reason: string;
}>): void {
  for (const task of interrupted) {
    const failedTask: BackgroundTask = {
      id: task.id,
      taskId: task.taskId,
      status: "error",
      toolName: task.toolName,
      params: task.params,
      startTime: task.startTime,
      error: `Task interrupted by agent restart (reason: ${task.reason})`,
      result: undefined
    };
    
    this.tasks.set(task.id, failedTask);
    
    // 添加到通知队列，让 agent 知道这些任务失败了
    this.notificationQueue.push({
      taskId: task.taskId,
      backgroundId: task.id,
      status: "error",
      result: `Task interrupted by agent restart`,
      duration: Date.now() - task.startTime
    });
    
    // 记录事件
    this.logEvent("background_task.restored_as_failed", {
      background_id: task.id,
      task_id: task.taskId,
      tool_name: task.toolName,
      reason: task.reason
    });
  }
}
```

### 5. api/index.ts

#### 新增函数：恢复任务状态

```typescript
function restoreTasksIntoManagers(
  restartData: RestartContext,
  taskManager: TaskManager,
  backgroundTaskManager: BackgroundTaskManager
): { taskCount: number; backgroundCount: number } {
  let taskCount = 0;
  let backgroundCount = 0;
  
  // 恢复 TaskManager 任务
  if (restartData.tasks) {
    const allTasks = [
      ...restartData.tasks.pending,
      ...restartData.tasks.inProgress,
      ...(restartData.tasks.completed || [])
    ];
    
    if (allTasks.length > 0) {
      taskManager.restoreTasks(allTasks);
      taskCount = restartData.tasks.pending.length + restartData.tasks.inProgress.length;
      console.log(`📋 已恢复 ${taskCount} 个未完成任务 (pending: ${restartData.tasks.pending.length}, in_progress: ${restartData.tasks.inProgress.length})`);
    }
  }
  
  // 恢复 BackgroundTaskManager 中断任务
  if (restartData.backgroundTasks?.interrupted && restartData.backgroundTasks.interrupted.length > 0) {
    backgroundTaskManager.restoreInterruptedTasks(restartData.backgroundTasks.interrupted);
    backgroundCount = restartData.backgroundTasks.interrupted.length;
    console.log(`⚠️  已标记 ${backgroundCount} 个后台任务为失败（被重启中断）`);
  }
  
  return { taskCount, backgroundCount };
}
```

#### 修改 restoreConversationIntoSession 函数

增强注入的提示消息，包含任务信息：

```typescript
function restoreConversationIntoSession(
  session: AgentSession,
  taskCounts: { taskCount: number; backgroundCount: number }
): void {
  if (!restartData?.messages || restartData.messages.length === 0) {
    // 即使没有对话历史，如果有任务也要触发
    if (taskCounts.taskCount > 0 || taskCounts.backgroundCount > 0) {
      triggerAgentLoop(session);
    }
    return;
  }
  
  // ... 现有的对话恢复逻辑 ...
  
  if (injected > 0) {
    console.log(`📋 已恢复 ${injected} 条对话消息（共 ${messages.length} 条）\n`);
    
    // 构建上下文提示消息
    let contextPrompt = `Agent 已重启完成，新工具已加载。

上下文已恢复：
- 最后的用户请求：${lastUserMessage.slice(0, 200)}${lastUserMessage.length > 200 ? '...' : ''}
- 你之前的回复：${lastAssistantMessage.slice(0, 200)}${lastAssistantMessage.length > 200 ? '...' : ''}`;

    // 如果有任务，添加任务信息
    if (taskCounts.taskCount > 0 || taskCounts.backgroundCount > 0) {
      contextPrompt += `

任务状态已恢复：`;
      
      if (restartData.tasks) {
        if (restartData.tasks.pending.length > 0) {
          contextPrompt += `\n- 待执行任务：${restartData.tasks.pending.length} 个`;
        }
        if (restartData.tasks.inProgress.length > 0) {
          contextPrompt += `\n- 进行中任务：${restartData.tasks.inProgress.length} 个`;
        }
      }
      
      if (taskCounts.backgroundCount > 0) {
        contextPrompt += `\n- 中断的后台任务：${taskCounts.backgroundCount} 个（已标记为失败）`;
      }
      
      contextPrompt += `

请使用 task_list 查看所有任务，然后继续执行未完成的工作。优先处理 in_progress 状态的任务。`;
    } else {
      contextPrompt += `

请继续完成之前的任务。如果任务已完成，请总结结果。`;
    }
    
    addMessage(session, createUserMessage(contextPrompt));
    console.log(`💡 已添加上下文提示，Agent 将自动继续之前的工作\n`);
  }
  
  // 清理上下文文件
  try { unlinkSync(RESTART_CONTEXT); } catch { /* ignore */ }
  restartData = null;
  
  // 总是自动触发 agent 循环
  triggerAgentLoop(session);
}

/**
 * 自动触发 agent 循环
 */
function triggerAgentLoop(session: AgentSession): void {
  setImmediate(() => {
    try {
      // 触发 agent 响应（发送空消息）
      if (typeof session.sendMessage === 'function') {
        session.sendMessage("");
      } else {
        console.warn("⚠️  session.sendMessage 不可用，无法自动触发 agent 循环");
      }
    } catch (error) {
      console.warn("⚠️  自动触发 agent 循环失败:", error);
    }
  });
}
```

#### 修改 main 函数执行顺序

```typescript
async function main() {
  // ... 现有的初始化代码 ...
  
  // 1. 检查重启上下文
  checkRestartContext();
  
  // 2. 初始化 logger
  logger.initSession(restartData?.prevSessionKey);
  console.log(`📋 Session: ${logger.getSessionKey()}\n`);
  
  // 3. 创建 session（会初始化 TaskManager 和 BackgroundTaskManager）
  const session = USE_BACKGROUND_MODE
    ? await getSessionBackground()
    : await getSessionNormal(/* ... */);
  
  // 4. 恢复任务状态（在 session 创建后，工具已初始化）
  let taskCounts = { taskCount: 0, backgroundCount: 0 };
  if (restartData) {
    const sessionDir = logger.getSessionDir();
    if (sessionDir) {
      const taskManager = getTaskManager(); // 需要暴露 TaskManager 实例
      const backgroundTaskManager = getBackgroundManager();
      taskCounts = restoreTasksIntoManagers(restartData, taskManager, backgroundTaskManager);
    }
  }
  
  // 5. 恢复对话历史并自动触发
  if (restartData) {
    restoreConversationIntoSession(session, taskCounts);
  }
  
  // ... 其余代码 ...
}
```

## 任务存储路径

任务按 session 存储：
```
.pi-invest/sessions/{sessionKey}/tasks/task_1.json
.pi-invest/sessions/{sessionKey}/tasks/task_2.json
...
```

重启时：
1. 保存当前 session 的 `sessionKey`（已有）
2. 保存当前 session 的任务（从任务目录读取）
3. 恢复时使用相同的 sessionKey 和任务目录

## 错误处理

### 错误处理策略

1. **Session 目录不存在**
   - 如果重启后 `getSessionDir()` 返回 null，跳过任务恢复
   - 仍然自动触发 agent 循环，让 agent 继续对话

2. **任务文件损坏**
   - 单个任务文件损坏时，记录警告并跳过该任务
   - 继续恢复其他任务，不中断启动流程

3. **自动触发失败**
   - 如果 `session.sendMessage()` 不可用，记录警告
   - 降级为只注入提示消息，用户下次输入时 agent 会看到提示

4. **TaskManager 或 BackgroundTaskManager 未初始化**
   - 在 `initTaskTools()` 和 `initBackgroundManager()` 之后才能恢复任务
   - 调整恢复时机：先创建 session → 初始化工具 → 恢复任务

### 边界情况处理

1. **没有未完成任务**
   - 仍然自动触发 agent 循环
   - Agent 看到重启提示，继续响应用户的最后一条消息

2. **Session 目录为空**
   - 如果 `{sessionDir}/tasks/` 目录不存在或为空，跳过任务恢复
   - 仍然自动触发 agent 循环

3. **重复重启**
   - 每次重启都会覆盖 `.restart/context.json`
   - 恢复后立即删除 context.json，避免重复恢复

4. **Session 一致性**
   - 重启后使用相同的 sessionKey，确保任务目录一致
   - 通过保存的 sessionFile 或 sessionId 恢复 session

5. **任务 ID 冲突**
   - 恢复时更新 `TaskManager.nextId` 为最大 ID + 1
   - 确保新创建的任务不会与恢复的任务冲突

## 日志和监控

使用 observable-logger 记录以下事件：

1. **任务收集事件**（重启前）
   ```typescript
   logEvent("restart.tasks_collected", {
     pending_count: tasks.pending.length,
     in_progress_count: tasks.inProgress.length,
     completed_count: tasks.completed.length,
     background_interrupted_count: backgroundTasks.interrupted.length
   });
   ```

2. **任务恢复事件**（重启后）
   ```typescript
   logEvent("restart.tasks_restored", {
     task_count: taskCount,
     background_count: backgroundCount,
     session_key: logger.getSessionKey(),
     duration_ms: Date.now() - startTime
   });
   ```

3. **自动触发事件**
   ```typescript
   logEvent("restart.auto_trigger", {
     has_tasks: taskCount > 0,
     success: true
   });
   ```

## 测试场景

### 场景 1：有未完成任务的重启

1. 创建 3 个任务：1 个 pending，1 个 in_progress，1 个 completed
2. 启动 1 个后台任务（background_run）
3. 调用 `restart_agent`
4. 验证：
   - 重启后恢复 2 个未完成任务（pending + in_progress）
   - 后台任务标记为失败
   - Agent 自动开始执行任务

### 场景 2：没有未完成任务的重启

1. 所有任务都是 completed 状态
2. 用户发送消息："分析一下贵州茅台"
3. Agent 开始回复，但在回复中途调用 `restart_agent`
4. 验证：
   - 重启后没有恢复任务
   - Agent 自动继续回复用户的问题

### 场景 3：任务文件损坏

1. 创建 3 个任务
2. 手动损坏其中 1 个任务文件（写入非法 JSON）
3. 调用 `restart_agent`
4. 验证：
   - 重启后恢复 2 个正常任务
   - 记录警告日志，但不中断启动

### 场景 4：Session 目录不存在

1. 删除 session 目录
2. 调用 `restart_agent`
3. 验证：
   - 重启后跳过任务恢复
   - Agent 仍然自动触发，继续对话

## 实现顺序

1. **task-tools.ts 改动**（新增 getTaskManager 导出函数）
2. **TaskManager 改动**（新增 getAllTasks 和 restoreTasks 方法）
3. **BackgroundTaskManager 改动**（新增 getRunningTasks 和 restoreInterruptedTasks 方法）
4. **restart-agent-tool.ts 改动**（收集任务状态）
5. **api/index.ts 改动**（恢复任务状态和自动触发）
6. **测试验证**（手动测试 4 个场景）
7. **文档更新**（更新 CLAUDE.md 中的重启说明）

## 依赖关系

- 依赖现有的 `.restart/context.json` 机制
- 依赖 TaskManager 和 BackgroundTaskManager 的文件存储
- 依赖 observable-logger 的 session 管理
- 依赖 agent-loop.ts 的工具初始化流程

## 风险和缓解

| 风险 | 影响 | 缓解措施 |
|-----|------|---------|
| 任务文件过大导致 context.json 过大 | 启动变慢 | 只保存最近 10 个 completed 任务 |
| 自动触发失败导致 agent 不响应 | 用户需要手动输入 | 降级为只注入提示消息 |
| Session 不一致导致任务目录错误 | 任务恢复失败 | 验证 sessionKey 一致性，记录错误日志 |
| 后台任务参数包含敏感信息 | 安全风险 | 不记录敏感参数（如 API key） |

## 未来优化

1. **增量任务持久化**：实时保存任务状态，支持崩溃恢复
2. **任务优先级**：恢复时按优先级排序任务
3. **任务依赖图**：可视化任务依赖关系
4. **任务执行历史**：记录任务执行的完整历史
5. **跨 session 任务迁移**：支持将任务从一个 session 迁移到另一个 session
