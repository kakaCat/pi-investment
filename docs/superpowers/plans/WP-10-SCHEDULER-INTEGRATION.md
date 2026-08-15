# WP-10: Agent OS Scheduler 完整集成设计

> **创建时间**: 2026-08-15  
> **状态**: Design Complete - Ready for Execution  
> **预计工作量**: 4-5 小时  
> **目标**: agent-ts 完全切换到 Agent OS Scheduler，移除本地 node-cron

---

## 0. 背景与目标

### 当前状态

**已完成（WP-1 ~ WP-9）**：
- ✅ Agent OS 已实现 Scheduler/Memory/Decision/Notification 等核心功能
- ✅ agent-ts 已集成 agent-os-client SDK（Memory/Decision/Notification）
- ✅ Agent OS 已部署并运行（Docker Compose）

**未完成**：
- ⏸️ agent-ts 仍在使用本地 node-cron 调度任务
- ⏸️ 任务未注册到 Agent OS Scheduler
- ⏸️ agent-ts 未实现 Webhook Endpoint 接收 OS 触发

**问题**：
- 双调度器并存（agent-ts cron + Agent OS scheduler）
- 无法统一管理、监控、重试
- 无法利用 Agent OS 的 DAG 依赖、Token 配额等高级特性

### 目标架构

**Before (AS-IS)**:
```
agent-ts
  └── node-cron (本地调度)
       ├── morning_ai_analysis (9:00)
       ├── realtime_quick_check (每30分钟)
       └── daily_ai_review (18:00)
```

**After (TO-BE)**:
```
Agent OS Scheduler (统一调度)
  ├── Task: morning_ai_analysis
  ├── Task: realtime_quick_check
  └── Task: daily_ai_review
       ↓ Cron 触发
  Webhook POST → agent-ts:3002/api/webhook/trigger
       ↓ 创建 Session
  执行 Skill
```

### 验收标准

1. agent-ts 启动时自动注册所有任务到 Agent OS
2. Agent OS Scheduler 按 cron 触发任务
3. agent-ts 通过 Webhook 接收触发，创建 Session 执行
4. agent-ts 删除本地 node-cron 代码
5. 至少运行 3 天无故障

---

## 1. 整体设计

### 1.1 架构组件

| 组件 | 职责 | 位置 |
|------|------|------|
| **Agent OS Scheduler** | Cron 触发器 | Agent OS (Go) |
| **Task Registry** | 启动时注册任务 | agent-ts/src/core/bootstrap/ |
| **Webhook Endpoint** | 接收 OS 触发 | agent-ts/src/api/webhook/ |
| **Session Executor** | 执行 Skill | agent-ts/src/services/scheduler/ |

### 1.2 数据流

```
┌─────────────────────────────────────────────────┐
│ Step 1: 启动时注册任务                           │
│                                                  │
│  agent-ts 启动                                   │
│     ↓                                            │
│  读取 skills/*.md (cron schedule)                │
│     ↓                                            │
│  调用 Agent OS SDK                               │
│     client.scheduler.registerTask({              │
│       name: 'morning_ai_analysis',               │
│       cron: '0 9 * * 1-5',                      │
│       webhook_url: 'http://localhost:3002/...'  │
│     })                                           │
│     ↓                                            │
│  Agent OS 存储任务定义                           │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ Step 2: Cron 触发                                │
│                                                  │
│  Agent OS Scheduler (每分钟检查)                 │
│     ↓                                            │
│  匹配到 cron: '0 9 * * 1-5' (周一到周五 9:00)   │
│     ↓                                            │
│  创建 TaskRun 记录 (status: running)             │
│     ↓                                            │
│  POST webhook_url                                │
│     Body: {                                      │
│       task_id: "uuid",                          │
│       task_name: "morning_ai_analysis",         │
│       run_id: "uuid",                           │
│       params: {}                                 │
│     }                                            │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ Step 3: Webhook 执行                             │
│                                                  │
│  agent-ts Webhook Handler                        │
│     ↓                                            │
│  解析 task_name 找到对应的 skill                 │
│     ↓                                            │
│  创建 SchedulerSession                           │
│     session = createSchedulerSession('fin')      │
│     ↓                                            │
│  执行 Skill                                      │
│     session.prompt(skill, { source: 'agent-os' })│
│     ↓                                            │
│  捕获错误，返回结果                              │
│     res.json({ success: true/false })            │
│     ↓                                            │
│  Agent OS 更新 TaskRun 状态                      │
│     (status: completed/failed)                   │
└─────────────────────────────────────────────────┘
```

