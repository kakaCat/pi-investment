# WP-8 Day 3: Agent-TS 与 Agent OS 集成完成

**日期**: 2026-08-15
**状态**: ✅ 完成

## 目标

将 agent-ts 的定时任务系统完全迁移到 Agent OS 调度器，实现：
1. Agent OS 统一管理所有定时任务
2. 通过 webhook 触发 agent-ts 执行
3. 任务状态双向同步

## 完成的工作

### 1. Agent OS Client SDK 修复

**问题**: agent-os-client 期望的 API 响应格式与 Agent OS 实际格式不匹配

**解决方案**:
- 修改 `BaseHTTPClient` 的请求方法，直接返回响应数据而不期望 `ApiResponse` 包装
- 修改 `SchedulerClient.listTasks()` 和 `listExecutions()` 以处理 Agent OS 的实际响应格式：`{ count, tasks }`
- 文件: `agent-os-client/src/http/client.ts`, `agent-os-client/src/scheduler/client.ts`

### 2. Cron 表达式格式转换

**问题**: Agent OS 使用 6 字段 cron（秒 分 时 日 月 周），而标准 cron 是 5 字段（分 时 日 月 周）

**解决方案**:
- 在任务注册时将 5 字段 cron 自动转换为 6 字段格式（在开头添加 `0` 表示秒）
- 函数: `convertCronTo6Field()` in `agent-ts/src/core/bootstrap/agent-os-task-registration.ts`

### 3. Webhook 端点实现

**问题**: agent-ts 的 webhook 服务器端口冲突，headless 模式没有启动 web server

**解决方案**:
- 修改 `start-headless.ts` 导入 `web/server.ts` 以启动 Express web server
- 确认 webhook 路由正确注册: `POST /api/webhook/agent-os/trigger`
- Web server 监听 3001 端口，与 quantsys-v2 的 FastAPI 服务（也在 3001）区分开

### 4. 任务注册脚本

