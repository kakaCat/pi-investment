# WP-13: agent-ts 接入 Agent OS Scheduler

> **优先级**: P0  
> **工作量**: 2天  
> **状态**: 🟡 等待 WP-12 完成  
> **依赖**: WP-12 (Scheduler HTTP API)  
> **阻塞**: 无

---

## 1. 背景与目标

### 1.1 问题

agent-ts 目前使用**本地 node-cron** 调度器，与 Agent OS 并存，导致：

❌ 两个调度器并存（Agent OS + node-cron）  
❌ 任务分散管理，无法统一监控  
❌ 无法利用 Agent OS 的统一调度能力  
❌ Skills 调度逻辑分散  

### 1.2 目标

移除 agent-ts 的本地调度器，完全接入 Agent OS Scheduler：

✅ 移除本地 node-cron  
✅ 实现 Webhook 接收端点  
✅ 启动时注册所有调度任务到 Agent OS  
✅ 运行时响应 Agent OS 的 Webhook 触发  

---

## 2. 核心工作

### 2.1 Day 1: Webhook 接收端点 + 移除本地调度器

#### A. 修改 Webhook Handler

**文件**: `agent-ts/src/api/webhook/trigger.ts`

**当前代码**:
```typescript
router.post('/trigger', async (req, res) => {
  const { task_id, task_name, run_id, params } = req.body;
  // 简单实现
});
```

**修改为**:

```typescript
import { executeSkillById, executeSkillByName } from '../../core/skills/skill-executor.js';
import { createSchedulerSession } from '../../services/scheduler/scheduler-session.js';
import { logger } from '../../infrastructure/logging/index.js';

router.post('/trigger', async (req, res) => {
  const { task_id, task_name, run_id, params } = req.body;
  
  logger.info(`[Webhook] Task triggered from Agent OS`, {
    task_id,
    task_name,
    run_id,
    params
  });
  
  try {
    // 1. 验证请求
    if (!task_id || !task_name || !run_id) {
      return res.status(400).json({
        success: false,
        error: 'Missing required fields: task_id, task_name, run_id'
      });
    }
    
    // 2. 提取 skill 信息
    const { skill_id, skill_name } = params || {};
    
    if (!skill_id && !skill_name) {
      return res.status(400).json({
        success: false,
        error: 'Missing skill_id or skill_name in params'
      });
    }
    
    // 3. 创建 Scheduler Session
    const { session } = await createSchedulerSession('fin');
    
    // 4. 立即返回成功（异步执行，不阻塞 Agent OS）
    res.json({ 
      success: true, 
      run_id,
      message: 'Task queued for execution'
    });
    
    // 5. 异步执行 skill
    const executionPromise = skill_id 
      ? executeSkillById(skill_id, {
          source: 'agent-os-scheduler',
          taskId: task_id,
          taskName: task_name,
          runId: run_id,
          session
        })
      : executeSkillByName(skill_name, {
          source: 'agent-os-scheduler',
          taskId: task_id,
          taskName: task_name,
          runId: run_id,
          session
        });
    
    // 6. 记录执行结果（不阻塞响应）
    executionPromise
      .then(() => {
        logger.info(`[Webhook] ✅ Task completed successfully`, {
          task_name,
          run_id
        });
      })
      .catch((error) => {
        logger.error(`[Webhook] ❌ Task execution failed`, {
          task_name,
          run_id,
          error: error.message,
          stack: error.stack
        });
      });
    
  } catch (error) {
    logger.error('[Webhook] Task execution error:', error);
    
    // 如果还没有返回响应，返回 500
    if (!res.headersSent) {
      res.status(500).json({
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      });
    }
  }
});

export default router;
```

**关键点**:
- ✅ 立即返回响应（不阻塞 Agent OS）
- ✅ 异步执行 skill（不影响响应时间）
- ✅ 完整的错误处理和日志记录
- ✅ 支持通过 skill_id 或 skill_name 执行

---

#### B. 标记本地 SchedulerService 为 Deprecated

**文件**: `agent-ts/src/services/scheduler/scheduler-service.ts`

在文件顶部添加：

```typescript
/**
 * @deprecated This local scheduler is deprecated. All scheduling is now handled by Agent OS.
 * 
 * Migration: 2026-08-15
 * - All tasks are now registered to Agent OS Scheduler via HTTP API
 * - Task execution is triggered via webhook from Agent OS
 * - This file is kept for rollback purposes only
 * 
 * DO NOT USE THIS CLASS.
 * 
 * See: docs/superpowers/specs/WP-13-agent-ts-scheduler-integration.md
 */

import cron from 'node-cron';
// ... 现有代码保持不变（不删除）
```

