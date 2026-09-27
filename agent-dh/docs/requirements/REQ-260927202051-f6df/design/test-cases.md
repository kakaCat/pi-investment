# 测试用例设计（REQ-260927202051-f6df）

> 单元 / 迁移 / 读方回归 / 集成 / 看板实测五层。看板实测单独成层——**单测绿不等于看板不回归**。

## 单元测试 `serves: FR-1, FR-2, FR-3, FR-4`

### TC-1.x topology 纯函数 `serves: FR-1`

| 用例 | 输入 | 预期 |
|---|---|---|
| TC-1.1 线性链 | t1→t2→t3 | layers=[[t1],[t2],[t3]]；ready=[t1] |
| TC-1.2 菱形 | t1→{t2,t3}→t4 | layers=[[t1],[t2,t3],[t4]]；ready=[t1] |
| TC-1.3 环 | t1→t2→t3→t1 | 抛错，message 含 `CIRCULAR` |
| TC-1.4 空输入 | `[]` | layers=[]；edges=[]；ready=[]（不抛错） |
| TC-1.5 多 ready | t1,t2 无依赖；t3 依赖 t1 | ready=[t1,t2] |
| TC-1.6 依赖已 done | t1 done，t2 依赖 t1 且 todo | ready 含 t2（解锁） |
| TC-1.7 纯函数 | 静态检查 | topology.ts 不 import `node:fs` |

### TC-2.x validateQueueFile（V-1~V-6） `serves: FR-5`

| 用例 | 构造的坏数据 | 预期 rule |
|---|---|---|
| TC-2.1 | 缺 `schemaVersion` / `ready` 类型错误 | V-1 |
| TC-2.2 | 两条任务同 `id` | V-2 |
| TC-2.3 | `dependsOn` 引用不存在的 id | V-3 |
| TC-2.4 | `task.requirementId` ≠ `queue.requirement_id`（跨需求串档） | V-3 |
| TC-2.5 | `layer` 小于依赖方 layer；`layer=0` 却有依赖 | V-4 |
| TC-2.6 | 假就绪（依赖未 done 却进 ready） | V-5 |
| TC-2.7 | 漏就绪（依赖全 done 却不在 ready） | V-5 |
| TC-2.8 | 三任务成环 | V-6 |
| TC-2.9 | 合法队列 | passed=true 且 issues.length=0 |
| TC-2.10 | 失败路径不抛错 | 所有坏数据均 `passed=false` 且未 throw |
| TC-2.11 | 6/6 规则覆盖 | 断言 6 条 rule 各至少出现一次 |

### TC-3.x QueueRepository 文件层 `serves: FR-1, FR-2, FR-4`

| 用例 | 操作 | 预期 |
|---|---|---|
| TC-3.1 | save 合法队列 | 文件存在；`jq` 解析成功 |
| TC-3.2 | load 不存在需求 | 返回 `undefined`（非抛错） |
| TC-3.3 | load 损坏 JSON | 返回 `undefined`；产生 `.corrupt-<ts>` 隔离文件 |
| TC-3.4 | save 校验失败 | 抛 `QUEUE_VALIDATION_FAILED`；**文件不存在**（不落盘） |
| TC-3.5 | 并发两次 save | 最终文件是完整 JSON（无半截） |
| TC-3.6 | 无残留临时文件 | save 后目录内无 `.tmp` |

### TC-4.x TaskStore `serves: FR-1, FR-2, FR-3`

| 用例 | 操作 | 预期 |
|---|---|---|
| TC-4.1 | createMany 5 任务 | 队列含 5 任务；`layer` 已算；台账无任务 |
| TC-4.2 | createMany 重复 id | 幂等跳过，不覆盖既有 |
| TC-4.3 | mutate 改 status=done | `ready` 解锁下游；`updated_at` 刷新 |
| TC-4.4 | mutate 到无队列的需求 | 抛 `QUEUE_NOT_FOUND`（不隐式建档） |
| TC-4.5 | mutate 后校验失败 | 抛错且文件 md5 与更新前一致 |
| TC-4.6 | listByRequirement 无文件 | 返回 `[]` |
| TC-4.7 | 缓存一致性 | 写后 `get` 立即读到新值（缓存已失效） |
| TC-4.8 | subscribe 收到 TaskChange | kind=`task-moved`；tasks 含改动任务 |

