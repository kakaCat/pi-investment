---
id: reqboard-queue-storage
title: reqboard 任务存储：按需求分片的队列文件（queue.json）
summary: 任务卡的唯一存储是 docs/requirements/<REQ>/queue.json（含 DAG 层级与 ready 队列），台账瘦身为 schemaVersion 9；拆分写队列、执行读队列、状态流转写回；含投产纪律、验证命令与三处已知坑。
type: architecture
status: living
updated: 2026-09-28
owners: [w-3936d77f]
tags: [reqboard, queue, dag, ledger-v9, archive, l2]
---

# reqboard 任务存储：队列文件（queue.json）

> 来源需求：[REQ-260927202051-f6df](../requirements/REQ-260927202051-f6df/)（已归档）。
> 本页是 **L2 结论**（现在系统是什么样、有哪些坑）；当时的取舍与证据在档案里。

## 1. 一句话

**任务是按需求分片存储的**：`docs/requirements/<REQ>/queue.json` 是任务卡的**唯一存储**；
单体的 `.dsh-data/dsh-reqboard.json` 只留**需求 / 分诊 / 迁移留痕**（`schemaVersion = 9`，**没有 `tasks` 字段**）。
「拆分开卡 → 执行取父卡 → 改状态解锁下游」三处全部以队列为准。

## 2. 队列文件长什么样

| 字段 | 含义 |
|---|---|
| `version` / `schemaVersion` | 队列文件版本 / 台账 schema 版本（当前 1 / 9） |
| `requirement_id` | 归属需求（一需求一文件，**不支持跨需求依赖**） |
| `tasks[]` | 任务卡：`QueueTask = TaskRecord + layer`（**类型级锁死**：多余键恰好只有 `layer`） |
| `edges[]` / `layers[]` | DAG 边与拓扑分层（同层 = 一批次） |
| `ready` | 当前就绪任务（依赖全部满足） |
| `generated_at` / `updated_at` | 生成 / 最近更新时点 |

- **出口契约**：`TaskStore` 返回的 `TaskRecord` **剥离 `layer`**（`layer` 只属于队列文件，不外泄到 `/state`）；只有 `readQueue()` 带 `layer`。
- **顺序契约（显式不变量）**：`taskStore.mutate` 必须**先于** `repo.mutate` —— 任务在队列、需求在台账，**两者不再同事务**；反序会产生「需求已验收但任务未完成」的悬空态（有打点断言）。
- **原子写**：同目录 dot 临时文件 → `fsync` → `rename`（`persistAtomic`）；并发写同队列由 **last-write-wins** 兜底（不引入分布式锁）。
- **校验 V-1~V-6**：必填 / id 唯一 / 引用完整 / 层级一致 / ready 双向一致 / 无环；**只报告不抛错**（校验是"报告"不是"断言"）。

## 3. 迁移（v8 → v9）

```bash
cd agent-dh && ./scripts/stop.sh                                     # ① 必须停机（脚本内有服务运行守卫）
node --import tsx/esm packages/web/dsh-pmboard/scripts/migrate-ledger.ts \
  --file .dsh-data/dsh-reqboard.json --root /Users/yunpeng/pi-investment/agent-dh --dry-run   # ② 零写预演
# 同命令换 --apply 落盘（自动备份 + manifest） / --verify 校验 / --rollback 回滚
cd agent-dh && ./scripts/start.sh                                    # ③ 起服务 → 看板实测
```

- **四态 CLI**：`--dry-run / --apply / --verify / --rollback`；`--apply` 幂等（重复执行报 `already_v9`）。
- **白名单**：只允许 `schemaVersion` / `migrations` / `tasks`(删除) 三类路径差异，出白名单即**中止且零落盘**。
- **可回滚**：`<ledger>.backup-*` 与 `<ledger>.migrate-manifest-*.json` **不要删**（rollback 靠 manifest 的 sha256 精确清理本次生成的队列）。
- ⚠️ **投产必须与重启在同一窗口**：新读方拒绝加载 v8 台账（`LEDGER_REQUIRES_MIGRATION`），旧进程存活时改台账会被内存态整册覆盖。

## 4. 怎么验（照抄即可）

| 验什么 | 命令（cwd = `agent-dh`） | 期望 |
|---|---|---|
| 队列/读方单测 | `cd packages/web/dsh-pmboard && npx vitest run tests/queue` | 12 files / 131 passed |
| 端到端链 | `npx vitest run packages/web/dsh-pmboard/tests/t17-queue-e2e.test.ts` | 退出码 0（建需求→拆分落队列→台账零新增→推进→进验收） |
| 定向回归套（14 文件） | `npx vitest run tests/queue tests/queue-types.test.ts … tests/advance-agent-handle.test.ts` | 23 files / 223 passed（EXIT=0） |
| 接口 × 磁盘真值 | `node docs/requirements/REQ-260927202051-f6df/notes/board-live/integration-probe.mjs --port 13080` | 全 passed；`/state` 的 tasks 与 `docs/requirements/*/queue.json` 逐项一致 |
| 看板真实渲染 | `node docs/requirements/REQ-260927202051-f6df/notes/board-live/cdp-board-check.mjs --port 13080 --req <REQ>` | 15 passed / 0 failed + 4 张截图（**不许用 curl 200 代替渲染验证**） |
| 台账形状 | python 读 `.dsh-data/dsh-reqboard.json` | `schemaVersion=9`、**无 `tasks` 键**、`migrations` 末条 `{from:8,to:9}` |