---

## 2. Task 2.1: Task Registration System

### 2.1.1 文件：`agent-ts/src/core/bootstrap/task-registration.ts`

**职责**：启动时自动注册所有任务到 Agent OS

**接口**：
```typescript
/**
 * 从 skills 读取任务定义并注册到 Agent OS
 */
export async function registerAgentTasks(): Promise<void>;

/**
 * 从 skill 文件提取 schedule
 */
function extractScheduleFromSkill(skillPath: string): TaskDefinition | null;

/**
 * 任务定义类型
 */
interface TaskDefinition {
  name: string;        // 任务名称（从 skill 文件名推断）
  cron: string;        // Cron 表达式
  skillName: string;   // Skill 名称（对应 skill 文件）
  description?: string; // 任务描述
}
```

**实现逻辑**：

```typescript
import fs from 'fs';
import path from 'path';
import { getAgentOSClient } from '../../infrastructure/agent-os/client.js';
import { logger } from '../../infrastructure/logging/index.js';

export async function registerAgentTasks(): Promise<void> {
  logger.info('[TaskRegistry] Starting task registration...');
  
  const client = getAgentOSClient();
  const skillsDir = path.join(process.cwd(), 'skills');
  
  // 1. 扫描 skills/ 目录
  const skillFiles = fs.readdirSync(skillsDir)
    .filter(f => f.endsWith('.md'));
  
  const tasks: TaskDefinition[] = [];
  
  // 2. 从每个 skill 提取 schedule
  for (const file of skillFiles) {
    const skillPath = path.join(skillsDir, file);
    const task = extractScheduleFromSkill(skillPath);
    if (task) {
      tasks.push(task);
    }
  }
  
  logger.info(`[TaskRegistry] Found ${tasks.length} scheduled tasks`);
  
  // 3. 注册到 Agent OS
  for (const task of tasks) {
    try {
      await client.scheduler.registerTask({
        name: task.name,
        owner: 'fin-agent',
        cron: task.cron,
        webhook_url: `http://localhost:3002/api/webhook/trigger`,
        params: {
          skill: task.skillName
        },
        metadata: {
          description: task.description,
          source: 'agent-ts'
        }
      });
      
      logger.info(`[TaskRegistry] ✅ Registered: ${task.name} (${task.cron})`);
    } catch (error) {
      logger.error(`[TaskRegistry] ❌ Failed to register ${task.name}:`, error);
    }
  }
  
  logger.info('[TaskRegistry] Task registration complete');
}

function extractScheduleFromSkill(skillPath: string): TaskDefinition | null {
  const content = fs.readFileSync(skillPath, 'utf-8');
  
  // 从 frontmatter 提取 schedule
  const scheduleMatch = content.match(/^schedule:\s*"(.+)"$/m);
  if (!scheduleMatch) {
    return null; // 无 schedule 的 skill 不注册
  }
  
  const cron = scheduleMatch[1];
  const skillName = path.basename(skillPath, '.md');
  
  // 提取描述（可选）
  const descMatch = content.match(/^description:\s*"(.+)"$/m);
  const description = descMatch ? descMatch[1] : undefined;
  
  return {
    name: skillName,
    cron,
    skillName,
    description
  };
}
```

**Skill 文件格式约定**：

```markdown
---
name: morning_ai_analysis
schedule: "0 9 * * 1-5"
description: "工作日早盘分析"
---

# Morning AI Analysis

分析今日市场...
```

**测试**：

```typescript
// agent-ts/src/core/bootstrap/task-registration.test.ts

import { extractScheduleFromSkill } from './task-registration.js';