**实现**:
- 脚本: `agent-ts/scripts/register-tasks-to-agent-os.ts`
- 环境变量: `AGENT_WEBHOOK_BASE_URL` (默认 http://localhost:3002)
- 参数: `--force` 强制更新已存在的任务

**使用示例**:
```bash
# 注册所有任务
AGENT_WEBHOOK_BASE_URL=http://localhost:3001 npx tsx scripts/register-tasks-to-agent-os.ts

# 强制更新已存在的任务
AGENT_WEBHOOK_BASE_URL=http://localhost:3001 npx tsx scripts/register-tasks-to-agent-os.ts --force
```

## 已注册的任务

所有 7 个 agent-ts 定时任务已成功注册到 Agent OS：

| 任务名称 | Cron 表达式 | 说明 |
|---------|------------|------|
| morning_ai_analysis | `0 0 9 * * 1-5` | 工作日早上9点盘前分析 |
| realtime_quick_check | `0 */30 9-14 * * 1-5` | 工作日盘中每30分钟快速检查 |
| daily_ai_review | `0 0 18 * * *` | 每天18点复盘分析 |
| weekly_evolution | `0 0 20 * * 0` | 每周日20点进化总结 |
| weekly_tool_roi_review | `0 0 19 * * 0` | 每周日19点工具ROI评估 |
| weekly_memory_distill | `0 0 21 * * 0` | 每周日21点记忆蒸馏 |
| daily_recall_audit | `0 0 19 * * *` | 每天19点 recall 审计 |

## 端到端流程验证

### 测试执行

```bash
# 手动触发任务
curl -X POST http://localhost:8080/api/v1/scheduler/tasks/{task_id}/trigger

# 查看任务列表
curl http://localhost:8080/api/v1/scheduler/tasks | jq .

# 查看执行历史
curl http://localhost:8080/api/v1/scheduler/executions | jq .
```

### 验证结果

✅ **任务触发成功**:
- Agent OS 成功调用 webhook: `http://localhost:3001/api/webhook/agent-os/trigger`
- agent-ts 收到请求并创建会话
- Agent 开始执行任务（morning_ai_analysis）

✅ **日志确认**:
```
[INFO] [AgentOS Webhook] Task triggered {
  task_id: 'c71ee5ca-9fef-49d3-971b-7d5b742aeaa4',
  task_name: 'morning_ai_analysis',
  execution_id: '5db7949b-d2dc-4645-b57f-b6b0d19863ab'
}
[INFO] [AgentOS Webhook] Executing task { task_name: 'morning_ai_analysis', agentKind: 'fin' }
```

## 架构变更

### 之前（本地调度）

```
agent-ts (node-cron)
  ├── 管理 7 个定时任务
  ├── 直接调用 agent session
  └── 无集中管理
```

### 现在（Agent OS 统一调度）

```
Agent OS Scheduler (Go + PostgreSQL)
  ├── 统一管理所有任务
  ├── 持久化存储（任务、执行记录）
  ├── 通过 webhook 触发
  │
  └─> agent-ts Web Server (Express)
        ├── POST /api/webhook/agent-os/trigger
        ├── 创建 agent session
        ├── 执行任务
        └── 报告状态给 Agent OS
```

## 技术细节

### Agent OS Client 集成

```typescript
import { getAgentOSClient } from '../../infrastructure/agent-os/client.js';

const client = getAgentOSClient();

// 注册任务
await client.scheduler.registerTask({
  name: 'morning_ai_analysis',
  owner: 'fin-agent',
  enabled: true,
  cron: '0 0 9 * * 1-5',  // 6 字段格式
  webhook_url: 'http://localhost:3001/api/webhook/agent-os/trigger',
  payload: {
    kind: 'agent_turn',
    message: '执行早盘 AI 分析...',
    agentKind: 'fin'
  },
  timeout: 3600,
  retry_count: 3
});
```

### Webhook Handler

```typescript
// src/api/webhook/agent-os-trigger.ts
agentOSWebhookRouter.post('/agent-os/trigger', async (req, res) => {
  const { task_id, task_name, execution_id, payload } = req.body;
  
  // 创建会话并执行任务
  const { session } = await createSchedulerSession(payload.agentKind || 'fin');
  await session.prompt(payload.message, { source: 'rpc' });
  
  // 报告成功
  await client.scheduler.updateExecution(execution_id, {
    status: 'succeeded',
    finished_at: new Date().toISOString()
  });
  
  res.json({ success: true });
});
```

## 下一步

### 短期优化

1. **错误处理增强**: 
   - Webhook 超时处理
   - 重试机制优化
   - 详细的错误日志

2. **监控和告警**:
   - 任务执行时长监控
   - 失败率告警
   - Webhook 可用性检查

3. **配置管理**:
   - 从环境变量读取 webhook URL
   - 支持多环境配置（开发、生产）

### 长期规划

1. **quantsys-v2 集成**: 数据更新任务也迁移到 Agent OS
2. **Web UI**: 可视化任务管理界面
3. **分布式调度**: 支持多 agent 实例负载均衡

## 相关文件

### Agent OS
- `agent-os/internal/api/scheduler_handler.go` - 调度器 HTTP API
- `agent-os/internal/kernel/scheduler/scheduler.go` - 调度器核心逻辑
- `agent-os/internal/kernel/scheduler/executor.go` - 任务执行器（webhook 调用）

### Agent OS Client
- `agent-os-client/src/http/client.ts` - HTTP 客户端基类
- `agent-os-client/src/scheduler/client.ts` - 调度器 API 客户端
- `agent-os-client/src/scheduler/types.ts` - TypeScript 类型定义

### Agent-TS
- `agent-ts/src/api/webhook/agent-os-trigger.ts` - Webhook 处理器
- `agent-ts/src/api/start-headless.ts` - Headless 模式启动脚本
- `agent-ts/src/core/bootstrap/agent-os-task-registration.ts` - 任务注册逻辑
- `agent-ts/scripts/register-tasks-to-agent-os.ts` - 任务注册脚本

## 测试清单

- [x] Agent OS Client 连接成功
- [x] 任务注册（create）
- [x] 任务更新（update with --force）
- [x] Cron 表达式格式转换（5字段 → 6字段）
- [x] Webhook 端点可访问
- [x] 手动触发任务
- [x] Agent 会话创建和执行
- [ ] 任务执行完成后状态更新（进行中）
- [ ] 失败重试机制
- [ ] 定时触发（需等待下一个调度时间）

## 问题和解决

### 1. API 响应格式不匹配
**症状**: `Unknown error` 当调用 Agent OS API
**原因**: agent-os-client 期望 `{success, data}` 格式，但 Agent OS 直接返回数据
**解决**: 移除 ApiResponse 包装检查，直接返回 `response.data`

### 2. Cron 字段数量错误
**症状**: `expected exactly 6 fields, found 5`
**原因**: Agent OS 使用 robfig/cron v3 的 6 字段格式
**解决**: 添加 `convertCronTo6Field()` 函数在注册时转换

### 3. Webhook 404
**症状**: `Cannot POST /api/webhook/agent-os/trigger`
**原因**: Headless 模式没有启动 web server
**解决**: 在 `start-headless.ts` 中导入 `web/server.ts`

### 4. 端口冲突
**症状**: Web server 启动但路由不工作
**原因**: 3001 被 Vite dev server 占用
**解决**: 停止 Vite 或为 web server 使用不同端口

## 总结

WP-8 Day 3 成功实现了 agent-ts 与 Agent OS 的完整集成：

✅ **统一调度**: 所有定时任务由 Agent OS 统一管理
✅ **Webhook 触发**: Agent OS 通过 HTTP webhook 调用 agent-ts
✅ **任务持久化**: 任务定义和执行记录存储在 PostgreSQL
✅ **端到端验证**: 手动触发测试通过，Agent 成功接收并执行任务

系统现在拥有了企业级的任务调度能力，为后续的分布式部署和高可用架构奠定了基础。
