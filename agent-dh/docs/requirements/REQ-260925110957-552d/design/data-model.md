---
requirement_refs: [FR-4, FR-3, FR-9]
---

# 数据模型设计（REQ-260925110957-552d）

> 台账新字段、迁移规则、兼容性约束。

## 台账 schema 变更 <!-- serves: FR-4, FR-3, FR-9 -->

### schema 版本 <!-- serves: FR-3, FR-4, FR-9 -->

```typescript
// src/shared/protocol.ts
export const REQBOARD_SCHEMA_VERSION = 8; // 由 7 递增
```

### TaskRecord 新增字段 <!-- serves: FR-4 -->

```typescript
interface TaskRecord {
  // ... 既有字段
  
  /**
   * 写集声明（FR-4 写集并行）：本卡会改动的文件路径（工作区相对）或目录前缀。
   * 
   * 例：["src/tools/AdvanceTool/", "src/application/use-cases/AdvanceChain.ts"]
   * 
   * 声明粒度：
   * - 文件：src/a.ts（精确）
   * - 目录：src/tools/（前缀，含该目录下所有文件）
   * 
   * 未声明（undefined）= 写集未知 → 调度器视作「与所有卡冲突」，单独成批（全串行，安全降级）。
   * 
   * 冲突判定：
   * - 精确匹配：src/a.ts 与 src/a.ts 冲突
   * - 前缀匹配：src/tools/ 与 src/tools/AdvanceTool/AdvanceTool.ts 冲突
   * - 不冲突例：src/a.ts 与 src/b.ts、src/tools/A/ 与 src/tools/B/
   */
  filesPlanned?: string[];
}
```

### RequirementRecord.advance 新增字段 <!-- serves: FR-3, FR-9 -->

```typescript
interface RequirementRecord {
  advance?: {
    // ... 既有字段（history, pausedReason, noopStreak）
    
    /**
     * 当前运行 id（FR-3 中断可续）：后台 run 的 uuid，用于关联 job 与台账。
     * 格式：uuid v4（如 `550e8400-e29b-41d4-a716-446655440000`）。
     * 
     * 生命周期：
     * - 投递时生成并写入台账
     * - 链跑完/暂停后保留（用于查询历史 run）
     * - 下次投递时生成新 uuid
     */
    runId?: string;
    
    /**
     * 当前正在执行的子卡 id（FR-9 可观测）。
     * 
     * 用途：
     * - `reqboard_run_status` 返回「跑到哪张卡」
     * - 看板渲染运行态
     * 
     * 更新时机：每次 RUN_SUBTASK 事件前写入，子卡完成后清空。
     */
    currentSubtaskId?: string;
    
    /**
     * 当前步号（FR-9 可观测）：后台循环内的 `for (i = 0; i < 20; i++)` 中的 i。
     * 
     * 用途：
     * - checkpoint 恢复时知道「跑了几步」
     * - 看板显示进度
     */
    stepIndex?: number;
    
    /**
     * 心跳时间戳（毫秒，FR-3 孤儿判定）：最后一次写 checkpoint 的时间。
     * 
     * 用途：
     * - 孤儿判定：`now - heartbeatAt > 15min && 无活跃执行` → 子卡退回 todo
     * - stale 接管：`now - lockAt > 15min` → 解除单飞锁
     * 
     * 注意：`lockAt` 既有字段语义改为心跳（原先只在开始时写一次）。
     */
    heartbeatAt?: number;
    
    lockAt?: number; // 既有字段，语义改为心跳（stale 接管）
    history?: AdvanceRecord[]; // 既有
    /**
     * 暂停原因（既有字段，本需求扩展取值）。
     * 
     * 取值示例：
     * - `'max_steps_reached'`：跑满 20 步上限，需续跑（正常终止，不是错误）
     * - `'subtask_failed'`：子卡失败（schema 不通过、执行抛错等）
     * - `'killed_by_user'`：用户调用 job_kill 终止
     * - `'orphan_threshold_exceeded'`：孤儿数量过多（防御性暂停）
     * - 其他既有值保留（如 `'noop_breaker'`）
     */
    pausedReason?: string; // 既有，扩展取值
    noopStreak?: number; // 既有
  };
}
```

## 迁移规则 <!-- serves: FR-4, FR-3 -->

### 读取路径（向后兼容） <!-- serves: FR-3 -->

```typescript
// JsonLedgerRepository.ts（伪代码）
async function load(): Promise<ReqboardLedger> {
  const raw = await fs.readFile(LEDGER_PATH, 'utf-8');
  const ledger = JSON.parse(raw) as ReqboardLedger;
  
  // 版本检查
  if (ledger.schemaVersion === undefined || ledger.schemaVersion < 7) {
    throw new Error('台账版本过旧，需手动迁移');
  }
  
  // v7 → v8：新字段全部可选，缺省值 = undefined（旧行为不变）
  if (ledger.schemaVersion === 7) {
    // 不做任何重写，直接使用
    // TypeScript 类型系统保证 filesPlanned/runId 等可选字段的访问安全
  }
  
  return ledger;
}
```

### 写入路径（版本号递增） <!-- serves: FR-3 -->

```typescript
// JsonLedgerRepository.ts
async function save(ledger: MutableLedger): Promise<void> {
  const toWrite = {
    ...ledger,
    schemaVersion: REQBOARD_SCHEMA_VERSION, // 8
    revision: ledger.revision + 1
  };
  
  await atomicWrite(LEDGER_PATH, JSON.stringify(toWrite, null, 2));
}
```