## 5. 已知坑（施工期实测，务必先读）

1. **陈旧 `advance` 锁没有回收路径**：链的锁只在 `driveChain` 的 `finally` 清理，**进程被 kill 就永不执行**；而重投递判据只看 `advance.runId` 是否存在、**不看过期时间**（15 分钟陈旧窗口只对 `lockAt` 生效）。症状是 `reqboard_task_run` 报「已有 run 在跑」而 `reqboard_run_status` 报 `jobStatus=not_found`。**处置**：人工清台账 `advance.runId/lockAt`，且必须落在「旧进程已死、新进程未 `load()`」之间的窗口（`load()` 是每进程一次，活着改文件必被覆盖）。
2. **`migrations` 留痕会被"读路径不重建该字段"的构建抹掉**：落盘的是整册 draft，`load()` 若只重建固定几个字段，第一次写入就永久丢留痕（`--verify` 首条报「migrations 末条不是 {from:8,to:9}」）。修法是 `load()` **原样带过** `migrations`。
3. **`--verify` 在跑过运行期改动的活台账上永远不会 `exit 0`**：队列因链推进漂移、台账因评论/autoRun/artifact 漂移（脚本只归一化 `migrations[].at`）。**退出码 0 只能在"apply 后未被运行期改动"的纯净副本上取证**。
4. **workflow 执行路径不写子卡卡文档**：`tasks/<subtaskId>.md` 不会自动生成，报告只进 run 记录（`reqboard_task_status` 可读）——验收文档门禁要求逐任务一份卡文档，需人工补 `reqboard_task_report`。

## 6. 两处「判据文本」遗留（口径问题，非实现缺陷）

- 既有验收文本里 `curl …/dashboard | grep -c pmboard` **命中 0**：`/dashboard` 是 dsh web 的**客户端 hash 路由**（服务端 404）；等价口径是 `GET /` → 200 且 `pmboard` 命中 ≥1。
- 早期设计文本要求甘特图有「依赖连线」，而甘特 SVG **无 edge 图元**（是按需求行的状态条甘特）；依赖信息由**任务表依赖列**与**需求详情 DAG 分层**承载，且本期明确「不做队列 DAG 图形 UI」。

## 7. 依赖写入口径：`dependsOn` 只存「直接前置」（2026-09-29，REQ-260929010300-dbf9）

**口径**：队列与计划里的 `tasks[].dependsOn` 一律只写**直接前置**，不再写传递闭包（「所有前置」）。

- **为什么**：拆分落库时每张卡习惯写全量前置，于是数据里普遍存在 A→B、B→C、A→C 三角形——2026-09-29 线上实测
  55 份队列、卡片层 646 条边里 **98 条（15.2%）** 存在替代路径，33/55 份中招。冗余留在数据里，每个消费者
  （画布 / 任务表 / 依赖列 / RTM）都要各自再折一次。
- **怎么做**：归约**前移到写入侧**。唯一实现 `src/domain/queue/transitiveReduction.ts`（纯函数、零 import）；
  `src/domain/queue/normalizeQueue.ts` 的 `normalizeQueueFile` 负责「归约 + layer/edges/layers/ready 整份重算」，
  被 `QueueTaskStore.recompute`（queue.json 写路径）与 `shared/protocol.ts` 的 `normalizePlanTasks`（计划解析）共用。
- **语义保证**：传递归约保持可达性 ⇒ `computeLayers`（最长路径）与 `computeReady` 结果**逐字不变**，
  执行序与可开工集不变；**悬空前置不删**（V-3 负责报）；环由 `computeLayers` / `validateQueue` 响亮报错。
- **存量迁移**：`packages/web/dsh-pmboard/scripts/normalize-queue-deps.ts`（默认 dry-run；`--req` 单需求；`--apply` 真写）。
  实测：73 需求扫描 / 32 需归约 / **115 条依赖折叠**；迁移后 55 份队列卡片层原始边 **548 = 画线 548**、仍有冗余的文件 **0**。
- **注意**：`QueueTaskStore` 按需求缓存队列，迁移后需**重启实例**让运行态读到新数据（画布自身仍有归约兜底，视觉不变）。

## 相关页面

- [需求流水线节点流程图](reqboard-pipeline-flow.md)
- [实施自动链（父卡/子卡）执行流程与缺陷落点](reqboard-implement-chain-flow.md)
- [需求归档规范](requirement-archive.md)
- [需求档案（本次来源）](../requirements/REQ-260927202051-f6df/)
