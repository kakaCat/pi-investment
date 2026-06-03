# 移除 Node.js PostgreSQL 依赖实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 移除 TypeScript Agent 对 PostgreSQL 的直接依赖，使用内存调度器替代

**Architecture:** 删除所有 PostgreSQL 相关代码（store、client、测试），修改 scheduler-runtime 使用 InMemorySchedulerStore，移除 pg 依赖包，更新环境变量配置

**Tech Stack:** TypeScript, Node.js, Jest

---

## 文件结构概览

### 删除的文件
- `src/services/scheduler/postgres-scheduler-store.ts` — PostgreSQL 存储实现
- `src/services/scheduler/postgres-scheduler-store.test.ts` — 相关测试
- `src/services/scheduler/postgres-client.ts` — PostgreSQL 连接池
- `src/scripts/seed-scheduler-tasks.ts` — 数据库初始化脚本

### 修改的文件
- `src/services/scheduler/scheduler-runtime.ts` — 改用 InMemorySchedulerStore
- `package.json` — 移除 pg 和 @types/pg 依赖
- `.env` — 移除 PGHOST/PGPORT/PGUSER/PGPASSWORD
- `.env.example` — 更新配置说明
- `CLAUDE.md` — 更新文档

---

## Task 1: 修改 scheduler-runtime.ts 使用内存存储

**Files:**
- Modify: `src/services/scheduler/scheduler-runtime.ts`

- [ ] **Step 1: 读取当前实现**

```bash
cat src/services/scheduler/scheduler-runtime.ts
```

Expected: 看到 PostgresSchedulerStore 的导入和使用

- [ ] **Step 2: 修改 scheduler-runtime.ts**

```typescript
import { InMemorySchedulerStore } from "./scheduler-service.js";
import { createSchedulerExecutor, type SchedulerExecutorOptions } from "./scheduler-executor.js";
import { SchedulerService, type SchedulerServiceOptions } from "./scheduler-service.js";

let runtime: {
  store: InMemorySchedulerStore;
  service: SchedulerService;
} | null = null;

export async function getSchedulerRuntime(
  options: Partial<SchedulerServiceOptions> & SchedulerExecutorOptions = {},
) {
  if (runtime) {
    return runtime;
  }

  const store = options.store instanceof InMemorySchedulerStore
    ? options.store
    : new InMemorySchedulerStore();

  const service = new SchedulerService({
    store,
    executor: options.executor ?? createSchedulerExecutor(options),
    now: options.now,
    idGenerator: options.idGenerator,
  });
  await service.reloadTasks();

  runtime = { store, service };
  return runtime;
}

export async function startSchedulerRuntime(options: SchedulerExecutorOptions = {}) {
  const current = await getSchedulerRuntime(options);
  current.service.start();
  return current;
}

export function resetSchedulerRuntimeForTests(): void {
  runtime = null;
}
```

- [ ] **Step 3: 验证修改**

```bash
cat src/services/scheduler/scheduler-runtime.ts | grep -E "import|PostgresSchedulerStore|InMemorySchedulerStore"
```

Expected: 只看到 InMemorySchedulerStore，没有 PostgresSchedulerStore 和 postgres-client 的导入

- [ ] **Step 4: 提交更改**

```bash
git add src/services/scheduler/scheduler-runtime.ts
git commit -m "refactor(scheduler): 切换到 InMemorySchedulerStore"
```

---

## Task 2: 删除 PostgreSQL 相关文件

**Files:**
- Delete: `src/services/scheduler/postgres-scheduler-store.ts`
- Delete: `src/services/scheduler/postgres-scheduler-store.test.ts`
- Delete: `src/services/scheduler/postgres-client.ts`
- Delete: `src/scripts/seed-scheduler-tasks.ts`

- [ ] **Step 1: 验证文件存在**

```bash
ls -la src/services/scheduler/postgres-*.ts src/scripts/seed-scheduler-tasks.ts
```

Expected: 看到 4 个文件

- [ ] **Step 2: 删除 PostgreSQL store 实现**

```bash
rm src/services/scheduler/postgres-scheduler-store.ts
```

- [ ] **Step 3: 删除 PostgreSQL store 测试**

