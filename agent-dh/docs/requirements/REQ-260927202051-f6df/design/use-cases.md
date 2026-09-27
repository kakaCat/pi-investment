# 用例设计（REQ-260927202051-f6df）

> 任务数据由台账迁入队列后的业务场景：拆分、执行、推进、迁移、看板、容错。

## 场景总览 `serves: FR-1`

| 用例 | 场景 | 主责条款 | 优先级 |
|---|---|---|---|
| UC-1 | 拆分需求生成队列 | FR-1 | P0 |
| UC-2 | 执行任务从队列取父卡 | FR-2 | P0 |
| UC-3 | 状态推进在队列实现并解锁下游 | FR-3 | P0 |
| UC-4 | 多窗口并发拆分/推进 | FR-3 | P1 |
| UC-5 | 队列文件损坏容错 | FR-4 | P2 |
| UC-6 | 看板查看任务与甘特（迁移后不回归） | FR-8 | P0 |
| UC-7 | 队列数据自动校验 | FR-5 | P0 |
| UC-8 | 存量任务一次性迁移（v8→v9） | FR-7 | P0 |
| UC-9 | 迁移回滚 | FR-7 | P1 |

## UC-1：拆分需求生成队列 `serves: FR-1`

**角色**：agent 窗口

**前置条件**：计划已获人批准；需求处于 decomposing

**主流程**：
1. 调 `reqboard_decompose(requirement_id, tasks=[...])`
2. 系统校验任务（依赖、必填 acceptance/implementation）
3. **`taskStore.createMany`**：构造 TaskRecord[] → 并入该需求 `queue.json`（已存在则合并，重复 id 幂等跳过）
4. **计算 DAG 视图**：`computeLayers` / `computeEdges` / `computeReady`
5. **校验** `validateQueueFile`（V-1~V-6）→ 通过则原子写
6. 返回 `{ success, tasks_created, queue_file }`

**后置条件**：`docs/requirements/<REQ>/queue.json` 含新任务与 DAG 视图；**台账 `tasks` 不新增任何记录**

**异常流**：
- E1 环依赖 → 抛 `CIRCULAR_DEPENDENCY`，不落盘
- E2 校验失败 → 抛 `QUEUE_VALIDATION_FAILED`，不落盘
- E3 队列文件损坏（已存在） → 隔离改名 + 重新生成

**验收点**：✅ 队列文件存在且结构正确 ✅ 台账无新任务 ✅ 返回体含 `queue_file`

---

## UC-2：执行任务从队列取父卡 `serves: FR-2`

**角色**：agent 窗口

**前置条件**：队列文件已生成；目标任务存在

**主流程**：
1. 调 `reqboard_task_run(task_id)`
2. **`taskStore.listByRequirement(reqId)`** 取该需求全部任务
3. 由 `ready` 判定当前可执行任务；日志打印 `Queue ready tasks: ...`
4. 取父卡信息（`acceptance` / `implementation` / `context` / `dependsSummary` / `parentId`）驱动执行
5. 启动子卡链

**后置条件**：任务进入执行；**队列文件未被本步骤修改**（只读）

**异常流**：
- E1 需求无队列文件 → 返回空列表，日志告警；本需求视为未拆分
- E2 队列损坏 → 隔离 + 告警；不崩
- E3 任务不在 ready（依赖未满足） → 记警告，但仍允许执行（队列是提示不是闸门）

**验收点**：✅ 日志含 ready 列表 ✅ 父卡字段完整取自队列 ✅ `task_run` 前后队列 md5 相同（只读）

---

## UC-3：状态推进在队列实现并解锁下游 `serves: FR-3`

**角色**：agent 窗口

**前置条件**：任务已存在；t2 依赖 t1

**主流程**：
1. 调 `reqboard_task_move(task_id, to='done')`
2. **`taskStore.mutate`（先）**：改 `status` / 追加 `statusHistory` / 刷 `updatedAt`
3. 重算 `edges` / `layers` / `ready`（`computeReady` 判定依赖是否全 done）
4. 校验 → 原子写 → 失效缓存 → 广播 `TaskChange`
5. **`repo.mutate`（后）**：更新需求状态（rollup 需要任务状态作为输入）
6. 日志：`Unlocked downstream tasks: t2`

**后置条件**：队列中 t1=`done`、`ready` 含 t2；需求状态与任务一致

