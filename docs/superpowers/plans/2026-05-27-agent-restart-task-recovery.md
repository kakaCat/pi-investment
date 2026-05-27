# Agent 重启后任务恢复功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 agent 重启后自动恢复任务状态并继续执行，无需用户手动输入

**Architecture:** 扩展现有的 `.restart/context.json` 机制，在重启时保存 TaskManager 和 BackgroundTaskManager 的状态，重启后恢复并自动触发 agent 循环

**Tech Stack:** TypeScript, Node.js, pi-coding-agent SDK

---

## 文件结构

### 需要修改的文件

1. **src/infrastructure/tools/agent/task-tools.ts**
   - 新增 `getTaskManager()` 导出函数

2. **src/core/task/task-manager.ts**
   - 新增 `getAllTasks()` 方法
   - 新增 `restoreTasks()` 方法

3. **src/core/task/background-task-manager.ts**
   - 新增 `getRunningTasks()` 方法
   - 新增 `restoreInterruptedTasks()` 方法

4. **src/infrastructure/tools/agent/restart-agent-tool.ts**
   - 新增 `collectTaskStates()` 函数
   - 修改 `execute()` 函数，调用 `collectTaskStates()`
   - 修改 `initRestartAgentTool()` 函数签名

5. **src/api/index.ts**
   - 扩展 `RestartContext` 接口
   - 新增 `restoreTasksIntoManagers()` 函数
   - 新增 `triggerAgentLoop()` 函数
   - 修改 `restoreConversationIntoSession()` 函数
   - 修改 `main()` 函数执行顺序

### 测试文件

- 手动测试（4个场景）

---

## Task 1: 添加 getTaskManager 导出函数

**Files:**
- Modify: `src/infrastructure/tools/agent/task-tools.ts:10-15`

- [ ] **Step 1: 在 task-tools.ts 中添加 getTaskManager 函数**

在 `getBackgroundManager()` 函数后面添加：

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

- [ ] **Step 2: 验证导出**

检查文件确保函数已添加且格式正确。

- [ ] **Step 3: Commit**

```bash
git add src/infrastructure/tools/agent/task-tools.ts
git commit -m "feat: add getTaskManager export function for restart recovery"
```

---

## Task 2: 添加 TaskManager 恢复方法

**Files:**
- Modify: `src/core/task/task-manager.ts:189-210`

- [ ] **Step 1: 添加 getAllTasks 方法**

在 `listAll()` 方法后面添加：

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
```

- [ ] **Step 2: 添加 restoreTasks 方法**

在 `getAllTasks()` 方法后面添加：

```typescript
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

- [ ] **Step 3: 验证方法**

检查文件确保两个方法已添加且格式正确。

- [ ] **Step 4: Commit**

```bash
git add src/core/task/task-manager.ts
git commit -m "feat: add getAllTasks and restoreTasks methods for restart recovery"
```

---

## Task 3: 添加 BackgroundTaskManager 恢复方法

**Files:**
- Modify: `src/core/task/background-task-manager.ts:233-267`

- [ ] **Step 1: 添加 getRunningTasks 方法**

在 `getRunningCount()` 方法后面添加：

```typescript
/**
 * 获取运行中的任务（用于重启时收集）
 */
getRunningTasks(): BackgroundTask[] {
  return Array.from(this.tasks.values()).filter(t => t.status === "running");
}
```

- [ ] **Step 2: 添加 restoreInterruptedTasks 方法**

在 `getRunningTasks()` 方法后面添加：

```typescript
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

- [ ] **Step 3: 验证方法**

检查文件确保两个方法已添加且格式正确。

- [ ] **Step 4: Commit**

```bash
git add src/core/task/background-task-manager.ts
git commit -m "feat: add getRunningTasks and restoreInterruptedTasks methods"
```

---

## Task 4: 修改 restart-agent-tool.ts 收集任务状态

**Files:**
- Modify: `src/infrastructure/tools/agent/restart-agent-tool.ts:54-58,99-111,244-275`

- [ ] **Step 1: 导入 TaskManager 和相关函数**

在文件顶部的 import 区域添加：

```typescript
import { getTaskManager, getBackgroundManager } from "../index.js";
import type { Task } from "../../../core/task/task-manager.js";
```

- [ ] **Step 2: 添加 collectTaskStates 函数**

在 `buildRestartContext()` 函数之前添加：

```typescript
/**
 * 收集任务状态（用于重启时保存）
 */