---

#### C. 停止使用本地 SchedulerService

**文件**: `agent-ts/src/index.ts` 或相关启动文件

**查找并注释掉**:

```typescript
// ❌ 注释掉这些
// import { SchedulerService } from './services/scheduler/scheduler-service.js';
// const schedulerService = new SchedulerService();
// await schedulerService.start();
```

---

### 2.2 Day 2: 任务注册到 Agent OS

#### A. 创建任务注册模块

**新建文件**: `agent-ts/src/core/bootstrap/agent-os-task-registration.ts`

```typescript
import axios from 'axios';
import { logger } from '../../infrastructure/logging/index.js';
import { getSkillRegistry } from './skill-registry.js';

const AGENT_OS_BASE_URL = process.env.AGENT_OS_BASE_URL || 'http://localhost:8080';
const WEBHOOK_URL = process.env.AGENT_WEBHOOK_URL || 'http://localhost:3002/api/webhook/trigger';

interface SkillWithSchedule {
  id: string;
  name: string;
  description: string;
  schedule: string;
  category?: string;
}

/**
 * 注册所有带 schedule 的 skills 到 Agent OS Scheduler
 */
export async function registerTasksToAgentOS(): Promise<void> {
  logger.info('[TaskRegistry] Registering tasks to Agent OS Scheduler...');
  
  try {
    // 1. 获取所有 skills（从本地或从 Agent OS Skill Hub）
    const skills = await getSkillsWithSchedule();
    
    if (skills.length === 0) {
      logger.warn('[TaskRegistry] No scheduled skills found');
      return;
    }
    
    logger.info(`[TaskRegistry] Found ${skills.length} scheduled skills`);
    
    // 2. 逐个注册到 Agent OS
    let successCount = 0;
    let failCount = 0;
    
    for (const skill of skills) {
      try {
        await registerSingleTask(skill);
        successCount++;
        logger.info(`[TaskRegistry] ✅ Registered: ${skill.name} (${skill.schedule})`);
      } catch (error) {
        failCount++;
        logger.error(`[TaskRegistry] ❌ Failed to register: ${skill.name}`, {
          error: error instanceof Error ? error.message : error
        });
      }
    }
    
    logger.info('[TaskRegistry] Task registration complete', {
      total: skills.length,
      success: successCount,
      failed: failCount
    });
    
  } catch (error) {
    logger.error('[TaskRegistry] Task registration failed:', error);
    throw error;
  }
}

/**
 * 获取所有带 schedule 的 skills
 */
async function getSkillsWithSchedule(): Promise<SkillWithSchedule[]> {
  // 如果已接入 Skill Hub，从 Agent OS 获取
  if (process.env.SKILL_HUB_ENABLED === 'true') {
    return getSkillsFromAgentOS();
  }
  
  // 否则从本地文件读取
  return getSkillsFromLocalFiles();
}

/**
 * 从 Agent OS Skill Hub 获取 skills
 */
async function getSkillsFromAgentOS(): Promise<SkillWithSchedule[]> {
  const response = await axios.get(`${AGENT_OS_BASE_URL}/api/v1/skills`, {
    params: {
      owner: 'fin-agent',
      status: 'active'
    }
  });
  
  const skills = response.data.skills || [];
  
  return skills
    .filter((s: any) => s.metadata?.schedule)
    .map((s: any) => ({
      id: s.id,
      name: s.name,
      description: s.description,
      schedule: s.metadata.schedule,
      category: s.category
    }));
}

/**
 * 从本地文件读取 skills
 */
async function getSkillsFromLocalFiles(): Promise<SkillWithSchedule[]> {
  const { getSkillRegistry } = await import('./skill-registry.js');
  const registry = getSkillRegistry();
  
  return registry
    .filter(s => s.metadata?.schedule)
    .map(s => ({
      id: s.id || s.name,  // 如果没有 id，用 name
      name: s.name,
      description: s.description,
      schedule: s.metadata.schedule,
      category: s.category
    }));
}

/**
 * 注册单个任务到 Agent OS
 */
async function registerSingleTask(skill: SkillWithSchedule): Promise<void> {
  const taskData = {
    name: skill.name,
    description: skill.description,
    schedule: skill.schedule,
    webhook_url: WEBHOOK_URL,
    enabled: true,
    owner: 'fin-agent',
    metadata: {
      skill_id: skill.id,
      skill_name: skill.name,
      category: skill.category
    }
  };
  
  try {
    // 先尝试查询是否已存在
    const existingTasks = await axios.get(`${AGENT_OS_BASE_URL}/api/v1/scheduler/tasks`, {
      params: { owner: 'fin-agent' }
    });
    
    const existing = existingTasks.data.tasks?.find((t: any) => t.name === skill.name);
    
    if (existing) {
      logger.info(`[TaskRegistry] Task already exists: ${skill.name}, skipping`);
      return;
    }
    
    // 不存在则创建
    await axios.post(`${AGENT_OS_BASE_URL}/api/v1/scheduler/tasks`, taskData, {
      timeout: 10000
    });
    
  } catch (error) {
    if (axios.isAxiosError(error)) {
      throw new Error(`HTTP ${error.response?.status}: ${error.response?.data?.error || error.message}`);
    }
    throw error;
  }
}

/**
 * 清理所有注册的任务（用于重新注册或回滚）
 */
export async function cleanupRegisteredTasks(): Promise<void> {
  logger.info('[TaskRegistry] Cleaning up registered tasks...');
  
  try {
    const response = await axios.get(`${AGENT_OS_BASE_URL}/api/v1/scheduler/tasks`, {
      params: { owner: 'fin-agent' }
    });
    
    const tasks = response.data.tasks || [];
    
    for (const task of tasks) {
      try {
        await axios.delete(`${AGENT_OS_BASE_URL}/api/v1/scheduler/tasks/${task.id}`);
        logger.info(`[TaskRegistry] ✅ Deleted: ${task.name}`);
      } catch (error) {
        logger.error(`[TaskRegistry] ❌ Failed to delete: ${task.name}`, error);
      }
    }
    
    logger.info('[TaskRegistry] Cleanup complete');
    
  } catch (error) {
    logger.error('[TaskRegistry] Cleanup failed:', error);
    throw error;
  }
}
```