**异常流**：
- E1 队列校验失败 → 抛错，文件保持上次有效内容；需求状态**不**被写入（顺序保护）
- E2 需求状态写失败 → 任务已推进（允许），由 rollup 幂等重算修复

**验收点**：✅ t1 状态正确 ✅ ready 含 t2 ✅ 打点证明任务写先于需求写

---

## UC-4：多窗口并发拆分/推进 `serves: FR-3`

**角色**：两个 agent 窗口

**前置条件**：两窗口操作**同一需求**的任务

**主流程**：
1. 窗口 A `taskStore.mutate` 改 t1
2. 窗口 B 同时 `taskStore.mutate` 改 t3
3. 两次写各自走「读 → 改 → 校验 → 原子 rename」

**后置条件**：队列文件为**完整合法 JSON**（不出现半截）

**异常流**：
- E1 last-write-wins：B 后写则 A 的改动可能丢失 → 属已知取舍；缓解：缓存按需求粒度、写前重读避免长事务
- E2 缓存陈旧导致覆盖 → 写路径强制重读文件后再合并（不信任缓存）

**验收点**：✅ 并发后 `jq .` 可解析 ✅ 无 `.tmp` 残留 ✅ 校验始终通过

---

## UC-5：队列文件损坏容错 `serves: FR-4`

**角色**：系统

**前置条件**：某需求 queue.json 内容非法

**主流程**：
1. 任一读方经 `TaskStore` 读取
2. `QueueRepository.load` 解析失败 → 改名为 `<file>.corrupt-<ts>` 隔离
3. 告警日志；该需求返回空任务列表并标记降级
4. 服务继续运行（不崩、不拖垮宿主）

**后置条件**：坏文件被保留供排查；系统可用

**验收点**：✅ 隔离文件存在 ✅ 告警出现 ✅ 服务未崩 ✅ 其余需求任务不受影响

---

## UC-6：看板查看任务与甘特（迁移后不回归） `serves: FR-8`

**角色**：人（看板使用者）

**前置条件**：迁移已完成（v9）；服务已启动

**主流程**：
1. 打开 `:13080` 看板「任务」页
2. `http/routers/stages.ts` 经 `TaskStore` 取各需求任务
3. 页面渲染任务列表（含状态、依赖、阶段）
4. 打开甘特/阶段视图，渲染依赖与批次

**后置条件**：人看到与迁移前**一致**的任务视图

**异常流**：
- E1 台账仍为 v8 → 服务拒绝启动并提示迁移（不是静默空白）
- E2 某需求队列缺失 → 该需求显示无任务（其余正常）
- E3 队列损坏 → 该需求降级显示 + 告警

**验收点**：✅ 历史任务可见且数量正确 ✅ 甘特不空白、无 500 ✅ 本需求自身任务可见
**纪律**：必须真实打开页面验证，禁止用接口返回 200 代替

---

## UC-7：队列数据自动校验 `serves: FR-5`

**角色**：系统（无人工介入）

**校验规则清单**（编号与设计一致，四份文档共用）：

| 规则 | 规则名 | 关注点 |
|---|---|---|
| V-1 | 必填字段完整性 | version/requirement_id/schemaVersion/generated_at/tasks/edges/layers/ready 齐全 |
| V-2 | 标识唯一性 | `tasks[].id` 不重复 |
| V-3 | 引用完整性 | dependsOn/edges/layers/ready 的 id 均在同需求 tasks 内；requirementId 不串档 |
| V-4 | 层级一致性 | `layer > 依赖方.layer`；layer 0 无依赖 |
| V-5 | ready 双向一致性 | 禁止假就绪与漏就绪 |
| V-6 | 无环性 | 拓扑排序可完成 |

**三个校验卡点**：
1. 写入前（`QueueRepository.save`）：失败 → 抛 `QUEUE_VALIDATION_FAILED`，**不落盘**
2. 读取后（`QueueRepository.load`）：失败 → 返回 `undefined` + 告警，该需求降级
3. 更新后（`TaskStore.mutate` 重算派生视图后）：失败 → 抛错，**文件保持上次有效内容**

**验收点**：✅ 三卡点均实际调用 ✅ 6/6 规则有正反例 ✅ 失败不污染磁盘

---

## UC-8：存量任务一次性迁移（v8→v9） `serves: FR-7`

**角色**：维护者（人工执行脚本）

**前置条件**：服务已停止；台账为 v8（587 条任务）