### 降级路径（删除本需求后回滚） <!-- serves: FR-3 -->

**场景**：本需求交付后发现严重 bug，需回滚到旧版本。

**操作**：
1. `git revert <本需求的 commit>`
2. 重启 profile

**效果**：
- 旧代码读台账时，新字段（`filesPlanned/runId/...`）被忽略（TypeScript 类型不含这些字段，JSON 解析后多余键不报错）
- 调度逻辑回到旧行为（全串行，因为读不到 `filesPlanned`）
- **不需要手动改台账文件**

**约束**：
- 新字段必须全部**可选**（`?: type`），不得有 `required: true`
- 新字段缺省值不得破坏旧语义（如 `filesPlanned=undefined` → 全串行，比旧行为更保守）

## 字段约束与校验 <!-- serves: FR-4, FR-3 -->

### filesPlanned <!-- serves: FR-4 -->

- **类型**：`string[] | undefined`
- **长度**：0~50 项（超出截断）
- **每项格式**：工作区相对路径（`src/...`、`packages/...`、`docs/...`）
- **规范化**：去除前导 `./`、去除尾随 `/`（统一为目录前缀判定）
- **校验**：拆分阶段生成任务表时，工具 schema 校验（`items: {type: 'string', pattern: '^[^/].*'}`）

### runId <!-- serves: FR-3, FR-9 -->

- **类型**：`string | undefined`
- **格式**：uuid v4（`/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/`）
- **生成**：`crypto.randomUUID()`（Node.js 内置）
- **唯一性**：同一需求的不同 run 有不同 runId

### currentSubtaskId <!-- serves: FR-3, FR-9 -->

- **类型**：`string | undefined`
- **格式**：`t-xxxxxx`（既有任务 id 格式）
- **校验**：必须是该需求的子卡（`task.parentId !== undefined && task.requirementId === req.id`）

### stepIndex <!-- serves: FR-3, FR-9 -->

- **类型**：`number | undefined`
- **范围**：0~19（`LIMITS.advanceMaxStepsPerCall - 1`）
- **语义**：从 0 开始（投递时 = 0，每步递增）

### heartbeatAt <!-- serves: FR-3, FR-9 -->

- **类型**：`number | undefined`
- **格式**：epoch 毫秒（`Date.now()` 返回值）
- **更新频率**：每步 checkpoint（每次 `writeCheckpoint` 写入）

## 数据一致性保证 <!-- serves: FR-3, FR-9 -->

### 原子性 <!-- serves: FR-1, FR-3 -->

- **单次 mutate**：`repo.mutate(reason, fn)` 保证 fn 内的改动要么全部生效、要么全部不生效（JsonLedgerRepository 的既有保证）
- **跨 mutate**：无事务保证，但链循环按「读快照 → 判定 → 写 checkpoint → 执行 → 写结果」顺序，每步独立提交

### 并发控制 <!-- serves: FR-4 -->

- **进程内单飞**：`inflight: Set<requirementId>`（既有）
- **跨进程**：台账 `advance.lockAt + stale 阈值`（既有）
- **后台 run**：同一需求同时只有一个 run（幂等认领：`runId` 已存在且 job 仍在跑 → 拒绝投递）

### 孤儿一致性 <!-- serves: FR-5 -->

**场景**：进程崩溃，子卡 status=in_progress 但无执行记录。

**恢复**：
1. 启动扫描（`scanAndResume`）触发 `advanceRequirement`
2. 选择器识别孤儿（`now - claimedAt > 15min && !hasActiveExecution`）
3. 事件 = `RECLAIM_ORPHAN`，子卡退回 todo + attempt+1
4. 下一步正常选中该卡重跑

**不变量**：任何时刻，`status=in_progress` 的子卡要么有活跃执行记录、要么被识别为孤儿。

## 索引与查询 <!-- serves: FR-9 -->

### 按 runId 查询 <!-- serves: FR-2 -->

```typescript
// 给定 runId，找对应需求
function findRequirementByRunId(
  ledger: LedgerView, 
  runId: string
): RequirementRecord | undefined {
  return ledger.requirements.find(r => r.advance?.runId === runId);
}
```

**用途**：`reqboard_run_status(run_id)` 查询特定 run。

### 按需求查询当前 run <!-- serves: FR-2 -->

```typescript
function getCurrentRun(req: RequirementRecord): RunSnapshot | undefined {
  if (!req.advance?.runId) return undefined;
  
  return {
    runId: req.advance.runId,
    stepIndex: req.advance.stepIndex ?? 0,
    currentSubtask: req.advance.currentSubtaskId,
    heartbeatAt: req.advance.heartbeatAt
  };
}
```

**用途**：看板渲染运行态、`reqboard_run_status` 默认查询。

## 测试数据工厂 <!-- serves: FR-4, FR-3 -->

```typescript
// tests/factories.ts（伪代码）
export function makeTaskWithWriteSet(
  overrides: Partial<TaskRecord> = {}
): TaskRecord {
  return {
    ...makeTask(), // 既有工厂
    filesPlanned: ['src/example.ts'],
    ...overrides
  };
}

export function makeRequirementWithRun(
  overrides: Partial<RequirementRecord> = {}
): RequirementRecord {
  return {
    ...makeRequirement(),
    advance: {
      runId: crypto.randomUUID(),
      stepIndex: 0,
      heartbeatAt: Date.now(),
      ...overrides.advance
    },
    ...overrides
  };
}
```

**用途**：单测写集分批、孤儿回收、运行态查询。