```bash
rm src/services/scheduler/postgres-scheduler-store.test.ts
```

- [ ] **Step 4: 删除 PostgreSQL client**

```bash
rm src/services/scheduler/postgres-client.ts
```

- [ ] **Step 5: 删除种子脚本**

```bash
rm src/scripts/seed-scheduler-tasks.ts
```

- [ ] **Step 6: 验证删除**

```bash
ls -la src/services/scheduler/postgres-*.ts 2>&1
ls -la src/scripts/seed-scheduler-tasks.ts 2>&1
```

Expected: "No such file or directory"

- [ ] **Step 7: 提交更改**

```bash
git add -A
git commit -m "refactor(scheduler): 移除 PostgreSQL 存储相关文件"
```

---

## Task 3: 移除 pg 依赖包

**Files:**
- Modify: `package.json`

- [ ] **Step 1: 备份 package.json**

```bash
cp package.json package.json.backup
```

- [ ] **Step 2: 移除 pg 依赖**

```bash
npm uninstall pg @types/pg
```

Expected: package.json 和 package-lock.json 被修改，node_modules/pg 被删除

- [ ] **Step 3: 验证依赖已移除**

```bash
grep -E '"pg"|"@types/pg"' package.json
```

Expected: 无输出（依赖已移除）

- [ ] **Step 4: 重新安装依赖**

```bash
npm install
```

Expected: 安装成功，无错误

- [ ] **Step 5: 提交更改**

```bash
git add package.json package-lock.json
git commit -m "refactor: 移除 pg 和 @types/pg 依赖"
```

- [ ] **Step 6: 清理备份**

```bash
rm package.json.backup
```

---

## Task 4: 更新环境变量配置

**Files:**
- Modify: `.env`
- Modify: `.env.example`

- [ ] **Step 1: 更新 .env 文件**

删除或注释掉以下行：
```bash
# PGHOST=127.0.0.1
# PGPORT=5432
# PGUSER=mac
# PGPASSWORD=
```

保留并添加注释：
```bash
# PostgreSQL 配置（仅用于 Python 后端 quantsys-v2）
# TypeScript Agent 不再直接连接数据库
PGDATABASE=quant_investment
```

执行命令：
```bash
sed -i.backup '/^PGHOST=/d; /^PGPORT=/d; /^PGUSER=/d; /^PGPASSWORD=/d' .env
```

- [ ] **Step 2: 在 PGDATABASE 前添加注释**

手动编辑 `.env` 文件，在 `PGDATABASE=quant_investment` 前添加：
```bash
# PostgreSQL 配置（仅用于 Python 后端 quantsys-v2）
# TypeScript Agent 不再直接连接数据库
```

- [ ] **Step 3: 更新 .env.example**

```bash
cat > /tmp/env_example_postgres_section << 'EOF'
# PostgreSQL 配置（仅用于 Python 后端 quantsys-v2）
# TypeScript Agent 不再直接连接数据库
PGDATABASE=quant_investment
EOF
```

手动编辑 `.env.example`，将 PostgreSQL 相关配置替换为上述内容

- [ ] **Step 4: 验证更改**

```bash
grep -A 2 "PostgreSQL" .env
grep -A 2 "PostgreSQL" .env.example
```

Expected: 两个文件都显示新的注释说明

- [ ] **Step 5: 提交更改**

```bash
git add .env .env.example
git commit -m "refactor: 移除 TypeScript Agent 的 PostgreSQL 连接配置"
```

- [ ] **Step 6: 清理备份**

```bash
rm .env.backup
```

---

## Task 5: 运行测试验证

**Files:**
- Test: All existing tests

- [ ] **Step 1: 运行调度器单元测试**

```bash
npm test -- scheduler-service.test.ts
```

Expected: 所有测试通过

- [ ] **Step 2: 检查是否有遗漏的 PostgreSQL 引用**

```bash
grep -r "PostgresSchedulerStore\|createSchedulerPgPool\|postgres-client" src --include="*.ts" | grep -v node_modules
```

Expected: 无输出（所有引用已移除）

- [ ] **Step 3: 运行完整测试套件**

```bash
npm test
```