describe('extractScheduleFromSkill', () => {
  it('should extract schedule from skill file', () => {
    const mockContent = `---
name: test_skill
schedule: "0 9 * * *"
description: "Test skill"
---

# Test Skill
`;
    
    // Mock fs.readFileSync
    const task = extractScheduleFromSkill('/fake/path.md');
    
    expect(task).toEqual({
      name: 'path',
      cron: '0 9 * * *',
      skillName: 'path',
      description: 'Test skill'
    });
  });
  
  it('should return null if no schedule', () => {
    const mockContent = `---
name: no_schedule_skill
---
`;
    const task = extractScheduleFromSkill('/fake/path.md');
    expect(task).toBeNull();
  });
});
```

---

## 3. Task 2.2: Webhook Endpoint

### 3.1 文件：`agent-ts/src/api/webhook/trigger.ts`

**职责**：接收 Agent OS Scheduler 的 HTTP POST 触发

**接口**：
```typescript
POST /api/webhook/trigger
Content-Type: application/json

Request Body:
{
  "task_id": "uuid",
  "task_name": "morning_ai_analysis",
  "run_id": "uuid",
  "params": {
    "skill": "morning_ai_analysis"
  }
}

Response (Success):
{
  "success": true,
  "run_id": "uuid"
}

Response (Error):
{
  "success": false,
  "error": "Error message"
}
```

**实现**：

```typescript
import express from 'express';
import { createSchedulerSession } from '../../services/scheduler/scheduler-session.js';
import { logger } from '../../infrastructure/logging/index.js';

const router = express.Router();

/**
 * Webhook endpoint for Agent OS Scheduler triggers
 */
router.post('/trigger', async (req, res) => {
  const { task_id, task_name, run_id, params } = req.body;
  
  logger.info(`[Webhook] Task triggered: ${task_name} (run: ${run_id})`);
  
  try {
    // 验证请求参数
    if (!task_name || !params?.skill) {
      return res.status(400).json({
        success: false,
        error: 'Missing required fields: task_name or params.skill'
      });
    }
    
    // 创建 Scheduler Session
    const { session } = await createSchedulerSession('fin');
    
    logger.info(`[Webhook] Executing skill: ${params.skill}`);
    
    // 执行 Skill（异步不阻塞 webhook 响应）
    session.prompt(params.skill, { 
      source: 'agent-os-scheduler',
      taskId: task_id,
      runId: run_id
    }).then(() => {
      logger.info(`[Webhook] ✅ Task completed: ${task_name}`);
    }).catch((error) => {
      logger.error(`[Webhook] ❌ Task failed: ${task_name}`, error);
    });
    
    // 立即返回成功（不等待 LLM 完成）
    res.json({ 
      success: true,
      run_id 
    });
    
  } catch (error) {
    logger.error(`[Webhook] Task execution failed:`, error);
    
    res.status(500).json({ 
      success: false, 
      error: error instanceof Error ? error.message : 'Unknown error'
    });
  }
});

/**
 * Health check endpoint
 */
router.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});

export default router;
```

### 3.2 集成到主 API

**文件**：`agent-ts/src/api/index.ts`

```typescript
// 添加 webhook 路由
import webhookRouter from './webhook/trigger.js';

// ... 现有代码 ...

app.use('/api/webhook', webhookRouter);

console.log('✅ Webhook endpoint registered: /api/webhook/trigger');
```

### 3.3 测试

```typescript
// agent-ts/src/api/webhook/trigger.test.ts

import request from 'supertest';
import express from 'express';
import webhookRouter from './trigger.js';

const app = express();
app.use(express.json());
app.use('/api/webhook', webhookRouter);

describe('POST /api/webhook/trigger', () => {
  it('should accept valid webhook request', async () => {
    const response = await request(app)
      .post('/api/webhook/trigger')
      .send({
        task_id: 'test-task-id',
        task_name: 'test_task',
        run_id: 'test-run-id',
        params: {
          skill: 'test_skill'
        }
      });
    
    expect(response.status).toBe(200);
    expect(response.body.success).toBe(true);
  });
  
  it('should reject missing skill param', async () => {
    const response = await request(app)
      .post('/api/webhook/trigger')
      .send({
        task_name: 'test_task'
      });
    
    expect(response.status).toBe(400);
    expect(response.body.success).toBe(false);
  });
});
```

---

## 4. Task 2.3: Remove Local Cron

### 4.1 删除 node-cron 代码

**文件**：`agent-ts/src/index.ts`

**修改前**：
```typescript
// ❌ 删除这些
await initAgentDecisionTasks();
console.log("✅ Agent AI 决策任务初始化完成");

