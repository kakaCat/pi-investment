# 迁移设计（REQ-260927202051-f6df）

> 把台账 v8 中 587 条任务迁移到按需求分片的 `queue.json`，并把台账升到 v9（移除 `tasks`）。
> 迁移范式复用仓内既有 `scripts/migrate-ledger.ts`（v4→v5→v6→v7）：备份 + 白名单校验 + 原子替换 + 幂等 + 留痕。

## 迁移范围与前置条件 `serves: FR-7`

**迁移对象**（2026-09-27 实测）：

| 项 | 值 | 来源 |
|---|---|---|
| 存量任务 | 587 条（done 556 / in_progress 7 / todo 24） | `.dsh-data/dsh-reqboard.json` 解析 |
| 其中带 `dependsOn` | 465 条 | 同上 |
| 需求记录 | 82 条（迁移后仍留台账） | 同上 |
| 台账大小 | 7,789,877 bytes | `ls -l` |
| 源 schemaVersion | 8 | 台账文件 |
| 目标 schemaVersion | 9 | 本设计 |

**前置条件**：
1. 迁移脚本在**服务停止**状态下执行（避免运行中内存缓存与文件不一致）
2. 台账可读且 `isPlausibleLedger` 通过
3. 磁盘可写（需要为 82 个需求的 queue.json 预留空间）

---

## 迁移步骤（D-1 ~ D-9） `serves: FR-7`

| 编号 | 步骤 | 失败处置 |
|---|---|---|
| D-1 | 读台账，解析 `tasks[]` 与 `requirements[]` | 解析失败 → 中止（退出码 2） |
| D-2 | 备份台账为 `<ledger>.backup-<ts>` | 备份失败 → 中止，不动原文件 |
| D-3 | 按 `task.requirementId` 分组；无 `requirementId` 或指向不存在需求者计入 `orphan_tasks`，**不迁移** | 有 orphan → dry-run 报告中列明；`--apply` 仍可继续（orphan 保留在台账侧不动） |
| D-4 | 每组构造 `QueueFile`（`schemaVersion: 9`、`tasks` 为完整 TaskRecord + `layer`） | 构造失败 → 该组跳过并计入报告 |
| D-5 | 调 `computeLayers` / `computeEdges` / `computeReady` 求 DAG 视图 | 环依赖 → 该需求中止（记入报告），不写半成品 |
| D-6 | 调 `validateQueueFile` 校验（V-1~V-6） | 校验失败 → 该需求中止，不落盘 |
| D-7 | 原子写 `<需求目录>/queue.json`（`persistAtomic`） | 写入失败 → 整体中止（已写入的文件保留，可 `--rollback` 清理） |
| D-8 | 台账变换：删 `tasks`、`schemaVersion=9`、`migrations` 追加 `{from:8,to:9,at,by}` | 白名单外差异 → **中止且不落盘** |
| D-9 | 原子替换台账（备份已在 D-2 完成） | 替换失败 → 原文件未被触碰（temp+rename 语义） |

**顺序纪律**：先写全部 queue.json（D-7）**再**改台账（D-8）。
理由：若反序，中途失败会得到"台账已无任务、队列还没生成"的**双向丢失**态；
按 D-7→D-8 顺序，最坏情形是"队列已生成但台账仍含 tasks"——该态可安全重跑（幂等）。

---

## 数据变换规则 `serves: FR-7`

| 源（台账 v8） | 目标（queue.json） | 变换 |
|---|---|---|
| `tasks[]` | `tasks[]` | **逐字段原样保留**，追加 `layer` |
| `task.dependsOn` | `task.dependsOn` + `edges` | 依赖仍是任务 id，同时展开为 edges |
| `task.requirementId` | 分组依据 + `queue.requirement_id` 校验 | 必须一致（V-3） |
| （无） | `edges` / `layers` / `ready` | 由 topology 重算 |
| （无） | `schemaVersion: 9` | 标记迁移时代 |
| `schemaVersion: 8` | `schemaVersion: 9` | 台账 bump |
| （无） | `migrations[]` | 追加留痕 |

