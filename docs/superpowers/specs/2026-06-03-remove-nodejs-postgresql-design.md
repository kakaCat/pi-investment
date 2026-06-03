# 移除 Node.js PostgreSQL 依赖设计文档

**日期:** 2026-06-03  
**状态:** 设计阶段  
**目标:** 移除 TypeScript Agent 对 PostgreSQL 的直接依赖，使用内存调度器替代

## 背景

当前 TypeScript Agent 通过 `PostgresSchedulerStore` 直接连接 PostgreSQL 数据库存储定时任务，导致：
1. 应用启动需要数据库连接，增加部署复杂度
2. 数据库连接失败会导致应用启动失败
3. 数据补充任务应该由 Python 后端（quantsys-v2）统一负责，而不是 Agent 端

**核心决策:** 数据补充任务由 quantsys-v2 负责，TypeScript Agent 只需要轻量级的内存调度器用于自身的定时提醒功能（如市场开盘通知、定时问候等）。

## 目标

1. **完全移除** TypeScript Agent 对 PostgreSQL 的依赖
2. **切换到** `InMemorySchedulerStore` 作为默认且唯一的调度存储
3. **简化** 启动流程，无需等待数据库连接
4. **保留** 调度器核心功能，支持 Agent 自身的定时任务

## 架构变更

### 变更前
```
TypeScript Agent
    ↓
SchedulerService
    ├── PostgresSchedulerStore (默认) → PostgreSQL
    └── InMemorySchedulerStore (仅测试)
```

### 变更后
```
TypeScript Agent
    ↓
SchedulerService
    └── InMemorySchedulerStore (默认且唯一)
```

### 职责划分

| 组件 | 职责 | 持久化 |
|------|------|--------|
| **TypeScript Agent** | 定时提醒、通知、Agent 自身调度 | 内存（重启丢失） |
| **quantsys-v2** | 数据补充、因子计算、市场数据同步 | PostgreSQL |

## 实施细节

### 1. 删除的文件

```
src/services/scheduler/postgres-scheduler-store.ts          # PostgreSQL 存储实现
src/services/scheduler/postgres-scheduler-store.test.ts     # 相关测试
src/services/scheduler/postgres-client.ts                   # PostgreSQL 连接池
src/scripts/seed-scheduler-tasks.ts                         # 数据库初始化脚本
```

### 2. 修改的文件

#### `src/services/scheduler/scheduler-runtime.ts`

**变更前:**
```typescript
import { createSchedulerPgPool } from "./postgres-client.js";
import { PostgresSchedulerStore } from "./postgres-scheduler-store.js";

const store = options.store instanceof PostgresSchedulerStore
  ? options.store
  : new PostgresSchedulerStore(createSchedulerPgPool());
await store.migrate();
```

**变更后:**
```typescript
import { InMemorySchedulerStore } from "./scheduler-service.js";

const store = options.store ?? new InMemorySchedulerStore();
// 无需 migrate
```

#### `package.json`

#### `src/index.ts` 或启动文件

需要在应用启动时初始化调度器并注册任务。具体实现见"调度任务初始化"章节。

**移除依赖:**
```json
{
  "dependencies": {
    "pg": "^8.x.x",           // 删除
    "pg-pool": "^3.x.x"       // 删除
  }
}
```

#### `.env` 和 `.env.example`

**变更前:**
```bash
PGHOST=127.0.0.1
PGPORT=5432
PGDATABASE=quant_investment
PGUSER=mac
PGPASSWORD=
```

**变更后:**
```bash
# PostgreSQL 配置（仅用于 Python 后端 quantsys-v2）
# TypeScript Agent 不再直接连接数据库
PGDATABASE=quant_investment  # 保留作为文档说明
```

### 3. 调度任务初始化

**变更前:** 任务存储在数据库，重启后自动恢复

**变更后:** 任务在应用启动时注册（在 `src/index.ts` 或相关初始化代码中）

**示例:**
```typescript
// src/index.ts 或 bootstrap 文件
import { getSchedulerRuntime } from "./services/scheduler/scheduler-runtime.js";

async function initializeScheduler() {
  const { service } = await getSchedulerRuntime();
  
  // 注册定时任务（示例）
  await service.createTask({
    id: "market-open-reminder",
    name: "市场开盘提醒",
    enabled: true,
    scheduleKind: "cron",
    scheduleExpr: "0 9 * * 1-5", // 工作日早上9点
    payload: { action: "send_notification", message: "市场开盘啦！" },
    compensationEnabled: false,
    compensationMaxAttempts: 1,
    deleteAfterRun: false,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  });
  
  service.start();
}
```

### 4. 测试调整

**受影响的测试:**
- `src/services/scheduler/postgres-scheduler-store.test.ts` — 删除
- 其他依赖 `PostgresSchedulerStore` 的集成测试 — 改用 `InMemorySchedulerStore`

**测试策略:**
- 单元测试：使用 `InMemorySchedulerStore`
- 集成测试：无需真实数据库，内存存储即可

## 迁移指南

### 开发环境

1. **更新依赖**:
   ```bash
   npm install  # 自动移除 pg 和 pg-pool
   ```

2. **更新环境变量**:
   - 编辑 `.env`，移除或注释 `PGHOST`/`PGPORT`/`PGUSER`/`PGPASSWORD`

3. **重启应用**:
   ```bash
   npm run dev
   ```

### 生产环境

1. **备份现有任务**（如果有重要任务需要迁移到代码中）
2. **部署新版本**（内存调度器会在启动时重新注册任务）
3. **验证调度任务**正常运行

## 权衡与限制

### 优点
- ✅ 无数据库依赖，部署更简单
- ✅ 启动更快（无需等待数据库连接）
- ✅ 职责清晰：Agent 负责提醒，quantsys-v2 负责数据
- ✅ 减少维护成本

### 限制
- ❌ 应用重启后任务定义丢失（需要在启动时重新注册）
- ❌ 无任务执行历史记录
- ❌ 不适合需要持久化的复杂调度场景

### 适用场景
- ✅ 定时提醒、通知类任务（重启后重新注册即可）
- ✅ Agent 自身的轻量级调度需求
- ❌ 不适合数据补充任务（应该在 quantsys-v2 实现）

## 后续扩展

如果未来需要任务持久化，可选方案：
1. **文件存储**: 实现 `FileSchedulerStore`，任务定义存储在 JSON 文件
2. **迁移到 Python**: 在 quantsys-v2 实现统一的调度系统
3. **恢复 PostgreSQL**: 如果确实需要，可以重新引入（作为可选依赖）

## 验收标准

- [ ] TypeScript Agent 启动无需 PostgreSQL 连接
- [ ] `npm install` 后不再包含 `pg` 依赖
- [ ] 调度器功能正常（可以创建、触发、执行任务）
- [ ] 应用重启后调度任务自动重新注册
- [ ] 所有相关测试通过
- [ ] CLAUDE.md 更新说明变更

## 文档更新

需要更新 `CLAUDE.md`：
- 移除 PostgreSQL 环境变量配置说明（针对 TypeScript Agent）
- 说明调度器使用内存存储
- 明确数据补充任务由 quantsys-v2 负责