await startSchedulerRuntime({
  promptAgent: async (message: string, agentKind?: AgentKind) => {
    // ... 本地调度逻辑
  }
});
```

**修改后**：
```typescript
// ✅ 替换为
import { registerAgentTasks } from './core/bootstrap/task-registration.js';

await registerAgentTasks();
console.log("✅ Tasks registered to Agent OS");
```

### 4.2 删除相关文件

**待删除的文件**：
- `agent-ts/src/services/scheduler/init-agent-tasks.ts`
- `agent-ts/src/services/scheduler/scheduler-runtime.ts`

**保留的文件**（仍需要）：
- `agent-ts/src/services/scheduler/scheduler-session.ts`（创建 session）

### 4.3 删除 node-cron 依赖

**文件**：`agent-ts/package.json`

```json
{
  "dependencies": {
    // ❌ 删除
    // "node-cron": "^3.0.2"
  }
}
```

运行：
```bash
npm uninstall node-cron
```

---

## 5. Task 2.4: 环境变量配置

### 5.1 新增环境变量

**文件**：`agent-ts/.env.example`

```bash
# Agent OS Scheduler Integration
AGENT_OS_WEBHOOK_ENABLED=true           # 启用 Webhook 接收
AGENT_OS_WEBHOOK_PORT=3002              # Webhook 端口（与 Gateway 一致）
AGENT_OS_AUTO_REGISTER_TASKS=true       # 启动时自动注册任务
```

### 5.2 配置读取

**文件**：`agent-ts/src/config/config.ts`

```typescript
export const config = {
  // ... 现有配置 ...
  
  agentOS: {
    webhookEnabled: process.env.AGENT_OS_WEBHOOK_ENABLED === 'true',
    webhookPort: parseInt(process.env.AGENT_OS_WEBHOOK_PORT || '3002', 10),
    autoRegisterTasks: process.env.AGENT_OS_AUTO_REGISTER_TASKS !== 'false', // 默认 true
  }
};
```

---

## 6. 验证方案

### 6.1 单元测试

```bash
# agent-ts
npm test -- task-registration.test.ts
npm test -- trigger.test.ts
```

**预期**：所有测试通过

### 6.2 集成测试

**步骤**：

1. **启动 Agent OS**
```bash
cd agent-os
./scripts/deploy.sh
```

2. **启动 agent-ts**
```bash
cd agent-ts
npm run dev
```

3. **验证任务注册**
```bash
# 查询 Agent OS 中的任务
curl http://localhost:8080/api/v1/scheduler/tasks?owner=fin-agent

# 预期返回：
# [
#   { "name": "morning_ai_analysis", "cron": "0 9 * * 1-5", ... },
#   { "name": "daily_ai_review", "cron": "0 18 * * *", ... },
#   ...
# ]
```

4. **手动触发任务**
```bash
# 触发 morning_ai_analysis
curl -X POST http://localhost:8080/api/v1/scheduler/tasks/morning_ai_analysis/trigger

# 观察 agent-ts 日志：
# [Webhook] Task triggered: morning_ai_analysis
# [Webhook] Executing skill: morning_ai_analysis
# [Webhook] ✅ Task completed: morning_ai_analysis
```

5. **等待自动触发**
```bash
# 修改某个任务的 cron 为 "*/5 * * * *"（每5分钟）
# 观察是否自动触发
```

### 6.3 回归测试

**测试场景**：

| 场景 | 预期结果 |
|------|---------|
| agent-ts 启动 | 自动注册所有任务到 Agent OS |
| Agent OS 按 cron 触发 | agent-ts 接收 webhook，创建 session 执行 |
| Skill 执行成功 | 日志正常，无错误 |
| Skill 执行失败 | 捕获错误，不崩溃 |
| agent-ts 重启 | 任务不重复注册（Agent OS 幂等） |
| Agent OS 重启 | 任务定义持久化，重启后恢复 |

### 6.4 稳定性测试

**要求**：连续运行 **3 天**，无以下问题：
- 任务漏触发
- Webhook 超时
- Session 泄漏
- 内存泄漏

---

## 7. 回滚方案

### 7.1 回滚开关

**环境变量**：`USE_AGENT_OS_SCHEDULER`

```bash
# .env
USE_AGENT_OS_SCHEDULER=false  # 回退到本地 node-cron
```

**实现**：
```typescript
// agent-ts/src/index.ts