function collectTaskStates(): {
  tasks: { pending: Task[]; inProgress: Task[]; completed: Task[] };
  backgroundTasks: { interrupted: Array<{
    id: string;
    taskId: number;
    toolName: string;
    params: any;
    startTime: number;
    reason: "restart";
  }> };
} {
  try {
    const taskManager = getTaskManager();
    const backgroundTaskManager = getBackgroundManager();
    
    // 从 TaskManager 收集任务
    const allTasks = taskManager.getAllTasks();
    const tasks = {
      pending: allTasks.filter(t => t.status === "pending"),
      inProgress: allTasks.filter(t => t.status === "in_progress"),
      completed: allTasks.filter(t => t.status === "completed").slice(-10) // 最近10个
    };
    
    // 从 BackgroundTaskManager 收集运行中的任务
    const runningTasks = backgroundTaskManager.getRunningTasks();
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
  } catch (error) {
    // 如果任务管理器未初始化，返回空状态
    console.warn("[restart] Failed to collect task states:", error);
    return {
      tasks: { pending: [], inProgress: [], completed: [] },
      backgroundTasks: { interrupted: [] }
    };
  }
}
```

- [ ] **Step 3: 修改 buildRestartContext 函数签名**

找到 `buildRestartContext` 函数定义（约第99行），修改参数类型：

```typescript
export function buildRestartContext(input: BuildRestartContextInput & {
  tasks?: { pending: Task[]; inProgress: Task[]; completed: Task[] };
  backgroundTasks?: { interrupted: Array<any> };
}) {
  return {
    timestamp: new Date().toISOString(),
    cwd: input.cwd,
    reason: "user_requested_restart",
    prevSessionKey: input.prevSessionKey,
    sdkSessionFile: input.sdkSessionFile,
    sdkSessionId: input.sdkSessionId,
    conversationMessageCount: input.conversationMessages.length,
    messages: input.conversationMessages.slice(-50),
    env: input.env,
    tasks: input.tasks,
    backgroundTasks: input.backgroundTasks,
  };
}
```

- [ ] **Step 4: 修改 execute 函数调用 collectTaskStates**

在 `execute` 函数中，找到 `buildRestartContext` 调用（约第258行），在调用前添加：

```typescript
// 收集任务状态
const taskStates = collectTaskStates();

const context = buildRestartContext({
  cwd: process.cwd(),
  prevSessionKey,
  conversationMessages,
  sdkSessionFile: currentSession.sessionFile,
  sdkSessionId: currentSession.sessionId,
  env: {
    NODE_ENV: process.env.NODE_ENV || "development",
    BACKGROUND_MODE: process.env.BACKGROUND_MODE || "false",
  },
  tasks: taskStates.tasks,
  backgroundTasks: taskStates.backgroundTasks,
});
```

- [ ] **Step 5: 验证修改**

检查文件确保所有修改已正确应用。

- [ ] **Step 6: Commit**

```bash
git add src/infrastructure/tools/agent/restart-agent-tool.ts
git commit -m "feat: collect task states during restart"
```

---

(继续下一部分...)

## Task 5: 修改 api/index.ts 添加恢复逻辑（第1部分：扩展接口和新增函数）

**Files:**
- Modify: `src/api/index.ts:34-89`

- [ ] **Step 1: 扩展 RestartContext 接口**

找到 `RestartContext` 接口定义（约第40行），在 `env` 字段后添加：

```typescript
interface RestartContext {
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
    pending: Task[];
    inProgress: Task[];
    completed: Task[];
  };
  backgroundTasks?: {
    interrupted: Array<{
      id: string;
      taskId: number;
      toolName: string;
      params: any;
      startTime: number;
      reason: string;
    }>;
  };
}
```

- [ ] **Step 2: 添加必要的 import**

在文件顶部的 import 区域添加：

```typescript
import { getTaskManager, getBackgroundManager } from "../infrastructure/tools/index.js";
import type { TaskManager } from "../core/task/task-manager.js";
import type { BackgroundTaskManager } from "../core/task/background-task-manager.js";
```

- [ ] **Step 3: 添加 restoreTasksIntoManagers 函数**

在 `checkRestartContext()` 函数之前添加：

```typescript
/**
 * 恢复任务状态到管理器中
 */
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