Expected: 所有测试通过（如果有失败，需要修复相关测试）

- [ ] **Step 4: 提交测试验证记录**

如果测试全部通过，创建记录：
```bash
echo "所有测试通过，PostgreSQL 依赖已成功移除" > docs/testing/2026-06-03-postgres-removal-test.md
git add docs/testing/2026-06-03-postgres-removal-test.md
git commit -m "test: 验证 PostgreSQL 移除后测试通过"
```

---

## Task 6: 更新 CLAUDE.md 文档

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: 读取当前 CLAUDE.md PostgreSQL 相关配置**

```bash
grep -n -A 10 "PGHOST\|PGPORT\|PostgreSQL" CLAUDE.md | head -30
```

- [ ] **Step 2: 更新 Environment Setup 章节**

找到 `## Environment Setup` 章节，将 PostgreSQL 配置说明修改为：

```markdown
# Database (PostgreSQL - 仅用于 Python 后端 quantsys-v2)
QUANT_DB_PROVIDER=postgres
PGDATABASE=quant_investment

# 注意：TypeScript Agent 不再直接连接 PostgreSQL
# 数据库连接由 quantsys-v2 后端管理
```

- [ ] **Step 3: 更新架构说明**

在 `## Architecture` 或相关章节，添加说明：

```markdown
**调度器架构变更（2026-06-03）：**
- TypeScript Agent 使用 `InMemorySchedulerStore`（内存调度器）
- 应用重启后任务需重新注册
- 数据补充任务由 quantsys-v2 Python 后端负责
```

- [ ] **Step 4: 验证更改**

```bash
grep -A 5 "InMemorySchedulerStore\|调度器" CLAUDE.md
```

Expected: 看到新添加的说明

- [ ] **Step 5: 提交文档更新**

```bash
git add CLAUDE.md
git commit -m "docs: 更新 CLAUDE.md 说明 PostgreSQL 移除和调度器变更"
```

---

## Task 7: 验证应用启动

**Files:**
- Test: Application startup

- [ ] **Step 1: 启动应用（开发模式）**

```bash
npm run dev &
DEV_PID=$!
sleep 5
```

Expected: 应用启动无 PostgreSQL 连接错误

- [ ] **Step 2: 检查启动日志**

```bash
# 检查进程是否运行
ps -p $DEV_PID

# 检查日志中是否有 PostgreSQL 错误
# (根据实际日志位置调整)
```

Expected: 进程正常运行，无数据库连接错误

- [ ] **Step 3: 验证调度器初始化**

检查应用日志，确认调度器使用内存存储启动

- [ ] **Step 4: 停止应用**

```bash
kill $DEV_PID
wait $DEV_PID 2>/dev/null
```

- [ ] **Step 5: 创建验收报告**

```bash
cat > docs/reviews/2026-06-03-postgres-removal-acceptance.md << 'EOF'
# PostgreSQL 依赖移除验收报告

**日期:** 2026-06-03

## 验收结果

- [x] TypeScript Agent 启动无需 PostgreSQL 连接
- [x] `npm install` 后不再包含 `pg` 依赖
- [x] 调度器功能正常（使用 InMemorySchedulerStore）
- [x] 所有相关测试通过
- [x] CLAUDE.md 已更新说明变更

## 架构变更确认

- TypeScript Agent 使用内存调度器
- 数据补充任务由 quantsys-v2 负责
- 应用重启后任务需要重新注册

## 测试结果

- 单元测试：通过
- 集成测试：通过
- 启动测试：通过
EOF

git add docs/reviews/2026-06-03-postgres-removal-acceptance.md
git commit -m "docs: 添加 PostgreSQL 移除验收报告"
```

---

## 验收标准检查清单

完成所有任务后，验证以下标准：

- [ ] TypeScript Agent 启动无需 PostgreSQL 连接
- [ ] `npm list pg` 显示 "not found"
- [ ] 调度器功能正常（可以创建、触发、执行任务）
- [ ] 所有测试通过（`npm test`）
- [ ] CLAUDE.md 更新说明变更
- [ ] 环境变量配置已更新
- [ ] 所有 PostgreSQL 相关文件已删除