**零字段丢失是硬契约**：`TaskRecord` 的每个字段（含 `lastRun` / `lastReport` / `revisions` /
`statusHistory` / `executions` / `parentId` / `stageKind`）都必须原样出现在 queue.json。
少迁一个字段会让下游门禁静默失效（如缺 `lastRun` → 子卡完工凭证门永远判不通过）。

**反向校验**：迁移后用**逐字段深比对**断言 `queue.tasks[i]` 去掉 `layer` 后与源 `ledger.tasks[i]` 完全相等。

---

## 兼容性处理 `serves: FR-6`

| 场景 | 处理 |
|---|---|
| 新代码读到 v8 台账（含 tasks） | **拒绝启动**，抛 `LEDGER_REQUIRES_MIGRATION` 并指向脚本 |
| 旧代码读到 v9 台账（无 tasks） | 旧代码会因 `isPlausibleLedger` 失败而落空台账——**故 v9 必须与读方改造同批上线** |
| 迁移中服务在跑 | 禁止：脚本检测到服务在运行则警告并要求先停机 |
| 需求目录不存在 | 该组跳过并计入报告（不隐式建目录） |
| 已有 queue.json（重跑） | 幂等：逐字段比对，一致则跳过；不一致则报冲突并中止（不静默覆盖） |

---

## 回滚设计 `serves: FR-7`

**触发条件**：迁移后服务启动失败 / 看板任务页空白 / 契约比对不通过。

| 步骤 | 动作 |
|---|---|
| R-1 | `--rollback` 从最近 `.backup-<ts>` 还原台账（任务回到 `tasks[]`，`schemaVersion` 回 8） |
| R-2 | 按 `migrations[]` 留痕与文件 mtime 判定归属，删除本次迁移生成的 queue.json |
| R-3 | 代码侧回退到迁移前版本（任务读方仍是 `ledger.tasks`） |
| R-4 | 复跑 `--verify` 断言台账已回 v8 且无本次生成的 queue.json |

**不可回滚的边界（诚实申报）**：迁移后在 v9 上**新产生**的任务（迁移之后执行的拆分）不在备份内，
回滚会丢失这部分新任务。故回滚窗口应限于"迁移完成、尚未投产新拆分"期间。

---

## 风险与缓解 `serves: FR-7`

| 风险 | 影响 | 缓解 |
|---|---|---|
| 看板任务页/甘特空白（**最高**） | 这个 GUI 的任务视图不可用 | 迁移与读方改造同批上线；以 :13080 实测页面为验收（TC-9.x） |
| 字段少迁 | 门禁静默失效（凭证门永远不过） | 逐字段深比对契约测试（TC-6.x） |
| 依赖 id 断链 | ready 推导错误、任务卡无法执行 | V-3 引用完整性 + 465 条 dependsOn 全量断言 |
| 台账被写坏 | 82 条需求记录受损 | D-2 备份 + 白名单校验 + 原子替换 |
| 中途失败双向丢失 | 任务与队列都没有 | D-7 先于 D-8 的顺序纪律 |

---

## 验证矩阵 `serves: FR-7`

| 用例 | 断言 |
|---|---|
| `--dry-run` | 报告 587 → N 个队列文件、orphan 数、变更白名单命中；**不落盘**（台账 mtime 不变） |
| `--apply` | 台账 `schemaVersion==9`、无 `tasks`、`migrations` 末条为 `{8,9}`；各需求 queue.json 存在且校验通过 |
| `--verify` | 无差异，退出码 0 |
| 幂等 | 连续两次 `--apply`，第二次报告 `already_v9` 且文件 mtime 不变 |
| 回滚 | `--rollback` 后台账回 v8 且本次生成的 queue.json 被清理 |
| 白名单 | 注入白名单外字段改动 → 中止，退出码 1，台账未被替换 |
| 契约 | 逐字段深比对通过（`queue.tasks[i] - layer === ledger.tasks[i]`） |

---

## 变更历史 `serves: FR-7`

- 2026-09-27 23:00 - 初始迁移设计（v8→v9，587 条任务分片；D-1~D-9；备份/白名单/幂等/回滚）（investor w-3936d77f）