- [ ] **Step 4: 添加 triggerAgentLoop 函数**

在 `restoreTasksIntoManagers()` 函数后添加：

```typescript
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

- [ ] **Step 5: 验证修改**

检查文件确保接口扩展和两个新函数已正确添加。

- [ ] **Step 6: Commit**

```bash
git add src/api/index.ts
git commit -m "feat: add task restoration functions in api/index.ts"
```

---

## Task 6: 修改 api/index.ts 添加恢复逻辑（第2部分：修改 restoreConversationIntoSession）

**Files:**
- Modify: `src/api/index.ts:94-141`

- [ ] **Step 1: 修改 restoreConversationIntoSession 函数签名**

找到 `restoreConversationIntoSession` 函数定义（约第94行），修改为：

```typescript
function restoreConversationIntoSession(
  session: AgentSession,
  taskCounts: { taskCount: number; backgroundCount: number }
): void {
```

- [ ] **Step 2: 在函数开头添加任务触发逻辑**

在函数开头，`if (!restartData?.messages...)` 判断中修改为：

```typescript
if (!restartData?.messages || restartData.messages.length === 0) {
  // 即使没有对话历史，如果有任务也要触发
  if (taskCounts.taskCount > 0 || taskCounts.backgroundCount > 0) {
    triggerAgentLoop(session);
  }
  return;
}
```

- [ ] **Step 3: 修改上下文提示消息构建逻辑**

找到构建 `contextPrompt` 的部分（约第126行），替换为：

```typescript
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
```

- [ ] **Step 4: 在函数末尾添加自动触发调用**

在 `restartData = null;` 之后添加：

```typescript
// 总是自动触发 agent 循环
triggerAgentLoop(session);
```

- [ ] **Step 5: 验证修改**

检查文件确保 `restoreConversationIntoSession` 函数已正确修改。

- [ ] **Step 6: Commit**

```bash
git add src/api/index.ts
git commit -m "feat: enhance restoreConversationIntoSession with task info and auto-trigger"
```

---

## Task 7: 修改 api/index.ts 添加恢复逻辑（第3部分：修改 main 函数）

**Files:**
- Modify: `src/api/index.ts:150-200`

- [ ] **Step 1: 在 main 函数中添加任务恢复逻辑**

找到 `main` 函数中创建 session 的部分（约第186行），在 `restoreConversationIntoSession(session)` 调用之前添加：

```typescript
// 恢复任务状态（在 session 创建后，工具已初始化）
let taskCounts = { taskCount: 0, backgroundCount: 0 };
if (restartData) {
  const sessionDir = logger.getSessionDir();
  if (sessionDir) {
    try {
      const taskManager = getTaskManager();
      const backgroundTaskManager = getBackgroundManager();
      taskCounts = restoreTasksIntoManagers(restartData, taskManager, backgroundTaskManager);
    } catch (error) {
      console.warn("⚠️  任务恢复失败:", error instanceof Error ? error.message : String(error));
    }
  }
}
```

- [ ] **Step 2: 修改 restoreConversationIntoSession 调用**

找到 `restoreConversationIntoSession(session)` 调用（约第195行），修改为：

```typescript
if (restartData) {
  restoreConversationIntoSession(session, taskCounts);
}
```

- [ ] **Step 3: 验证修改**

检查文件确保 main 函数已正确修改。

- [ ] **Step 4: 运行 TypeScript 编译检查**

```bash
npm run build
```

预期：编译成功，无类型错误

- [ ] **Step 5: Commit**

```bash
git add src/api/index.ts
git commit -m "feat: integrate task restoration into main startup flow"
```

---

## Task 8: 手动测试场景 1 - 有未完成任务的重启

**Files:**
- Test: Manual testing

- [ ] **Step 1: 启动 agent**

```bash
npm run dev
```

- [ ] **Step 2: 创建测试任务**

在 agent 中执行：
```
创建3个任务：
1. pending 任务：分析贵州茅台
2. in_progress 任务：获取市场数据
3. completed 任务：生成报告
```

- [ ] **Step 3: 启动后台任务**

在 agent 中执行：
```
启动一个后台任务获取股票数据
```

- [ ] **Step 4: 调用 restart_agent**

在 agent 中执行：
```
restart_agent
```

- [ ] **Step 5: 验证重启后的行为**

预期结果：
- ✅ 控制台显示"已恢复 2 个未完成任务"
- ✅ 控制台显示"已标记 1 个后台任务为失败"
- ✅ Agent 自动开始执行，无需手动输入
- ✅ Agent 提到任务列表并开始处理

- [ ] **Step 6: 检查任务状态**

在 agent 中执行：
```
task_list
```

预期：显示 2 个未完成任务（pending + in_progress）

---

## Task 9: 手动测试场景 2 - 没有未完成任务的重启

**Files:**
- Test: Manual testing

- [ ] **Step 1: 启动 agent**

```bash
npm run dev
```

- [ ] **Step 2: 发送消息**

在 agent 中输入：
```
分析一下贵州茅台的投资价值
```

- [ ] **Step 3: 在 agent 回复中途调用 restart_agent**

等待 agent 开始回复后，立即执行：
```
restart_agent
```

- [ ] **Step 4: 验证重启后的行为**

预期结果：
- ✅ 控制台显示"已恢复对话消息"
- ✅ 没有显示任务恢复信息（因为没有任务）
- ✅ Agent 自动继续回复用户的问题
- ✅ 无需手动输入

---

## Task 10: 手动测试场景 3 - 任务文件损坏

**Files:**
- Test: Manual testing

- [ ] **Step 1: 启动 agent 并创建任务**

```bash
npm run dev
```

创建 3 个任务。

- [ ] **Step 2: 手动损坏一个任务文件**

```bash
# 找到 session 目录
SESSION_DIR=$(ls -t .pi-invest/sessions/ | head -1)
# 损坏第二个任务文件
echo "invalid json" > .pi-invest/sessions/$SESSION_DIR/tasks/task_2.json
```

- [ ] **Step 3: 调用 restart_agent**

在 agent 中执行：
```
restart_agent
```

- [ ] **Step 4: 验证重启后的行为**

预期结果：
- ✅ 控制台显示警告"Failed to read task file task_2.json"
- ✅ 恢复了其他 2 个正常任务
- ✅ Agent 正常启动，没有崩溃
- ✅ Agent 自动开始工作

---

## Task 11: 手动测试场景 4 - Session 目录不存在

**Files:**
- Test: Manual testing

- [ ] **Step 1: 启动 agent**

```bash
npm run dev
```

- [ ] **Step 2: 发送消息**

在 agent 中输入：
```
你好
```

- [ ] **Step 3: 删除 session 目录**

```bash
# 找到 session 目录
SESSION_DIR=$(ls -t .pi-invest/sessions/ | head -1)
# 删除 tasks 目录
rm -rf .pi-invest/sessions/$SESSION_DIR/tasks
```

- [ ] **Step 4: 调用 restart_agent**

在 agent 中执行：
```
restart_agent
```

- [ ] **Step 5: 验证重启后的行为**

预期结果：
- ✅ 没有显示任务恢复信息
- ✅ Agent 正常启动，没有崩溃
- ✅ Agent 自动继续对话
- ✅ 无需手动输入

---

## Task 12: 更新文档

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: 在 CLAUDE.md 中添加重启功能说明**

找到 "Agent 工具系统" 部分，在 "Agent 元工具" 小节中更新 `restart_agent` 的说明：

```markdown
### Agent 元工具

系统级操作工具：
- `restart_agent` — 重启 agent 进程（TypeScript + Python bridge）
  - 保存并恢复对话历史
  - **新增**：保存并恢复任务状态（TaskManager + BackgroundTaskManager）
  - **新增**：自动触发 agent 循环，无需手动输入
  - 重启后自动恢复未完成任务（pending + in_progress）
  - 中断的后台任务标记为失败，agent 可选择重试
  - 适用场景：新工具注册、Python bridge 异常、性能下降
```

- [ ] **Step 2: 验证文档**

检查 CLAUDE.md 确保说明已正确添加。

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update restart_agent tool description with task recovery"
```

---

## Task 13: 最终验证和清理

**Files:**
- All modified files

- [ ] **Step 1: 运行完整编译**

```bash
npm run build
```

预期：编译成功，无错误

- [ ] **Step 2: 运行测试套件**

```bash
npm test
```

预期：所有测试通过

- [ ] **Step 3: 检查 git 状态**

```bash
git status
```

预期：所有修改已提交

- [ ] **Step 4: 查看提交历史**

```bash
git log --oneline -13
```

预期：看到 13 个新提交（对应 13 个任务）

- [ ] **Step 5: 创建功能总结提交**

```bash
git log --oneline HEAD~12..HEAD > /tmp/commits.txt
cat > /tmp/summary.txt << 'SUMMARY'
feat: implement agent restart task recovery

实现 agent 重启后自动恢复任务状态并继续执行的功能。

核心改动：
- TaskManager: 新增 getAllTasks() 和 restoreTasks() 方法
- BackgroundTaskManager: 新增 getRunningTasks() 和 restoreInterruptedTasks() 方法
- restart-agent-tool: 收集任务状态并保存到 .restart/context.json
- api/index.ts: 恢复任务状态并自动触发 agent 循环

功能特性：
- 重启后自动恢复未完成任务（pending + in_progress）
- 中断的后台任务标记为失败
- 自动触发 agent 循环，无需用户手动输入
- 错误处理：任务文件损坏、session 目录不存在等边界情况

测试场景：
- ✅ 有未完成任务的重启
- ✅ 没有未完成任务的重启
- ✅ 任务文件损坏
- ✅ Session 目录不存在

相关文档：
- 设计文档: docs/superpowers/specs/2026-05-27-agent-restart-task-recovery-design.md
- 实现计划: docs/superpowers/plans/2026-05-27-agent-restart-task-recovery.md

Commits:
SUMMARY
cat /tmp/commits.txt >> /tmp/summary.txt

git commit --allow-empty -F /tmp/summary.txt
```

- [ ] **Step 6: 推送到远程（可选）**

如果需要推送到远程分支：
```bash
git push origin evolution/2026-05-27
```

---

## 完成检查清单

- [ ] 所有 13 个任务的步骤都已完成
- [ ] 编译成功，无类型错误
- [ ] 4 个测试场景全部通过
- [ ] 文档已更新
- [ ] 所有修改已提交到 git
- [ ] 功能符合设计规范

---

## 故障排查

### 问题 1: TaskManager not initialized 错误

**症状**: 重启时报错 "TaskManager not initialized"

**原因**: session 创建时 initTaskTools() 尚未调用

**解决**: 在 api/index.ts 的 main 函数中，确保在调用 restoreTasksIntoManagers 前 session 已创建

### 问题 2: session.sendMessage is not a function

**症状**: 自动触发失败，控制台显示警告

**原因**: session 对象没有 sendMessage 方法

**解决**: 这是预期的降级行为，agent 会在用户下次输入时看到提示

### 问题 3: 任务恢复后 ID 冲突

**症状**: 新创建的任务 ID 与恢复的任务 ID 重复

**原因**: restoreTasks 没有正确更新 nextId

**解决**: 检查 TaskManager.restoreTasks() 方法中的 nextId 更新逻辑

### 问题 4: 后台任务没有标记为失败

**症状**: 重启后后台任务状态不是 error

**原因**: restoreInterruptedTasks 没有正确添加到通知队列

**解决**: 检查 BackgroundTaskManager.restoreInterruptedTasks() 方法中的 notificationQueue.push() 调用