---

## 台账改造测试 `serves: FR-6`

| 用例 | 操作 | 预期 |
|---|---|---|
| TC-5.1 | `emptyLedger()` | 无 `tasks` 字段；`schemaVersion===9` |
| TC-5.2 | `isPlausibleLedger` 无 tasks | 返回 true（v9 不算损坏） |
| TC-5.3 | 加载 v8 台账（含 tasks） | **抛 `LEDGER_REQUIRES_MIGRATION`**，不静默丢弃 |
| TC-5.4 | `repo.mutate` 返回体 | 不再含 `tasks` 通道 |
| TC-5.5 | `LedgerChange` 类型 | 无 `tasks` 字段（编译期断言） |
| TC-5.6 | 台账写入内容 | 落盘 JSON 中无 `tasks` 键 |

---

## 迁移测试 `serves: FR-7`

### TC-6.x 迁移行为 `serves: FR-7`

| 用例 | 操作 | 预期 |
|---|---|---|
| TC-6.1 dry-run 不落盘 | `--dry-run` | 台账 mtime 与 md5 不变；无 queue.json 生成 |
| TC-6.2 dry-run 报告 | `--dry-run` | 报告任务总数 587、分组数、orphan 数、白名单命中三类 |
| TC-6.3 apply 写队列 | `--apply` | 每个有任务的需求生成 `queue.json`，均通过 V-1~V-6 |
| TC-6.4 apply 改台账 | `--apply` | `schemaVersion===9`；无 `tasks` 键；`migrations` 末条 `{from:8,to:9}` |
| TC-6.5 幂等 | 连续两次 `--apply` | 第二次报 `already_v9`；所有文件 mtime 不变 |
| TC-6.6 verify | `--verify` | 无差异；退出码 0 |
| TC-6.7 白名单拦截 | 注入白名单外字段改动 | 中止；退出码 1；台账未被替换 |
| TC-6.8 rollback | `--rollback` | 台账回 v8（含 tasks）；本次生成的 queue.json 被清理 |
| TC-6.9 orphan 处理 | 构造 `requirementId` 指向不存在需求的任务 | 计入 `orphan_tasks`；**不迁移**；不串档 |
| TC-6.10 环依赖中止 | 构造成环需求 | 该需求不落盘；其余需求照常迁移；报告列出 |

### TC-7.x 迁移契约（零字段丢失） `serves: FR-7`

| 用例 | 断言 |
|---|---|
| TC-7.1 字段深比对 | `queue.tasks[i]` 去掉 `layer` 后 **deepEqual** 源 `ledger.tasks[i]` |
| TC-7.2 关键字段点名 | 逐条断言 `lastRun` / `lastReport` / `revisions` / `statusHistory` / `executions` / `parentId` / `stageKind` / `implementation` / `context` 均被迁移 |
| TC-7.3 依赖完整 | 465 条 `dependsOn` 全部在目标队列中可解析（V-3 通过） |
| TC-7.4 状态分布一致 | 目标队列 status 计数 = 源（done 556 / in_progress 7 / todo 24） |
| TC-7.5 需求归属 | 每个 queue.json 的 `requirement_id` 与其目录一致；无任务落到错误需求 |

---

## 读方改造回归 `serves: FR-8`

> 36 个模块改数据源后，**逐个断言输出与迁移前一致**。方法：迁移前对每个读方产出快照，
> 迁移后重跑同样调用，断言 JSON 相等。

| 用例 | 读方 | 断言 |
|---|---|---|
| TC-8.1 | `http/routers/stages.ts` | 各需求任务列表与迁移前一致（含 dependsOn） |
| TC-8.2 | `http/routers/tasks.ts` | 单任务详情字段集合与迁移前一致 |
| TC-8.3 | `http/routers/requirements.ts` | 需求详情的任务聚合数一致 |
| TC-8.4 | `http/routers/verdicts.ts` | 返工任务列表一致 |
| TC-8.5 | `tools/AdvanceTool` | ready 选择结果一致 |
| TC-8.6 | `tools/TaskStatusTool` / `RunStatusTool` | run 摘要字段一致 |
| TC-8.7 | `tools/TaskReportTool` | 汇报写回落到队列且字段一致 |
| TC-8.8 | `application/internal/rollup.ts` | 需求状态推导结果一致（任务全 done → accepting） |
| TC-8.9 | `application/internal/rtm-yaml.ts` + 覆盖门禁 | 覆盖对照读到的任务键集一致 |
| TC-8.10 | `application/use-cases/TaskTree.ts` | 父子卡树结构一致 |
| TC-8.11 | `application/use-cases/MoveTask.ts` | 顺序契约：`taskStore.mutate` 先于 `repo.mutate`（打点断言） |
| TC-8.12 | 静态检查 | `grep -rn 'ledger\.tasks\|snapshot()\.tasks' src/` 命中数为 **0** |