---

#### B. 集成到启动流程

**文件**: `agent-ts/src/index.ts`

```typescript
import { registerTasksToAgentOS } from './core/bootstrap/agent-os-task-registration.js';

async function bootstrap() {
  try {
    // 1. 初始化配置
    await initializeConfig();
    logger.info('✅ Config initialized');
    
    // 2. 初始化 Agent OS Client
    const agentOSURL = process.env.AGENT_OS_BASE_URL || 'http://localhost:8080';
    initAgentOSClient(agentOSURL);
    logger.info('✅ Agent OS Client initialized');
    
    // 3. 加载 Skill Registry
    // （如果已接入 Skill Hub，从 Agent OS 加载；否则从本地文件）
    await loadSkillRegistry();
    logger.info('✅ Skill Registry loaded');
    
    // 4. 注册调度任务到 Agent OS
    await registerTasksToAgentOS();
    logger.info('✅ Tasks registered to Agent OS Scheduler');
    
    // 5. 启动 Gateway API（接收 webhook）
    await startGatewayServer();
    logger.info('✅ Gateway API started');
    
    logger.info('🚀 agent-ts started with Agent OS Scheduler integration');
    
  } catch (error) {
    logger.error('❌ Bootstrap failed:', error);
    process.exit(1);
  }
}

bootstrap();
```

---

#### C. 添加环境变量配置

**文件**: `agent-ts/.env.example`

添加：

```bash
# Agent OS Integration
AGENT_OS_BASE_URL=http://localhost:8080
AGENT_WEBHOOK_URL=http://localhost:3002/api/webhook/trigger

# Skill Hub (可选，如果已接入)
SKILL_HUB_ENABLED=false
```

---

#### D. 创建手动注册脚本（可选）

**新建文件**: `agent-ts/scripts/register-tasks.ts`

```typescript
#!/usr/bin/env tsx

import { registerTasksToAgentOS, cleanupRegisteredTasks } from '../src/core/bootstrap/agent-os-task-registration.js';

const command = process.argv[2];

async function main() {
  if (command === 'register') {
    console.log('🚀 Registering tasks to Agent OS...');
    await registerTasksToAgentOS();
    console.log('✅ Done');
  } else if (command === 'cleanup') {
    console.log('🧹 Cleaning up registered tasks...');
    await cleanupRegisteredTasks();
    console.log('✅ Done');
  } else {
    console.log('Usage:');
    console.log('  npm run register-tasks register  # 注册任务');
    console.log('  npm run register-tasks cleanup   # 清理任务');
  }
}

main().catch(console.error);
```

**添加到 package.json**:

```json
{
  "scripts": {
    "register-tasks": "tsx scripts/register-tasks.ts"
  }
}
```

---

## 3. 验收标准