if (process.env.USE_AGENT_OS_SCHEDULER === 'false') {
  // 使用本地 node-cron（回退模式）
  await initAgentDecisionTasks();
  await startSchedulerRuntime({ ... });
} else {
  // 使用 Agent OS Scheduler（默认）
  await registerAgentTasks();
}
```

### 7.2 回滚步骤

1. 设置 `USE_AGENT_OS_SCHEDULER=false`
2. 重启 agent-ts
3. 观察本地 cron 是否正常触发

---

## 8. 部署清单

### 8.1 部署前检查

- [ ] Agent OS 已部署并运行（`docker ps` 看到 agent-os 容器）
- [ ] Agent OS 健康检查通过（`curl http://localhost:8080/health`）
- [ ] agent-ts 环境变量配置正确（`.env` 文件）
- [ ] 单元测试全部通过（`npm test`）

### 8.2 部署步骤

1. **停止 agent-ts**
```bash
# 停止当前 agent-ts 进程
pkill -f "node.*agent-ts"
```

2. **拉取最新代码**
```bash
cd agent-ts
git pull origin main
npm install
npm run build
```

3. **启动 agent-ts**
```bash
npm run dev
```

4. **验证日志**
```bash
# 应看到：
# [TaskRegistry] Starting task registration...
# [TaskRegistry] Found 3 scheduled tasks
# [TaskRegistry] ✅ Registered: morning_ai_analysis (0 9 * * 1-5)
# [TaskRegistry] ✅ Registered: realtime_quick_check (*/30 9-14 * * 1-5)
# [TaskRegistry] ✅ Registered: daily_ai_review (0 18 * * *)
# [TaskRegistry] Task registration complete
# ✅ Tasks registered to Agent OS
```

5. **查询 Agent OS**
```bash
curl http://localhost:8080/api/v1/scheduler/tasks?owner=fin-agent | jq
```

### 8.3 监控指标

**关键指标**：
- 任务注册成功率（100%）
- Webhook 响应时间（< 500ms）
- 任务执行成功率（> 95%）
- 任务触发准时性（± 1 分钟）

**监控工具**：
- Grafana Dashboard（Agent OS Metrics）
- agent-ts 日志（`~/agent-ts.log`）

---

## 9. 风险与缓解

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| Agent OS 宕机 | 任务不触发 | 回滚到本地 cron |
| Webhook 超时 | 任务失败 | 增加超时时间，异步执行 |
| 任务重复注册 | 数据污染 | Agent OS 幂等检查 |
| Session 泄漏 | 内存溢出 | Session 自动清理，监控内存 |
| 网络分区 | webhook 不可达 | 健康检查，自动重试 |

---

## 10. 成功标准

### 10.1 功能完整性

- [x] agent-ts 启动时自动注册任务
- [x] Agent OS 按 cron 准时触发
- [x] agent-ts 接收 webhook 并执行
- [x] 任务执行结果正确记录
- [x] 删除本地 node-cron 代码

### 10.2 性能指标

- Webhook 响应时间 < 500ms
- 任务触发准时性 ± 1 分钟
- Session 创建时间 < 2s
- 内存增长 < 100MB/天

### 10.3 稳定性

- 连续运行 3 天无崩溃
- 任务执行成功率 > 95%
- 无内存泄漏
- 无 Session 泄漏

---

## 11. 时间线

| 阶段 | 任务 | 时间 |
|------|------|------|
| **Phase 1** | Task Registration System | 1.5h |
| **Phase 2** | Webhook Endpoint | 1.5h |
| **Phase 3** | Remove Local Cron | 0.5h |
| **Phase 4** | 测试与验证 | 1h |
| **Phase 5** | 部署与监控 | 0.5h |
| **总计** | | **5h** |