---

## 集成测试 `serves: FR-1, FR-2, FR-3`

| 用例 | 步骤 | 预期 |
|---|---|---|
| TC-9.1 拆分生成队列 | 新建测试需求 → 批准计划 → `reqboard_decompose` | `queue.json` 生成；返回体含 `queue_file`；**台账无新任务** |
| TC-9.2 执行读队列 | `reqboard_task_run` | 日志含 `Queue ready tasks:`；任务从队列取到 |
| TC-9.3 推进解锁 | `reqboard_task_move(to=done)` | 队列 `ready` 出现下游；台账需求状态同步 |
| TC-9.4 队列缺失容错 | 删除 queue.json 后 `task_move` | 台账侧照常；日志含回退提示；不崩 |
| TC-9.5 队列损坏容错 | 写入坏 JSON 后读任务 | 隔离改名 + 告警；返回空；服务不崩 |

---

## 看板实测（最高风险，**不可用单测替代**） `serves: FR-8`

| 用例 | 操作 | 通过标准 |
|---|---|---|
| TC-10.1 任务页渲染 | 启动 :13080 → 打开看板「任务」页 | 历史任务与在制任务**可见**，数量与迁移后一致 |
| TC-10.2 甘特图渲染 | 打开甘特/阶段视图 | 依赖连线与批次正常，无空白、无 500 |
| TC-10.3 需求详情 | 打开一条含任务的在制需求 | 任务列表非空，字段完整 |
| TC-10.4 服务日志 | 迁移后启动 | 无 `LEDGER_REQUIRES_MIGRATION`、无未捕获异常 |
| TC-10.5 本需求自身 | 打开 REQ-260927202051-f6df | 其任务（由迁移迁入）可见 |

**纪律**：TC-10.x 必须**真实打开页面**并截图/记录，禁止以 `curl` 返回 200 代替渲染验证。

---

## 边界与性能 `serves: FR-4`

| 用例 | 输入 | 预期 |
|---|---|---|
| TC-11.1 最大任务数 | 单需求 100 任务 | 生成成功；<50ms |
| TC-11.2 深依赖 | 20 层线性链 | layers.length=20；警告深链 |
| TC-11.3 空任务列表 | `[]` | 空队列文件可写可读 |
| TC-11.4 大文件读 | ~100KB 队列 | 读取 <10ms |
| TC-11.5 更新耗时 | 单任务状态更新 | <20ms |
| TC-11.6 启动不扫全量 | 82 个需求 | 启动不预读全部 queue.json（懒加载断言） |

---

## 测试覆盖目标 `serves: FR-5`

- 单元覆盖：`domain/queue/*` 与 `repositories/Queue{Repository,TaskStore}.ts` ≥90%
- 校验规则：**6/6**（V-1~V-6 各有正反例）
- 迁移：7 项行为 + 5 项契约全绿
- 读方：**36/36 模块**产出快照一致 + 静态检查 0 处残留 `ledger.tasks`
- 看板：**5/5** 实测用例通过（不可用单测替代）
- 门禁：`pnpm build` + `plugin-schema.smoke.test.ts`

---

## 变更历史 `serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8`

- 2026-09-27 21:15 - 初始用例（队列为派生副本）
- 2026-09-27 23:10 - **范围变更重写**：新增台账改造 TC-5.x、迁移 TC-6.x/TC-7.x、
  读方回归 TC-8.x（36 模块快照一致 + 残留静态检查）、看板实测 TC-10.x；
  明确「单测绿 ≠ 看板不回归」（investor w-3936d77f）