### 3.1 启动测试

```bash
# 1. 确保 Agent OS 正在运行
curl http://localhost:8080/health

# 2. 启动 agent-ts
cd agent-ts
npm run start

# 观察启动日志：
# ✅ Config initialized
# ✅ Agent OS Client initialized
# ✅ Skill Registry loaded
# [TaskRegistry] Found 15 scheduled skills
# [TaskRegistry] ✅ Registered: morning_ai_analysis (0 9 * * 1-5)
# [TaskRegistry] ✅ Registered: pool_maintenance (0 2 * * *)
# ...
# ✅ Tasks registered to Agent OS Scheduler
# ✅ Gateway API started
# 🚀 agent-ts started with Agent OS Scheduler integration
```

---

### 3.2 验证任务已注册

```bash
# 查询 Agent OS 中注册的任务
curl http://localhost:8080/api/v1/scheduler/tasks?owner=fin-agent | jq '.tasks[] | {name, schedule, webhook_url}'

# 预期输出：
# {
#   "name": "morning_ai_analysis",
#   "schedule": "0 9 * * 1-5",
#   "webhook_url": "http://localhost:3002/api/webhook/trigger"
# }
# ...
```

---

### 3.3 手动触发测试

```bash
# 1. 手动触发一个任务
TASK_ID=$(curl -s http://localhost:8080/api/v1/scheduler/tasks?owner=fin-agent | jq -r '.tasks[0].id')

curl -X POST http://localhost:8080/api/v1/scheduler/tasks/$TASK_ID/trigger

# 2. 观察 agent-ts 日志
# 预期看到：
# [Webhook] Task triggered from Agent OS
# [Webhook] ✅ Task completed successfully
```

---

### 3.4 自动触发测试

```bash
# 1. 注册一个每分钟触发的测试任务
curl -X POST http://localhost:8080/api/v1/scheduler/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "name": "test_every_minute",
    "schedule": "*/1 * * * *",
    "webhook_url": "http://localhost:3002/api/webhook/trigger",
    "enabled": true,
    "owner": "fin-agent",
    "metadata": {
      "skill_name": "test_skill"
    }
  }'

# 2. 观察 agent-ts 日志，等待 1 分钟
# 预期：每分钟自动触发一次

# 3. 测试完成后删除
curl -X DELETE http://localhost:8080/api/v1/scheduler/tasks/$TASK_ID
```

---

### 3.5 回归测试

- [ ] agent-ts 启动成功
- [ ] Skills 正常加载
- [ ] 手动调用 skill 正常工作
- [ ] Gateway API 正常响应
- [ ] 日志记录完整

---

## 4. 交付物清单

- [ ] `src/api/webhook/trigger.ts` (修改)
- [ ] `src/core/bootstrap/agent-os-task-registration.ts` (新建)
- [ ] `src/services/scheduler/scheduler-service.ts` (标记 deprecated)
- [ ] `src/index.ts` (修改)
- [ ] `.env.example` (修改)
- [ ] `scripts/register-tasks.ts` (新建)
- [ ] `package.json` (修改)
- [ ] 测试通过的截图或日志

---

## 5. 回滚方案

如果出现问题，可以快速回滚：

```typescript
// src/index.ts

// 回滚：恢复本地调度器
import { SchedulerService } from './services/scheduler/scheduler-service.js';

async function bootstrap() {
  // ... 其他初始化 ...
  
  // 启动本地调度器
  const schedulerService = new SchedulerService();
  await schedulerService.start();
  
  // 注释掉 Agent OS 注册
  // await registerTasksToAgentOS();
  
  // ... 其他启动 ...
}
```

---

## 6. 注意事项

### 6.1 幂等性

- 任务注册是幂等的（重复注册会跳过已存在的任务）
- 可以安全地多次运行 `registerTasksToAgentOS()`

### 6.2 错误处理

- 如果 Agent OS 不可用，agent-ts 启动会失败
- 建议添加重试机制或降级方案

### 6.3 日志记录

- Webhook 触发要记录完整上下文
- 执行失败要记录错误堆栈

### 6.4 性能

- Webhook 响应要快（< 1s）
- Skill 执行是异步的，不阻塞响应

---

## 7. 完成后通知

完成后请通知主窗口进行 Code Review，提供：
- 启动日志（证明任务注册成功）
- 手动触发测试结果
- 自动触发测试结果（等待 cron 触发）
- 遇到的问题和解决方案

---

**任务文档版本**: v1.0  
**创建时间**: 2026-08-15 23:40  
**创建人**: Claude (Opus 5) - 主窗口
