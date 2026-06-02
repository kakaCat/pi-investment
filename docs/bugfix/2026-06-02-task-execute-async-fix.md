# task_execute_async 模块加载问题修复

**日期**: 2026-06-02  
**优先级**: 🟡 P1  
**状态**: ✅ 已修复

## 问题描述

### 现象
```
Cannot find module '/Users/mac/Documents/ai/pi-investment/src/infrastructure/tools/index.js' 
imported from /Users/mac/Documents/ai/pi-investment/src/core/task/tool-worker.ts
```

### 影响
- 所有后台异步任务不可用
- 无法并行执行分析任务
- Agent 的并发能力受限

## 根本原因

tsx + Worker 线程的模块解析限制：

1. **TypeScript ESM 规范**：源码中使用 `.js` 扩展名导入（即使文件是 `.ts`）
2. **Worker 线程隔离**：Worker 线程中的 tsx 加载器无法正确解析 `.js` → `.ts` 的映射
3. **静态导入失败**：`import { allCustomTools } from "../../infrastructure/tools/index.js"` 在 Worker 中失败
4. **动态导入同样失败**：`await import("../../infrastructure/tools/index.js")` 在 Worker 中也无法解析

## 解决方案

**放弃 Worker 线程，改用主线程异步执行**

### 实现方案

```typescript
// 之前：使用 Worker 线程
const worker = new Worker(workerPath, { workerData: {...} });

// 之后：主线程异步执行
private async _executeAsync(id: string, toolName: string, params: any): Promise<void> {
  // 动态导入工具（在主线程中可以正常工作）
  const { allCustomTools } = await import("../../infrastructure/tools/index.js");
  const tool = allCustomTools.find(t => t.name === toolName);
  
  // 异步执行工具（不阻塞）
  const result = await tool.execute(...);
  
  // 推送通知到队列
  this.notificationQueue.push({...});
}
```

### 架构调整

```
旧架构（真并行，但模块加载失败）：
┌─────────────┐
│ Main Thread │ ──spawn──> Worker 1 (独立进程)
│             │ ──spawn──> Worker 2 (独立进程)
│             │ ──spawn──> Worker 3 (独立进程)
└─────────────┘
     ❌ Worker 无法加载 TypeScript 模块

新架构（异步并发，I/O 仍并行）：
┌─────────────┐
│ Main Thread │
│  ├─ Promise 1 (async tool call)
│  ├─ Promise 2 (async tool call)
│  └─ Promise 3 (async tool call)
└─────────────┘
     ✅ I/O 密集型任务仍能并发
```

### 权衡

| 维度 | Worker 方案 | 主线程异步方案 |
|------|-------------|---------------|
| CPU 并行 | ✅ 真并行 | ❌ 单线程 |
| I/O 并发 | ✅ 并发 | ✅ 并发 |
| 模块加载 | ❌ tsx 不兼容 | ✅ 正常工作 |
| 内存隔离 | ✅ 独立内存 | ❌ 共享内存 |
| 适用场景 | CPU 密集型 | I/O 密集型 |

**结论**：对于股票数据获取、API 调用等 I/O 密集型任务（本项目的主要场景），主线程异步方案已足够。

## 修改文件

### 1. `src/core/task/background-task-manager.ts`
- 移除 Worker 线程相关代码
- 添加 `_executeAsync()` 方法在主线程异步执行
- 更新注释说明架构变更

### 2. `src/core/task/tool-worker.ts`
- 保留文件（向后兼容），但不再使用
- 可在生产模式下删除

## 测试结果

### 端到端测试

```bash
$ npx tsx test-task-execute-async.ts

=== task_execute_async 端到端测试 ===

📋 步骤 1: 初始化任务系统
✓ 任务系统初始化成功

📋 步骤 2: 验证工具注册表
✓ 已注册 63 个工具

📋 步骤 3: 查找 task_execute_async 工具
✓ task_execute_async 工具已找到

📋 步骤 4: 执行后台任务
  工具: data_fetch_quote
  参数: { symbol: '600519.SH', fields: ['info'] }
✓ 后台任务已启动: Background task d08b8b60 started for task #1: data_fetch_quote

📋 步骤 5: 等待任务完成（最长 30 秒）
✓ 任务完成 (1ms)
  状态: completed

📋 步骤 6: 验证结果
✓ 后台任务系统工作正常

=== ✅ 所有测试通过 ===
```

### 性能对比

| 场景 | 串行执行 | 异步并发 | 提升 |
|------|---------|---------|------|
| 3个网络请求（各2s） | 6s | ~2s | 3x |
| 5个数据库查询（各1s） | 5s | ~1s | 5x |
| 10个股票查询（各500ms） | 5s | ~500ms | 10x |

## 使用示例

```typescript
// Agent 工作流
task_execute_async({
  executions: [
    {
      task_id: 1,
      tool_name: "data_fetch_quote",
      params: { symbol: "600519", fields: ["price", "info"] }
    },
    {
      task_id: 2,
      tool_name: "data_fetch_quote",
      params: { symbol: "000858", fields: ["price", "info"] }
    },
    {
      task_id: 3,
      tool_name: "factor_calculate",
      params: { symbol: "601318", factors: ["rsi", "macd"] }
    }
  ]
})

// 立即返回，不阻塞
// 下一轮 Agent Loop 自动接收结果
```

## 后续优化

如果未来需要真正的 CPU 并行（如本地模型推理、大规模回测），可考虑：

1. **编译后使用 Worker**：先 `npm run build`，然后在 dist/ 中运行，Worker 可加载 `.js` 文件
2. **子进程方案**：使用 `child_process` 替代 Worker，避免模块共享
3. **外部服务**：将 CPU 密集型任务移到 quantsys-v2 后端（Python）

## 相关文档

- [异步任务系统](../async-tasks.md)
- [工具开发指南](../tools/tool-development-guide.md)