**主流程**：
1. `--dry-run`：报告 587 条任务 → N 个队列文件、orphan 数、白名单命中；**不落盘**
2. 人工核对报告
3. `--apply`：备份台账 → 按 requirementId 分组 → 逐组构造 QueueFile → 分层/校验 → 写 queue.json →
   台账删 `tasks`、`schemaVersion=9`、`migrations` 留痕 → 原子替换
4. `--verify`：断言无差异

**后置条件**：任务分布在 82 个需求的 queue.json；台账仅剩需求/分诊；留痕可追溯

**异常流**：
- E1 orphan 任务（requirementId 缺失/指向不存在需求）→ 计入报告，**不迁移**，不串档
- E2 环依赖 → 该需求中止迁移，其余继续，报告列出
- E3 白名单外差异 → 整体中止且不落盘，退出码 1
- E4 已存在 queue.json 且内容冲突 → 报冲突并中止（不静默覆盖）

**验收点**：✅ 587 条全部有归属（或明确计入 orphan）✅ 台账 v9 无 tasks ✅ 契约逐字段比对通过

---

## UC-9：迁移回滚 `serves: FR-7`

**角色**：维护者

**前置条件**：已 `--apply`；发现看板空白或启动失败

**主流程**：
1. `--rollback`
2. 从最近 `.backup-<ts>` 还原台账（任务回到 `tasks[]`，schemaVersion 回 8）
3. 按 `migrations` 留痕与 mtime 判定归属，删除本次迁移生成的 queue.json
4. 代码侧回退到迁移前版本；复跑 `--verify` 断言已回 v8

**后置条件**：系统回到迁移前状态

**异常流**：
- E1 备份缺失 → 拒绝回滚并报错（不猜测）
- E2 归属判定不明确 → 只还原台账、**不删**任何 queue.json（宁可留冗余也不误删）

**诚实边界**：迁移后在 v9 上**新产生**的任务不在备份内；回滚窗口限于"迁移完成、尚未投产新拆分"期间。

**验收点**：✅ 台账回 v8 含 tasks ✅ 本次生成的 queue.json 被清理 ✅ `--verify` 通过

---

## 用例优先级 `serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8`

| 用例 | 优先级 | 理由 |
|---|---|---|
| UC-1 拆分生成队列 | P0 | 队列入口 |
| UC-2 执行取父卡 | P0 | 用户核心诉求 |
| UC-3 状态推进解锁 | P0 | 用户核心诉求 |
| UC-6 看板不回归 | P0 | **最高风险**：只移数据不改读方 = 界面空白 |
| UC-7 数据校验 | P0 | 脏数据防线 |
| UC-8 一次性迁移 | P0 | 587 条历史任务的唯一通路 |
| UC-4 并发 | P1 | 真实多窗口场景 |
| UC-9 回滚 | P1 | 破坏性操作的安全网 |
| UC-5 损坏容错 | P2 | 健壮性 |

---

## 用例覆盖的功能点 `serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8`

| 功能点 | 覆盖用例 |
|---|---|
| FR-1 队列作为任务主存储 | UC-1, UC-4 |
| FR-2 执行从队列读取父卡 | UC-2 |
| FR-3 状态更新在队列实现 | UC-3, UC-4 |
| FR-4 原子写入 | UC-4, UC-5 |
| FR-5 数据校验与版本兼容 | UC-7 |
| FR-6 台账 schema v8→v9 | UC-8, UC-6 |
| FR-7 历史任务迁移 | UC-8, UC-9 |
| FR-8 读方改造 | UC-6, UC-2, UC-3 |

---

## 校验规则的单一事实源 `serves: FR-5`

V-1~V-6 定义在 [data-model.md](./data-model.md)「数据约束」，接口见 [interfaces.md](./interfaces.md)，
测试见 [test-cases.md](./test-cases.md)。**改任一规则必须同步四处，否则视为设计漂移。**

---

## 变更历史 `serves: FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8`

- 2026-09-27 21:20 - 初始用例（6 个场景）
- 2026-09-27 23:20 - **范围变更重写**：新增 UC-8 迁移、UC-9 回滚；UC-6 从「未来扩展」升级为 P0
  看板回归（最高风险）；UC-3 写明"先任务后需求"的顺序契约；补 FR-6/FR-7/FR-8 覆盖表（investor w-3936d77f）