---

## 12. 交付物

### 12.1 代码

- `agent-ts/src/core/bootstrap/task-registration.ts`
- `agent-ts/src/core/bootstrap/task-registration.test.ts`
- `agent-ts/src/api/webhook/trigger.ts`
- `agent-ts/src/api/webhook/trigger.test.ts`
- `agent-ts/src/index.ts`（修改）
- `agent-ts/.env.example`（更新）

### 12.2 文档

- 本设计文档（WP-10-SCHEDULER-INTEGRATION.md）
- 部署说明（集成到 agent-ts/README.md）
- 故障排查指南（Troubleshooting.md）

### 12.3 测试

- 单元测试（Jest）
- 集成测试脚本（`scripts/test-scheduler.sh`）
- 稳定性测试报告（3 天运行日志）

---

## 附录 A：Agent OS Scheduler API

### A.1 注册任务

```http
POST /api/v1/scheduler/tasks
Content-Type: application/json

{
  "name": "morning_ai_analysis",
  "owner": "fin-agent",
  "cron": "0 9 * * 1-5",
  "webhook_url": "http://localhost:3002/api/webhook/trigger",
  "params": {
    "skill": "morning_ai_analysis"
  },
  "metadata": {
    "description": "工作日早盘分析"
  }
}

Response:
{
  "id": "uuid",
  "name": "morning_ai_analysis",
  "owner": "fin-agent",
  "cron": "0 9 * * 1-5",
  "status": "active",
  "created_at": "2026-08-15T00:00:00Z"
}
```

### A.2 查询任务

```http
GET /api/v1/scheduler/tasks?owner=fin-agent

Response:
[
  {
    "id": "uuid",
    "name": "morning_ai_analysis",
    "cron": "0 9 * * 1-5",
    "status": "active"
  },
  ...
]
```

### A.3 手动触发

```http
POST /api/v1/scheduler/tasks/morning_ai_analysis/trigger

Response:
{
  "run_id": "uuid",
  "status": "running",
  "started_at": "2026-08-15T09:00:00Z"
}
```

---

## 附录 B：Skill Schedule 格式

**标准格式**：

```markdown
---
name: morning_ai_analysis
schedule: "0 9 * * 1-5"
description: "工作日早盘分析"
enabled: true
timeout: 600  # 秒（可选）
---

# Morning AI Analysis

分析今日市场环境，扫描买入信号...
```

**Cron 表达式格式**：
```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6) (Sunday=0)
│ │ │ │ │
│ │ │ │ │
* * * * *

示例：
"0 9 * * 1-5"      # 工作日 9:00
"*/30 9-14 * * 1-5" # 工作日 9:00-14:30 每30分钟
"0 18 * * *"       # 每天 18:00
```

---

## 附录 C：故障排查

### C.1 任务未注册

**症状**：agent-ts 启动无日志

**检查**：
```bash
# 1. 确认 Agent OS 运行
curl http://localhost:8080/health

# 2. 确认 skill 文件有 schedule
grep -r "schedule:" agent-ts/skills/

# 3. 查看 agent-ts 启动日志
tail -f ~/agent-ts.log | grep TaskRegistry
```

### C.2 Webhook 不触发

**症状**：Agent OS 触发了，但 agent-ts 无反应

**检查**：
```bash
# 1. 确认 webhook endpoint 运行
curl http://localhost:3002/api/webhook/health

# 2. 手动测试 webhook
curl -X POST http://localhost:3002/api/webhook/trigger \
  -H "Content-Type: application/json" \
  -d '{"task_name":"test","params":{"skill":"test"}}'

# 3. 查看 Agent OS 日志
docker logs agent-os | grep webhook
```

### C.3 任务执行失败

**症状**：webhook 收到了，但 skill 执行报错

**检查**：
```bash
# 查看 agent-ts 执行日志
tail -f ~/agent-ts.log | grep -A 10 "Webhook"

# 常见错误：
# - Skill 不存在
# - Session 创建失败
# - LLM API 超时
```

---

**状态**: ✅ 设计完成，Ready for Execution  
**审查**: 待 Claude 主会话审查  
**执行**: 交由执行模型实施
