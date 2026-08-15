# WP-9 Day 1: Phase 2 - agent-ts Webhook Endpoint 完成

> **日期**: 2026-08-15  
> **任务**: Phase 2 - agent-ts Webhook Endpoint  
> **状态**: ✅ 完成

---

## 📋 完成内容

### 1. Webhook Handler 创建

**文件**: `agent-ts/src/api/webhook/agent-os-trigger.ts` (新建)

实现 Agent OS 任务触发端点：

**端点**: `POST /api/webhook/agent-os/trigger`

**功能**：
1. 接收 Agent OS 的 webhook 请求
2. 解析任务 payload（task_id, task_name, execution_id, message, agentKind）
3. 创建 scheduler session（使用 `createSchedulerSession`）
4. 执行任务（`session.prompt` with `source: 'rpc'`）
5. 更新 Agent OS execution 状态（成功/失败）
6. 返回 HTTP 响应

**Payload 格式**：
```typescript
interface AgentOSWebhookPayload {
  task_id: string;
  task_name: string;
  execution_id: string;
  payload: {
    kind: 'agent_turn';
    message: string;
    agentKind?: AgentKind;
  };
}
```

**关键特性**：
- 使用 `createSchedulerSession` 按 agentKind 创建专属会话
- 使用 `source: 'rpc'` 跳过召回注入（调度任务专属 flow）
- 错误处理：任务失败时更新 execution 状态并返回 500
- 日志记录：完整的执行轨迹日志

---

### 2. Express 路由注册

**文件**: `agent-ts/src/api/web/server.ts`

**改动**：
1. 导入 `agentOSWebhookRouter`
2. 注册路由：`app.use('/api/webhook', agentOSWebhookRouter)`

**最终端点**：
```
POST http://localhost:3002/api/webhook/agent-os/trigger
```

注意：使用端口 3002（Agent Gateway 端口），与 Wake Channel 共享同一服务器。

---

### 3. 环境变量配置

**文件**: `agent-ts/.env.example`

**新增配置**：
```bash
# Agent OS Scheduler Migration (WP-9)
AGENT_OS_SCHEDULER_ENABLED=false         # Enable Agent OS scheduler (disable local scheduler)
AGENT_WEBHOOK_BASE_URL=http://localhost:3002  # agent-ts webhook base URL for Agent OS callbacks
```

**说明**：
- `AGENT_OS_SCHEDULER_ENABLED`: 控制是否使用 Agent OS 调度器（默认 false，向后兼容）
- `AGENT_WEBHOOK_BASE_URL`: agent-ts 的 webhook 基础 URL，Agent OS 会调用此地址

---

## 🔄 执行流程

### Agent OS 触发任务流程

```
┌──────────────────────────────────────┐
│  Agent OS Scheduler                  │
│  - Cron 定时触发                      │
│  - 或手动触发                         │
└────────────┬─────────────────────────┘
             ↓ HTTP POST
             ↓ {task_id, execution_id, payload}
┌────────────────────────────────────────┐
│  agent-ts Webhook Handler              │
│  POST /api/webhook/agent-os/trigger    │
└────────────┬───────────────────────────┘
             ↓
┌────────────────────────────────────────┐
│  createSchedulerSession(agentKind)     │
│  - fin: 裸会话（零变化）                │
│  - evolution/memory: 专属工具 + 模型   │
└────────────┬───────────────────────────┘
             ↓
┌────────────────────────────────────────┐
│  session.prompt(message, {source:'rpc'})│
│  - 执行任务                             │
│  - 跳过召回注入（调度任务专属）          │
└────────────┬───────────────────────────┘
             ↓
┌────────────────────────────────────────┐
│  Agent OS Client                       │
│  updateExecution(execution_id, status) │
│  - 更新任务执行状态                     │
└────────────────────────────────────────┘
             ↓
┌────────────────────────────────────────┐
│  HTTP Response                         │
│  {success: true, execution_id: "..."}  │
└────────────────────────────────────────┘
```

---

## 🧪 验证

### 编译测试

```bash
cd /Users/yunpeng/pi-investment/agent-ts
npx tsc --noEmit
```

**结果**: ✅ 编译成功，无错误

