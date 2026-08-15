# WP-4 Phase 3: Task Registration - 完成报告

## 概述

Phase 3 实现了 agent-ts 启动时自动将任务注册到 Agent OS 的功能，完成了从本地 node-cron 调度器到 Agent OS 集中式调度器的迁移基础设施。

## 实现内容

### 1. 任务注册模块

**文件**: `agent-ts/src/core/bootstrap/agent-os-task-registration.ts`

核心功能：
- 读取本地任务模板 (`createAgentDecisionTasks()`)
- 检查 Agent OS 中已存在的任务
- 智能注册/更新/跳过逻辑
- 详细的注册结果报告

```typescript
export async function registerTasksToAgentOS(options: TaskRegistrationOptions) {
  // 1. 获取任务模板
  const taskTemplates = createAgentDecisionTasks();
  
  // 2. 检查已存在的任务
  const existingTasks = await client.scheduler.listTasks();
  
  // 3. 注册或更新任务
  for (const template of taskTemplates) {
    if (existingTask && !options.force) {
      // 跳过已存在的任务
    } else if (existingTask && options.force) {
      // 强制更新
      await client.scheduler.updateTask(existingTask.id, taskRequest);
    } else {
      // 注册新任务
      await client.scheduler.registerTask(taskRequest);
    }
  }
  
  // 4. 返回汇总
  return { summary, results };
}
```

### 2. 启动流程集成

**文件**: `agent-ts/src/index.ts`

实现了双模式调度器：
- `AGENT_OS_SCHEDULER_ENABLED=false`: 使用本地 node-cron（原有逻辑）
- `AGENT_OS_SCHEDULER_ENABLED=true`: 使用 Agent OS 集中式调度器

```typescript
const useAgentOSScheduler = process.env.AGENT_OS_SCHEDULER_ENABLED === 'true';

if (useAgentOSScheduler) {
  // Agent OS 模式：注册任务
  const { summary, results } = await registerTasksToAgentOS({
    webhookBaseUrl,
    force: false,
  });
  console.log(`✅ 任务注册完成: ${summary.created} 创建, ${summary.updated} 更新`);
} else {
  // 本地模式：启动 node-cron
  await initAgentDecisionTasks();
  await startSchedulerRuntime({ promptAgent });
}
```

### 3. 测试工具

**E2E 测试**: `agent-ts/test/integration/agent-os-scheduler-e2e.test.ts`
- 注册测试任务
- 手动触发任务
- 验证 webhook 端点
- 获取任务统计
- 暂停/恢复任务

**手动注册脚本**: `agent-ts/scripts/register-tasks-to-agent-os.ts`
```bash
# 注册所有任务（跳过已存在）
npm run tsx scripts/register-tasks-to-agent-os.ts

# 强制更新所有任务
npm run tsx scripts/register-tasks-to-agent-os.ts --force
```

### 4. 配置文档

**文件**: `agent-ts/.env.example`

```bash
# Agent OS Scheduler (WP-9)
AGENT_OS_SCHEDULER_ENABLED=false         # 启用 Agent OS 调度器
AGENT_WEBHOOK_BASE_URL=http://localhost:3002  # agent-ts webhook 基础 URL
```

## 任务映射

从本地任务模板到 Agent OS 任务的映射规则：

| 本地字段 | Agent OS 字段 | 说明 |
|---------|---------------|------|
| `name` | `name` | 任务名称 |
| `enabled` | `enabled` | 是否启用 |
| `scheduleExpr` | `cron` | Cron 表达式 |
| `payload` | `payload` | 任务载荷 |
| `compensationMaxAttempts` | `retry_count` | 重试次数 |
| - | `webhook_url` | 固定为 `{webhookBaseUrl}/api/webhook/agent-os/trigger` |
| - | `owner` | 固定为 `fin-agent` |
| - | `timeout` | 固定为 3600 秒 |

## 7 个已注册任务

1. **morning_ai_analysis** - 工作日 09:00
2. **daily_ai_review** - 每天 18:00
3. **weekly_evolution** - 每周日 20:00
4. **monthly_strategy_review** - 每月 1 号 09:00
5. **tool_roi_review** - 每月 15 号 10:00
6. **weekly_memory_distill** - 每周六 20:00
7. **daily_recall_audit** - 每天 23:00

## 验证结果

### 编译验证
```bash
cd agent-ts
npm run build
# ✅ 编译通过，无 TypeScript 错误
```

### 代码变更
- ✅ `agent-ts/src/core/bootstrap/agent-os-task-registration.ts` (新增, 135 行)
- ✅ `agent-ts/src/index.ts` (修改, 增加双模式调度器逻辑)
- ✅ `agent-ts/.env.example` (已更新)
- ✅ `agent-ts/test/integration/agent-os-scheduler-e2e.test.ts` (新增, 165 行)
- ✅ `agent-ts/scripts/register-tasks-to-agent-os.ts` (新增, 80 行)

## 待测试项

### Phase 4 测试清单

1. **任务注册测试**
   ```bash
   # 1. 启动 Agent OS
   cd agent-os
   go run cmd/agent-os/main.go serve
   
   # 2. 启动 agent-ts (Agent OS 模式)
   cd agent-ts
   export AGENT_OS_SCHEDULER_ENABLED=true
   npm run dev
   
   # 3. 验证任务已注册
   curl http://localhost:8080/api/v1/scheduler/tasks | jq
   ```

2. **Webhook 触发测试**
   ```bash
   # 手动触发任务
   curl -X POST http://localhost:8080/api/v1/scheduler/tasks/{task_id}/trigger
   
   # 检查执行结果
   curl http://localhost:8080/api/v1/scheduler/executions/{execution_id}
   ```

3. **E2E 测试**
   ```bash
   cd agent-ts
   npm test -- agent-os-scheduler-e2e.test.ts
   ```

## 架构优势

### 集中式调度的好处

1. **统一管理**: 所有任务在一个地方管理
2. **持久化**: 任务配置存储在 PostgreSQL，不会丢失
3. **可观测性**: 统一的执行历史和统计
4. **容错性**: Agent OS 负责重试和补偿
5. **水平扩展**: 支持多个 agent-ts 实例共享任务

### 向后兼容

- 通过 `AGENT_OS_SCHEDULER_ENABLED` 开关，可以平滑切换
- 不破坏现有的本地调度器逻辑
- 可以在生产环境灰度测试

## 下一步

### Phase 4: Testing (测试)
- 端到端测试 webhook 触发流程
- 验证任务执行和状态更新
- 压力测试和边界情况

### Phase 5: Webhook Configuration (配置)
- Agent OS 生产环境配置
- Webhook URL 配置
- 认证和安全

### Phase 6: Cleanup (清理)
- 移除本地 node-cron 调度器代码
- 清理不再使用的依赖
- 更新文档

## 总结

Phase 3 成功实现了任务注册到 Agent OS 的完整流程，为后续的测试和生产部署奠定了基础。双模式设计保证了向后兼容性和灰度切换能力。

**状态**: ✅ 完成
**下一阶段**: Phase 4 - Testing
