# 异步任务执行系统

## 概述

基于 `s08_background_tasks.py` 的 BackgroundManager 设计，为 pi-investment 添加了异步并行执行投资工具的能力。

## 架构

```
Agent Loop (主线程)
    ↓
plan_task → task_create (批量创建任务)
    ↓
task_execute_async (启动后台任务)
    ↓
BackgroundTaskManager
    ├─ Worker 1: get_stock_info(600519)
    ├─ Worker 2: get_stock_info(000858)
    └─ Worker 3: calculate_technical_indicators(601318)
    ↓
Notification Queue → 下一轮 Agent Loop 自动注入
```

## 核心组件

### 1. BackgroundTaskManager
- 位置: `src/core/task/background-task-manager.ts`
- 功能: 管理后台任务执行、通知队列
- 使用 Worker 线程避免阻塞主线程

### 2. Tool Worker
- 位置: `src/core/task/tool-worker.ts`
- 功能: 在独立线程中执行投资工具调用
- 支持超时控制（默认 300 秒）

### 3. 新增工具

#### task_execute_async
并行执行多个投资工具调用：

```typescript
task_execute_async({
  executions: [
    {
      task_id: 1,
      tool_name: "get_stock_info",
      params: { symbol: "600519" }
    },
    {
      task_id: 2,
      tool_name: "calculate_technical_indicators",
      params: { symbol: "000858", period: "daily" }
    }
  ]
})
```

#### task_check_background
检查后台任务状态：

```typescript
// 检查特定任务
task_check_background({ background_id: "a1b2c3d4" })

// 列出所有后台任务
task_check_background({})
```

## 使用示例

### Agent 工作流

```
用户: "帮我分析 5 只股票：600519, 000858, 601318, 600036, 000333"

Agent 执行流程:
1. plan_task
   → 规划：获取 5 只股票的实时数据和技术指标

2. task_create
   → 创建 5 个任务

3. task_execute_async
   → 并行执行：
     - Task #1: get_stock_info(600519)
     - Task #2: get_stock_info(000858)
     - Task #3: get_stock_info(601318)
     - Task #4: get_stock_info(600036)
     - Task #5: get_stock_info(000333)

4. 继续其他工作...

5. 下一轮自动收到通知
   → 汇总分析 5 只股票的结果
```

## 通知机制

后台任务完成后，结果会在下一轮 Agent Loop 开始时自动注入：

```xml
<background-results>
[Task #1] completed (2s):
{"name": "贵州茅台", "price": 1680.5, ...}

[Task #2] completed (3s):
{"name": "五粮液", "price": 145.2, ...}
</background-results>
```

Agent 会自动确认：
```
Noted background results.
```

### 自动等待机制

**关键特性**：Agent Loop 会自动等待后台任务完成

- 如果有后台任务正在运行，Agent Loop 不会立即结束
- 每 2 秒检查一次后台任务状态
- 所有任务完成后，自动注入结果并继续执行
- 避免了任务还未完成就退出的问题

```typescript
// agent-loop.ts 中的实现
if (runningCount > 0) {
  console.log(`⏳ 等待 ${runningCount} 个后台任务完成...`);
  await new Promise(resolve => setTimeout(resolve, 2000));
  return agentLoop(messages);  // 递归继续
}
```

## 适用场景

✅ **适合并行执行**:
- 获取多只股票的实时数据
- 批量计算技术指标
- 并行查询财务数据
- 多个独立的市场数据获取

❌ **不适合并行**:
- 有依赖关系的串行任务
- 需要前一步结果的计算
- 需要事务一致性的操作

## 性能优势

- **真正并行**: 多个任务同时执行
- **不阻塞主线程**: Agent 可以继续其他工作
- **自动通知**: 无需轮询，结果自动注入
- **超时保护**: 防止任务无限运行

## 实现细节

### 初始化
在 `agent-loop.ts` 的 `getSession()` 中：
```typescript
initBackgroundManager();
```

### 通知注入
在 `agentLoop()` 开头：
```typescript
const notifications = bgManager.drainNotifications();
if (notifications.length > 0) {
  // 注入为系统消息
}
```

### Worker 执行
`tool-worker.ts` 调用 `callInvestTool()` 执行实际工具。

## 注意事项

1. **并发限制**: 建议控制同时运行的任务数（如最多 5 个）
2. **超时设置**: 默认 300 秒，可根据需要调整
3. **错误处理**: Worker 异常会被捕获并通知
4. **任务状态**: 执行时自动更新为 `in_progress`