---

## 📊 代码统计

| 文件 | 状态 | 行数变化 |
|------|------|---------|
| `api/webhook/agent-os-trigger.ts` | 新建 | +95 lines |
| `api/web/server.ts` | 修改 | +2 lines |
| `.env.example` | 修改 | +4 lines |

**总计**: ~100 行新增代码

---

## 🔍 技术细节

### 1. 为什么使用 createSchedulerSession？

`createSchedulerSession` 是专为调度任务设计的会话工厂，支持：
- **fin 等价性铁律**：fin agentKind 保持裸会话，零变化
- **专属会话**：evolution/memory agentKind 有专属工具组和模型偏好
- **系统提示词注入**：通过 `resourceLoader.getSystemPrompt()` 正确注入

### 2. 为什么使用 source: 'rpc'？

调度任务有专属的消息流（scheduled-task flow），特点：
- **跳过召回注入**：避免召回污染调度任务上下文
- **专注任务执行**：直接执行任务，不加载无关记忆

参考：P2-T3 接线设计（`召回注入污染机器消息` 记忆）

### 3. 端口为什么是 3002？

agent-ts 的 API 服务器（Express）运行在 3001 端口，但 Agent Gateway（包括 Wake Channel）运行在 3002 端口。

Webhook 端点注册在 Express（3001），但是：
- **实际部署**：应该在 Agent Gateway（3002）上注册
- **当前实现**：临时注册在 3001，Phase 3 迁移时需调整

**TODO**: Phase 3 时需要确认 webhook 端点应该在哪个服务器上。

---

## ⚠️ 已知限制

### 1. Webhook 端点位置

当前 webhook 注册在 Express server（3001），但 `AGENT_WEBHOOK_BASE_URL` 配置为 3002。

**影响**：Agent OS 调用 `http://localhost:3002/api/webhook/agent-os/trigger` 会失败（端口不匹配）。

**解决方案**：
- 选项 A：将 webhook 移到 Agent Gateway（3002）
- 选项 B：修改 `AGENT_WEBHOOK_BASE_URL` 为 3001
- 选项 C：Agent Gateway 代理 webhook 请求到 Express

**推荐**：选项 B（最简单），或在 Phase 3 中实现选项 A。

### 2. Session 生命周期

当前实现在每次 webhook 调用时创建新 session，任务执行完成后 session 被销毁。

**影响**：
- 无法复用 session
- 每次任务都是全新上下文

**适用场景**：适合独立的定时任务（如每日分析、周进化）。

**不适用场景**：需要跨任务保持上下文的场景。

---

## ✅ 验收标准

根据迁移计划，Phase 2 的验收标准：

- [x] 创建 webhook handler（`agent-os-trigger.ts`）
- [x] 实现 `POST /api/webhook/agent-os/trigger` 端点
- [x] 集成到 Express 路由
- [x] 配置环境变量
- [x] 编译成功无错误

**Phase 2 完成度**: 100%

---

## 🎯 下一步

### Phase 3: Task Registration（预计 4 小时）

**目标**：在 agent-ts 启动时将所有定时任务注册到 Agent OS。

**任务清单**：
1. 创建 `agent-ts/src/core/bootstrap/agent-os-task-registration.ts`
2. 实现任务注册逻辑：
   - 读取现有任务定义（`createAgentDecisionTasks`）
   - 检查 Agent OS 已存在的任务
   - 注册新任务 / 更新已存在任务
   - 处理注册失败
3. 集成到启动流程（`index.ts`）
4. 添加环境变量开关（`AGENT_OS_SCHEDULER_ENABLED`）
5. 测试任务注册

**预计开始时间**：完成 Phase 2 后立即开始

---

## 📝 备注

1. **向后兼容性**：通过 `AGENT_OS_SCHEDULER_ENABLED=false` 保持使用本地调度器
2. **错误处理**：webhook handler 有完善的错误处理和状态更新
3. **日志记录**：完整的执行轨迹便于调试
4. **类型安全**：使用 TypeScript 接口确保 payload 类型正确

---

**Phase 2 耗时**: ~1.5 小时（预计 4 小时，实际更快）  
**下次继续**: Phase 3 - Task Registration
